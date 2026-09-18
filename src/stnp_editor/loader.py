"""STNP 加载期入口：两文件读取、schema 校验、版本标识检查与 IR 构建接线。

职责（0.9 冻结计划 §4.2.1）：

- `.stnp`：读取原始 JSON、版本标识检查、schema 校验，产出 protocol /
  ``common_types`` / 启用模块切片。
- ``stnp.build.json``：读取原始 JSON、版本标识与 ``target`` 检查、schema 校验；
  校验前按内部 SDK 注册表向 ``sdks`` / ``python_sdks`` 注入枚举。

两文件的版本标识各自独立维护支持列表，均不进入 IR。全部报错改抛加载期
异常并附错误码；schema 校验附 JSON 指针，JSON 解析附行列。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaError

from stnp_editor.diagnostics import Diagnostic
from stnp_editor.errors import LoadingError, StnpError, ValidationError
from stnp_editor.ir.builder import build_project_ir
from stnp_editor.ir.models import ProjectIR
from stnp_editor.settings import resources_root, settings

#: `.stnp` 的 `schema_version` 支持列表（生成器独立维护）。
SUPPORTED_SCHEMA_VERSIONS = ("stnp-schema-alpha",)

#: build 文件的 `build_schema_version` 支持列表（生成器独立维护）。
SUPPORTED_BUILD_SCHEMA_VERSIONS = ("stnp-build-schema-alpha",)

#: build 文件 `target` 的合法取值。
_BUILD_TARGETS = ("c", "python")

#: build 枚举注入：build 顶层选择列表 -> 内部 SDK 注册表目标。
_BUILD_SDK_LISTS = (("sdks", "c"), ("python_sdks", "python"))


def _read_json(
    path: Path,
    *,
    missing_code: str,
    parse_code: str,
    parse_message: str | None = None,
) -> dict[str, Any]:
    """读取 JSON 对象文件，按码位映射 I/O 与解析失败。"""
    display = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LoadingError(missing_code, file=display) from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LoadingError(
            parse_code,
            message=parse_message,
            file=display,
            line=exc.lineno,
            column=exc.colno,
        ) from exc
    if not isinstance(data, dict):
        raise LoadingError(parse_code, message=parse_message, file=display)
    return data


def _read_schema(schema_path: Path) -> dict[str, Any]:
    """读取内部 schema 文件；缺失/非法归入内部资源错误码。"""
    return _read_json(schema_path, missing_code="E1051", parse_code="E1052")


def _iter_leaf_errors(error: JsonSchemaError):
    """展开 ``anyOf`` / ``allOf`` 子错误，只保留具体叶子错误。"""
    if error.context:
        for child in error.context:
            yield from _iter_leaf_errors(child)
    else:
        yield error


def _deepest_error(errors: list[JsonSchemaError]) -> JsonSchemaError:
    """在全部叶子错误中取路径最深者，避免只报顶层 ``anyOf``。"""
    best: JsonSchemaError | None = None
    best_depth = -1
    for root in errors:
        for leaf in _iter_leaf_errors(root):
            depth = len(leaf.absolute_path)
            if depth > best_depth:
                best, best_depth = leaf, depth
    assert best is not None
    return best


def _additional_properties(error: JsonSchemaError) -> list[str]:
    """取 ``additionalProperties`` 报错命中的未声明键（供根级指针使用）。"""
    if error.validator != "additionalProperties":
        return []
    schema = error.schema
    instance = error.instance
    if not isinstance(schema, dict) or not isinstance(instance, dict):
        return []
    declared = schema.get("properties")
    if not isinstance(declared, dict):
        return []
    return [str(key) for key in instance if key not in declared]


def _json_pointer(error: JsonSchemaError) -> str:
    """由 ``absolute_path`` 生成 JSON 指针；根级未声明键回退到具体键名。

    根级 ``additionalProperties`` 报错的绝对路径为空串，此时以命中的未声明
    键生成指针（如 ``/modules/0``），避免指针退化为空。
    """
    parts = [str(part) for part in error.absolute_path]
    if parts:
        return "/" + "/".join(parts)
    extra = _additional_properties(error)
    if extra:
        return "/" + extra[0]
    return ""


def _validate(
    instance: Any,
    schema: dict[str, Any],
    *,
    error_code: str,
    file: str | None = None,
) -> None:
    """用 Draft 2020-12 校验实例，失败即抛带 JSON 指针的加载期异常。"""
    errors = list(Draft202012Validator(schema).iter_errors(instance))
    if not errors:
        return
    error = _deepest_error(errors)
    raise LoadingError(error_code, file=file, json_pointer=_json_pointer(error))


def _inject_build_enums(schema: dict[str, Any]) -> None:
    """按内部 SDK 注册表向 build schema 的 ``sdks`` / ``python_sdks`` 注入枚举。"""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return
    for key, target in _BUILD_SDK_LISTS:
        items = properties.get(key, {})
        if not isinstance(items, dict):
            continue
        items_schema = items.get("items")
        if not isinstance(items_schema, dict):
            continue
        available = settings.available_sdks_for(target)
        items_schema["enum"] = list(available)
        items_schema["x-enumLabels"] = {
            sdk: str(settings.sdk_definition_for(target, sdk).get("label", sdk))
            for sdk in available
        }


def load_project_data(project_json: Path) -> dict[str, Any]:
    """Read a .stnp file as raw JSON without converting it to IR.

    Keeping the raw mapping intact means fields can be inspected as written
    before schema validation and conversion to the target-neutral IR.
    """
    project_json = project_json.resolve()
    if project_json.suffix.lower() != ".stnp":
        raise LoadingError(
            "E1001",
            message=f"期望 .stnp 文件: {project_json.name}",
            file=str(project_json),
        )
    data = _read_json(project_json, missing_code="E1001", parse_code="E1002")
    version = data.get("schema_version")
    if version is not None and version not in SUPPORTED_SCHEMA_VERSIONS:
        raise LoadingError("E1005", file=str(project_json))
    return data


def load_build_data(build_json: Path) -> dict[str, Any]:
    """Read a stnp.build.json file as raw JSON; version/target checks follow."""
    build_json = build_json.resolve()
    return _read_json(
        build_json,
        missing_code="E1054",
        parse_code="E1056",
        parse_message="build 文件 JSON 解析失败",
    )


def save_project_data(project_json: Path, data: dict[str, Any]) -> None:
    """Write raw project JSON using a stable, human-readable format."""
    if project_json.suffix.lower() != ".stnp":
        raise LoadingError(
            "E1001",
            message=f"期望 .stnp 文件: {project_json.name}",
            file=str(project_json),
        )
    project_json.parent.mkdir(parents=True, exist_ok=True)
    project_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def validate_project_data(
    data: dict[str, Any], schema_dir: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Validate project JSON and return protocol/common/enabled-module slices."""
    schema_dir = schema_dir or (resources_root() / settings.schemas_dir)
    _validate(data, _read_schema(schema_dir / settings.schema_file("stnp")), error_code="E1003")

    protocol = data["protocol"]
    _validate(protocol, _read_schema(schema_dir / settings.schema_file("protocol")), error_code="E1003")

    common_types = data.get("common_types") or {"types": []}
    _validate(
        common_types,
        _read_schema(schema_dir / settings.schema_file("common_types")),
        error_code="E1003",
    )

    modules_raw: list[dict[str, Any]] = []
    module_schema = _read_schema(schema_dir / settings.schema_file("module"))
    for mod in data["modules"]:
        if not mod.get("enabled", True):
            continue
        _validate(mod, module_schema, error_code="E1003")
        modules_raw.append(mod)

    if not modules_raw:
        raise ValidationError("E2134")
    return protocol, common_types, modules_raw


def validate_build_data(
    data: dict[str, Any], schema_dir: Path | None = None
) -> dict[str, Any]:
    """Validate build JSON: version check, target check, then schema check."""
    if "build_schema_version" in data and data["build_schema_version"] not in SUPPORTED_BUILD_SCHEMA_VERSIONS:
        raise LoadingError("E1055")
    if data.get("target") not in _BUILD_TARGETS:
        raise LoadingError("E1057", json_pointer="/target")

    schema_dir = schema_dir or (resources_root() / settings.schemas_dir)
    schema = _read_schema(schema_dir / settings.schema_file("build"))
    _inject_build_enums(schema)
    _validate(data, schema, error_code="E1056")
    return data


def build_project_from_data(
    data: dict[str, Any],
    build_data: dict[str, Any],
    *,
    source_path: Path | None = None,
    schema_dir: Path | None = None,
    diagnostics: list[Diagnostic] | None = None,
) -> ProjectIR:
    """Validate raw project data then build the target-neutral IR."""
    file = str(source_path) if source_path is not None else None
    try:
        protocol, common_types, modules_raw = validate_project_data(data, schema_dir)
    except StnpError as exc:
        if exc.file is None and file is not None:
            exc.file = file
        raise

    stem = build_data.get("output_stem") or (
        source_path.stem if source_path is not None else data.get("project_name", "stnp")
    )
    project = {
        "project_name": data["project_name"],
        "instances": copy.deepcopy(data["instances"]),
        "global_results": copy.deepcopy(data.get("global_results") or []),
    }
    build = {**copy.deepcopy(build_data), "output_stem": stem}
    try:
        return build_project_ir(
            project,
            protocol,
            modules_raw,
            build,
            common_raw=common_types,
            embedded_raw=copy.deepcopy(data.get("embedded_files") or {}),
            diagnostics=diagnostics,
        )
    except StnpError as exc:
        if exc.file is None and file is not None:
            exc.file = file
        raise


def load_project(
    project_json: Path,
    build_json: Path,
    schema_dir: Path | None = None,
    diagnostics: list[Diagnostic] | None = None,
) -> ProjectIR:
    """Load a .stnp project plus its build file into IR for CLI/generation."""
    project_json = project_json.resolve()
    build_json = build_json.resolve()
    data = load_project_data(project_json)
    build_data = load_build_data(build_json)
    try:
        validate_build_data(build_data, schema_dir)
    except StnpError as exc:
        if exc.file is None:
            exc.file = str(build_json)
        raise
    return build_project_from_data(
        data,
        build_data,
        source_path=project_json,
        schema_dir=schema_dir,
        diagnostics=diagnostics,
    )
