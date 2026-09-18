"""Guard tests that keep ``examples/`` runnable after the golden split.

``tests/golden/**`` is regenerated from ``fixtures/**`` and is never compared
against ``examples/**``.  Examples are illustrative only; the one obligation
they keep is that every example project still generates and checks cleanly.
Nothing here compares an example against a committed golden tree.

One example may ship more than one build config (``dual_multi_c_py`` has one C
config and one Python config sharing a single ``.stnp``), so the guard collects
every sibling ``stnp.build*.json`` of every ``.stnp`` and runs generate + check
once per (project, build) pair.

The guard is deliberately non-vacuous: fewer than ``_MIN_EXAMPLES`` discovered
projects fails, an ``*.stnp`` without any sibling build config fails and lists
the offender, at least one example must expose two or more build configs (so the
multi-config code path cannot be silently skipped), and every pair is generated
and checked in a real CLI subprocess run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

#: Three example projects exist today (handshake_c, stm32_hal_uart_c,
#: dual_multi_c_py); two is the floor that still proves the guard is not
#: silently checking nothing when the tree is renamed or emptied.
_MIN_EXAMPLES = 3


def _build_configs(project: Path) -> list[Path]:
    """Every sibling ``stnp.build*.json`` of an example project, sorted."""
    return sorted(project.parent.glob("stnp.build*.json"))


_PROJECTS = sorted(EXAMPLES.rglob("*.stnp"))


def _project_id(project: Path) -> str:
    return "/".join(project.relative_to(EXAMPLES).parts[:-1]) or project.stem


_PAIRS = [
    pytest.param(project, build, id=f"{_project_id(project)}::{build.name}")
    for project in _PROJECTS
    for build in _build_configs(project)
]


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the source-checkout CLI entry point in a fresh process."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_examples_tree_is_not_empty() -> None:
    assert len(_PROJECTS) >= _MIN_EXAMPLES, (
        f"expected at least {_MIN_EXAMPLES} example projects under {EXAMPLES}, "
        f"found {len(_PROJECTS)}: {[str(p) for p in _PROJECTS]}"
    )


def test_every_example_project_has_a_build_config() -> None:
    missing = [p for p in _PROJECTS if not _build_configs(p)]
    assert not missing, "example project(s) without stnp.build*.json: " + ", ".join(
        str(p.relative_to(ROOT)) for p in missing
    )


def test_at_least_one_example_has_multiple_build_configs() -> None:
    multi = [p for p in _PROJECTS if len(_build_configs(p)) >= 2]
    assert multi, (
        "expected at least one example project with two or more build configs "
        f"under {EXAMPLES}, found none"
    )


@pytest.mark.parametrize("project,build", _PAIRS)
def test_example_generates_and_checks_cleanly(
    project: Path, build: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    generated = _run_cli(
        "generate", str(project), str(build), "-o", str(out), cwd=tmp_path
    )
    assert generated.returncode == 0, generated.stderr
    assert generated.stdout.startswith("generated: ")

    # `check` requires --golden; point it at the tree this test just generated
    # so the property under test is "the example loads, emits and regenerates
    # cleanly", not equality with any committed golden.
    checked = _run_cli(
        "check", str(project), str(build), "--golden", str(out), cwd=tmp_path
    )
    assert checked.returncode == 0, checked.stderr
    assert "CHECK OK" in checked.stdout
