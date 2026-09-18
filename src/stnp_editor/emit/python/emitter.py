from __future__ import annotations

from pathlib import Path

from stnp_editor import __version__
from stnp_editor.emit.manifest import cleanup_stale, load_manifest, write_manifest
from stnp_editor.emit.python.render import make_env, render
from stnp_editor.errors import GenerationError
from stnp_editor.generation import ensure_supported_sdks, generated_dir_name, validate_output_stem
from stnp_editor.ir.models import ProjectIR

TARGET = "python"


def resolve_stnp_python_root(output: Path, stem: str, build: dict) -> Path:
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


def emit_python(ir: ProjectIR, output: Path, build: dict, *, template_root: Path | None = None) -> Path:
    root = resolve_stnp_python_root(output, ir.output_stem, build)
    env = make_env(template_root)
    python_sdks = ensure_supported_sdks(list(build.get("python_sdks") or []), target="python")
    emit_user_scaffold = bool((build.get("python") or {}).get("emit_user_scaffold", False))
    emit_examples = ir.emit_examples
    ctx = {"ir": ir, "p": ir.protocol, "pycfg": build, "sdks": python_sdks, "stnp_version": __version__}

    files: dict[str, str] = {}
    kinds: dict[str, str] = {}

    def add(rel: str, template: str, *, kind: str = "generated", **extra) -> None:
        files[rel] = render(env, template, **ctx, **extra)
        kinds[rel] = kind

    add("pyproject.toml", "pyproject.toml.j2")
    add("config/stnp.yaml", "config/stnp.yaml.j2")
    add("stnp/__init__.py", "stnp/__init__.py.j2")
    add("stnp/core/__init__.py", "stnp/core/__init__.py.j2")
    for name in ("errors.py", "transport.py", "codec.py", "crc.py", "frame.py", "model.py", "dispatch.py", "stats.py", "runtime.py"):
        add(f"stnp/core/{name}", f"stnp/core/{name}.j2")
    add("stnp/sdk/__init__.py", "stnp/sdk/__init__.py.j2")

    if "uart" in python_sdks:
        for name in ("__init__.py", "config.py", "transport.py", "uart.yaml"):
            add(f"stnp/sdk/uart/{name}", f"stnp/sdk/uart/{name}.j2")

    add("stnp/protocol/__init__.py", "stnp/protocol/__init__.py.j2")
    add("stnp/protocol/constants.py", "stnp/protocol/constants.py.j2")
    add("stnp/protocol/types.py", "stnp/protocol/types.py.j2")
    add("stnp/protocol/registry.py", "stnp/protocol/registry.py.j2")
    add("stnp/protocol/instances.py", "stnp/protocol/instances.py.j2")
    add("stnp/protocol/protocol.yaml", "stnp/protocol/protocol.yaml.j2")
    add("stnp/protocol/modules/__init__.py", "stnp/protocol/modules/__init__.py.j2")
    add("stnp/protocol/payloads/__init__.py", "stnp/protocol/payloads/__init__.py.j2")
    for mod in ir.modules:
        add(f"stnp/protocol/modules/{mod.snake}.py", "stnp/protocol/modules/module.py.j2", m=mod)
        add(f"stnp/protocol/payloads/{mod.snake}.py", "stnp/protocol/payloads/module.py.j2", m=mod)

    if emit_examples:
        add("Example/mock_serial.py", "Example/mock_serial.py.j2")
        add("Example/main.py", "Example/main.py.j2")
        add("Example/README.md", "Example/README.md.j2")

    if ir.emit_readme:
        add("README.md", "README.md.j2")

    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GenerationError("E4010", message=f"生成目录创建失败: {root}") from exc
    # 清单损坏不再阻断生成；此调用点无诊断收集器，按契约静默忽略。
    old_manifest = load_manifest(root)
    cleanup_stale(root, old_manifest, files)
    for rel, content in files.items():
        path = root / rel
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise GenerationError("E4010", message=f"生成文件写出失败: {rel}") from exc

    # User scaffold is intentionally unmanaged: create once, never overwrite or delete.
    if emit_user_scaffold:
        user_root = root / "User"
        try:
            user_root.mkdir(parents=True, exist_ok=True)
            init_path = user_root / "__init__.py"
            if not init_path.exists():
                init_path.write_text("# User-owned package. The generator never overwrites this directory.\n", encoding="utf-8")
            for mod in ir.modules:
                if not mod.commands:
                    continue
                rel = user_root / f"{mod.snake}_logic.py"
                if not rel.exists():
                    rel.write_text(render(env, "User/module_logic.py.j2", **ctx, m=mod), encoding="utf-8", newline="\n")
        except OSError as exc:
            raise GenerationError("E4010", message=f"用户 scaffold 写出失败: {user_root}") from exc

    write_manifest(root, kinds)
    return root
