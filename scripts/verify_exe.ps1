<#
.SYNOPSIS
    Acceptance harness for the packaged `stnpe.exe` (six checks).

.DESCRIPTION
    Copies `dist\stnpe.exe`, the shared regression inputs (`fixtures\C\**`,
    `fixtures\python\**`) and their expectations (the generated trees under
    `tests\golden\C\regression_c\` and `tests\golden\python\regression_py\`)
    into a brand-new temp directory and exercises the exe there.  The exe never
    bundled these files: sandboxing comes from copying the inputs into a temp
    directory, not from the fixture source, so the gate can stage the same
    fixtures the rest of the test suite uses.

    Checks:
      1. `stnpe.exe --help` exits 0
      2. `--version` and `version` both print the version, exit 0
      3. `generate` for the C and Python fixtures exits 0 with a non-empty tree
      4. `check` for both fixtures prints `CHECK OK`, exits 0
      5. config.json: first-run creation next to the exe (content == bundled
         default) and authority proof (editing `dir_names.core` takes effect)
      6. `bundle_root()` is read-only: static assertion that settings.py's only
         write target is `user_config_path()`, plus a TMP-isolation probe

    Prints PASS/FAIL per check and a summary; exits non-zero if any check fails.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\verify_exe.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ExeSource = Join-Path $RepoRoot "dist\stnpe.exe"
$FixtureC = Join-Path $RepoRoot "fixtures\C"
$FixturePython = Join-Path $RepoRoot "fixtures\python"
$GoldenC = Join-Path $RepoRoot "tests\golden\C\regression_c\regression_c_STNP_C"
$GoldenPython = Join-Path $RepoRoot "tests\golden\python\regression_py\regression_py_STNP_Python"
$SettingsPy = Join-Path $RepoRoot "src\stnp_editor\settings.py"
$BundledConfig = Join-Path $RepoRoot "src\stnp_editor\resources\config.json"
$VersionSource = Join-Path $RepoRoot "src\stnp_editor\__init__.py"

foreach ($required in @($ExeSource, $SettingsPy, $BundledConfig, $VersionSource, $FixtureC, $FixturePython, $GoldenC, $GoldenPython)) {
    if (-not (Test-Path -LiteralPath $required)) {
        Write-Host ("FAIL: missing required path: {0}" -f $required) -ForegroundColor Red
        exit 2
    }
}

# Derived, never repeated: `stnp_editor.__version__` is the single literal
# (pyproject.toml reads it via `dynamic`).  A hardcoded copy here is how 0.9.1
# once shipped expecting 0.9.0; tests/test_core_generation.py now guards it.
$versionMatch = [regex]::Match(
    (Get-Content -LiteralPath $VersionSource -Raw -Encoding UTF8),
    '__version__\s*=\s*"([^"]+)"')
if (-not $versionMatch.Success) {
    Write-Host ("FAIL: cannot read __version__ from {0}" -f $VersionSource) -ForegroundColor Red
    exit 2
}
$ExpectedVersion = $versionMatch.Groups[1].Value

# --- Stage the exe + fixtures in a clean temp directory ---------------------
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("stnpe_verify_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work -Force | Out-Null
Copy-Item -LiteralPath $ExeSource -Destination $work -Force

$cDir = Join-Path $work "c"
$pythonDir = Join-Path $work "python"
New-Item -ItemType Directory -Path $cDir, $pythonDir -Force | Out-Null
Copy-Item -Path (Join-Path $FixtureC "*") -Destination $cDir -Recurse -Force
Copy-Item -Path (Join-Path $FixturePython "*") -Destination $pythonDir -Recurse -Force

# Golden dirs hold the generated tree only; a sibling vectors.json would be
# reported by `check --golden` as a file the generated output lacks.
$cGoldenDir = Join-Path $cDir "golden"
$pythonGoldenDir = Join-Path $pythonDir "golden"
New-Item -ItemType Directory -Path $cGoldenDir, $pythonGoldenDir -Force | Out-Null
Copy-Item -LiteralPath $GoldenC -Destination (Join-Path $cGoldenDir "regression_c_STNP_C") -Recurse -Force
Copy-Item -LiteralPath $GoldenPython -Destination (Join-Path $pythonGoldenDir "regression_py_STNP_Python") -Recurse -Force

$exe = Join-Path $work "stnpe.exe"
$configPath = Join-Path $work "config.json"
$exeSize = (Get-Item -LiteralPath $exe).Length

# Must be recorded BEFORE any exe invocation (which triggers config creation).
$preExistingConfig = Test-Path -LiteralPath $configPath

$script:Results = New-Object System.Collections.ArrayList
$script:LastDetail = ""

function Invoke-Check {
    param([string]$Name, [scriptblock]$Body)
    $script:LastDetail = ""
    $ok = $false
    try {
        $ok = [bool](& $Body)
    } catch {
        $ok = $false
        $script:LastDetail = $_.Exception.Message
    }
    [void]$script:Results.Add([pscustomobject]@{ Name = $Name; Passed = $ok; Detail = $script:LastDetail })
    if ($ok) {
        Write-Host ("PASS: {0}" -f $Name) -ForegroundColor Green
        if ($script:LastDetail) { Write-Host ("      {0}" -f $script:LastDetail) }
    } else {
        Write-Host ("FAIL: {0} -- {1}" -f $Name, $script:LastDetail) -ForegroundColor Red
    }
}

Write-Host ("exe        : {0} ({1:N2} MB)" -f $exe, ($exeSize / 1MB))
Write-Host ("work dir   : {0}" -f $work)
Write-Host ""

# --- 1. --help --------------------------------------------------------------
Invoke-Check "1. stnpe.exe --help -> exit 0" {
    $out = & $exe --help 2>&1 | Out-String
    $rc = $LASTEXITCODE
    $script:LastDetail = "rc=$rc; mentions generate/check/version"
    return ($rc -eq 0 -and $out -match "generate" -and $out -match "check" -and $out -match "version")
}

# --- 2. --version + version subcommand --------------------------------------
Invoke-Check "2. --version and version both print $ExpectedVersion, exit 0" {
    $v1 = (& $exe --version 2>&1 | Out-String).Trim()
    $rc1 = $LASTEXITCODE
    $v2 = (& $exe version 2>&1 | Out-String).Trim()
    $rc2 = $LASTEXITCODE
    $script:LastDetail = "--version='$v1' rc=$rc1; version='$v2' rc=$rc2"
    return ($rc1 -eq 0 -and $rc2 -eq 0 -and
            $v1 -match [regex]::Escape($ExpectedVersion) -and
            $v2 -match [regex]::Escape($ExpectedVersion))
}

# --- 3. generate both targets -----------------------------------------------
Invoke-Check "3. generate C + Python fixtures -> exit 0, non-empty trees" {
    $outC = Join-Path $work "out_c"
    $outP = Join-Path $work "out_py"
    $gc = & $exe generate (Join-Path $work "c\regression_c.stnp") (Join-Path $work "c\stnp.build.json") -o $outC 2>&1 | Out-String
    $rcC = $LASTEXITCODE
    $gp = & $exe generate (Join-Path $work "python\regression_py.stnp") (Join-Path $work "python\stnp.build.json") -o $outP 2>&1 | Out-String
    $rcP = $LASTEXITCODE
    $treeC = Join-Path $outC "regression_c_STNP_C"
    $treeP = Join-Path $outP "regression_py_STNP_Python"
    $nC = if (Test-Path -LiteralPath $treeC) { (Get-ChildItem -LiteralPath $treeC -Recurse -File | Measure-Object).Count } else { 0 }
    $nP = if (Test-Path -LiteralPath $treeP) { (Get-ChildItem -LiteralPath $treeP -Recurse -File | Measure-Object).Count } else { 0 }
    $script:LastDetail = "C rc=$rcC files=$nC ('$($gc.Trim())'); Python rc=$rcP files=$nP ('$($gp.Trim())')"
    return ($rcC -eq 0 -and $rcP -eq 0 -and $nC -gt 0 -and $nP -gt 0)
}

# --- 4. check both targets against golden -----------------------------------
Invoke-Check "4. check C + Python fixtures -> CHECK OK, exit 0" {
    $ckC = & $exe check (Join-Path $work "c\regression_c.stnp") (Join-Path $work "c\stnp.build.json") --golden (Join-Path $work "c\golden") 2>&1 | Out-String
    $rcC = $LASTEXITCODE
    $ckP = & $exe check (Join-Path $work "python\regression_py.stnp") (Join-Path $work "python\stnp.build.json") --golden (Join-Path $work "python\golden") 2>&1 | Out-String
    $rcP = $LASTEXITCODE
    $script:LastDetail = "C rc=$rcC out='$($ckC.Trim())'; Python rc=$rcP out='$($ckP.Trim())'"
    return ($rcC -eq 0 -and $rcP -eq 0 -and $ckC -match "CHECK OK" -and $ckP -match "CHECK OK")
}

# --- 5. config.json first-run creation + authority --------------------------
Invoke-Check "5. config.json: first-run creation + authority over bundle" {
    $created = Test-Path -LiteralPath $configPath
    $createdOk = (-not $preExistingConfig) -and $created

    $sameContent = $false
    if ($created) {
        $a = ([IO.File]::ReadAllText($configPath, [Text.Encoding]::UTF8)) -replace "`r`n", "`n"
        $b = ([IO.File]::ReadAllText($BundledConfig, [Text.Encoding]::UTF8)) -replace "`r`n", "`n"
        $sameContent = ($a -eq $b)
    }

    # Authority proof: change dir_names.core in the exe-sibling config.json.
    $cfg = ([IO.File]::ReadAllText($configPath, [Text.Encoding]::UTF8)) | ConvertFrom-Json
    $cfg.dir_names.core = "FakeCore"
    $newJson = $cfg | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText($configPath, $newJson, (New-Object System.Text.UTF8Encoding($false)))

    $outFake = Join-Path $work "out_fake"
    $gf = & $exe generate (Join-Path $work "c\regression_c.stnp") (Join-Path $work "c\stnp.build.json") -o $outFake 2>&1 | Out-String
    $rcF = $LASTEXITCODE
    $fakeDir = Join-Path $outFake "regression_c_STNP_C\FakeCore"
    $defaultCoreGone = -not (Test-Path -LiteralPath (Join-Path $outFake "regression_c_STNP_C\Core"))
    $authorityOk = ($rcF -eq 0) -and (Test-Path -LiteralPath $fakeDir) -and $defaultCoreGone

    $script:LastDetail = "pre-existing=$preExistingConfig; created=$created; default-content-match=$sameContent; authority rc=$rcF fakeCore-dir=$(Test-Path -LiteralPath $fakeDir) default-Core-absent=$defaultCoreGone"
    return ($createdOk -and $sameContent -and $authorityOk)
}

# --- 6. bundle_root is read-only -------------------------------------------
Invoke-Check "6. bundle_root read-only (static assertion + TMP probe)" {
    $src = [IO.File]::ReadAllText($SettingsPy, [Text.Encoding]::UTF8)
    $writeCalls = [regex]::Matches($src, '\.write_text\s*\(')
    $byteWrites = [regex]::Matches($src, '\.write_bytes\s*\(')
    $writesToTarget = [regex]::Matches($src, 'target\.write_text\s*\(')
    $targetFromUser = [regex]::IsMatch($src, 'target\s*=\s*user_config_path\(\)')
    $staticOk = ($writeCalls.Count -eq 1) -and ($writesToTarget.Count -eq 1) -and
                ($byteWrites.Count -eq 0) -and $targetFromUser

    # Runtime probe (supplementary): point TMP at a fresh dir and make sure the
    # exe never leaves a config.json there.  NOTE: _MEIPASS is deleted on exit,
    # so this probe is weaker than the static assertion.
    $probeTmp = Join-Path $work "probe_tmp"
    New-Item -ItemType Directory -Path $probeTmp -Force | Out-Null
    $savedTmp = $env:TMP
    $savedTemp = $env:TEMP
    $env:TMP = $probeTmp
    $env:TEMP = $probeTmp
    try {
        $null = & $exe --help 2>&1 | Out-String
    } finally {
        $env:TMP = $savedTmp
        $env:TEMP = $savedTemp
    }
    $leaked = @(Get-ChildItem -LiteralPath $probeTmp -Recurse -File -Filter "config.json" -ErrorAction SilentlyContinue)

    $script:LastDetail = "settings.py write_text=$($writeCalls.Count) (to user_config_path=$($writesToTarget.Count)); write_bytes=$($byteWrites.Count); TMP probe config.json leaked=$($leaked.Count) [probe weak]"
    return ($staticOk -and ($leaked.Count -eq 0))
}

# --- Summary ----------------------------------------------------------------
Write-Host ""
$passed = @($script:Results | Where-Object { $_.Passed }).Count
$total = $script:Results.Count
foreach ($r in $script:Results) {
    $mark = if ($r.Passed) { "PASS" } else { "FAIL" }
    Write-Host ("[{0}] {1}" -f $mark, $r.Name)
}
Write-Host ""
Write-Host ("RESULT: {0}/{1} PASS" -f $passed, $total)

if ($passed -eq $total) {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    exit 0
}

Write-Host ("work dir kept for inspection: {0}" -f $work) -ForegroundColor Yellow
exit 1
