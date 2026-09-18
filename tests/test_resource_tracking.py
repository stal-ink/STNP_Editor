"""Guard tests: every file under ``src/stnp_editor/resources/**`` must be git-trackable.

Regression guard for the F1 defect (0.9.0): the unanchored ``build/`` ignore pattern
matched ``resources/templates/c/Build/`` on case-insensitive filesystems (Windows
``core.ignorecase=true``), so ``Build/CMakeLists.txt.j2`` never entered git. A fresh
clone was left without that template and the ``build_system: "cmake"`` tests failed
with ``E4009`` (missing template). The fix anchors the packaging/environment patterns
to the repository root; these tests keep them anchored:

1. ``git check-ignore`` reports zero matches for the whole resource tree.
2. ``git ls-files -co --exclude-standard`` (tracked plus untracked-not-ignored, i.e.
   exactly what the next commit would contain) equals the on-disk set.
3. On a scratch repo in ``tmp_path`` the anchored rules ignore root-level packaging
   artifacts but never nested resource directories named ``Build/``-like - the
   root-cause semantics, independent of this repository's index state.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "src" / "stnp_editor" / "resources"
RESOURCES_REL = "src/stnp_editor/resources"

# Resolution order (same as the F1 batch): PATH first, then the known install location
# of this machine (git is deliberately not on PATH), then the common Windows defaults.
_GIT_CANDIDATES = (
    Path(r"E:\assistant.software.pack\Git\cmd\git.exe"),
    Path(r"C:\Program Files\Git\cmd\git.exe"),
    Path(r"C:\Program Files (x86)\Git\cmd\git.exe"),
)

_git_cache: str | None = None


def _git_exe() -> str:
    """Resolve a git executable; skip (with reason) only if none can be found."""
    global _git_cache
    if _git_cache is None:
        found = shutil.which("git")
        if not found:
            found = next((str(p) for p in _GIT_CANDIDATES if p.is_file()), None)
        _git_cache = found
    if _git_cache is None:
        pytest.skip(
            "git executable not found: not on PATH and no candidate at "
            + ", ".join(str(p) for p in _GIT_CANDIDATES)
        )
    return _git_cache


def _run_git(*args: str) -> subprocess.CompletedProcess[bytes]:
    proc = subprocess.run([_git_exe(), *args], cwd=ROOT, capture_output=True)
    assert proc.returncode == 0, (
        f"git {' '.join(args)} failed (rc={proc.returncode}):\n"
        f"{proc.stderr.decode(errors='replace')}"
    )
    return proc


def _resource_rels() -> list[str]:
    """Repo-root-relative posix paths of every file on disk under ``resources/**``."""
    return sorted(p.relative_to(ROOT).as_posix() for p in RESOURCES.rglob("*") if p.is_file())


def test_resources_have_no_gitignore_matches() -> None:
    """No file in the resource tree may match any ignore rule (anchored or nested)."""
    rels = _resource_rels()
    assert rels, f"no resource files found under {RESOURCES}"

    proc = subprocess.run(
        [_git_exe(), "check-ignore", "-v", "--stdin"],
        cwd=ROOT,
        input="\n".join(rels).encode("utf-8"),
        capture_output=True,
    )
    # rc 0 = at least one match, rc 1 = no match, anything else = git failure.
    assert proc.returncode in (0, 1), (
        f"git check-ignore failed (rc={proc.returncode}):\n"
        f"{proc.stderr.decode(errors='replace')}"
    )
    hits = [line for line in proc.stdout.decode(errors="replace").splitlines() if line.strip()]
    assert not hits, (
        "git ignores resource file(s), so a fresh clone would not have them:\n  "
        + "\n  ".join(hits)
    )


def test_resource_tree_matches_what_git_would_commit() -> None:
    """The trackable set must equal the on-disk set - the exact F1 defect detector."""
    disk = set(_resource_rels())
    proc = _run_git("ls-files", "-z", "-co", "--exclude-standard", "--", RESOURCES_REL)
    committable = {p for p in proc.stdout.decode("utf-8").split("\0") if p}

    only_disk = sorted(disk - committable)
    only_git = sorted(committable - disk)
    assert not only_disk and not only_git, (
        f"resource tree mismatch: {len(disk)} file(s) on disk, "
        f"{len(committable)} would be committed\n"
        f"on disk but never committable ({len(only_disk)}):\n"
        + "".join(f"  - {p}\n" for p in only_disk)
        + f"committable but missing from disk ({len(only_git)}):\n"
        + "".join(f"  - {p}\n" for p in only_git)
    )


def test_anchored_ignore_rules_leave_nested_build_dir_alone(tmp_path: Path) -> None:
    """Positive control for the fix: root packaging dirs ignored, nested ones not.

    Uses an isolated scratch repo in ``tmp_path`` so the outcome does not depend on
    this repository's index state (``git check-ignore`` reports nothing for files that
    are already tracked). The probe names mirror the patterns that were anchored.
    """
    git = _git_exe()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())

    root_probes: list[str] = []
    nested_probes: list[str] = []
    for name in ("dist", "build", "eggs", ".venv", "venv", "env"):
        root_probe = scratch / name / "probe.txt"
        root_probe.parent.mkdir(parents=True, exist_ok=True)
        root_probe.write_text("x", encoding="utf-8")
        root_probes.append(f"{name}/probe.txt")

        nested_probe = scratch / RESOURCES_REL / name / "probe.txt"
        nested_probe.parent.mkdir(parents=True, exist_ok=True)
        nested_probe.write_text("x", encoding="utf-8")
        nested_probes.append(f"{RESOURCES_REL}/{name}/probe.txt")

    init = subprocess.run([git, "init", "-q"], cwd=scratch, capture_output=True)
    assert init.returncode == 0, init.stderr.decode(errors="replace")

    proc = subprocess.run(
        [git, "-c", "core.excludesfile=", "check-ignore", "-v", "--stdin"],
        cwd=scratch,
        input="\n".join(root_probes + nested_probes).encode("utf-8"),
        capture_output=True,
    )
    assert proc.returncode == 0, (
        f"expected at least one ignore match in scratch repo (rc={proc.returncode}):\n"
        f"{proc.stderr.decode(errors='replace')}"
    )
    matched = {
        line.split("\t", 1)[1].strip()
        for line in proc.stdout.decode(errors="replace").splitlines()
        if "\t" in line
    }

    root_not_ignored = [p for p in root_probes if p not in matched]
    nested_ignored = [p for p in nested_probes if p in matched]
    assert not root_not_ignored and not nested_ignored, (
        "anchored packaging/environment rules are wrong:\n"
        f"root probes not ignored (patterns must be root-anchored): {root_not_ignored}\n"
        f"nested resource probes ignored (would hide templates): {nested_ignored}"
    )
