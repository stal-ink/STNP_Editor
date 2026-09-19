"""Toolchain resolver: contract pinning and self-checks (S5).

Five properties, one file:

1. the PowerShell twin (scripts/toolchain.ps1) and tests/_toolchain.py expose the
   same three-level order (environment variable -> PATH -> loud failure), the same
   environment-variable names and the same failure wording -- they cannot drift;
2. a declared-but-unusable toolchain is a loud failure of scripts/test.ps1, never a
   silent fallback to PATH;
3. a foreign/cross gcc on PATH (e.g. arm-none-eabi) is ADOPTED and its triple is
   reported -- the resolver detects and reports, it does not judge suitability;
4. multiple candidates are all listed and the first one is adopted;
5. the D12 disclaimer is wired into every entry point and the getting-started doc.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import _toolchain

ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN_PS1 = ROOT / "scripts" / "toolchain.ps1"
TEST_PS1 = ROOT / "scripts" / "test.ps1"

ORDER_PIN = ["env", "path", "fail"]
ENV_PIN = {
    "python": "STNP_PYTHON",
    "gcc": "STNP_MINGW_BIN",
    "cmake": "STNP_CMAKE_BIN",
    "git": "STNP_GIT",
}
DISCLAIMER_PIN = "工具链由本机环境决定，软件不保证其正确或匹配；请自行确认。"
SCRIPT_SITES = (
    ROOT / "scripts" / "toolchain.ps1",
    ROOT / "scripts" / "test.ps1",
    ROOT / "scripts" / "build_exe.ps1",
    *(ROOT / "examples" / name / "run.ps1" for name in ("handshake_c", "dual_multi_c_py", "stm32_hal_uart_c")),
)


def _powershell() -> str:
    found = shutil.which("powershell")
    if found is None:
        pytest.skip("powershell not available: cannot check the PowerShell twin")
    return found


def _run_ps(args: list[str], *, env: dict[str, str] | None = None, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    if env:
        environment.update(env)
    return subprocess.run(
        [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(TOOLCHAIN_PS1), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=environment,
    )


def _write_gcc_shim(directory: Path, triple: str) -> Path:
    """A `gcc` that reports `triple` for `-dumpmachine` (any triple)."""
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        shim = directory / "gcc.bat"
        shim.write_text("@echo " + triple + "\r\n", encoding="ascii")
    else:
        shim = directory / "gcc"
        shim.write_text("#!/bin/sh\necho " + triple + "\n", encoding="utf-8")
        shim.chmod(0o755)
    return shim


def _front_path(*directories: Path) -> str:
    return os.pathsep.join(str(directory) for directory in directories) + os.pathsep + os.environ["PATH"]


def _isolate_toolchain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove ambient STNP_* declarations so a test exercises the level it targets.

    An environment override outranks PATH by design, so a developer who declares
    STNP_MINGW_BIN / STNP_CMAKE_BIN (the intended usage) would otherwise make every
    PATH-level test resolve the declared tool instead of the fixture.  That is test
    state leaking in, not resolver behaviour; the override behaviour has its own
    tests, which set the variable on purpose.
    """
    for name in _toolchain.ENV_VARS.values():
        monkeypatch.delenv(name, raising=False)


def _norm(path: object) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def test_python_contract_pins_the_decided_order_and_names() -> None:
    assert list(_toolchain.ORDER) == ORDER_PIN
    assert dict(_toolchain.ENV_VARS) == ENV_PIN
    assert _toolchain.DISCLAIMER == DISCLAIMER_PIN
    hints = {
        "python": ("STNP_PYTHON", "requires-python"),
        "gcc": ("STNP_MINGW_BIN", "MinGW-w64"),
        "cmake": ("STNP_CMAKE_BIN", "CMake"),
        "git": ("STNP_GIT", "Git"),
    }
    for tool, needles in hints.items():
        for needle in needles:
            assert needle in _toolchain.FAILURE_TEMPLATES[tool]


def test_powershell_contract_matches_python() -> None:
    result = _run_ps(["-Contract", "-AsJson"])
    assert result.returncode == 0, result.stderr
    ps_contract = json.loads(result.stdout)
    py_contract = _toolchain.contract()
    assert sorted(ps_contract) == sorted(py_contract)
    for key, value in py_contract.items():
        assert ps_contract[key] == value, key


def test_declared_environment_value_never_falls_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_toolchain(monkeypatch)
    missing = str(tmp_path / "missing-mingw")
    monkeypatch.setenv("STNP_MINGW_BIN", missing)
    expected = _toolchain.DECLARED_INVALID_TEMPLATE.format("STNP_MINGW_BIN", "gcc", missing)

    with pytest.raises(_toolchain.ToolchainError) as excinfo:
        _toolchain.resolve_gcc()
    assert str(excinfo.value) == expected

    # The PowerShell twin fails the same way even though a working gcc may sit on PATH.
    result = _run_ps(["-Tool", "gcc"], env={"STNP_MINGW_BIN": missing})
    assert result.returncode == 2
    assert expected in (result.stdout + result.stderr)


def test_clean_environment_script_fails_loudly(tmp_path: Path) -> None:
    environment = dict(os.environ)
    for name in ("STNP_PYTHON", "STNP_MINGW_BIN", "STNP_CMAKE_BIN", "STNP_GIT"):
        environment.pop(name, None)
    environment["STNP_MINGW_BIN"] = str(tmp_path / "missing-mingw")
    environment["STNP_CMAKE_BIN"] = str(tmp_path / "missing-cmake")
    # The interpreter that runs the suite must stay discoverable through PATH so the
    # script reaches the gcc/cmake resolution this test is about.
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")

    result = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(TEST_PS1),
            "-FailOnSkip",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        env=environment,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 2, combined
    for name in ("STNP_MINGW_BIN", "STNP_CMAKE_BIN"):
        assert name in combined, name
    assert "不可用" in combined
    assert DISCLAIMER_PIN in combined


def test_cross_toolchain_on_path_is_adopted_and_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A foreign/cross gcc is adopted and its triple shown -- detect and report."""
    _isolate_toolchain(monkeypatch)
    shim_dir = tmp_path / "cross-bin"
    _write_gcc_shim(shim_dir, "arm-none-eabi")
    monkeypatch.setenv("PATH", _front_path(shim_dir))

    resolved = _toolchain.resolve_gcc()
    assert resolved.detail == "arm-none-eabi"
    assert "arm-none-eabi" in resolved.describe()

    # Same PATH for the PowerShell twin: adopted, triple in Detail, exit 0.
    result = _run_ps(["-Tool", "gcc", "-AsJson"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["Detail"] == "arm-none-eabi"


def test_environment_variable_beats_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The env override (level 1) must outrank PATH (level 2)."""
    _isolate_toolchain(monkeypatch)
    path_dir = tmp_path / "path-bin"
    env_dir = tmp_path / "env-bin"
    _write_gcc_shim(path_dir, "x86_64-w64-mingw32")
    env_gcc = _write_gcc_shim(env_dir, "x86_64-w64-mingw32")
    monkeypatch.setenv("PATH", _front_path(path_dir))
    monkeypatch.setenv("STNP_MINGW_BIN", str(env_dir))

    resolved = _toolchain.resolve_gcc()
    assert _norm(resolved.path) == _norm(env_gcc)
    assert resolved.source == "STNP_MINGW_BIN"

    result = _run_ps(["-Tool", "gcc", "-AsJson"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert _norm(payload["Path"]) == _norm(env_gcc)
    assert payload["Source"] == "STNP_MINGW_BIN"


def test_multiple_candidates_are_listed_and_first_adopted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_toolchain(monkeypatch)
    first_dir = tmp_path / "first-bin"
    second_dir = tmp_path / "second-bin"
    first = _write_gcc_shim(first_dir, "x86_64-w64-mingw32")
    second = _write_gcc_shim(second_dir, "x86_64-w64-mingw32")
    monkeypatch.setenv("PATH", _front_path(first_dir, second_dir))

    resolved = _toolchain.resolve_gcc()
    assert _norm(resolved.path) == _norm(first)
    assert _norm(resolved.directory) == _norm(first.parent)
    assert re.fullmatch(r"gcc : .+ \(from .+, x86_64-w64-mingw32\)", resolved.describe())
    others = " | ".join(resolved.other_candidates())
    assert str(second) in others or _norm(second) in _norm(others)

    json_result = _run_ps(["-Tool", "gcc", "-AsJson"])
    assert json_result.returncode == 0, json_result.stderr
    payload = json.loads(json_result.stdout)
    assert _norm(payload["Path"]) == _norm(first)
    assert _norm(payload["Directory"]) == _norm(first.parent)
    adopted = [item for item in payload["Candidates"] if item["Adopted"]]
    assert [_norm(item["Path"]) for item in adopted] == [_norm(first)]
    assert _norm(second) in [_norm(item["Path"]) for item in payload["Candidates"]]

    human = _run_ps(["-Tool", "gcc"])
    assert human.returncode == 0
    assert "其它候选：" in human.stdout
    assert _norm(first) in _norm(human.stdout) and _norm(second) in _norm(human.stdout)


def test_bootstrap_never_fabricates_a_toolchain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_toolchain(monkeypatch)
    monkeypatch.setenv("STNP_MINGW_BIN", str(tmp_path / "missing-mingw"))
    monkeypatch.setenv("STNP_CMAKE_BIN", str(tmp_path / "missing-cmake"))
    before = os.environ["PATH"]

    resolved, failures = _toolchain.bootstrap()

    assert resolved == ()
    assert len(failures) == 2
    assert os.environ["PATH"] == before
    if os.name == "nt":
        assert os.environ["CMAKE_GENERATOR"] == "MinGW Makefiles"


def _design_skip_markers() -> list[str]:
    text = TEST_PS1.read_text(encoding="utf-8-sig")
    match = re.search(r"\$ExpectedSkipReasonMarkers\s*=\s*@\(([^)]*)\)", text)
    assert match is not None, "scripts/test.ps1 no longer declares $ExpectedSkipReasonMarkers"
    return re.findall(r'"([^"]+)"', match.group(1))


def test_toolchain_skips_are_unexpected_for_failonskip() -> None:
    markers = _design_skip_markers()
    assert markers == ["STNP_TEST_EXE", "stnpe"]
    reasons = (
        "gcc not available",
        "cmake not available",
        _toolchain.FAILURE_TEMPLATES["gcc"],
        _toolchain.FAILURE_TEMPLATES["cmake"],
    )
    for reason in reasons:
        assert not any(marker.lower() in reason.lower() for marker in markers), reason


def test_disclaimer_is_wired_into_every_entry_point_and_doc() -> None:
    for path in SCRIPT_SITES:
        text = path.read_text(encoding="utf-8-sig")
        assert "Write-StnpToolchainDisclaimer" in text or DISCLAIMER_PIN in text, path
    docs = (ROOT / "docs" / "01_getting_started.md").read_text(encoding="utf-8")
    assert DISCLAIMER_PIN in docs
