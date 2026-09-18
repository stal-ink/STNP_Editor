"""Toolchain-agnostic completeness gate for the single-file ``stnpe.exe``.

Why this exists
---------------
PyInstaller happily produces an executable even when it cannot resolve a
dependency of a bundled extension module: it logs ``WARNING: Library not
found`` and keeps going.  A bundle that ships ``_ssl.pyd``/``_hashlib.pyd``
without ``libcrypto*``/``libssl*`` starts fine and only fails the first time
TLS is used.

The first version of this gate hardcoded the dependency-name prefixes of one
particular Python distribution (conda's ``Library\\bin``: liblzma, libexpat,
libbz2, ffi).  Official CPython statically links ``_lzma``/``_bz2``/
``pyexpat``, so those DLL names can never appear in a bundle built with it --
the gate failed forever on toolchains like the GitHub runners even though the
produced exe was fine.  This module replaces name matching with the only
source of truth that is identical on every toolchain: the PE import tables of
the binaries that actually made it into the bundle.

Decision rule
-------------
* ``bundle_names`` -- basenames (lowercased) of every entry of the exe archive.
* For every PE binary in the bundle (PE-suffixed archive entries -- PyInstaller
  stores data files as the same ``b`` blob type -- extracted to a scratch
  directory) -- plus any ``*.pyd``/``*.dll``/``*.exe`` found under the
  PyInstaller workpath -- each imported DLL must either
    1. match an entry in ``bundle_names`` (case-insensitively), or
    2. be classified as a Windows system DLL by ``is_system_dll``.
  Otherwise the import is a missing dependency and the gate fails.

On PyInstaller 6.15 a onefile build does NOT physically copy the collected
binaries into the workpath (only ``.toc``/``.pkg`` files live there), so the
archive itself is the primary input; the workpath scan covers other/future
build layouts and feeds the informational ``dropped`` count only.

The pure decision function receives its side-effectful dependencies as keyword
arguments, so it is unit-testable without PyInstaller or pefile; those two are
imported lazily by ``main()``.

CLI::

    python scripts/check_bundle_integrity.py --exe dist/stnpe.exe --build-dir build/pyinstaller

Exit code 0 = every non-system import of every bundled PE resolves inside the
bundle.  Exit code 1 = missing dependencies, or the checker itself cannot run
(missing PyInstaller/pefile, empty analysis set).  The latter never passes
silently.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

_PE_SUFFIXES = frozenset({".pyd", ".dll", ".exe"})

# API-set virtual DLLs: resolved by the loader, typically not present as files.
_API_SET_PREFIXES = ("api-ms-win-", "ext-ms-win-")

# Belt-and-braces core Windows DLLs.  The System32 existence probe below is the
# primary classifier and already covers all of these on a real Windows box;
# the whitelist keeps the classifier correct if the probe is unavailable.
_SYSTEM_DLL_WHITELIST = frozenset({
    "advapi32.dll",
    "bcrypt.dll",
    "bcryptprimitives.dll",
    "cfgmgr32.dll",
    "combase.dll",
    "comctl32.dll",
    "comdlg32.dll",
    "crypt32.dll",
    "cryptbase.dll",
    "dbghelp.dll",
    "dnsapi.dll",
    "dwmapi.dll",
    "gdi32.dll",
    "imm32.dll",
    "iphlpapi.dll",
    "kernel32.dll",
    "kernelbase.dll",
    "msimg32.dll",
    "mpr.dll",
    "msvcrt.dll",
    "mswsock.dll",
    "ncrypt.dll",
    "netapi32.dll",
    "normaliz.dll",
    "nsi.dll",
    "ntdll.dll",
    "odbc32.dll",
    "odbccp32.dll",
    "ole32.dll",
    "oleaut32.dll",
    "powrprof.dll",
    "propsys.dll",
    "psapi.dll",
    "rpcrt4.dll",
    "rsaenh.dll",
    "sechost.dll",
    "secur32.dll",
    "setupapi.dll",
    "shcore.dll",
    "shell32.dll",
    "shlwapi.dll",
    "sspicli.dll",
    "ucrtbase.dll",
    "urlmon.dll",
    "user32.dll",
    "userenv.dll",
    "uxtheme.dll",
    "version.dll",
    "windowscodecs.dll",
    "winhttp.dll",
    "wininet.dll",
    "winmm.dll",
    "winspool.drv",
    "wintrust.dll",
    "wtsapi32.dll",
    "ws2_32.dll",
    "wsock32.dll",
})


def find_unresolved_imports(pe_paths, bundle_names, *, get_imports, is_system_dll):
    """Return ``{imported_dll_name: [PE file names that import it]}``.

    Only imports that resolve neither inside the bundle nor to a Windows
    system DLL are reported.  Names are compared case-insensitively (Windows
    DLL names are), and the returned keys are lowercased.  A path whose
    ``get_imports`` raises is skipped -- callers that want to notice those
    should pre-parse and count them separately.

    ``bundle_names`` -- basenames of every bundle entry (any case).
    ``get_imports``  -- ``path -> set[str]`` of imported DLL names.
    ``is_system_dll`` -- ``name -> bool`` system-DLL classifier.
    """
    bundle = {str(name).lower() for name in bundle_names}
    unresolved: "dict[str, list[str]]" = {}
    for path in pe_paths:
        pe_path = Path(path)
        try:
            imports = get_imports(pe_path)
        except Exception:  # non-PE candidate: not this function's verdict
            continue
        for dep in imports:
            dep_key = str(dep).lower()
            if dep_key in bundle or is_system_dll(str(dep)):
                continue
            owners = unresolved.setdefault(dep_key, [])
            if pe_path.name not in owners:
                owners.append(pe_path.name)
    return unresolved


def _real_get_imports(path: Path) -> "set[str]":
    """Real PE import reader; lazily imports pefile."""
    import pefile  # lazy: keeps the pure function importable without pefile

    pe = pefile.PE(str(path), fast_load=True)
    try:
        pe.parse_data_directories(
            directories=[
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
            ],
            import_dllnames_only=True,
        )
        names: "set[str]" = set()
        for attr in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
            for entry in getattr(pe, attr, None) or ():
                if entry.dll:
                    names.add(entry.dll.decode("utf-8", "replace"))
        return names
    finally:
        pe.close()


def _real_is_system_dll(name: str) -> bool:
    """True for API-set shims, whitelisted core DLLs, or any System32 file."""
    lowered = str(name).lower()
    if lowered.startswith(_API_SET_PREFIXES):
        return True
    if lowered in _SYSTEM_DLL_WHITELIST:
        return True
    system_root = (
        os.environ.get("SystemRoot")
        or os.environ.get("windir")
        or r"C:\Windows"
    )
    try:
        return (Path(system_root) / "System32" / lowered).is_file()
    except OSError:
        return False


def _extract_archive_binaries(reader, scratch: Path) -> "list[Path]":
    """Materialize PE-suffixed ``b``-type archive entries.

    In PyInstaller 6.15 CArchive, ``b`` marks a raw blob: collected data files
    (templates, schemas, dist-info) use it too, so the file suffix is what
    identifies candidate PE binaries here.  One subdirectory per entry keeps
    basenames intact even if two entries share a name.
    """
    paths: "list[Path]" = []
    for index, name in enumerate(sorted(reader.toc)):
        if reader.toc[name][4] != "b":
            continue
        if Path(name).suffix.lower() not in _PE_SUFFIXES:
            continue
        entry_dir = scratch / "{0:04d}".format(index)
        entry_dir.mkdir(parents=True, exist_ok=True)
        target = entry_dir / Path(name).name
        target.write_bytes(reader.extract(name))
        paths.append(target)
    return paths


def _find_physical_pes(build_dir: Path) -> "list[Path]":
    """PE-suffixed files under the PyInstaller workpath (may be empty)."""
    if not build_dir.is_dir():
        return []
    return [
        path
        for path in sorted(build_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in _PE_SUFFIXES
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Import-table completeness gate for a PyInstaller bundle."
    )
    parser.add_argument("--exe", required=True, help="produced single-file exe")
    parser.add_argument(
        "--build-dir",
        required=True,
        dest="build_dir",
        help="PyInstaller workpath (scanned for extra PE files)",
    )
    args = parser.parse_args(argv)

    exe = Path(args.exe)
    build_dir = Path(args.build_dir)
    if not exe.is_file():
        print("ERROR: exe not found: {0}".format(exe))
        print("INTEGRITY FAILED: checker cannot open the artifact")
        return 1

    try:
        from PyInstaller.archive.readers import CArchiveReader
    except Exception as exc:
        print("ERROR: PyInstaller is required to inspect the bundle ({0}: {1})".format(
            type(exc).__name__, exc))
        print("INTEGRITY FAILED: checker unavailable (PyInstaller import failed)")
        return 1

    try:
        import pefile  # noqa: F401  capability probe; _real_get_imports uses it
    except Exception as exc:
        print("ERROR: pefile is required to walk PE import tables ({0}: {1})".format(
            type(exc).__name__, exc))
        print("INTEGRITY FAILED: checker unavailable (pefile import failed)")
        return 1

    reader = CArchiveReader(str(exe))
    names = sorted(reader.toc)
    bundle_names = {Path(name).name.lower() for name in names}

    with tempfile.TemporaryDirectory(prefix="stnp-integrity-") as tmp:
        archive_pes = _extract_archive_binaries(reader, Path(tmp))
        physical_pes = _find_physical_pes(build_dir)
        seen = {path.name.lower() for path in archive_pes}
        pe_paths = list(archive_pes)
        for path in physical_pes:
            key = path.name.lower()
            if key not in seen:
                seen.add(key)
                pe_paths.append(path)
        dropped = [
            path for path in physical_pes
            if path.name.lower() not in bundle_names
        ]

        memo: "dict[str, object]" = {}

        def cached_get_imports(path):
            pe_path = Path(path)
            key = str(pe_path)
            if key not in memo:
                try:
                    memo[key] = _real_get_imports(pe_path)
                except Exception:
                    memo[key] = None
            result = memo[key]
            if result is None:
                raise ValueError("not a parseable PE: {0}".format(pe_path))
            return result

        analyzed: "list[Path]" = []
        unparsable: "list[str]" = []
        for path in pe_paths:
            try:
                cached_get_imports(path)
            except Exception:
                unparsable.append(path.name)
            else:
                analyzed.append(path)

        imported_names = set()
        system_names = set()
        for path in analyzed:
            for dep in cached_get_imports(path):
                key = dep.lower()
                imported_names.add(key)
                if _real_is_system_dll(dep):
                    system_names.add(key)

        unresolved = find_unresolved_imports(
            analyzed,
            bundle_names,
            get_imports=cached_get_imports,
            is_system_dll=_real_is_system_dll,
        )

    crypto_entries = sorted(
        Path(name).name for name in names
        if Path(name).name.lower().startswith(("libcrypto", "libssl"))
    )
    print("info       : libcrypto/libssl entries: {0}".format(
        ", ".join(crypto_entries) or "(none)"))
    print("info       : dropped PEs (build-dir binaries absent from the archive): {0}".format(
        len(dropped)))
    if unparsable:
        print("warn       : unparsable PE candidates: {0}".format(
            ", ".join(sorted(set(unparsable)))))

    if not analyzed:
        print("INTEGRITY FAILED: no PE binaries could be analyzed (empty set cannot pass)")
        return 1

    if unresolved:
        for dll in sorted(unresolved):
            owners = ", ".join(sorted(unresolved[dll]))
            print("MISSING  {0}  <- {1}".format(dll, owners))
        print("INTEGRITY FAILED: unresolved non-system imports: {0}".format(
            ", ".join(sorted(unresolved))))
        return 1

    print("INTEGRITY OK: binaries={0} checked_imports={1} unresolved=0 system={2}".format(
        len(analyzed), len(imported_names), len(system_names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
