"""Shared developer-toolchain resolution: one resolution order, two thin implementations.

``scripts/toolchain.ps1`` is the PowerShell twin of this module.  Both implement the
order below and ``tests/test_toolchain.py`` compares their contracts (order,
environment-variable names, failure wording) so the two cannot drift.

Resolution order (rev.2 -- three levels):

1. environment variable  ``STNP_PYTHON`` / ``STNP_MINGW_BIN`` / ``STNP_CMAKE_BIN`` / ``STNP_GIT``
                         optional override; SET but unusable -> loud error, no fallback
2. ``PATH`` lookup       the first match is ADOPTED; ALL candidates are listed
3. loud failure      one line of install guidance, non-zero exit

The resolver only *detects and reports*: it runs a minimal usability check per tool --
a candidate that cannot run its job is not adopted and its one-line reason is listed --
but it never decides for the user whether the adopted toolchain suits the target
platform.  Correctness of the chosen toolchain is the user's to verify (D12).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# allow: SIZE_OK -- the three-level order, the per-tool usability checks and the
# reporting helpers live in ONE module on purpose: scripts/toolchain.ps1 is the
# PowerShell twin compared against it verbatim, and splitting the checks from the
# reporting would let the two implementations drift exactly where this design forbids it.

ORDER = ("env", "path", "fail")
ENV_VARS = {
    "python": "STNP_PYTHON",
    "gcc": "STNP_MINGW_BIN",
    "cmake": "STNP_CMAKE_BIN",
    "git": "STNP_GIT",
}
BINARIES = {"python": "python", "gcc": "gcc", "cmake": "cmake", "git": "git"}
MIN_CMAKE = (3, 20)
DISCLAIMER = "工具链由本机环境决定，软件不保证其正确或匹配；请自行确认。"

FAILURE_TEMPLATES = {
    "python": 'STNP toolchain: python 未找到。请安装满足 requires-python 的 Python（并执行 python -m pip install -e ".[dev]"），或用 STNP_PYTHON 指定解释器。',
    "gcc": "STNP toolchain: gcc 未找到。请安装 MinGW-w64（x86_64 主机目标）并把其 bin 目录加入 PATH，或用 STNP_MINGW_BIN 指定该目录。",
    "cmake": "STNP toolchain: cmake 未找到。请安装 CMake >= {0} 并把其 bin 目录加入 PATH，或用 STNP_CMAKE_BIN 指定该目录。",
    "git": "STNP toolchain: git 未找到。请安装 Git 并把 cmd 目录加入 PATH，或用 STNP_GIT 指定 git 可执行文件。",
}
IDENTITY_TEMPLATES = {
    "gcc_run": "STNP toolchain: gcc 身份校验失败：{0} 无法运行 gcc -dumpmachine（{1}）。",
    "cmake_run": "STNP toolchain: cmake 身份校验失败：{0} 无法运行 cmake --version（{1}）。",
    "cmake_version": "STNP toolchain: cmake 身份校验失败：{0} 版本 {1} 低于要求的 {2}。",
    "python_run": "STNP toolchain: python 身份校验失败：{0} 无法运行（{1}）。",
    "python_version": "STNP toolchain: python 身份校验失败：{0} 版本 {1} 不满足 requires-python（{2}）。",
    "python_import": "STNP toolchain: python 身份校验失败：{0} 无法 import stnp_editor（{1}）。仅用于 PyInstaller 打包的解释器可用 -RequireImport:$false 跳过本项。",
    "git_run": "STNP toolchain: git 身份校验失败：{0} 无法运行 git --version（{1}）。",
}
DECLARED_INVALID_TEMPLATE = (
    "STNP toolchain: {0} 指定的 {1} 不可用：{2}。"
    "已声明的位置不会静默回退到 PATH；请修正该设置。"
)


class ToolchainError(RuntimeError):
    """Canonical one-line toolchain failure; wording is pinned by the contract test."""


@dataclass(frozen=True, slots=True)
class ToolCandidate:
    path: Path
    source: str
    adopted: bool = False
    rejected_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedTool:
    name: str
    path: Path
    source: str
    detail: str
    candidates: tuple[ToolCandidate, ...]

    @property
    def directory(self) -> Path:
        return self.path.parent

    def describe(self) -> str:
        """D11 line: ``gcc : <path> (from <source>, <version/triple>)``."""
        return f"{self.name} : {self.path} (from {self.source}, {self.detail})"

    def other_candidates(self) -> tuple[str, ...]:
        """D9 lines for every non-adopted candidate, rejection reason included."""
        lines = []
        for candidate in self.candidates:
            if candidate.adopted:
                continue
            suffix = f"，拒绝：{candidate.rejected_reason}" if candidate.rejected_reason else ""
            lines.append(f"{candidate.path} (from {candidate.source}{suffix})")
        return tuple(lines)


def _first_line(text: str, limit: int = 160) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    return stripped.splitlines()[0][:limit]


def _run(command: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _version_tuple(text: str) -> tuple[int, ...]:
    parts = []
    for chunk in text.split("."):
        match = re.match(r"\d+", chunk)
        parts.append(int(match.group(0)) if match else 0)
    return tuple(parts)


def _compare(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    size = max(len(left), len(right))
    left = left + (0,) * (size - len(left))
    right = right + (0,) * (size - len(right))
    return (left > right) - (left < right)


def _version_satisfies(version: str, specifier: str) -> bool:
    current = _version_tuple(version)
    for clause in specifier.split(","):
        match = re.fullmatch(r"(>=|<=|==|!=|>|<|~=)\s*(\d+(?:\.\d+)*)", clause.strip())
        if match is None:
            continue
        op, bound = match.group(1), _version_tuple(match.group(2))
        order = _compare(current, bound)
        if op == ">=" and order < 0:
            return False
        if op == "<=" and order > 0:
            return False
        if op == "==" and order != 0:
            return False
        if op == "!=" and order == 0:
            return False
        if op == ">" and order <= 0:
            return False
        if op == "<" and order >= 0:
            return False
        if op == "~=" and (order < 0 or current[0] != bound[0]):
            return False
    return True


def python_requires() -> str:
    """`requires-python` from pyproject.toml - single source of truth for both twins."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*"([^"]+)"', text)
    if match is None:
        raise ToolchainError("STNP toolchain: pyproject.toml 缺少 requires-python，无法校验 Python 版本。")
    return match.group(1)


def contract() -> dict[str, object]:
    """Machine-readable twin of ``scripts/toolchain.ps1 -Contract -AsJson``."""
    return {
        "order": list(ORDER),
        "env_vars": dict(ENV_VARS),
        "failure_templates": dict(FAILURE_TEMPLATES),
        "identity_templates": dict(IDENTITY_TEMPLATES),
        "declared_invalid_template": DECLARED_INVALID_TEMPLATE,
        "disclaimer": DISCLAIMER,
        "min_cmake": ".".join(str(part) for part in MIN_CMAKE),
        "python_requires": python_requires(),
    }


def _gcc_detail(exe: Path) -> str:
    proc = _run([str(exe), "-dumpmachine"])
    triple = proc.stdout.strip()
    if proc.returncode != 0 or not triple:
        raise ToolchainError(
            IDENTITY_TEMPLATES["gcc_run"].format(exe, _first_line(proc.stderr) or f"exit {proc.returncode}")
        )
    return triple


def _cmake_detail(exe: Path) -> str:
    proc = _run([str(exe), "--version"])
    match = re.search(r"cmake version (\d+\.\d+(?:\.\d+)?)", proc.stdout)
    if proc.returncode != 0 or match is None:
        raise ToolchainError(
            IDENTITY_TEMPLATES["cmake_run"].format(exe, _first_line(proc.stderr) or f"exit {proc.returncode}")
        )
    version = match.group(1)
    if not _version_satisfies(version, f">={'.'.join(str(part) for part in MIN_CMAKE)}"):
        raise ToolchainError(
            IDENTITY_TEMPLATES["cmake_version"].format(exe, version, ".".join(str(part) for part in MIN_CMAKE))
        )
    return version


def _python_detail(exe: Path, require_import: bool) -> str:
    proc = _run([str(exe), "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"])
    version = proc.stdout.strip()
    if proc.returncode != 0 or re.fullmatch(r"\d+\.\d+\.\d+", version) is None:
        raise ToolchainError(
            IDENTITY_TEMPLATES["python_run"].format(exe, _first_line(proc.stderr) or f"exit {proc.returncode}")
        )
    required = python_requires()
    if not _version_satisfies(version, required):
        raise ToolchainError(IDENTITY_TEMPLATES["python_version"].format(exe, version, required))
    if require_import:
        candidate = _run([str(exe), "-c", "import stnp_editor"])
        if candidate.returncode != 0:
            raise ToolchainError(
                IDENTITY_TEMPLATES["python_import"].format(
                    exe, _first_line(candidate.stderr) or f"exit {candidate.returncode}"
                )
            )
    return version


def _git_detail(exe: Path) -> str:
    proc = _run([str(exe), "--version"])
    text = proc.stdout.strip()
    if proc.returncode != 0 or not text.startswith("git version "):
        raise ToolchainError(
            IDENTITY_TEMPLATES["git_run"].format(exe, _first_line(proc.stderr) or f"exit {proc.returncode}")
        )
    return text.removeprefix("git version ")


def _validate(name: str, exe: Path, require_import: bool) -> str:
    if name == "gcc":
        return _gcc_detail(exe)
    if name == "cmake":
        return _cmake_detail(exe)
    if name == "python":
        return _python_detail(exe, require_import)
    if name == "git":
        return _git_detail(exe)
    raise ToolchainError(f"STNP toolchain: 未知工具 {name}。")


def _path_candidates(name: str) -> list[ToolCandidate]:
    entries = [entry for entry in os.environ.get("PATH", "").split(os.pathsep) if entry]
    total = len(entries)
    candidates: list[ToolCandidate] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        found = shutil.which(name, path=entry)
        if found is None:
            continue
        key = os.path.normcase(os.path.abspath(found))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(ToolCandidate(Path(found), f"PATH #{index} of {total}"))
    return candidates


def resolve(name: str, *, require_import: bool = True) -> ResolvedTool:
    """Resolve one tool through the three fixed levels, or raise ToolchainError."""
    declared_value = os.environ.get(ENV_VARS[name], "").strip()
    if declared_value:
        declared = Path(declared_value).expanduser()
        if declared.is_dir():
            found = shutil.which(BINARIES[name], path=str(declared))
            declared = Path(found) if found else declared / BINARIES[name]
        if not declared.is_file():
            raise ToolchainError(DECLARED_INVALID_TEMPLATE.format(ENV_VARS[name], name, declared_value))
        detail = _validate(name, declared, require_import)
        candidate = ToolCandidate(declared, ENV_VARS[name], adopted=True)
        return ResolvedTool(name, declared, ENV_VARS[name], detail, (candidate,))

    candidates = _path_candidates(BINARIES[name])
    adopted_index = -1
    detail = ""
    rejected: dict[int, str] = {}
    for index, candidate in enumerate(candidates):
        try:
            detail = _validate(name, candidate.path, require_import)
        except ToolchainError as exc:
            # Detect and report: an unusable candidate is skipped, never a global stop.
            rejected[index] = _first_line(str(exc))
            continue
        adopted_index = index
        break
    if adopted_index < 0:
        raise ToolchainError(FAILURE_TEMPLATES[name].format(".".join(str(part) for part in MIN_CMAKE)))

    listing = tuple(
        ToolCandidate(candidate.path, candidate.source, index == adopted_index, rejected.get(index))
        for index, candidate in enumerate(candidates)
    )
    adopted = candidates[adopted_index]
    return ResolvedTool(name, adopted.path, adopted.source, detail, listing)


def resolve_python(*, require_import: bool = True) -> ResolvedTool:
    return resolve("python", require_import=require_import)


def resolve_gcc() -> ResolvedTool:
    return resolve("gcc")


def resolve_cmake() -> ResolvedTool:
    return resolve("cmake")


def resolve_git() -> ResolvedTool:
    return resolve("git")


def _prepend_path(directory: Path, environ) -> bool:
    normalized = os.path.normcase(os.path.abspath(str(directory)))
    for entry in environ.get("PATH", "").split(os.pathsep):
        if entry and os.path.normcase(os.path.abspath(entry)) == normalized:
            return False
    environ["PATH"] = str(directory) + os.pathsep + environ.get("PATH", "")
    return True


def bootstrap() -> tuple[tuple[ResolvedTool, ...], tuple[str, ...]]:
    """Session bootstrap for conftest.py (D5): resolve gcc/cmake, prepend, set generator.

    Missing tools are NEVER faked: the failure text is returned so the caller can
    print it loudly while the toolchain-gated tests still skip -- and those skips are
    UNEXPECTED for ``scripts/test.ps1 -FailOnSkip`` (D7).
    """
    resolved: list[ResolvedTool] = []
    failures: list[str] = []
    for name in ("gcc", "cmake"):
        try:
            tool = resolve(name)
        except ToolchainError as exc:
            failures.append(str(exc))
            continue
        _prepend_path(tool.directory, os.environ)
        resolved.append(tool)
    if os.name == "nt":
        os.environ["CMAKE_GENERATOR"] = "MinGW Makefiles"
    return tuple(resolved), tuple(failures)
