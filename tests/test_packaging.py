"""Opt-in acceptance tests for the frozen single-file ``dist/stnpe.exe``.

Building the executable with PyInstaller takes one to three minutes, so the
whole module is skipped during collection unless ``STNP_TEST_EXE`` is truthy::

    $env:STNP_TEST_EXE = "1"
    pytest tests/test_packaging.py -q

Without the variable the default ``pytest -q`` stays fast and toolchain-only.

When enabled, three things are verified with real subprocesses (no mocks):

1. ``scripts/build_exe.ps1`` exits 0 and leaves exactly one file, ``dist/stnpe.exe``.
2. ``scripts/verify_exe.ps1`` exits 0 with all six checks reported ``PASS``.
3. The ``config.json`` authority proof is reproduced independently: built-in
   defaults produce ``Core/``; a rewritten exe-sibling ``config.json`` produces
   ``FakeCore/``; ``STNP_EDITOR_CONFIG`` produces ``EnvCore/`` and beats the
   exe-sibling file.  Every stage asserts on the generated directory tree, not
   on stdout.

Everything is staged under ``tmp_path``.  The inputs come from the shared
``fixtures/C`` regression project and the expectations from the generated tree
under ``tests/golden/C/regression_c/``; both are copied into the sandbox, so
isolation comes from the temp directory, not from a packaging-only fixture
copy.  The repository is only touched via the two scripts, which own ``dist/``
and ``build/``.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
EXE = DIST / "stnpe.exe"
FIXTURES = ROOT / "fixtures"
GOLDEN = ROOT / "tests" / "golden"
GOLDEN_C_TREE = GOLDEN / "C" / "regression_c" / "regression_c_STNP_C"
BUILD_PS1 = ROOT / "scripts" / "build_exe.ps1"
VERIFY_PS1 = ROOT / "scripts" / "verify_exe.ps1"

_TRUTHY = {"1", "true", "yes", "on"}

if os.environ.get("STNP_TEST_EXE", "").strip().lower() not in _TRUTHY:
    pytest.skip("set STNP_TEST_EXE=1 to run packaging tests", allow_module_level=True)

# Onefile PyInstaller builds are slow; the other budgets cover exe startup plus
# fixture generation on a cold runner.
_BUILD_TIMEOUT_S = 1800
_VERIFY_TIMEOUT_S = 900
_EXE_TIMEOUT_S = 300


def _run_ps1(script: Path, *, timeout_s: int) -> subprocess.CompletedProcess[str]:
    # Resolve powershell absolutely instead of relying on the inherited PATH:
    # tooling in the same session (e.g. scripts/build_exe.ps1) may narrow PATH
    # while it runs, and a missing System32 entry must not break this test.
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = os.path.join(
        system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
    )
    powershell = candidate if os.path.isfile(candidate) else shutil.which("powershell")
    if not powershell:
        raise FileNotFoundError(
            f"powershell.exe not found at {candidate} and "
            "shutil.which('powershell') returned nothing"
        )
    return subprocess.run(
        [
            powershell,
            "-ExecutionPolicy",
            "Bypass",
            "-NoProfile",
            "-File",
            str(script),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )


def _run_exe(
    exe: Path,
    args: list[str],
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    # The three authority stages must not inherit a developer's global override.
    env.pop("STNP_EDITOR_CONFIG", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(exe), *args],
        cwd=str(exe.parent),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_EXE_TIMEOUT_S,
    )


def _describe(result: subprocess.CompletedProcess[str]) -> str:
    return (
        f"rc={result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


def _line_with(output: str, marker: str) -> str:
    for line in output.splitlines():
        if marker in line:
            return line
    raise AssertionError(f"no output line contains {marker!r}:\n{output}")


def _require_exe() -> None:
    assert EXE.is_file(), (
        f"missing artifact {EXE}; run scripts/build_exe.ps1 first "
        f"(test_build_exe_produces_single_file in this module does it)"
    )


def test_build_exe_produces_single_file() -> None:
    result = _run_ps1(BUILD_PS1, timeout_s=_BUILD_TIMEOUT_S)
    assert result.returncode == 0, f"build_exe.ps1 failed\n{_describe(result)}"
    assert EXE.is_file(), f"build reported success but {EXE} is missing"

    entries = sorted(path.name for path in DIST.iterdir())
    assert entries == ["stnpe.exe"], (
        f"dist/ must hold exactly the onefile artifact, found {entries}"
    )


# Check number -> substrings that must appear on both the per-check PASS line
# and the matching [PASS] summary line.
_SIX_CHECKS: dict[int, tuple[str, ...]] = {
    1: ("--help", "exit 0"),
    2: ("--version", "version"),
    3: ("generate", "non-empty"),
    4: ("check", "CHECK OK"),
    5: ("config.json", "authority"),
    6: ("bundle_root read-only",),
}


def test_verify_exe_reports_six_of_six() -> None:
    _require_exe()
    result = _run_ps1(VERIFY_PS1, timeout_s=_VERIFY_TIMEOUT_S)
    assert result.returncode == 0, f"verify_exe.ps1 failed\n{_describe(result)}"

    out = result.stdout
    assert "RESULT: 6/6 PASS" in out, f"missing summary line\n{out}"
    assert "FAIL" not in out, f"verify output mentions a failure\n{out}"
    for index, needles in _SIX_CHECKS.items():
        for prefix in (f"PASS: {index}.", f"[PASS] {index}."):
            line = _line_with(out, prefix)
            for needle in needles:
                assert needle in line, (
                    f"check {index} line {line!r} lacks {needle!r}\n{out}"
                )


def _stage_sandbox(tmp_path: Path) -> Path:
    """Copy the exe, the C fixture and its golden tree into a clean sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    shutil.copy2(EXE, sandbox / "stnpe.exe")
    shutil.copytree(FIXTURES / "C", sandbox / "c")
    golden_dir = sandbox / "c" / "golden"
    golden_dir.mkdir()
    shutil.copytree(GOLDEN_C_TREE, golden_dir / "regression_c_STNP_C")
    return sandbox


def _generate(
    sandbox: Path,
    out_name: str,
    *,
    extra_env: dict[str, str] | None = None,
) -> Path:
    """Run ``generate`` on the C fixture; return the ``regression_c_STNP_C`` tree."""
    out_dir = sandbox / out_name
    result = _run_exe(
        sandbox / "stnpe.exe",
        [
            "generate",
            str(sandbox / "c" / "regression_c.stnp"),
            str(sandbox / "c" / "stnp.build.json"),
            "-o",
            str(out_dir),
        ],
        extra_env=extra_env,
    )
    assert result.returncode == 0, f"generate failed\n{_describe(result)}"
    tree = out_dir / "regression_c_STNP_C"
    assert tree.is_dir(), (
        f"expected tree {tree}; output dir holds "
        f"{sorted(p.name for p in out_dir.iterdir()) if out_dir.is_dir() else '<missing>'}"
    )
    return tree


def _write_json_no_bom(path: Path, data: dict) -> None:
    """Write UTF-8 JSON without BOM (PowerShell ``-Encoding UTF8`` adds one)."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    assert path.read_bytes()[:3] != b"\xef\xbb\xbf", "JSON file must not start with a BOM"


def test_config_authority_three_stage(tmp_path: Path) -> None:
    """Built-in < exe-sibling config.json < STNP_EDITOR_CONFIG, proven by dirs."""
    _require_exe()
    sandbox = _stage_sandbox(tmp_path)
    config_path = sandbox / "config.json"
    assert not config_path.exists(), "sandbox must not contain a pre-existing config"

    # Stage 1: built-in default -> Core/
    tree = _generate(sandbox, "out_default")
    assert (tree / "Core").is_dir(), f"built-in default must produce Core/ under {tree}"
    assert not (tree / "FakeCore").exists(), "FakeCore/ must not exist before an override"
    assert config_path.is_file(), "the first exe run must create config.json next to the exe"

    # Stage 2: rewritten exe-sibling config.json -> FakeCore/ (and Core/ gone)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    data["dir_names"]["core"] = "FakeCore"
    _write_json_no_bom(config_path, data)

    tree = _generate(sandbox, "out_fakecore")
    assert (tree / "FakeCore").is_dir(), "exe-sibling config.json must be authoritative"
    assert not (tree / "Core").exists(), "default Core/ must disappear once overridden"

    # Stage 3: STNP_EDITOR_CONFIG -> EnvCore/ (beats the FakeCore exe-sibling file)
    alt = copy.deepcopy(data)
    alt["dir_names"]["core"] = "EnvCore"
    alt_path = sandbox / "alt.json"
    _write_json_no_bom(alt_path, alt)

    tree = _generate(
        sandbox,
        "out_envcore",
        extra_env={"STNP_EDITOR_CONFIG": str(alt_path)},
    )
    assert (tree / "EnvCore").is_dir(), "STNP_EDITOR_CONFIG must be authoritative"
    assert not (tree / "FakeCore").exists(), "exe-sibling FakeCore/ must be bypassed"
