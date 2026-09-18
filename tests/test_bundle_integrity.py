"""Unit tests for ``scripts/check_bundle_integrity.py``.

Fast and build-free: the pure decision function is exercised with injected fake
PE readers.  The module is loaded by path because ``scripts/`` is not a package
and is not on ``sys.path``.  Loading must have no side effects (no PyInstaller
or pefile import at module level).
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = ROOT / "scripts" / "check_bundle_integrity.py"

_spec = importlib.util.spec_from_file_location("check_bundle_integrity", _SCRIPT)
if _spec is None or _spec.loader is None:  # pragma: no cover - broken checkout
    raise RuntimeError(f"cannot load integrity checker from {_SCRIPT}")
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

find_unresolved_imports = checker.find_unresolved_imports

_SYSTEM = {
    "kernel32.dll",
    "user32.dll",
    "api-ms-win-crt-runtime-l1-1-0.dll",
}


def _reader(imports: dict[str, set[str]]):
    """Fake ``get_imports``: basename -> imports from the given mapping."""

    def get_imports(path):
        return set(imports[Path(path).name])

    return get_imports


def _is_system(name: str) -> bool:
    return name.lower() in _SYSTEM


def test_missing_dependency_is_reported_with_its_owner_pe():
    imports = {
        "_ssl.pyd": {"libcrypto-3-x64.dll", "libssl-3-x64.dll", "KERNEL32.dll"},
        "_hashlib.pyd": {"libcrypto-3-x64.dll", "KERNEL32.dll"},
    }
    unresolved = find_unresolved_imports(
        ["_ssl.pyd", "_hashlib.pyd"],
        {"python312.dll"},
        get_imports=_reader(imports),
        is_system_dll=_is_system,
    )
    assert set(unresolved) == {"libcrypto-3-x64.dll", "libssl-3-x64.dll"}
    assert sorted(unresolved["libcrypto-3-x64.dll"]) == ["_hashlib.pyd", "_ssl.pyd"]
    assert unresolved["libssl-3-x64.dll"] == ["_ssl.pyd"]


def test_dependency_present_in_bundle_is_not_reported():
    imports = {"_ssl.pyd": {"libcrypto-3-x64.dll", "KERNEL32.dll"}}
    unresolved = find_unresolved_imports(
        ["_ssl.pyd"],
        {"_ssl.pyd", "libcrypto-3-x64.dll"},
        get_imports=_reader(imports),
        is_system_dll=_is_system,
    )
    assert unresolved == {}, unresolved


def test_system_dlls_are_never_failures():
    imports = {
        "python312.dll": {
            "KERNEL32.dll",
            "USER32.dll",
            "api-ms-win-crt-runtime-l1-1-0.dll",
        }
    }
    unresolved = find_unresolved_imports(
        ["python312.dll"],
        {"python312.dll"},
        get_imports=_reader(imports),
        is_system_dll=_is_system,
    )
    assert unresolved == {}, unresolved


def test_statically_linked_extension_module_reports_nothing():
    """Regression for the CI false negative.

    Official CPython links liblzma/libexpat statically into ``_lzma.pyd`` /
    ``pyexpat.pyd``; a bundle built with it legitimately contains no liblzma*/
    libexpat* DLL and must still pass the gate.
    """
    imports = {
        "_lzma.pyd": {"KERNEL32.dll", "api-ms-win-crt-runtime-l1-1-0.dll"},
        "pyexpat.pyd": {"KERNEL32.dll", "api-ms-win-crt-runtime-l1-1-0.dll"},
    }
    unresolved = find_unresolved_imports(
        ["_lzma.pyd", "pyexpat.pyd"],
        {"python312.dll"},
        get_imports=_reader(imports),
        is_system_dll=_is_system,
    )
    assert unresolved == {}, unresolved


def test_dynamically_linked_extension_module_still_fails():
    """Companion of the static-link test: a real missing DLL must be caught."""
    imports = {"_lzma.pyd": {"liblzma.dll", "KERNEL32.dll"}}
    unresolved = find_unresolved_imports(
        ["_lzma.pyd"],
        {"python312.dll"},
        get_imports=_reader(imports),
        is_system_dll=_is_system,
    )
    assert unresolved == {"liblzma.dll": ["_lzma.pyd"]}


def test_bundle_matching_is_case_insensitive():
    imports = {"_bz2.pyd": {"libbz2.dll", "KERNEL32.dll"}}
    unresolved = find_unresolved_imports(
        ["_bz2.pyd"],
        {"LIBBZ2.DLL"},
        get_imports=_reader(imports),
        is_system_dll=_is_system,
    )
    assert unresolved == {}, unresolved


def test_unresolved_names_are_lowercased_and_owners_deduplicated():
    imports = {"_ssl.pyd": {"LIBCRYPTO-3-X64.DLL", "libcrypto-3-x64.dll"}}
    unresolved = find_unresolved_imports(
        ["_ssl.pyd"],
        set(),
        get_imports=_reader(imports),
        is_system_dll=_is_system,
    )
    assert unresolved == {"libcrypto-3-x64.dll": ["_ssl.pyd"]}


def test_unparsable_candidate_is_skipped():
    def boom(path):
        raise ValueError("not a PE")

    unresolved = find_unresolved_imports(
        ["not-a-pe.dll"],
        set(),
        get_imports=boom,
        is_system_dll=lambda name: False,
    )
    assert unresolved == {}


def test_real_classifier_handles_api_sets_whitelist_and_unknowns():
    assert checker._real_is_system_dll("api-ms-win-crt-runtime-l1-1-0.dll") is True
    assert checker._real_is_system_dll("EXT-MS-WIN-ntuser-window-l1-1-0.dll") is True
    assert checker._real_is_system_dll("kernel32.dll") is True
    assert checker._real_is_system_dll("libstnp-not-a-real-system-dll-9.dll") is False


def test_module_has_no_third_party_imports_at_top_level():
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    top_level: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level.add(node.module.split(".")[0])
    assert "pefile" not in top_level
    assert "PyInstaller" not in top_level
