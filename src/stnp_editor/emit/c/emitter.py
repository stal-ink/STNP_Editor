from __future__ import annotations

from pathlib import Path
from typing import Iterable

from stnp_editor import __version__
from stnp_editor.encoding import decode_base64_content
from stnp_editor.emit.c.merge import merge_user_regions
from stnp_editor.emit.c.render import make_env, render
from stnp_editor.emit.manifest import cleanup_stale, load_manifest, write_manifest
from stnp_editor.errors import GenerationError, LoadingError
from stnp_editor.generation import generated_dir_name, validate_output_stem
from stnp_editor.ir.models import ProjectIR
from stnp_editor.settings import settings

TARGET = "c"
EMBEDDED_ROOT = "Embedded"


def resolve_stnp_c_root(output: Path, stem: str, build: dict) -> Path:
    stem = validate_output_stem(stem)
    dir_name = f"{stem}_{generated_dir_name(build, TARGET)}"
    output = output.resolve()
    if output.name == dir_name:
        return output
    root = (output / dir_name).resolve()
    if root.parent != output:
        raise GenerationError(
            "E4005",
            message=f"generated output escapes selected directory: {root}",
        )
    return root


def emit_c(ir: ProjectIR, output: Path, build: dict, *, template_root: Path | None = None) -> Path:
    root = resolve_stnp_c_root(output, ir.output_stem, build)
    env = make_env(template_root)
    ctx = {"ir": ir, "p": ir.protocol, "stnp_version": __version__}

    platform_dir = settings.dir_name("platform")
    core_dir = settings.dir_name("core")
    module_dir = settings.dir_name("module")
    instance_dir = settings.dir_name("instance")
    examples_dir = settings.dir_name("examples")
    implementation_dir = settings.dir_name("implementation")
    sdk_dir = settings.dir_name("sdk")

    files: dict[str, str] = {}
    kinds: dict[str, str] = {}

    def add(rel: str, content: str, kind: str = "generated") -> None:
        files[rel] = content
        kinds[rel] = kind

    add(f"{platform_dir}/stnp_platform.h", render(env, "Platform/stnp_platform.h.j2", **ctx))
    add(f"{platform_dir}/stnp_platform_config.h", render(env, "Platform/stnp_platform_config.h.j2", **ctx))
    add(f"{platform_dir}/stnp_types.h", render(env, "Platform/stnp_types.h.j2", **ctx))

    core_names = [
        "stnp.h", "stnp_core.h", "stnp_core.c", "stnp_frame.h", "stnp_frame.c",
        "stnp_codec.h", "stnp_codec.c", "stnp_vtl.h", "stnp_vtl.c", "stnp_task.h", "stnp_task.c",
        "stnp_notify.h", "stnp_notify.c", "stnp_router.h", "stnp_router.c",
        "stnp_runtime.h", "stnp_runtime.c",
    ]
    if ir.protocol.crc_enabled:
        core_names.extend(["stnp_crc.h", "stnp_crc.c"])
    for name in core_names:
        add(f"{core_dir}/{name}", render(env, f"Core/{name}.j2", **ctx))

    add(f"{module_dir}/stnp_module.h", render(env, "Module/stnp_module.h.j2", **ctx))
    add(f"{module_dir}/stnp_module.c", render(env, "Module/stnp_module.c.j2", **ctx))
    for mod in ir.modules:
        mctx = {**ctx, "m": mod}
        base = f"{module_dir}/{mod.dir_name}"
        add(f"{base}/{mod.snake}.h", render(env, "Module/module/module.h.j2", **mctx))
        add(f"{base}/{mod.snake}.c", render(env, "Module/module/module.c.j2", **mctx))

    add(f"{instance_dir}/stnp_instances.h", render(env, "Instance/stnp_instances.h.j2", **ctx))
    add(f"{instance_dir}/stnp_instances.c", render(env, "Instance/stnp_instances.c.j2", **ctx))

    for mod in ir.modules:
        if not mod.commands:
            continue
        mctx = {**ctx, "m": mod}
        add(f"{implementation_dir}/{mod.snake}_impl.c", render(env, "Implementation/module.c.j2", **mctx), "implementation")
    add(f"{implementation_dir}/stnp_notify_callback.c", render(env, "Implementation/stnp_notify_callback.c.j2", **ctx), "implementation")

    if ir.emit_examples:
        add(f"{examples_dir}/transport_mock.h", render(env, "Examples/transport_mock.h.j2", **ctx))
        add(f"{examples_dir}/transport_mock.c", render(env, "Examples/transport_mock.c.j2", **ctx))
        add(f"{examples_dir}/main.c", render(env, "Examples/main.c.j2", **ctx))

    for sdk_key in ir.sdks:
        sdk = settings.sdk_definition_for("c", sdk_key)
        template_dir = str(sdk.get("template_dir") or "").strip("/")
        output_dir = str(sdk.get("output_dir") or "").strip("/")
        if not template_dir or not output_dir:
            raise GenerationError(
                "E4004",
                message=f"SDK 注册表条目缺少模板目录或输出目录: {sdk_key}",
            )
        for name in sdk.get("files", []):
            add(
                f"{sdk_dir}/{output_dir}/{name}",
                render(env, f"{template_dir}/{name}.j2", **ctx),
            )

    if ir.build_system == "cmake":
        add("CMakeLists.txt", render(env, "Build/CMakeLists.txt.j2", **ctx))

    if ir.emit_readme:
        add("README.md", render(env, "README.md.j2", **ctx))

    embedded = _embedded_payloads(ir)
    for rel in embedded:
        kinds[rel] = "embedded"

    _validate_unique_c_basenames(files.keys())
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GenerationError("E4010", message=f"生成目录创建失败: {root}") from exc
    # 清单损坏不再阻断生成；此调用点无诊断收集器，按契约静默忽略。
    old_manifest = load_manifest(root)
    _migrate_legacy_implementation_names(root, ir, implementation_dir, old_manifest)
    cleanup_stale(root, old_manifest, set(files) | set(embedded))

    for rel, content in files.items():
        path = root / rel
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if kinds[rel] == "implementation" and path.is_file():
                content = merge_user_regions(content, path.read_text(encoding="utf-8"))
            path.write_text(content, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise GenerationError("E4010", message=f"生成文件写出失败: {rel}") from exc

    for rel, payload in embedded.items():
        path = root / rel
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(payload, bytes):
                path.write_bytes(payload)
            else:
                path.write_text(payload, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise GenerationError("E4012", message=f"嵌入文件写出失败: {rel}") from exc

    write_manifest(root, kinds)
    return root



def _migrate_legacy_implementation_names(
    root: Path, ir: ProjectIR, implementation_dir: str, old_manifest: dict[str, str]
) -> None:
    """0.6.2 -> 0.6.3: rename generated user files without losing USER CODE.

    Only manifest-owned implementation files are migrated. If the new path already
    exists, normal orphan protection handles the legacy file instead of overwriting it.
    """
    for mod in ir.modules:
        if not mod.commands:
            continue
        legacy_rel = f"{implementation_dir}/{mod.snake}.c"
        new_rel = f"{implementation_dir}/{mod.snake}_impl.c"
        if old_manifest.get(legacy_rel) != "implementation":
            continue
        legacy = root / legacy_rel
        new = root / new_rel
        if legacy.is_file() and not new.exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            legacy.replace(new)

def _embedded_payloads(ir: ProjectIR) -> dict[str, str | bytes]:
    out: dict[str, str | bytes] = {}
    for item in ir.embedded_files:
        rel = f"{EMBEDDED_ROOT}/{item.path}"
        if item.encoding == "text":
            out[rel] = item.content
            continue
        try:
            out[rel] = decode_base64_content(item.content, owner=f"embedded file {item.path!r}")
        except LoadingError as exc:
            raise GenerationError(
                "E4012", message=f"嵌入文件负载解码失败: {item.path}"
            ) from exc
    return out


def _validate_unique_c_basenames(paths: Iterable[str]) -> None:
    """Reject output trees that would collide in Keil's basename-based object directory.

    Keil MDK commonly emits every source as <basename>.o in one object folder.
    Treat C source basenames case-insensitively so generated output is safe on
    Windows/Keil without per-file object-directory configuration.
    """
    seen: dict[str, str] = {}
    for rel in paths:
        path = Path(rel)
        if path.suffix.casefold() != ".c":
            continue
        key = path.name.casefold()
        previous = seen.get(key)
        if previous is not None and previous != rel:
            raise GenerationError(
                "E4007",
                message=(
                    "Keil object basename collision: "
                    f"{previous!r} and {rel!r} both compile as {path.stem}.o"
                ),
            )
        seen[key] = rel
