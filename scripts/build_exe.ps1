<#
.SYNOPSIS
    Build the single-file `stnpe.exe` with PyInstaller.

.DESCRIPTION
    Produces `dist\stnpe.exe` from `packaging\stnpe.spec` (onefile).  Cleans the
    previous PyInstaller work dir and dist dir first, then prints the artifact
    path and size.  Safe to run from any working directory.

    Before anything destructive happens it verifies the build-time prerequisites
    (PyInstaller, plus pywin32-ctypes and altgraph>=0.17.5 on Windows -- see
    `requirements-build.txt`).  A failed check prints what is missing and exits
    non-zero WITHOUT deleting `dist\` or `build\pyinstaller`.

    `gcc` / `cmake` are reported as warnings only: PyInstaller does not compile
    C code, so they are not required to build this exe.

    Determinism and completeness (F2 batch)
    ---------------------------------------
    * Normalized build PATH, scoped to the build.  The PyInstaller child does
      NOT inherit the caller's PATH; the caller's PATH (and any
      SOURCE_DATE_EPOCH this script sets) is restored in a `finally` block,
      so the script returns the caller's environment unchanged on every path,
      failures included.  A fresh PATH is built from a fixed list: system base
      (`system32`, `%SystemRoot%`, `System32\Wbem`), the interpreter's own
      directory, the interpreter-sibling `Library\bin` (conda; holds
      libcrypto/libssl/liblzma/libexpat/libbz2/ffi) and the optional repo
      toolchain dirs.  Rationale: a `conda init` profile hook used to decide by
      accident whether those dependency DLLs were resolvable, which is how an
      INCOMPLETE bundle (8.6 MB, missing every one of them) could be produced.
    * Post-build completeness gate (toolchain-agnostic).  The PRODUCED exe is
      opened with `PyInstaller.archive.readers.CArchiveReader`, every bundled
      binary's PE import table is walked by `scripts/check_bundle_integrity.py`
      and every imported DLL must resolve inside the bundle (an archive entry)
      or be a Windows system DLL.  No dependency names are hardcoded, so the
      gate holds both for conda (separate liblzma/libexpat/LIBBZ2/ffi DLLs)
      and for official CPython (statically linked _lzma/_bz2/pyexpat).  Any
      unresolved non-system import fails the build non-zero.  A bundle that
      ships `_ssl.pyd`/`_hashlib.pyd` without their dependency DLLs starts fine
      and only fails at runtime, the first time one of those modules is used.
      The lazy alternative -- simply excluding those modules so the DLLs are
      never needed -- was considered and REJECTED: it would shrink the
      artifact at the price of a silent future failure instead of a loud one
      today.
    * Reproducibility criterion.  Byte-identical output is NOT reachable today:
      upstream PyInstaller writes `base_library.zip` with a nondeterministic
      internal entry ORDER, the outer CArchive zlib-compresses that zip (so its
      compressed size jitters and every later offset shifts), and the PE header
      `TimeDateStamp` follows the build clock.  Therefore two builds count as
      reproducible when the ENTRY MANIFEST matches: the entry name set plus the
      CRC32 and size of every entry's bytes, including the internal entries of
      `base_library.zip` (its outer blob is compared by inner content only).
      Total size and file SHA-256 are explicitly NOT criteria -- offsets and
      timestamps may still shift them.  `SOURCE_DATE_EPOCH` is set from the
      last commit (when git is resolvable) to reduce timestamp variance; it
      does NOT make the build byte-identical.
      `-ReproducibilityCheck` builds twice and compares those manifests.

.PARAMETER Python
    Python interpreter that has PyInstaller installed.  Resolution order:
    -Python > $env:STNP_PYTHON > known conda env for this repo > `python` on PATH.

.PARAMETER NoClean
    Skip removing `build\pyinstaller` and `dist` before building.

.PARAMETER CheckOnly
    Run only the build-time prerequisite check and return its exit code; do not
    build and do not touch `dist\` or `build\pyinstaller`.

.PARAMETER ReproducibilityCheck
    Build twice (both clean) and compare the archive entry manifests; exit
    non-zero if they differ (see the reproducibility criterion above).  Roughly
    doubles the build time, so it is off by default.  Cannot be combined with
    -NoClean (each of the two builds must be clean).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -CheckOnly
#>
[CmdletBinding()]
param(
    [string]$Python,
    [switch]$NoClean,
    [switch]$CheckOnly,
    [switch]$ReproducibilityCheck
)

$ErrorActionPreference = "Stop"

if ($ReproducibilityCheck -and $NoClean) {
    throw "-ReproducibilityCheck requires two clean builds; it cannot be combined with -NoClean."
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$SpecPath = Join-Path $RepoRoot "packaging\stnpe.spec"
$IntegrityScript = Join-Path $RepoRoot "scripts\check_bundle_integrity.py"
$DistDir = Join-Path $RepoRoot "dist"
$WorkDir = Join-Path $RepoRoot "build\pyinstaller"
$BuildReqs = Join-Path $RepoRoot "requirements-build.txt"

function Resolve-PythonExe {
    param([string]$Explicit)

    if ($Explicit) { return $Explicit }
    if ($env:STNP_PYTHON) { return $env:STNP_PYTHON }

    $known = "E:\develop.environment.pack\anaconda3\envs\STNP_EDITOR_ENV_py3.12\python.exe"
    if (Test-Path -LiteralPath $known) { return $known }

    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    throw "No Python interpreter found. Pass -Python <path> or set STNP_PYTHON."
}

$pythonExe = Resolve-PythonExe -Explicit $Python
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python interpreter not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $SpecPath)) {
    throw "Spec file not found: $SpecPath"
}
if (-not (Test-Path -LiteralPath $IntegrityScript)) {
    throw "Integrity checker not found: $IntegrityScript"
}

# --- Build-time prerequisite check (BEFORE any destructive action) ----------
# altgraph is compared numerically (0.17.10 must count as newer than 0.17.5).
$PrereqScript = @'
import importlib.metadata as md
import sys

problems = []


def check_import(module, label):
    try:
        __import__(module)
    except Exception as exc:  # report, never swallow silently
        problems.append("missing/not importable: {0} ({1}: {2})".format(label, type(exc).__name__, exc))


def parse_version(text):
    parts = []
    for chunk in text.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


check_import("PyInstaller", "PyInstaller")

if sys.platform == "win32":
    check_import("win32ctypes.pywin32", "pywin32-ctypes")
    try:
        altgraph_version = md.version("altgraph")
    except md.PackageNotFoundError:
        problems.append("missing/not installed: altgraph (need >= 0.17.5)")
    else:
        if parse_version(altgraph_version) < (0, 17, 5):
            problems.append("too old: altgraph {0} (need >= 0.17.5)".format(altgraph_version))

if problems:
    print("PREREQ FAILED")
    for item in problems:
        print("  - " + item)
    sys.exit(3)

print("PREREQ OK")
'@

# Pipe the script via stdin ("python -"): PS 5.1 mangles embedded quotes when a
# multi-line string is passed as a native argument to `python -c`.
$prereqOutput = $PrereqScript | & $pythonExe - 2>&1 | Out-String
$prereqRc = $LASTEXITCODE

# gcc/cmake are not used by PyInstaller (it compiles no C here) -> warn only.
$missingTools = @()
foreach ($tool in @("gcc", "cmake")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        $missingTools += $tool
    }
}

if ($prereqRc -ne 0) {
    Write-Host "prereq     : FAILED" -ForegroundColor Red
    Write-Host $prereqOutput.TrimEnd()
    Write-Host ""
    Write-Host "Missing build-time prerequisites. Install them with:" -ForegroundColor Yellow
    Write-Host ("  `"{0}`" -m pip install -r `"{1}`"" -f $pythonExe, $BuildReqs)
    exit 1
}

if ($missingTools.Count -gt 0) {
    $prereqLine = "prereq     : OK (gcc/cmake not on PATH: {0}; not required by PyInstaller)" -f ($missingTools -join ", ")
} else {
    $prereqLine = "prereq     : OK"
}

Write-Host "python     : $pythonExe"
Write-Host "spec       : $SpecPath"
Write-Host "repo root  : $RepoRoot"
Write-Host $prereqLine

# --- Archive manifest (F2.3 reproducibility) ---------------------------------
# Opens the PRODUCED exe with PyInstaller's own CArchiveReader, so it validates
# the artifact itself rather than the build-time plan.  The reader ships with
# PyInstaller (no extra dependency) and is pinned exactly
# (`requirements-build.txt`: pyinstaller==6.15.0).  The completeness gate
# (F2.2) lives in `scripts/check_bundle_integrity.py`.
$ArchiveScript = @'
import io
import sys
import zipfile
import zlib

from PyInstaller.archive.readers import CArchiveReader


def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def dump_manifest(reader):
    lines = ["# outer={0} entries".format(len(reader.toc))]
    for name in sorted(reader.toc):
        if name == "base_library.zip":
            # Upstream orders this zip's entries nondeterministically, so its
            # outer bytes (and CRC) vary while the content does not.  Compare
            # the INNER entries instead of the outer blob.
            lines.append("OUTER\t{0}\tORDER-DEPENDENT\t-".format(name))
            continue
        data = reader.extract(name)
        lines.append("OUTER\t{0}\t{1:08x}\t{2}".format(name, crc32(data), len(data)))
    inner = zipfile.ZipFile(io.BytesIO(reader.extract("base_library.zip")))
    infos = sorted(inner.infolist(), key=lambda info: info.filename)
    lines.append("# base_library.zip inner={0} entries".format(len(infos)))
    for info in infos:
        lines.append("INNER\t{0}\t{1:08x}\t{2}".format(
            info.filename, info.CRC & 0xFFFFFFFF, info.file_size))
    return lines


def main():
    mode = sys.argv[1]
    exe = sys.argv[2]
    reader = CArchiveReader(exe)

    if mode == "manifest":
        print("\n".join(dump_manifest(reader)))
        return 0

    print("unsupported archive mode: {0}".format(mode), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
'@

function Invoke-StnpeBuild {
    if (-not $NoClean) {
        foreach ($dir in @($WorkDir, $DistDir)) {
            if (Test-Path -LiteralPath $dir) {
                Write-Host "cleaning   : $dir"
                Remove-Item -LiteralPath $dir -Recurse -Force
            }
        }
    }

    & $pythonExe -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $DistDir `
        --workpath $WorkDir `
        $SpecPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }

    $built = Join-Path $DistDir "stnpe.exe"
    if (-not (Test-Path -LiteralPath $built)) {
        throw "Build reported success but artifact is missing: $built"
    }

    # F2.2: fail loudly on an incomplete bundle instead of shipping one that
    # only breaks when _ssl/_hashlib/_lzma/_bz2/pyexpat/_ctypes is first used.
    # The gate walks PE import tables (scripts/check_bundle_integrity.py), so
    # it does not depend on which dependency DLLs a given Python ships.
    $integrityOutput = (& $pythonExe $IntegrityScript --exe $built --build-dir $WorkDir 2>&1 | Out-String)
    $integrityRc = $LASTEXITCODE
    if ($integrityRc -ne 0) {
        Write-Host "integrity  : FAILED" -ForegroundColor Red
        Write-Host $integrityOutput.TrimEnd()
        Write-Host ("hint       : incomplete bundle left at {0} for inspection; do not ship" -f $built) -ForegroundColor Yellow
        exit 1
    }
    $integritySummary = @($integrityOutput.TrimEnd() -split "`r?`n")[-1]
    Write-Host ("integrity  : OK ({0})" -f ($integritySummary -replace '^INTEGRITY OK:\s*', ''))
}

function Get-ArchiveManifest {
    param([string]$ExePath)
    $manifest = ($ArchiveScript | & $pythonExe - manifest $ExePath 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw "archive manifest extraction failed (exit $LASTEXITCODE)`n$manifest"
    }
    return $manifest.TrimEnd()
}

function Write-ArtifactInfo {
    $artifact = Join-Path $DistDir "stnpe.exe"
    $bytes = (Get-Item -LiteralPath $artifact).Length
    Write-Host ""
    Write-Host ("artifact   : {0}" -f $artifact)
    Write-Host ("size       : {0:N2} MB ({1} bytes)" -f ($bytes / 1MB), $bytes)
    return $bytes
}

# --- Normalized build environment (F2.1), scoped to the build ---------------
# Everything below (PyInstaller inherits it) runs on the normalized PATH, and
# the caller's PATH/`SOURCE_DATE_EPOCH` are restored before this script
# returns -- see the try/finally around the build.  Never inherit the caller
# PATH: profile hooks such as `conda init` silently add a DIFFERENT
# Library\bin, which changes which dependency DLLs PyInstaller can resolve and
# can yield an incomplete bundle.
$BuildPath = New-Object System.Collections.ArrayList
$BuildPathSeen = @{}
function Add-BuildPathEntry {
    param([string]$Directory)
    if ([string]::IsNullOrWhiteSpace($Directory)) { return }
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) { return }
    $full = (Get-Item -LiteralPath $Directory).FullName
    $key = $full.ToLowerInvariant()
    if ($BuildPathSeen.ContainsKey($key)) { return }
    $BuildPathSeen[$key] = $true
    [void]$BuildPath.Add($full)
}

Add-BuildPathEntry (Join-Path $env:SystemRoot "system32")
Add-BuildPathEntry $env:SystemRoot
Add-BuildPathEntry (Join-Path $env:SystemRoot "System32\Wbem")
$pythonDir = Split-Path -Parent $pythonExe
Add-BuildPathEntry $pythonDir
# conda: `<env>\Library\bin` is where libcrypto/libssl/liblzma/libexpat/libbz2/
# ffi live.  Adding it is what makes the bundle COMPLETE; without it PyInstaller
# cannot resolve the dependencies of _ssl/_hashlib/_lzma/_bz2/pyexpat/_ctypes.
Add-BuildPathEntry (Join-Path $pythonDir "Library\bin")
# Optional repo toolchain dirs: PyInstaller compiles no C here, so these are
# harmless extras kept for parity with the rest of the toolchain.
Add-BuildPathEntry "E:\develop.environment.pack\mingw64\bin"
Add-BuildPathEntry "E:\develop.environment.pack\CMake\bin"

# The caller's environment is captured before anything is replaced.  The
# try/finally below restores it on EVERY exit path: normal return, -CheckOnly,
# a failed integrity gate (exit 1), a build failure or any terminating error.
# Without the restore the normalized PATH leaks into the caller's session and
# its omissions (C:\Windows\System32\WindowsPowerShell\v1.0) break later
# bare-name `powershell` invocations in the same shell.
$CallerPath = $env:PATH
$CallerSourceDateEpoch = $env:SOURCE_DATE_EPOCH

try {
    $env:PATH = ($BuildPath -join [IO.Path]::PathSeparator)

    # SOURCE_DATE_EPOCH reduces PE timestamp variance (PyInstaller honours it when
    # set); it does NOT make the build byte-identical.  Prefer the last commit so
    # rebuilds of the same revision agree; otherwise keep an inherited value.
    $gitExe = $null
    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCmd) { $gitExe = $gitCmd.Source }
    elseif (Test-Path -LiteralPath "E:\assistant.software.pack\Git\cmd\git.exe") {
        $gitExe = "E:\assistant.software.pack\Git\cmd\git.exe"
    }
    $epochSource = "not set (git unavailable)"
    if ($gitExe) {
        $commitEpoch = (& $gitExe -C $RepoRoot log -1 --format=%ct 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $commitEpoch -match '^\d+$') {
            $env:SOURCE_DATE_EPOCH = $commitEpoch
            $epochSource = "$commitEpoch (last commit)"
        } else {
            $epochSource = "not set (git log failed)"
        }
    } elseif ($env:SOURCE_DATE_EPOCH) {
        $epochSource = "$($env:SOURCE_DATE_EPOCH) (inherited)"
    }

    Write-Host ("build path : {0} entries (normalized during the build; caller PATH restored before returning)" -f $BuildPath.Count)
    Write-Host ("epoch      : SOURCE_DATE_EPOCH {0}" -f $epochSource)

    if ($CheckOnly) {
        Write-Host "check-only : prerequisites satisfied; no build performed"
        exit 0
    }

    Invoke-StnpeBuild
    $size1 = Write-ArtifactInfo

    if ($ReproducibilityCheck) {
        $exePath = Join-Path $DistDir "stnpe.exe"
        $manifest1 = Get-ArchiveManifest -ExePath $exePath
        Write-Host ("repro      : build #1 manifest captured ({0} lines)" -f (@($manifest1 -split "`r?`n").Count))

        Invoke-StnpeBuild
        $size2 = Write-ArtifactInfo
        $manifest2 = Get-ArchiveManifest -ExePath $exePath
        Write-Host ("repro      : build #2 manifest captured ({0} lines)" -f (@($manifest2 -split "`r?`n").Count))

        if ($manifest1 -ne $manifest2) {
            Write-Host "repro      : FAILED - entry manifests differ" -ForegroundColor Red
            Compare-Object -ReferenceObject ($manifest1 -split "`r?`n") -DifferenceObject ($manifest2 -split "`r?`n") |
                Select-Object -First 40 |
                ForEach-Object { Write-Host ("  {0} {1}" -f $_.SideIndicator, $_.InputObject) }
            exit 1
        }
        if ($size2 -ne $size1) {
            Write-Host ("repro      : note - total size {0} -> {1} bytes (CArchive offset shift; NOT a criterion)" -f $size1, $size2)
        } else {
            Write-Host ("repro      : total size also identical: {0} bytes" -f $size2)
        }
        Write-Host "repro      : OK - entry names, CRC32s and sizes are identical across both builds"
    }

    Write-Host "BUILD OK"
}
finally {
    $env:PATH = $CallerPath
    if ($null -eq $CallerSourceDateEpoch) {
        Remove-Item Env:\SOURCE_DATE_EPOCH -ErrorAction SilentlyContinue
    } else {
        $env:SOURCE_DATE_EPOCH = $CallerSourceDateEpoch
    }
}
