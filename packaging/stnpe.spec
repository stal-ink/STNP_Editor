# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller **onefile** spec for the ``stnpe`` CLI.

Build from anywhere (the spec resolves paths via ``SPECPATH``):

    pyinstaller --noconfirm --clean packaging/stnpe.spec

Output::

    dist/stnpe.exe        # single self-contained executable

Resource layout inside the bundle (``sys._MEIPASS``) mirrors the source tree so
that ``stnp_editor.settings.resources_root()`` / ``bundle_root()`` resolve:

    _MEIPASS/stnp_editor/resources/config.json
    _MEIPASS/stnp_editor/resources/schemas/*.json
    _MEIPASS/stnp_editor/resources/templates/**/*.j2

The explicit ``datas`` entries below are the primary mechanism (deterministic,
no metadata guessing).  ``collect_data_files('stnp_editor')`` is layered on as
a belt-and-braces fallback.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH is injected by PyInstaller: the directory holding this .spec file.
_SPEC_DIR = Path(SPECPATH).resolve()  # noqa: F821  (PyInstaller-provided global)
_REPO_ROOT = _SPEC_DIR.parent
_SRC = _REPO_ROOT / "src"
_RESOURCES = _SRC / "stnp_editor" / "resources"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# --- Data files: read-only bundled resources (never written at runtime) -----
datas = [
    (str(_RESOURCES / "config.json"), "stnp_editor/resources"),
    (str(_RESOURCES / "schemas"), "stnp_editor/resources/schemas"),
    (str(_RESOURCES / "templates"), "stnp_editor/resources/templates"),
]

# Belt-and-braces: pick up anything else shipped with the package.  Only add
# sources we have not already listed explicitly, to avoid duplicate entries.
_declared_sources = {src for src, _dest in datas}
for _src, _dest in collect_data_files("stnp_editor"):
    if _src not in _declared_sources:
        datas.append((_src, _dest))
        _declared_sources.add(_src)

# --- Hidden imports ---------------------------------------------------------
# jsonschema discovers its referencing/format backends lazily via entry points
# and dynamic imports, so PyInstaller's static analysis misses them.  Without
# these the exe builds fine but crashes the moment a schema is validated.
hiddenimports = list(collect_submodules("jsonschema"))
for _extra in ("jsonschema_specifications", "referencing", "rpds", "attrs"):
    if _extra not in hiddenimports:
        hiddenimports.append(_extra)

a = Analysis(
    [str(_SRC / "stnp_editor" / "__main__.py")],
    pathex=[str(_SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# onefile: binaries + datas are embedded directly into EXE (no COLLECT).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="stnpe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Keep the spec portable: cwd-independent output names.
    icon=None,
)
