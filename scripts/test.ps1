<#
.SYNOPSIS
    One-command full test run for STNP Editor (T1 -- test automation).

.DESCRIPTION
    Behaviour contract:

      1. The repository root is derived from $PSScriptRoot, so the script works
         from any current working directory.
      2. Console output is forced to UTF-8 (no BOM) so the Chinese warning text
         stays valid UTF-8 when stdout is redirected into CI logs or pipes,
         regardless of the host code page.
      3. Toolchain resolution goes through the shared resolver
         (`scripts/toolchain.ps1`, the twin of `tests/_toolchain.py`).  The order
         is fixed and identical everywhere:

             1. environment variable STNP_PYTHON / STNP_MINGW_BIN / STNP_CMAKE_BIN
                                   optional override; SET but unusable -> loud error
             2. PATH lookup          first match is adopted; all candidates listed
             3. loud failure     one line of install guidance

         The resolver detects and reports: a candidate must pass a minimal
         usability check (`gcc -dumpmachine` runs, `cmake --version` runs, python
         satisfies requires-python and imports stnp_editor), but whether the
         adopted toolchain suits your target platform is yours to verify.  A
         declared-but-unusable STNP_* value never falls back silently.
      4. `gcc` / `cmake` are REQUIRED: when the resolver cannot find them the
         script prints the resolver's guidance and exits 2.  Skipping silently was
         the defect this replaced -- no toolchain must never look like success.
      5. The resolved gcc / cmake directories are idempotently prepended to this
         process' PATH and CMAKE_GENERATOR is set to "MinGW Makefiles", so the
         tests that decide to skip on shutil.which("gcc"/"cmake") actually run
         (issue I-001: skipped tests hide defects).
      6. Python Scripts directory: when the interpreter's console-script directory
         exists next to it -- its sibling `Scripts`, or the interpreter's own
         directory when that directory is already named `Scripts` (a venv) -- it
         is prepended the same way, so an installed `stnpe` console script is
         discoverable without activating the environment.
      7. The FULL suite runs as `python -m pytest -q -rs` (never narrowed).
      8. Skip accounting:
         - The `-rs` short summary lines `SKIPPED [<n>] <location>: <reason>`
           are parsed into per-reason records.
         - A skip whose reason contains one of $ExpectedSkipReasonMarkers is a
           DESIGN skip: the test module itself declares it is an opt-in gate that
           is deliberately disabled in a default run.
         - Every other skip is UNEXPECTED (an environment gap).  Toolchain skips
           ("gcc not available" / "cmake not available") never match the design
           markers, so they are exactly what -FailOnSkip catches.
         - UNEXPECTED skips are the only thing reported as a problem: they get
           the loud WARNING banner, and each one is listed with location +
           reason.  Design skips get a one-line note instead; the skip detail
           list still shows both, so nothing is hidden.
      9. Exit code:
         - the pytest exit code is passed through unchanged (highest priority);
         - else `-FailOnSkip` + unexpected > 0 -> exit 1;
         - else exit 0.  DESIGN skips never fail the run.

    Toolchain overrides (optional; they are level 1 of the resolver, not defaults
    baked into this file): $env:STNP_PYTHON, $env:STNP_MINGW_BIN,
    $env:STNP_CMAKE_BIN.  When unset, the first match on PATH is adopted.

    Disclaimer: 工具链由本机环境决定，软件不保证其正确或匹配；请自行确认。

.PARAMETER FailOnSkip
    Exit non-zero when pytest reports UNEXPECTED skipped tests (intended for
    CI).  DESIGN skips -- the ones the tests themselves declare as opt-in, see
    $ExpectedSkipReasonMarkers -- are reported with a single note line and never
    fail the run.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
    powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1 -FailOnSkip
#>
[CmdletBinding()]
param(
    [switch]$FailOnSkip
)

$ErrorActionPreference = "Stop"

# Skip reasons containing one of these markers are DESIGN skips: the test module
# declares by itself that it is an opt-in gate (e.g. "set STNP_TEST_EXE=1 to run
# packaging tests", or "stnpe console script not found ... install with
# `pip install -e .[dev]`"), so skipping it in a default run is the intended
# behaviour, not an environment gap.  Everything else is UNEXPECTED, and
# UNEXPECTED skips are the only thing this script reports and fails on.
# Keep this list deliberately short: it must only echo declarations made by the
# tests themselves, never paper over missing tooling.  The toolchain gates
# ("gcc not available" / "cmake not available") deliberately do not match.
# It mirrors the two keywords of conftest.py's _DESIGN_SKIP_NOTES.
$ExpectedSkipReasonMarkers = @("STNP_TEST_EXE", "stnpe")

# Force deterministic UTF-8 console output (no BOM) even when stdout/stderr are
# redirected.  PS 5.1 otherwise encodes with the host console code page, which
# garbles the Chinese warning text in CI logs.  Non-fatal by design: hosts that
# refuse the change keep their default encoding and the run continues.
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {
    # Intentionally ignored: never abort a test run because of console encoding.
}

$RepoRoot = Split-Path -Parent $PSScriptRoot

function Add-PathFront {
    param([string]$Directory)
    $normalized = $Directory.TrimEnd('\')
    foreach ($entry in @($env:PATH -split ';' | Where-Object { $_ -ne '' })) {
        if ([string]::Equals($entry.TrimEnd('\'), $normalized, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $false
        }
    }
    $env:PATH = $normalized + ';' + $env:PATH
    return $true
}

# --- Shared toolchain resolver (S2/S3) --------------------------------------
. (Join-Path $PSScriptRoot "toolchain.ps1")

Write-Host "== STNP Editor full test run =="
Write-Host ("repo root : {0}" -f $RepoRoot)
Write-Host ("cwd       : {0}" -f (Get-Location).Path)
Write-StnpToolchainDisclaimer
Write-Host ""

# --- Python interpreter (resolver level 1 env override -> level 2 PATH) -------
$ResolvedPython = $null
try {
    $ResolvedPython = Resolve-StnpPython
} catch {
    Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
    exit 2
}
$PythonExe = $ResolvedPython.Path
Write-Host (Format-StnpToolLine -Resolved $ResolvedPython)
$otherPython = @(Get-StnpOtherCandidates -Resolved $ResolvedPython)
if ($otherPython.Count -gt 0) {
    Write-Host ("其它候选：{0}" -f ($otherPython -join "; "))
}

# Make an installed `stnpe` console script discoverable without activating the
# environment (see the .DESCRIPTION note about the interpreter's Scripts dir).
$PythonDir = Split-Path -Parent $PythonExe
if ($PythonDir) {
    $ScriptsDir = if ((Split-Path -Leaf $PythonDir) -eq "Scripts") {
        $PythonDir
    } else {
        Join-Path $PythonDir "Scripts"
    }
    if (Test-Path -LiteralPath $ScriptsDir) {
        $added = Add-PathFront -Directory $ScriptsDir
        $state = if ($added) { "prepended to PATH" } else { "already in PATH" }
        Write-Host ("scripts   : {0} ({1})" -f $ScriptsDir, $state)
    }
}
Write-Host ""

# --- gcc / cmake are required (D7: no silent skips) --------------------------
$missingToolchain = New-Object System.Collections.ArrayList
$ResolvedGcc = $null
$ResolvedCmake = $null
try {
    $ResolvedGcc = Resolve-StnpGcc
} catch {
    Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
    [void]$missingToolchain.Add("gcc")
}
try {
    $ResolvedCmake = Resolve-StnpCmake
} catch {
    Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
    [void]$missingToolchain.Add("cmake")
}
if ($missingToolchain.Count -gt 0) {
    Write-Host ""
    Write-Host ("ERROR: required toolchain missing: {0}" -f ($missingToolchain -join ", ")) -ForegroundColor Red
    Write-Host "       the full suite cannot run; fix PATH or use STNP_MINGW_BIN / STNP_CMAKE_BIN" -ForegroundColor Red
    exit 2
}

$env:CMAKE_GENERATOR = "MinGW Makefiles"
Write-Host "toolchain:"
foreach ($resolved in @($ResolvedGcc, $ResolvedCmake)) {
    $added = Add-PathFront -Directory $resolved.Directory
    $state = if ($added) { "prepended to PATH" } else { "already in PATH" }
    Write-Host ("  " + (Format-StnpToolLine -Resolved $resolved))
    Write-Host ("  [{0}] {1}" -f $state, $resolved.Directory)
    $others = @(Get-StnpOtherCandidates -Resolved $resolved)
    if ($others.Count -gt 0) {
        Write-Host ("  其它候选：{0}" -f ($others -join "; "))
    }
}
Write-Host ("  [env]     CMAKE_GENERATOR = {0}" -f $env:CMAKE_GENERATOR)

# mingw32-make is not resolved by the shared resolver; it is reported and a
# missing one is a warning (cmake --build with MinGW Makefiles will report it).
if (-not (Get-Command mingw32-make -ErrorAction SilentlyContinue)) {
    Write-Host "  [warn]    mingw32-make -> NOT FOUND (cmake builds may fail)" -ForegroundColor Yellow
} else {
    Write-Host ("  [ok]      mingw32-make -> {0}" -f (Get-Command mingw32-make).Source)
}
Write-Host ""

# --- Full test suite ---------------------------------------------------------
Write-Host ("running   : {0} -m pytest -q -rs" -f $PythonExe)
Write-Host ("workdir   : {0}" -f $RepoRoot)
Write-Host ("-" * 78)
Push-Location -LiteralPath $RepoRoot
try {
    $pytestRaw = @(& $PythonExe -m pytest -q -rs)
    $pytestExit = $LASTEXITCODE
} finally {
    Pop-Location
}
foreach ($line in $pytestRaw) {
    Write-Host $line
}
Write-Host ("-" * 78)

# --- Skip accounting ---------------------------------------------------------
$pytestText = ($pytestRaw | ForEach-Object { [string]$_ }) -join "`n"

# Total from the pytest summary line ("133 passed, 2 skipped in ..."), unchanged
# by -rs; only the lowercase "skipped" form is matched.
$skipCount = 0
$skipMatches = [regex]::Matches($pytestText, '(\d+)\s+skipped')
if ($skipMatches.Count -gt 0) {
    $skipCount = [int]$skipMatches[$skipMatches.Count - 1].Groups[1].Value
}

# Per-reason detail from the `-rs` short summary:
#   SKIPPED [<n>] <location>: <reason>
$skipRecords = New-Object System.Collections.ArrayList
foreach ($rawLine in ($pytestText -split "`n")) {
    $line = $rawLine.TrimEnd("`r")
    if (-not $line.StartsWith("SKIPPED [")) { continue }
    $closing = $line.IndexOf("] ")
    if ($closing -lt 0) { continue }
    $quantity = 0
    if (-not [int]::TryParse($line.Substring(9, $closing - 9), [ref]$quantity) -or $quantity -le 0) { continue }
    $body = $line.Substring($closing + 2)
    $separator = $body.IndexOf(": ")
    if ($separator -lt 0) {
        $location = $body
        $reason = ""
    } else {
        $location = $body.Substring(0, $separator)
        $reason = $body.Substring($separator + 2)
    }
    [void]$skipRecords.Add([pscustomobject]@{ Count = $quantity; Location = $location; Reason = $reason })
}

$expectedRecords = New-Object System.Collections.ArrayList
$unexpectedRecords = New-Object System.Collections.ArrayList
$attributedCount = 0
foreach ($record in $skipRecords) {
    $attributedCount += $record.Count
    $isExpected = $false
    foreach ($marker in $ExpectedSkipReasonMarkers) {
        if ($record.Reason.IndexOf($marker, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            $isExpected = $true
            break
        }
    }
    if ($isExpected) {
        [void]$expectedRecords.Add($record)
    } else {
        [void]$unexpectedRecords.Add($record)
    }
}

$expectedCount = 0
foreach ($record in $expectedRecords) { $expectedCount += $record.Count }
$unexpectedCount = 0
foreach ($record in $unexpectedRecords) { $unexpectedCount += $record.Count }

# Safety net: a skip that the -rs parse could not attribute is never forgiven.
$unattributedCount = $skipCount - $attributedCount
if ($unattributedCount -gt 0) {
    [void]$unexpectedRecords.Add([pscustomobject]@{
        Count    = $unattributedCount
        Location = "<unattributed>"
        Reason   = "skip detail missing from pytest -rs output"
    })
    $unexpectedCount += $unattributedCount
}

Write-Host ""
Write-Host ("pytest exit code : {0}" -f $pytestExit)
Write-Host ("skipped tests    : {0} (expected: {1}, unexpected: {2})" -f $skipCount, $expectedCount, $unexpectedCount)

if ($skipCount -gt 0) {
    Write-Host "skip detail:"
    foreach ($record in $expectedRecords) {
        Write-Host ("  [expected]   x{0} {1} -- {2}" -f $record.Count, $record.Location, $record.Reason)
    }
    foreach ($record in $unexpectedRecords) {
        Write-Host ("  [UNEXPECTED] x{0} {1} -- {2}" -f $record.Count, $record.Location, $record.Reason) -ForegroundColor Yellow
    }
    Write-Host ""
    if ($unexpectedCount -gt 0) {
        Write-Host "##############################################################################" -ForegroundColor Yellow
        Write-Host ("#  WARNING: {0} UNEXPECTED test(s) were SKIPPED and did NOT actually run." -f $unexpectedCount) -ForegroundColor Yellow
        Write-Host "#  非设计跳过：有测试未真正执行，结论不可信。" -ForegroundColor Yellow
        Write-Host "#  Remedy for the unexpected skips listed above:" -ForegroundColor Yellow
        Write-Host "#    - toolchain      : make gcc / cmake visible (see resolver guidance above)" -ForegroundColor Yellow
        Write-Host '#    - console script : python -m pip install -e ".[dev]" with the selected interpreter' -ForegroundColor Yellow
        if ($expectedCount -gt 0) {
            Write-Host ("#  design (declared opt-in) skips, not counted as unexpected: {0}" -f $expectedCount) -ForegroundColor Yellow
        }
        Write-Host "##############################################################################" -ForegroundColor Yellow
        Write-Host ""
    } else {
        Write-Host ("note      : {0} design skip(s), declared opt-in by the tests; no unexpected skips" -f $expectedCount) -ForegroundColor DarkGray
        Write-Host ""
    }
}

if ($FailOnSkip -and $unexpectedCount -gt 0) {
    Write-Host ("-FailOnSkip: forcing a non-zero exit because {0} UNEXPECTED test(s) were skipped" -f $unexpectedCount) -ForegroundColor Red
    if ($pytestExit -eq 0) {
        $pytestExit = 1
    }
} elseif ($FailOnSkip -and $skipCount -gt 0) {
    Write-Host ("-FailOnSkip: {0} design skip(s) declared opt-in; not failing the run" -f $expectedCount) -ForegroundColor DarkYellow
}

Write-Host ("final exit code  : {0}" -f $pytestExit)
exit $pytestExit
