"""End-to-end CLI tests that drive real subprocesses (T1.2).

The module deliberately avoids importing ``stnp_editor.cli`` and calling
``main()`` in-process: a separate process is the only way to observe the exact
argparse behaviour, the stdout/stderr split and the process exit code that
users and CI actually see.

Entry points under test (all three):

- ``python main.py ...`` — source-checkout entry point, always available.
- ``python -m stnp_editor ...`` — I-007: this conda environment does **not**
  have the ``stnp-editor`` distribution installed, so ``python -m
  stnp_editor`` cannot import the package by name (unlike an installed env).
  The test therefore injects ``PYTHONPATH=<repo>/src`` into the child process
  environment, which is exactly what ``main.py`` does for itself; the real
  ``__main__`` + argparse path still runs in a separate process.
- ``stnpe`` — console script (``[project.scripts]``).  The entry is added to
  the parametrization only when ``shutil.which("stnpe")`` resolves; when it
  does not, ``test_stnpe_entry_point_availability`` skips with an explicit
  "not installed" reason, so the absence is reported and never silent.

Every artifact is written under ``tmp_path``; the repository itself is never
written to (``cwd`` for all subprocesses is ``tmp_path`` as well).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from stnp_editor import __version__
from stnp_editor.errors import EXIT_FAILURE, EXIT_OK, EXIT_USAGE

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_C = ROOT / "fixtures" / "C"
FIXTURE_PY = ROOT / "fixtures" / "python"
GOLDEN_C = ROOT / "tests" / "golden" / "C" / "regression_c"
GOLDEN_PY = ROOT / "tests" / "golden" / "python" / "regression_py"


@dataclass(frozen=True)
class Entry:
    """One CLI entry point: display name, argv prefix and extra child env."""

    name: str
    prefix: tuple[str, ...]
    env: dict[str, str]


_STNPE = shutil.which("stnpe")


def _entry_params() -> list:
    params = [
        pytest.param(
            Entry("python main.py", (sys.executable, str(ROOT / "main.py")), {}),
            id="main-py",
        ),
        pytest.param(
            Entry(
                "python -m stnp_editor",
                (sys.executable, "-m", "stnp_editor"),
                {"PYTHONPATH": str(ROOT / "src")},
            ),
            id="python-m",
        ),
    ]
    if _STNPE is not None:
        params.append(pytest.param(Entry("stnpe", (_STNPE,), {}), id="stnpe"))
    return params


@pytest.fixture(params=_entry_params())
def entry(request: pytest.FixtureRequest) -> Entry:
    return request.param


def test_stnpe_entry_point_availability() -> None:
    """Third entry point: covered when the console script exists, skipped when not.

    ``stnpe`` comes from the distribution's ``[project.scripts]``; I-007 records
    that this conda environment does not have ``stnp-editor`` installed, so the
    script cannot be on PATH here.  The other two entry points always run.
    """
    if _STNPE is None:
        pytest.skip(
            "stnpe console script not found: the stnp-editor package is not "
            "installed in this environment (no [project.scripts] shim on PATH); "
            'install with `pip install -e ".[dev]"` to enable this entry point.'
        )
    result = subprocess.run(
        [_STNPE, "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == EXIT_OK, result.stderr
    assert result.stdout.strip() == __version__


def _run(entry: Entry, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run one CLI invocation in a fresh process and capture both streams.

    ``PYTHONIOENCODING=utf-8`` keeps the child's text streams locale-independent:
    the product's diagnostics are Chinese, and a non-CJK Windows ANSI codepage
    cannot encode them, which would otherwise make the stdout/stderr text depend
    on the host locale instead of on the CLI contract under test.
    """
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.update(entry.env)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [*entry.prefix, *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------
# --help / version
# ---------------------------------------------------------------------------


def test_help_exits_zero_and_lists_commands(entry: Entry, tmp_path: Path) -> None:
    result = _run(entry, "--help", cwd=tmp_path)
    assert result.returncode == EXIT_OK, result.stderr
    for command in ("generate", "check", "version"):
        assert command in result.stdout, f"--help output is missing {command!r}"


def test_version_flag_prints_exact_version(entry: Entry, tmp_path: Path) -> None:
    result = _run(entry, "--version", cwd=tmp_path)
    assert result.returncode == EXIT_OK, result.stderr
    assert result.stdout.strip() == __version__


def test_version_subcommand_prints_exact_version(entry: Entry, tmp_path: Path) -> None:
    result = _run(entry, "version", cwd=tmp_path)
    assert result.returncode == EXIT_OK, result.stderr
    assert result.stdout.strip() == __version__


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

_GENERATE_CASES = [
    pytest.param(FIXTURE_C, "regression_c", "regression_c_STNP_C", id="c"),
    pytest.param(FIXTURE_PY, "regression_py", "regression_py_STNP_Python", id="python"),
]


@pytest.mark.parametrize(("fixture_dir", "stem", "tree_name"), _GENERATE_CASES)
def test_generate_creates_non_empty_tree(
    entry: Entry,
    tmp_path: Path,
    fixture_dir: Path,
    stem: str,
    tree_name: str,
) -> None:
    out = tmp_path / f"out_{stem}"
    result = _run(
        entry,
        "generate",
        str(fixture_dir / f"{stem}.stnp"),
        str(fixture_dir / "stnp.build.json"),
        "-o",
        str(out),
        cwd=tmp_path,
    )
    assert result.returncode == EXIT_OK, result.stderr
    assert result.stdout.startswith("generated: ")
    tree = out / tree_name
    assert tree.is_dir(), f"missing generated tree: {tree}"
    assert any(p.is_file() for p in tree.rglob("*")), "generated tree is empty"


def test_generate_list_prints_numbered_posix_paths(entry: Entry, tmp_path: Path) -> None:
    out = tmp_path / "out_list"
    result = _run(
        entry,
        "generate",
        str(FIXTURE_C / "regression_c.stnp"),
        str(FIXTURE_C / "stnp.build.json"),
        "-o",
        str(out),
        "-list",
        cwd=tmp_path,
    )
    assert result.returncode == EXIT_OK, result.stderr

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    tree = out / "regression_c_STNP_C"
    actual = sorted(
        p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file()
    )
    assert lines, "-list printed nothing"
    assert len(lines) == len(actual), "M in [N/M] must equal the real file count"

    listed: list[str] = []
    for index, line in enumerate(lines, start=1):
        match = re.fullmatch(r"\[(\d+)/(\d+)\] (.+)", line)
        assert match, f"unexpected -list line: {line!r}"
        assert int(match.group(1)) == index, f"bad sequence number in {line!r}"
        assert int(match.group(2)) == len(lines), f"bad total in {line!r}"
        rel = match.group(3)
        assert "\\" not in rel, f"expected posix path, got: {rel!r}"
        listed.append(rel)
    assert listed == actual


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

_CHECK_CASES = [
    pytest.param(FIXTURE_C, "regression_c", GOLDEN_C, id="c"),
    pytest.param(FIXTURE_PY, "regression_py", GOLDEN_PY, id="python"),
]


@pytest.mark.parametrize(("fixture_dir", "stem", "golden"), _CHECK_CASES)
def test_check_repo_golden_prints_check_ok(
    entry: Entry,
    tmp_path: Path,
    fixture_dir: Path,
    stem: str,
    golden: Path,
) -> None:
    result = _run(
        entry,
        "check",
        str(fixture_dir / f"{stem}.stnp"),
        str(fixture_dir / "stnp.build.json"),
        "--golden",
        str(golden),
        cwd=tmp_path,
    )
    assert result.returncode == EXIT_OK, result.stderr
    assert "CHECK OK" in result.stdout


def test_check_detects_broken_golden(entry: Entry, tmp_path: Path) -> None:
    # Never touch tests/golden/** — corrupt a private copy instead.
    broken = tmp_path / "broken_golden"
    shutil.copytree(GOLDEN_C, broken)
    victim = broken / "regression_c_STNP_C" / "Core" / "stnp_core.h"
    assert victim.is_file(), f"expected golden file missing: {victim}"
    victim.write_text(
        victim.read_text(encoding="utf-8") + "\n/* broken golden */\n",
        encoding="utf-8",
        newline="\n",
    )

    result = _run(
        entry,
        "check",
        str(FIXTURE_C / "regression_c.stnp"),
        str(FIXTURE_C / "stnp.build.json"),
        "--golden",
        str(broken),
        cwd=tmp_path,
    )
    assert result.returncode == EXIT_FAILURE
    assert "CHECK FAILED:" in result.stdout
    assert "content differs: Core/stnp_core.h" in result.stdout


# ---------------------------------------------------------------------------
# error code -> exit code mapping
# ---------------------------------------------------------------------------


def test_unsupported_schema_version_maps_to_failure_exit(
    entry: Entry, tmp_path: Path
) -> None:
    data = json.loads((FIXTURE_C / "regression_c.stnp").read_text(encoding="utf-8"))
    # E1005: schema_version must be one of the generator's supported strings;
    # an integer is rejected by loader.load_project_data.
    data["schema_version"] = 2
    bad = tmp_path / "bad_schema_version.stnp"
    bad.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    result = _run(
        entry,
        "check",
        str(bad),
        str(FIXTURE_C / "stnp.build.json"),
        "--golden",
        str(GOLDEN_C),
        cwd=tmp_path,
    )
    assert result.returncode == EXIT_FAILURE, result.stderr
    assert "E1005" in result.stderr


def test_missing_subcommand_maps_to_usage_exit(entry: Entry, tmp_path: Path) -> None:
    result = _run(entry, cwd=tmp_path)
    assert result.returncode == EXIT_USAGE
    assert "usage:" in result.stderr.lower()
