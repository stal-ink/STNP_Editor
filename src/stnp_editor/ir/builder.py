from __future__ import annotations

import re
from typing import Any, cast

from stnp_editor.diagnostics import Diagnostic, Level
from stnp_editor.encoding import decode_base64_content
from stnp_editor.errors import BuildError, LoadingError, ValidationError
from stnp_editor.generation import ensure_supported_sdks, validate_output_stem
from stnp_editor.ir.models import (
    C_TYPES, TYPE_RANGES, TYPE_SIZES,
    CommandIR, CommonTypeIR, EmbeddedFileIR, FieldIR, GlobalResultIR, InstanceIR, ModuleIR,
    NotificationIR, ProjectIR, ProtocolIR, ReturnCodeIR,
    to_pascal, to_snake_lower,
)

_C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if",
    "inline", "int", "long", "register", "restrict", "return", "short",
    "signed", "sizeof", "static", "struct", "switch", "typedef", "union",
    "unsigned", "void", "volatile", "while", "_Alignas", "_Alignof",
    "_Atomic", "_Bool", "_Complex", "_Generic", "_Imaginary",
    "_Noreturn", "_Static_assert", "_Thread_local",
}

# Public typedef names owned by the generated runtime. common_types are emitted
# as STNP_<Name>, so reject collisions before they can become invalid C.
_RESERVED_STNP_TYPE_NAMES = {
    "U8", "U16", "U32", "I32", "Result", "TransportWrite",
    "ModuleHandle", "ModuleOps", "CommandEntry", "TaskFrame", "NotifyFrame",
    "EnableState",
}

# Public names owned by the generated Python namespace (``stnp.core`` /
# ``stnp.sdk.*`` / ``stnp.protocol``); module snake names must not shadow them.
_PYTHON_RESERVED_NAMES = frozenset(
    {"init", "task", "notify", "register", "runtime", "protocol", "sdk", "core"}
)

#: Return Code 分段宽度：每个 Module 固定占用 256 个 u16 码位。
_RETURN_CODE_SEGMENT_SIZE = 256


class _LevelPolicy:
    """校验规则级别表：``id -> level``，缺省 ``error``。"""

    def __init__(self, validations: list[dict[str, Any]] | None) -> None:
        self._levels: dict[str, str] = {}
        for item in validations or []:
            if not isinstance(item, dict):
                continue
            rule_id = item.get("id")
            if rule_id:
                self._levels[str(rule_id)] = str(item.get("level") or "error")

    def level_for(self, code: str) -> str:
        return self._levels.get(code, "error")


def _report_symbol_conflict(
    exc: ValidationError,
    policy: _LevelPolicy,
    diagnostics: list[Diagnostic] | None,
) -> None:
    """符号冲突按 validations 级别处理：``error`` 即抛，否则收集为诊断。"""
    level = policy.level_for(exc.code)
    if diagnostics is None or level == "error":
        raise exc
    diagnostics.append(
        Diagnostic(
            code=exc.code,
            level=cast(Level, level),
            message=exc.message,
            file=exc.file,
            line=exc.line,
            column=exc.column,
            json_pointer=exc.json_pointer,
            help=exc.help or None,
        )
    )


def _require_c_identifier(name: str, owner: str, json_pointer: str) -> None:
    if not _C_IDENTIFIER.fullmatch(name) or name in _C_KEYWORDS:
        raise ValidationError(
            "E2101",
            message=f"{owner}: 非法 C 标识符 {name!r}",
            json_pointer=json_pointer,
        )


def build_project_ir(
    project: dict[str, Any],
    protocol: dict[str, Any],
    modules_raw: list[dict[str, Any]],
    build: dict[str, Any],
    common_raw: dict[str, Any] | None = None,
    embedded_raw: dict[str, Any] | None = None,
    diagnostics: list[Diagnostic] | None = None,
) -> ProjectIR:
    target = str(build["target"])
    common_types = _build_common_types(common_raw or {})
    common_by_name = {t.name: t for t in common_types}
    protocol_ir = _build_protocol(protocol)

    if len(modules_raw) > 255:
        raise BuildError(
            "E3007",
            message=f"模块数 {len(modules_raw)} 超过 255",
            json_pointer="/modules",
        )

    modules: list[ModuleIR] = []
    seen_module_names: set[str] = set()
    seen_module_pascal: set[str] = set()
    seen_user_symbols: set[str] = set()
    for index, raw in enumerate(modules_raw):
        module_pointer = f"/modules/{index}"
        mod = _build_module(raw, common_by_name, protocol_ir.max_payload, index)
        if mod.name in seen_module_names:
            raise ValidationError(
                "E2102",
                message=f"模块名重复: {mod.name}",
                json_pointer=f"{module_pointer}/name",
            )
        if mod.pascal in seen_module_pascal:
            raise ValidationError(
                "E2103",
                message=f"模块名归一化后冲突: {mod.name}",
                json_pointer=f"{module_pointer}/name",
            )
        seen_module_names.add(mod.name)
        seen_module_pascal.add(mod.pascal)
        for cmd_index, cmd in enumerate(mod.commands):
            if cmd.user_symbol in seen_user_symbols:
                raise ValidationError(
                    "E2104",
                    message=f"生成的命令行为符号重复: {cmd.user_symbol}",
                    json_pointer=f"{module_pointer}/commands/{cmd_index}/name",
                )
            seen_user_symbols.add(cmd.user_symbol)
        modules.append(mod)

    module_by_name = {m.name: m for m in modules}
    instances: list[InstanceIR] = []
    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    seen_api_prefixes: set[str] = set()
    for index, item in enumerate(project["instances"]):
        instance_pointer = f"/instances/{index}"
        mid = int(item["id"])
        if mid < 1 or mid > 255:
            raise ValidationError(
                "E2128",
                message=f"实例 ID 超出 1..255: {mid}",
                json_pointer=f"{instance_pointer}/id",
            )
        if mid in seen_ids:
            raise ValidationError(
                "E2105",
                message=f"实例 ID 重复: {mid}",
                json_pointer=f"{instance_pointer}/id",
            )
        seen_ids.add(mid)
        iname = item["name"]
        if iname in seen_names:
            raise ValidationError(
                "E2106",
                message=f"实例名重复: {iname}",
                json_pointer=f"{instance_pointer}/name",
            )
        seen_names.add(iname)
        mod_name = item["module"]
        if mod_name not in module_by_name:
            raise ValidationError(
                "E2130",
                message=f"实例引用的模块不存在: {mod_name}",
                json_pointer=f"{instance_pointer}/module",
            )
        mod = module_by_name[mod_name]
        pascal = to_pascal(iname)
        api_prefix = f"STNP_{pascal}"
        if api_prefix in seen_api_prefixes:
            raise ValidationError(
                "E2107",
                message=f"实例名归一化后冲突: {iname}",
                json_pointer=f"{instance_pointer}/name",
            )
        seen_api_prefixes.add(api_prefix)
        macro = re.sub(r"[^A-Za-z0-9]", "_", iname).upper()
        instances.append(
            InstanceIR(
                name=iname,
                pascal=pascal,
                macro=macro,
                module_name=mod_name,
                module=mod,
                id_value=mid,
                handle_var=f"g_{to_snake_lower(iname)}",
                api_prefix=api_prefix,
            )
        )

    if len(instances) > protocol_ir.router_instance_max:
        raise ValidationError(
            "E2129",
            message=(
                f"实例数量 {len(instances)} 超过 router_instance_max "
                f"{protocol_ir.router_instance_max}"
            ),
            json_pointer="/instances",
        )

    global_results = _build_global_results(project.get("global_results") or [])

    _validate_generated_symbols(
        modules,
        common_types,
        instances,
        global_results,
        target,
        build.get("validations") or [],
        diagnostics,
    )

    stem = validate_output_stem(build.get("output_stem") or project.get("project_name") or "stnp")
    target_config = build.get(target) or {}
    return ProjectIR(
        project_name=project["project_name"],
        protocol=protocol_ir,
        modules=modules,
        instances=instances,
        global_results=global_results,
        emit_readme=bool(build.get("emit_readme", True)),
        emit_examples=bool(target_config.get("emit_examples", False)),
        build_system=(
            str((build.get("c") or {}).get("build_system", "mdk_arm"))
            if target == "c"
            else "python"
        ),
        sdks=ensure_supported_sdks(list(build.get("sdks") or []), target="c"),
        common_types=common_types,
        embedded_files=_build_embedded(embedded_raw or {}),
        output_stem=stem,
    )


def _build_common_types(raw: dict[str, Any]) -> list[CommonTypeIR]:
    out: list[CommonTypeIR] = []
    seen: set[str] = set()
    for index, item in enumerate(raw.get("types", [])):
        pointer = f"/common_types/types/{index}"
        name = item["name"]
        if name in seen:
            raise ValidationError(
                "E2108",
                message=f"通用类型名重复: {name}",
                json_pointer=f"{pointer}/name",
            )
        if name in _RESERVED_STNP_TYPE_NAMES or f"STNP_{name}" in set(C_TYPES.values()):
            raise ValidationError(
                "E2109",
                message=f"通用类型 {name} 与保留 STNP 类型冲突",
                json_pointer=f"{pointer}/name",
            )
        seen.add(name)
        kind = item["kind"]
        base = item["type"]
        if base not in TYPE_SIZES:
            raise ValidationError(
                "E2123",
                message=f"不支持的基础类型: {base}",
                json_pointer=f"{pointer}/type",
            )
        values: list[tuple[str, int]] = []
        if kind == "enum":
            seen_value_names: set[str] = set()
            seen_values: set[int] = set()
            lo, hi = TYPE_RANGES[base]
            for value_index, v in enumerate(item.get("values") or []):
                value_pointer = f"{pointer}/values/{value_index}"
                vname = v["name"]
                value = int(v["value"])
                if vname in seen_value_names:
                    raise ValidationError(
                        "E2110",
                        message=f"枚举 {name}: 枚举值名重复 {vname}",
                        json_pointer=f"{value_pointer}/name",
                    )
                if value in seen_values:
                    raise ValidationError(
                        "E2111",
                        message=f"枚举 {name}: 枚举值重复 {value}",
                        json_pointer=f"{value_pointer}/value",
                    )
                if value < lo or value > hi:
                    raise ValidationError(
                        "E2122",
                        message=f"枚举 {name}: 值 {value} 超出 {base} 范围",
                        json_pointer=f"{value_pointer}/value",
                    )
                seen_value_names.add(vname)
                seen_values.add(value)
                values.append((vname, value))
            if not values:
                raise ValidationError(
                    "E2121",
                    message=f"枚举 {name} 没有任何取值",
                    json_pointer=f"{pointer}/values",
                )
        out.append(
            CommonTypeIR(
                name=name,
                kind=kind,
                base_type=base,
                c_type=f"STNP_{name}",
                size=TYPE_SIZES[base],
                values=values,
            )
        )
    return out


def _build_embedded(raw: dict[str, Any]) -> list[EmbeddedFileIR]:
    files: list[EmbeddedFileIR] = []
    for path, spec in raw.items():
        pointer = f"/embedded_files/{path}"
        _check_embedded_path(path, pointer)
        if spec["encoding"] == "base64":
            try:
                decode_base64_content(spec["content"], owner=f"embedded file {path!r}")
            except ValueError as exc:
                raise LoadingError(
                    "E1004",
                    message=f"嵌入文件 {path}: Base64 内容无效",
                    json_pointer=pointer,
                ) from exc
        files.append(EmbeddedFileIR(path=path, encoding=spec["encoding"], content=spec["content"]))
    return files


def _check_embedded_path(path: str, json_pointer: str) -> None:
    if not path or path.startswith("/") or "\\" in path or ":" in path:
        raise ValidationError(
            "E2135",
            message=f"嵌入文件路径不安全: {path}",
            json_pointer=json_pointer,
        )
    parts = path.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ValidationError(
            "E2135",
            message=f"嵌入文件路径不安全: {path}",
            json_pointer=json_pointer,
        )


def _build_protocol(raw: dict[str, Any]) -> ProtocolIR:
    features = raw.get("features", {})
    crc = features.get("crc", {})
    seq_feature = features.get("seq", {})
    options = raw.get("options", {})
    task_sof = tuple(int(x) for x in raw["task"]["sof"])
    notify_sof = tuple(int(x) for x in raw["notify"]["sof"])
    if task_sof == notify_sof:
        raise ValidationError(
            "E2126",
            message="task 与 notify 的 SOF 相同",
            json_pointer="/protocol/task/sof",
        )
    seq = raw["task"]["seq"]
    seq_start = int(seq["start"])
    seq_reserved = tuple(sorted({int(v) for v in seq.get("reserved", [])}))
    if seq_start in seq_reserved:
        raise ValidationError(
            "E2127",
            message=f"task seq 起始值 {seq_start} 属于保留集合",
            json_pointer="/protocol/task/seq/start",
        )
    if len(seq_reserved) >= 65536:
        raise ValidationError(
            "E2127",
            message="task seq 保留集合没有可用序号",
            json_pointer="/protocol/task/seq/reserved",
        )
    seq_enabled = bool(seq_feature.get("enabled", False))
    crc_enabled = bool(crc.get("enabled", False))
    notify_dispatch_receive = bool(
        options.get("notify_dispatch_receive", {}).get("enabled", False)
    )
    task_fixed_size = 2 + (2 if seq_enabled else 0) + 1 + 1 + 1
    notify_fixed_size = 2 + (2 if seq_enabled else 0) + 1 + 1 + 2 + 1
    return ProtocolIR(
        name=raw["name"],
        version=raw["version"],
        max_payload=int(raw["max_payload"]),
        router_instance_max=int(raw.get("router_instance_max", 8)),
        task_sof=(task_sof[0], task_sof[1]),
        notify_sof=(notify_sof[0], notify_sof[1]),
        seq_start=seq_start,
        seq_reserved=seq_reserved,
        task_fixed_size=task_fixed_size,
        notify_fixed_size=notify_fixed_size,
        crc_enabled=crc_enabled,
        seq_enabled=seq_enabled,
        notify_dispatch_receive=notify_dispatch_receive,
    )


def _resolve_field(
    raw: dict[str, Any], common_by_name: dict[str, CommonTypeIR], json_pointer: str
) -> FieldIR:
    t = raw["type"]
    if t in TYPE_SIZES:
        base = t
        c_type = C_TYPES[t]
    elif t in common_by_name:
        ct = common_by_name[t]
        base = ct.base_type
        c_type = ct.c_type
    else:
        raise ValidationError(
            "E2123",
            message=f"不支持的基础类型: {t}",
            json_pointer=f"{json_pointer}/type",
        )

    min_value = raw.get("min")
    max_value = raw.get("max")
    lo, hi = TYPE_RANGES[base]
    if min_value is not None:
        min_value = int(min_value)
        if min_value < lo or min_value > hi:
            raise ValidationError(
                "E2124",
                message=f"字段 {raw['name']}: min {min_value} 超出 {base} 范围",
                json_pointer=f"{json_pointer}/min",
            )
    if max_value is not None:
        max_value = int(max_value)
        if max_value < lo or max_value > hi:
            raise ValidationError(
                "E2124",
                message=f"字段 {raw['name']}: max {max_value} 超出 {base} 范围",
                json_pointer=f"{json_pointer}/max",
            )
    if min_value is not None and max_value is not None and min_value > max_value:
        raise ValidationError(
            "E2125",
            message=f"字段 {raw['name']}: min 大于 max",
            json_pointer=f"{json_pointer}/min",
        )
    return FieldIR(
        name=raw["name"], type_name=base, c_type=c_type, size=TYPE_SIZES[base],
        min_value=min_value, max_value=max_value, declared_type=t,
    )


def _build_fields(
    raw_fields: list[dict[str, Any]],
    common_by_name: dict[str, CommonTypeIR],
    *, owner: str,
    max_payload: int,
    json_pointer: str,
) -> tuple[list[FieldIR], int]:
    fields: list[FieldIR] = []
    length = 0
    seen: set[str] = set()
    for index, f in enumerate(raw_fields):
        field_pointer = f"{json_pointer}/{index}"
        _require_c_identifier(f["name"], f"{owner} field", f"{field_pointer}/name")
        if f["name"] in seen:
            raise ValidationError(
                "E2112",
                message=f"{owner}: 载荷字段名重复 {f['name']}",
                json_pointer=f"{field_pointer}/name",
            )
        seen.add(f["name"])
        field = _resolve_field(f, common_by_name, field_pointer)
        fields.append(field)
        length += field.size
    if length > max_payload:
        raise BuildError(
            "E3001",
            message=f"{owner}: 载荷累计长度 {length} 超过 max_payload {max_payload}",
            json_pointer=json_pointer,
        )
    return fields, length


def _build_global_results(raw_list: list[dict[str, Any]]) -> list[GlobalResultIR]:
    out: list[GlobalResultIR] = []
    seen_names: set[str] = set()
    seen_values: set[int] = set()
    for index, item in enumerate(raw_list):
        pointer = f"/global_results/{index}"
        name = item["name"]
        value = int(item["value"])
        if name in seen_names or value in seen_values:
            raise ValidationError(
                "E2120",
                message=f"global_results: 返回码名称或值重复 {name}",
                json_pointer=f"{pointer}/name",
            )
        seen_names.add(name)
        seen_values.add(value)
        if name == "OK":
            if value != 0x0000:
                raise BuildError(
                    "E3005",
                    message=f"工程级 OK 的值必须为 0x0000，实际为 {value:#06x}",
                    json_pointer=f"{pointer}/value",
                )
        elif not 0x0001 <= value <= 0x00FF:
            raise BuildError(
                "E3006",
                message=f"工程级返回码 {name} 的值 {value:#06x} 不在 0x0001..0x00FF",
                json_pointer=f"{pointer}/value",
            )
        out.append(
            GlobalResultIR(
                name=name,
                value=value,
                enum_member=f"GLOBAL_{name}",
                brief=item.get("brief") or name,
            )
        )
    if not any(r.name == "OK" and r.value == 0x0000 for r in out):
        raise BuildError(
            "E3005",
            message="工程级返回码必须包含名为 OK 且值为 0x0000 的条目",
            json_pointer="/global_results",
        )
    if len(out) > 255:
        raise BuildError(
            "E3007",
            message=f"工程级返回码条目数 {len(out)} 超过 255",
            json_pointer="/global_results",
        )
    return out


def _build_return_codes(
    module_name: str, raw_list: list[dict[str, Any]], module_index: int
) -> list[ReturnCodeIR]:
    out: list[ReturnCodeIR] = []
    seen_names: set[str] = set()
    seen_values: set[int] = set()
    segment_lo = 0x0100 + _RETURN_CODE_SEGMENT_SIZE * module_index
    segment_hi = 0x00FF + _RETURN_CODE_SEGMENT_SIZE * (module_index + 1)
    for index, item in enumerate(raw_list):
        pointer = f"/modules/{module_index}/return_codes/{index}"
        name = item["name"]
        value = int(item["value"])
        if name in seen_names or value in seen_values:
            raise ValidationError(
                "E2120",
                message=f"{module_name}: 返回码名称或值重复 {name}",
                json_pointer=f"{pointer}/name",
            )
        seen_names.add(name)
        seen_values.add(value)
        if value < 0 or value > 0xFFFF:
            raise BuildError(
                "E3003",
                message=f"{module_name}: 返回码 {name} 的值 {value} 超出 u16 范围",
                json_pointer=f"{pointer}/value",
            )
        if not segment_lo <= value <= segment_hi:
            raise BuildError(
                "E3004",
                message=(
                    f"{module_name}: 返回码 {name} 的值 {value:#06x} 不在本模块区间 "
                    f"{segment_lo:#06x}..{segment_hi:#06x}"
                ),
                json_pointer=f"{pointer}/value",
            )
        out.append(
            ReturnCodeIR(
                name=name,
                value=value,
                enum_member=f"{module_name}_{name}",
                brief=item.get("brief") or name,
            )
        )
    if not any(r.name == "OK" for r in out):
        raise BuildError(
            "E3002",
            message=f"{module_name}: 返回码必须包含名为 OK 的条目",
            json_pointer=f"/modules/{module_index}/return_codes",
        )
    if len(out) > 256:
        raise BuildError(
            "E3007",
            message=f"{module_name}: 返回码条目数 {len(out)} 超过 256",
            json_pointer=f"/modules/{module_index}/return_codes",
        )
    return out


def _build_module(
    raw: dict[str, Any],
    common_by_name: dict[str, CommonTypeIR],
    max_payload: int,
    module_index: int,
) -> ModuleIR:
    name = raw["name"]
    pascal = to_pascal(name)
    snake = to_snake_lower(name)
    enabled = bool(raw.get("enabled", True))
    auto_notify_enabled = bool(raw.get("auto_notify_enabled", False))
    return_codes = _build_return_codes(name, raw.get("return_codes") or [], module_index)
    result_ok = next(r.enum_member for r in return_codes if r.name == "OK")

    notif_map: dict[str, NotificationIR] = {}
    notifications: list[NotificationIR] = []
    seen_codes: set[int] = set()
    seen_notify_pascal: set[str] = set()
    for index, n in enumerate(raw.get("notifications") or []):
        pointer = f"/modules/{module_index}/notifications/{index}"
        nname = n["name"]
        if nname in notif_map:
            raise ValidationError(
                "E2114",
                message=f"{name}: 通知名重复 {nname}",
                json_pointer=f"{pointer}/name",
            )
        code = int(n["code"])
        if code in seen_codes:
            raise ValidationError(
                "E2115",
                message=f"{name}: 通知码重复 {code}",
                json_pointer=f"{pointer}/code",
            )
        seen_codes.add(code)
        fields, plen = _build_fields(
            n["payload"], common_by_name,
            owner=f"{name}.notify.{nname}",
            max_payload=max_payload,
            json_pointer=f"{pointer}/payload",
        )
        ev_pascal = to_pascal(nname)
        if ev_pascal in seen_notify_pascal:
            raise ValidationError(
                "E2116",
                message=f"{name}: 通知名归一化后冲突 {nname}",
                json_pointer=f"{pointer}/name",
            )
        seen_notify_pascal.add(ev_pascal)
        nir = NotificationIR(
            name=nname, pascal=ev_pascal, code=code,
            macro_name=f"{name}_NOTIFY_{nname}", fields=fields, payload_length=plen,
            payload_struct=f"{pascal}_{ev_pascal}Payload" if fields else None,
            decode_fn=f"{pascal}_{ev_pascal}Decode" if fields else None,
            brief=n.get("brief") or nname,
        )
        notifications.append(nir)
        notif_map[nname] = nir

    commands: list[CommandIR] = []
    seen_cmd_names: set[str] = set()
    seen_cmd_codes: set[int] = set()
    seen_cmd_pascal: set[str] = set()
    for index, cmd in enumerate(raw.get("commands") or []):
        pointer = f"/modules/{module_index}/commands/{index}"
        cmd_name = cmd["name"]
        if cmd_name in seen_cmd_names:
            raise ValidationError(
                "E2117",
                message=f"{name}: 命令名重复 {cmd_name}",
                json_pointer=f"{pointer}/name",
            )
        seen_cmd_names.add(cmd_name)
        ccode = int(cmd["code"])
        if ccode in seen_cmd_codes:
            raise ValidationError(
                "E2118",
                message=f"{name}: 命令码重复 {ccode}",
                json_pointer=f"{pointer}/code",
            )
        seen_cmd_codes.add(ccode)
        cmd_pascal = to_pascal(cmd_name)
        if cmd_pascal in seen_cmd_pascal:
            raise ValidationError(
                "E2119",
                message=f"{name}: 命令名归一化后冲突 {cmd_name}",
                json_pointer=f"{pointer}/name",
            )
        seen_cmd_pascal.add(cmd_pascal)
        commands.append(
            _build_command(pascal, name, cmd, notif_map, common_by_name, max_payload, pointer)
        )

    if auto_notify_enabled:
        for cmd_index, cmd in enumerate(commands):
            for field_name, notification in (
                ("notify_on_accept", cmd.notify_on_accept),
                ("notify_on_reject", cmd.notify_on_reject),
                ("notify_on_done", cmd.notify_on_done),
            ):
                if notification is not None and notification.payload_length != 0:
                    raise ValidationError(
                        "E2133",
                        message=(
                            f"{name}.{cmd.name}: {field_name} 在自动通知启用时必须引用"
                            "零载荷通知"
                        ),
                        json_pointer=(
                            f"/modules/{module_index}/commands/{cmd_index}/{field_name}"
                        ),
                    )

    return ModuleIR(
        name=name, pascal=pascal, snake=snake, auto_notify_enabled=auto_notify_enabled, dir_name=pascal,
        header_guard=f"__{name}_H", handle_type=f"{pascal}Handle", ops_type=f"{pascal}Ops",
        commands=commands, notifications=notifications,
        return_codes=return_codes, result_type=f"{pascal}_Result", result_ok=result_ok,
        notify_desc_type=f"{pascal}_NotifyDesc", notify_table_var=f"g_{snake}_notify_table",
        notify_count_var=f"g_{snake}_notify_count", notify_dispatch_fn=f"{pascal}_NotifyDispatch",
        validator_typedef=f"{pascal}_ValidateCallback", validator_setter=f"{pascal}_SetValidate",
        notify_callback_fn=f"{pascal}_NotifyCallback", notify_callback_enable_fn=f"{pascal}_NotifyCallbackEnable",
        on_task_fn=f"{pascal}_OnTask", enabled=enabled,
    )


def _validate_generated_symbols(
    modules: list[ModuleIR],
    common_types: list[CommonTypeIR],
    instances: list[InstanceIR],
    global_results: list[GlobalResultIR],
    target: str,
    validations: list[dict[str, Any]] | None,
    diagnostics: list[Diagnostic] | None,
) -> None:
    """按目标分派公共符号校验：C 目标与 Python 目标各一套命名空间规则。"""
    policy = _LevelPolicy(validations)
    if target == "python":
        _validate_python_symbols(modules, global_results, policy, diagnostics)
    else:
        _validate_c_symbols(modules, common_types, instances, global_results, policy, diagnostics)


def _validate_c_symbols(
    modules: list[ModuleIR],
    common_types: list[CommonTypeIR],
    instances: list[InstanceIR],
    global_results: list[GlobalResultIR],
    policy: _LevelPolicy,
    diagnostics: list[Diagnostic] | None,
) -> None:
    """Validate user-derived identifiers against the complete public C namespace.

    Generated typedefs, functions, variables, enum constants and preprocessor
    macros can collide even when each individual schema object is valid.  Keep
    one conservative registry that includes the fixed Core/Platform API as well
    as common types, instance macros and module-derived symbols.
    """

    def claim(registry: dict[str, str], symbol: str, owner: str, json_pointer: str) -> None:
        previous = registry.get(symbol)
        if previous is not None:
            _report_symbol_conflict(
                ValidationError(
                    "E2113",
                    message=f"生成的 C 符号冲突: {symbol}: {previous} vs {owner}",
                    json_pointer=json_pointer,
                ),
                policy,
                diagnostics,
            )
        registry[symbol] = owner

    public: dict[str, str] = {}

    fixed_public_symbols = (
        # Platform/Core types and constants.
        "STNP_U8", "STNP_U16", "STNP_U32", "STNP_I32", "STNP_NULL",
        "STNP_UNUSED", "STNP_WEAK", "STNP_WEAK_WARN", "STNP_EnableState",
        "STNP_DISABLE", "STNP_ENABLE", "STNP_Result", "STNP_TransportWrite",
        "STNP_ModuleHandle", "STNP_ModuleOps", "STNP_TaskFrame",
        "STNP_NotifyFrame", "STNP_VTL_Type", "STNP_VTL_Field", "STNP_VTL_Desc",
        "STNP_VTL_U8", "STNP_VTL_U16", "STNP_VTL_U32", "STNP_VTL_I32",
        "STNP_OK", "STNP_ERR_LENGTH", "STNP_ERR_TARGET", "STNP_ERR_COMMAND",
        "STNP_ERR_PARAM", "STNP_ERR_STATE", "STNP_IDLE", "STNP_ERR_BUFFER",
        # Public Core/Router/VTL/codec APIs and generated instance entry point.
        "STNP_Init", "STNP_Transport_Write", "STNP_Transport_Receive",
        "STNP_Process", "STNP_Dispatch",
        "STNP_Task_Send", "STNP_Task_SendBytes", "STNP_Task_SendBytes_Impl",
        "STNP_Notify_Send", "STNP_Notify_SendBytes",
        "STNP_Notify_SendBytes_Impl", "STNP_Notify_Dispatch",
        "STNP_Notify_Callback", "STNP_Router_Register",
        "STNP_Router_EncodeTask",
        "STNP_Router_EncodeNotify", "STNP_VTL_Find", "STNP_VTL_Encode",
        "STNP_VTL_Decode", "STNP_Encode_U16", "STNP_Decode_U16",
        "STNP_Encode_U32", "STNP_Decode_U32", "STNP_Encode_I32",
        "STNP_Decode_I32", "STNP_Frame_BuildTask", "STNP_Frame_ParseTask",
        "STNP_Frame_BuildNotify", "STNP_Frame_ParseNotify", "STNP_Instances_Init",
        "STNP_Frame_ReserveSeq", "STNP_NotifyDispatchReceive_Enable",
        "STNP_NotifyDispatchReceive_Disable",
        "STNP_NotifyDispatchReceive_IsEnabled",
        # Public frame/platform macros.
        "STNP_PAYLOAD_MAX", "STNP_ROUTER_INSTANCE_MAX", "STNP_TASK_HEADER_SIZE",
        "STNP_NOTIFY_HEADER_SIZE", "STNP_TASK_FIXED_SIZE",
        "STNP_NOTIFY_FIXED_SIZE", "STNP_CRC_SIZE", "STNP_TASK_HEADER0",
        "STNP_TASK_HEADER1", "STNP_NOTIFY_HEADER0", "STNP_NOTIFY_HEADER1",
    )
    for symbol in fixed_public_symbols:
        claim(public, symbol, "STNP Core/Platform API", "/protocol")

    for index, common in enumerate(common_types):
        pointer = f"/common_types/types/{index}/name"
        claim(public, common.c_type, f"common type {common.name}", pointer)
        if common.kind == "enum":
            for value_name, _ in common.values:
                claim(
                    public,
                    f"STNP_{common.name}_{value_name}",
                    f"common enum {common.name}.{value_name}",
                    pointer,
                )

    for index, inst in enumerate(instances):
        claim(
            public,
            f"STNP_INSTANCE_{inst.macro}_ID",
            f"instance {inst.name} id macro",
            f"/instances/{index}/name",
        )

    for index, result in enumerate(global_results):
        claim(
            public,
            result.enum_member,
            f"工程级返回码 {result.name}",
            f"/global_results/{index}/name",
        )

    for module_index, mod in enumerate(modules):
        name = mod.name
        pascal = mod.pascal
        module_pointer = f"/modules/{module_index}"
        module_symbols: dict[str, str] = {}

        def claim_public(symbol: str, owner: str, json_pointer: str) -> None:
            claim(module_symbols, symbol, owner, json_pointer)
            claim(public, symbol, owner, json_pointer)

        # Public typedefs and public/framework functions from module.h.
        for symbol, owner in (
            (f"{pascal}_Command", f"{name} command enum type"),
            (f"{pascal}_Notify", f"{name} notify enum type"),
            (mod.result_type, f"{name} result type"),
            (mod.handle_type, f"{name} handle type"),
            (mod.validator_typedef, f"{name} validate callback type"),
            (f"{pascal}_Init", f"{name} init function"),
            (f"{pascal}_AsModule", f"{name} module adapter function"),
            (mod.on_task_fn, f"{name} task dispatch function"),
            (mod.validator_setter, f"{name} validator setter"),
            (mod.notify_callback_enable_fn, f"{name} notify callback enable function"),
            (mod.notify_callback_fn, f"{name} notify callback function"),
            (mod.notify_dispatch_fn, f"{name} notify dispatch function"),
        ):
            claim_public(symbol, owner, f"{module_pointer}/name")

        if mod.commands:
            for cmd_index, cmd in enumerate(mod.commands):
                claim_public(
                    f"{name}_CMD_{cmd.name}",
                    f"{name}.{cmd.name} command code",
                    f"{module_pointer}/commands/{cmd_index}/name",
                )
        else:
            claim_public(f"{name}_CMD_NONE", f"{name} empty command placeholder", f"{module_pointer}/name")

        if mod.notifications:
            for notify_index, notify in enumerate(mod.notifications):
                claim_public(
                    notify.macro_name,
                    f"{name}.{notify.name} notify code",
                    f"{module_pointer}/notifications/{notify_index}/name",
                )
        else:
            claim_public(f"{name}_NOTIFY_NONE", f"{name} empty notify placeholder", f"{module_pointer}/name")

        for code_index, code in enumerate(mod.return_codes):
            claim_public(
                code.enum_member,
                f"{name}.{code.name} return code",
                f"{module_pointer}/return_codes/{code_index}/name",
            )

        payload_items = [
            (cmd.name, cmd.payload_struct, cmd.payload_length, f"{name}.{cmd.name} command payload")
            for cmd in mod.commands
        ] + [
            (notify.name, notify.payload_struct, notify.payload_length, f"{name}.{notify.name} notify payload")
            for notify in mod.notifications
        ]
        if any(length for _, _, length, _ in payload_items):
            for item_name, payload_struct, payload_length, owner in payload_items:
                if payload_struct is not None:
                    claim_public(payload_struct, f"{owner} type", f"{module_pointer}/name")
                if payload_length:
                    claim_public(
                        f"{name}_{item_name}_PAYLOAD_SIZE",
                        f"{owner} size constant",
                        f"{module_pointer}/name",
                    )
        else:
            claim_public(f"{name}_PAYLOAD_SIZE_NONE", f"{name} empty payload-size placeholder", f"{module_pointer}/name")

        # User behavior functions are public and therefore must not reuse any
        # generated API/type/constant. The static TaskHandler lives only in this
        # module translation unit, so validate it against this module's symbols.
        local = dict(module_symbols)
        claim(local, f"{pascal}_TaskHandler", f"{name} internal task handler", f"{module_pointer}/name")
        for cmd_index, cmd in enumerate(mod.commands):
            owner = f"{name}.{cmd.name} user behavior function"
            pointer = f"{module_pointer}/commands/{cmd_index}/name"
            claim(local, cmd.user_symbol, owner, pointer)
            claim(public, cmd.user_symbol, owner, pointer)


def _validate_python_symbols(
    modules: list[ModuleIR],
    global_results: list[GlobalResultIR],
    policy: _LevelPolicy,
    diagnostics: list[Diagnostic] | None,
) -> None:
    """Validate module/command/notify snake names in the ``stnp`` namespace."""

    def report(symbol: str, owner: str, json_pointer: str) -> None:
        _report_symbol_conflict(
            ValidationError(
                "E2113",
                message=f"生成的 Python 符号冲突: {symbol}: {owner}",
                json_pointer=json_pointer,
            ),
            policy,
            diagnostics,
        )

    seen_modules: dict[str, str] = {}
    for module_index, mod in enumerate(modules):
        module_pointer = f"/modules/{module_index}"
        if mod.snake in seen_modules:
            _report_symbol_conflict(
                ValidationError(
                    "E2103",
                    message=f"模块名归一化后冲突: {mod.snake}",
                    json_pointer=f"{module_pointer}/name",
                ),
                policy,
                diagnostics,
            )
        else:
            seen_modules[mod.snake] = mod.name
        if mod.snake in _PYTHON_RESERVED_NAMES:
            report(
                mod.snake,
                f"模块 {mod.name} 使用了 Python 保留命名空间名",
                f"{module_pointer}/name",
            )

        local_names: dict[str, str] = {}
        for cmd_index, cmd in enumerate(mod.commands):
            snake = to_snake_lower(cmd.name)
            pointer = f"{module_pointer}/commands/{cmd_index}/name"
            owner = f"命令 {mod.name}.{cmd.name}"
            if snake in local_names:
                report(snake, f"{local_names[snake]} 与 {owner} 的 snake 名重复", pointer)
            else:
                local_names[snake] = owner
            if snake in _PYTHON_RESERVED_NAMES:
                report(snake, f"{owner} 使用 Python 保留名", pointer)
        for notify_index, notify in enumerate(mod.notifications):
            snake = to_snake_lower(notify.name)
            pointer = f"{module_pointer}/notifications/{notify_index}/name"
            owner = f"通知 {mod.name}.{notify.name}"
            if snake in local_names:
                report(snake, f"{local_names[snake]} 与 {owner} 的 snake 名重复", pointer)
            else:
                local_names[snake] = owner
            if snake in _PYTHON_RESERVED_NAMES:
                report(snake, f"{owner} 使用 Python 保留名", pointer)


def _resolve_notify_ref(
    module_name: str,
    cmd_name: str,
    field: str,
    raw_cmd: dict[str, Any],
    notif_map: dict[str, NotificationIR],
    json_pointer: str,
) -> NotificationIR | None:
    spec = raw_cmd.get(field)
    if not spec:
        return None
    nname = spec.get("notify")
    if not nname:
        raise ValidationError(
            "E2131",
            message=f"{module_name}.{cmd_name}: {field} 缺少 notify",
            json_pointer=json_pointer,
        )
    if nname not in notif_map:
        raise ValidationError(
            "E2131",
            message=f"{module_name}.{cmd_name}: {field} 引用的通知不存在: {nname}",
            json_pointer=json_pointer,
        )
    return notif_map[nname]


def _build_command(
    pascal: str, module_name: str, raw: dict[str, Any], notif_map: dict[str, NotificationIR],
    common_by_name: dict[str, CommonTypeIR], max_payload: int, json_pointer: str,
) -> CommandIR:
    cmd_name = raw["name"]
    fields, length = _build_fields(
        raw["payload"], common_by_name,
        owner=f"{module_name}.task.{cmd_name}",
        max_payload=max_payload,
        json_pointer=f"{json_pointer}/payload",
    )
    cmd_pascal = to_pascal(cmd_name)
    payload_struct = f"{pascal}_{cmd_pascal}Payload" if fields else None
    validate = bool(raw.get("validate_hook", False))
    doc = raw.get("doc", {})
    ops_member = to_snake_lower(cmd_name)
    return CommandIR(
        name=cmd_name, pascal=cmd_pascal, code=int(raw["code"]), fields=fields, payload_length=length,
        payload_struct=payload_struct,
        user_symbol=f"{pascal}_{cmd_pascal}", user_brief=doc.get("brief", cmd_name),
        user_description=doc.get("detail", "") or "", validate_hook=validate,
        ops_member=ops_member, decode_fn=f"{pascal}_{cmd_pascal}Decode",
        doc_brief=doc.get("brief", ""), doc_detail=doc.get("detail", ""),
        notify_on_done=_resolve_notify_ref(module_name, cmd_name, "notify_on_done", raw, notif_map, f"{json_pointer}/notify_on_done"),
        notify_on_accept=_resolve_notify_ref(module_name, cmd_name, "notify_on_accept", raw, notif_map, f"{json_pointer}/notify_on_accept"),
        notify_on_reject=_resolve_notify_ref(module_name, cmd_name, "notify_on_reject", raw, notif_map, f"{json_pointer}/notify_on_reject"),
    )
