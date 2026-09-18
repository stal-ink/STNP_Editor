"""Non-GUI generator regression tests migrated from the deleted ``tests/test_gui_core.py``.

0.9 removes the whole GUI tree and the GUI core test module (freeze plan §5.6 F4).
The four cases below have no GUI dependency and are kept here:

- ``test_returncode_only_module_builds_ir``
- ``test_save_format_is_readable_json``
- ``test_returncode_only_module_generates_strict_c``
- ``test_product_version_matches_pyproject`` (rewritten from
  ``test_product_version_is_0_8_0``; since 0.9.0 it proves that
  ``stnp_editor.__version__`` stays the only literal, because pyproject.toml
  declares the version dynamic and derives it from that attribute)

Two cases from the old module are deliberately abandoned because their subjects were
removed in 0.9:

- ``test_generation_target_is_kept_in_target_neutral_ir`` asserted ``ir.extras``
  target/generation containers. The IR no longer carries generation-target extras
  (freeze plan §4.3.1); build options live only in ``stnp.build.json``.
- ``test_generation_target_validation_accepts_python`` asserted
  ``stnp_editor.generation.ensure_supported_generation_target``. That runtime target
  check was deleted; the target is now validated as a build-schema enum at load time
  (freeze plan §4.3.2 / §4.3.6).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from stnp_editor import __version__
from stnp_editor.emit.c import emit_c
from stnp_editor.loader import (
    build_project_from_data,
    load_build_data,
    load_project_data,
    save_project_data,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "fixtures" / "C" / "regression_c.stnp"
BUILD = ROOT / "fixtures" / "C" / "stnp.build.json"


def _returncode_only_project() -> dict:
    """regression_c plus a command/notification-free module.

    The appended module is the fourth enabled module, so 0.9 return-code
    partitioning puts its ``OK`` at ``0x0100 + 256 * 3 = 0x0400``.
    """
    data = load_project_data(EXAMPLE)
    data["modules"].append({
        "enabled": True,
        "name": "RETURNCODE",
        "return_codes": [{"name": "OK", "value": 0x0400, "brief": "success"}],
        "commands": [],
        "notifications": [],
    })
    return data


def test_returncode_only_module_builds_ir() -> None:
    data = _returncode_only_project()
    ir = build_project_from_data(data, load_build_data(BUILD), source_path=EXAMPLE)
    module = next(m for m in ir.modules if m.name == "RETURNCODE")
    assert module.commands == []
    assert module.notifications == []
    assert module.return_codes


def test_save_format_is_readable_json(tmp_path: Path) -> None:
    data = load_project_data(EXAMPLE)
    out = tmp_path / "copy.stnp"
    save_project_data(out, data)
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == data


def test_returncode_only_module_generates_strict_c(tmp_path: Path) -> None:
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")

    build = load_build_data(BUILD)
    ir = build_project_from_data(_returncode_only_project(), build, source_path=EXAMPLE)
    out = emit_c(ir, tmp_path, build)
    sources: list[str] = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c", "Implementation/*.c", "Examples/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    exe = out / "returncode_demo"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out,
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run([str(exe)], cwd=out, check=True, capture_output=True, text=True)
    assert "demo ok" in result.stdout


def test_product_version_matches_pyproject() -> None:
    version = __version__
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert version
    assert len(version.split(".")) == 3
    # 0.9.0: __version__ is the single source.  pyproject.toml declares the
    # version dynamic and asks setuptools to read it from the package
    # attribute, so there is exactly one literal to bump.
    assert project["project"]["dynamic"] == ["version"]
    assert "version" not in project["project"]
    assert project["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "stnp_editor.__version__"
    }
