<#
.SYNOPSIS
    Shared developer-toolchain resolver: one resolution order, two thin implementations.

.DESCRIPTION
    PowerShell twin of `tests/_toolchain.py`; both implement the same three levels and
    `tests/test_toolchain.py` compares their contracts (order, environment variable
    names, failure wording) so the two cannot drift.

    Resolution order (rev.2):
      1. environment variable STNP_PYTHON / STNP_MINGW_BIN / STNP_CMAKE_BIN / STNP_GIT
                            optional override; SET but unusable -> loud error, NO fallback
      2. PATH lookup        the first match is ADOPTED; ALL candidates are listed
      3. loud failure   one line of install guidance, non-zero exit

    The resolver only detects and reports: it runs a minimal usability check per tool --
    a candidate that cannot run its job is not adopted and its one-line reason is listed
    -- but it never decides for the user whether the adopted toolchain suits the target
    platform.  Correctness of the chosen toolchain is the user's to verify.

    Dot-source this file to load `Resolve-StnpPython`, `Resolve-StnpGcc`,
    `Resolve-StnpCmake`, `Resolve-StnpGit`, `Write-StnpToolReport` and
    `Write-StnpToolchainDisclaimer`.  Running it directly is a small diagnostic CLI:

        powershell -File scripts/toolchain.ps1 -Help
        powershell -File scripts/toolchain.ps1 -Tool gcc
        powershell -File scripts/toolchain.ps1 -Contract -AsJson

.PARAMETER Tool
    Diagnostic CLI: resolve one tool and print the D11 report line, or fail non-zero.

.PARAMETER Contract
    Print this resolver's contract as JSON (order / names / wording) and exit.

.PARAMETER AsJson
    Print the resolution result as JSON instead of the human report.

.PARAMETER Help
    Print the resolution order and the D12 disclaimer, then exit.
#>
[CmdletBinding()]
param(
    [ValidateSet("", "python", "gcc", "cmake", "git")]
    [string]$Tool = "",
    [switch]$Contract,
    [switch]$AsJson,
    [switch]$Help
)

# allow: SIZE_OK -- the three-level order, the per-tool usability checks and the
# reporting helpers live in ONE file on purpose: tests/_toolchain.py is the Python
# twin compared against this file verbatim, and splitting the checks from the
# reporting would let the two implementations drift exactly where this design forbids it.

# Top-level statements run only while loading; callers dot-source this file.  The
# CLI branches below run only when the file is invoked directly with arguments.
$script:StnpRepoRoot = Split-Path -Parent $PSScriptRoot
$script:StnpOrder = @("env", "path", "fail")
$script:StnpEnvVars = @{ python = "STNP_PYTHON"; gcc = "STNP_MINGW_BIN"; cmake = "STNP_CMAKE_BIN"; git = "STNP_GIT" }
$script:StnpBinaries = @{ python = "python"; gcc = "gcc"; cmake = "cmake"; git = "git" }
$script:StnpMinCmake = "3.20"
$script:StnpDisclaimer = "工具链由本机环境决定，软件不保证其正确或匹配；请自行确认。"
$script:StnpFailureTemplates = @{
    python = 'STNP toolchain: python 未找到。请安装满足 requires-python 的 Python（并执行 python -m pip install -e ".[dev]"），或用 STNP_PYTHON 指定解释器。'
    gcc    = 'STNP toolchain: gcc 未找到。请安装 MinGW-w64（x86_64 主机目标）并把其 bin 目录加入 PATH，或用 STNP_MINGW_BIN 指定该目录。'
    cmake  = 'STNP toolchain: cmake 未找到。请安装 CMake >= {0} 并把其 bin 目录加入 PATH，或用 STNP_CMAKE_BIN 指定该目录。'
    git    = 'STNP toolchain: git 未找到。请安装 Git 并把 cmd 目录加入 PATH，或用 STNP_GIT 指定 git 可执行文件。'
}
$script:StnpIdentityTemplates = @{
    gcc_run        = 'STNP toolchain: gcc 身份校验失败：{0} 无法运行 gcc -dumpmachine（{1}）。'
    cmake_run      = 'STNP toolchain: cmake 身份校验失败：{0} 无法运行 cmake --version（{1}）。'
    cmake_version  = 'STNP toolchain: cmake 身份校验失败：{0} 版本 {1} 低于要求的 {2}。'
    python_run     = 'STNP toolchain: python 身份校验失败：{0} 无法运行（{1}）。'
    python_version = 'STNP toolchain: python 身份校验失败：{0} 版本 {1} 不满足 requires-python（{2}）。'
    python_import  = 'STNP toolchain: python 身份校验失败：{0} 无法 import stnp_editor（{1}）。仅用于 PyInstaller 打包的解释器可用 -RequireImport:$false 跳过本项。'
    git_run        = 'STNP toolchain: git 身份校验失败：{0} 无法运行 git --version（{1}）。'
}
$script:StnpDeclaredInvalidTemplate = 'STNP toolchain: {0} 指定的 {1} 不可用：{2}。已声明的位置不会静默回退到 PATH；请修正该设置。'

function Test-StnpWindows {
    return ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT)
}

function Get-StnpPathExtensions {
    if (Test-StnpWindows) { return @("", ".exe", ".cmd", ".bat") }
    return @("")
}

function Get-StnpWhich {
    param([string]$Name, [string]$Directory)
    foreach ($extension in (Get-StnpPathExtensions)) {
        $candidate = Join-Path $Directory ($Name + $extension)
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

function Invoke-StnpCapture {
    param([string]$FilePath, [string[]]$Arguments)
    # PS 5.1 turns redirected native stderr into a terminating error when
    # $ErrorActionPreference is Stop, so the capture is scoped to Continue.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $stdout = (& $FilePath @Arguments 2>$null | Out-String)
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    return [pscustomobject]@{ ExitCode = $code; Stdout = $stdout }
}

function Get-StnpShortDetail {
    param([string]$Text)
    $line = ($Text -split "`r?`n")[0]
    if (-not $line) { return "" }
    if ($line.Length -gt 160) { return $line.Substring(0, 160) }
    return $line
}

function ConvertTo-StnpVersion {
    param([string]$Text)
    $parts = New-Object System.Collections.ArrayList
    foreach ($chunk in ($Text -split '\.')) {
        $match = [regex]::Match($chunk, '^\d+')
        [void]$parts.Add($(if ($match.Success) { [int]$match.Value } else { 0 }))
    }
    return , @($parts)
}

function Compare-StnpVersion {
    param([int[]]$Left, [int[]]$Right)
    $size = [Math]::Max($Left.Count, $Right.Count)
    for ($i = 0; $i -lt $size; $i++) {
        $a = if ($i -lt $Left.Count) { $Left[$i] } else { 0 }
        $b = if ($i -lt $Right.Count) { $Right[$i] } else { 0 }
        if ($a -gt $b) { return 1 }
        if ($a -lt $b) { return -1 }
    }
    return 0
}

function Test-StnpVersionSatisfies {
    param([string]$Version, [string]$Specifier)
    $current = ConvertTo-StnpVersion -Text $Version
    foreach ($clause in ($Specifier -split ',')) {
        $match = [regex]::Match($clause.Trim(), '^(>=|<=|==|!=|>|<|~=)\s*(\d+(?:\.\d+)*)$')
        if (-not $match.Success) { continue }
        $op = $match.Groups[1].Value
        $bound = ConvertTo-StnpVersion -Text $match.Groups[2].Value
        $order = Compare-StnpVersion -Left $current -Right $bound
        switch ($op) {
            '>=' { if ($order -lt 0) { return $false } }
            '<=' { if ($order -gt 0) { return $false } }
            '==' { if ($order -ne 0) { return $false } }
            '!=' { if ($order -eq 0) { return $false } }
            '>' { if ($order -le 0) { return $false } }
            '<' { if ($order -ge 0) { return $false } }
            '~=' { if ($order -lt 0 -or $current[0] -ne $bound[0]) { return $false } }
        }
    }
    return $true
}

function Get-StnpRequiresPython {
    $pyproject = Join-Path $script:StnpRepoRoot "pyproject.toml"
    $text = Get-Content -LiteralPath $pyproject -Raw -Encoding UTF8
    $match = [regex]::Match($text, 'requires-python\s*=\s*"([^"]+)"')
    if (-not $match.Success) {
        throw 'STNP toolchain: pyproject.toml 缺少 requires-python，无法校验 Python 版本。'
    }
    return $match.Groups[1].Value
}

function New-StnpIdentityError {
    param([string]$Key, [object[]]$Values)
    return ($script:StnpIdentityTemplates[$Key] -f $Values)
}

function Get-StnpGccDetail {
    param([string]$Path)
    $result = Invoke-StnpCapture -FilePath $Path -Arguments @("-dumpmachine")
    $triple = $result.Stdout.Trim()
    if ($result.ExitCode -ne 0 -or -not $triple) {
        throw (New-StnpIdentityError -Key "gcc_run" -Values @($Path, ("exit {0}" -f $result.ExitCode)))
    }
    return $triple
}

function Get-StnpCmakeDetail {
    param([string]$Path)
    $result = Invoke-StnpCapture -FilePath $Path -Arguments @("--version")
    $match = [regex]::Match($result.Stdout, 'cmake version (\d+\.\d+(?:\.\d+)?)')
    if ($result.ExitCode -ne 0 -or -not $match.Success) {
        throw (New-StnpIdentityError -Key "cmake_run" -Values @($Path, ("exit {0}" -f $result.ExitCode)))
    }
    $version = $match.Groups[1].Value
    if (-not (Test-StnpVersionSatisfies -Version $version -Specifier (">=" + $script:StnpMinCmake))) {
        throw (New-StnpIdentityError -Key "cmake_version" -Values @($Path, $version, $script:StnpMinCmake))
    }
    return $version
}

function Get-StnpPythonDetail {
    param([string]$Path, [bool]$RequireImport = $true)
    $result = Invoke-StnpCapture -FilePath $Path -Arguments @("-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])")
    $version = $result.Stdout.Trim()
    if ($result.ExitCode -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') {
        throw (New-StnpIdentityError -Key "python_run" -Values @($Path, ("exit {0}" -f $result.ExitCode)))
    }
    $required = Get-StnpRequiresPython
    if (-not (Test-StnpVersionSatisfies -Version $version -Specifier $required)) {
        throw (New-StnpIdentityError -Key "python_version" -Values @($Path, $version, $required))
    }
    if ($RequireImport) {
        $importCheck = Invoke-StnpCapture -FilePath $Path -Arguments @("-c", "import stnp_editor")
        if ($importCheck.ExitCode -ne 0) {
            throw (New-StnpIdentityError -Key "python_import" -Values @($Path, ("exit {0}" -f $importCheck.ExitCode)))
        }
    }
    return $version
}

function Get-StnpGitDetail {
    param([string]$Path)
    $result = Invoke-StnpCapture -FilePath $Path -Arguments @("--version")
    $text = $result.Stdout.Trim()
    if ($result.ExitCode -ne 0 -or -not $text.StartsWith("git version ")) {
        throw (New-StnpIdentityError -Key "git_run" -Values @($Path, ("exit {0}" -f $result.ExitCode)))
    }
    return $text.Substring("git version ".Length)
}

function Get-StnpToolDetail {
    param([string]$Name, [string]$Path, [bool]$RequireImport = $true)
    switch ($Name) {
        "gcc" { return Get-StnpGccDetail -Path $Path }
        "cmake" { return Get-StnpCmakeDetail -Path $Path }
        "python" { return Get-StnpPythonDetail -Path $Path -RequireImport $RequireImport }
        "git" { return Get-StnpGitDetail -Path $Path }
        default { throw "unknown tool: $Name" }
    }
}

function Get-StnpPathCandidates {
    param([string]$Name)
    $entries = @($env:PATH -split ([IO.Path]::PathSeparator) | Where-Object { $_ -ne "" })
    $total = $entries.Count
    $candidates = New-Object System.Collections.ArrayList
    $seen = @{}
    for ($index = 0; $index -lt $total; $index++) {
        $found = Get-StnpWhich -Name $Name -Directory $entries[$index]
        if (-not $found) { continue }
        $full = (Get-Item -LiteralPath $found).FullName
        $key = $full.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        [void]$candidates.Add([pscustomobject]@{ Path = $full; Source = ("PATH #{0} of {1}" -f ($index + 1), $total) })
    }
    return @($candidates)
}

function Resolve-StnpTool {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("python", "gcc", "cmake", "git")]
        [string]$Name,
        [bool]$RequireImport = $true
    )
    $declaredValue = [Environment]::GetEnvironmentVariable($script:StnpEnvVars[$Name])
    if ($declaredValue) {
        $path = $declaredValue
        if (Test-Path -LiteralPath $path -PathType Container) {
            $found = Get-StnpWhich -Name $script:StnpBinaries[$Name] -Directory $path
            if ($found) { $path = (Get-Item -LiteralPath $found).FullName }
            else { $path = Join-Path $path $script:StnpBinaries[$Name] }
        }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw ($script:StnpDeclaredInvalidTemplate -f $script:StnpEnvVars[$Name], $Name, $declaredValue)
        }
        $detail = Get-StnpToolDetail -Name $Name -Path $path -RequireImport $RequireImport
        return [pscustomobject]@{
            Name       = $Name
            Path       = $path
            Directory  = (Split-Path -Parent $path)
            Source     = $script:StnpEnvVars[$Name]
            Detail     = $detail
            Candidates = @([pscustomobject]@{ Path = $path; Source = $script:StnpEnvVars[$Name]; Adopted = $true; RejectedReason = $null })
        }
    }

    $candidates = @(Get-StnpPathCandidates -Name $script:StnpBinaries[$Name])
    $adoptedIndex = -1
    $detail = ""
    $rejected = @{}
    for ($index = 0; $index -lt $candidates.Count; $index++) {
        try {
            $detail = Get-StnpToolDetail -Name $Name -Path $candidates[$index].Path -RequireImport $RequireImport
        } catch {
            # Detect and report: an unusable candidate is skipped, never a global stop.
            $rejected[$index] = Get-StnpShortDetail -Text $_.Exception.Message
            continue
        }
        $adoptedIndex = $index
        break
    }
    if ($adoptedIndex -lt 0) {
        throw ($script:StnpFailureTemplates[$Name] -f $script:StnpMinCmake)
    }
    $listing = New-Object System.Collections.ArrayList
    for ($index = 0; $index -lt $candidates.Count; $index++) {
        [void]$listing.Add([pscustomobject]@{
            Path           = $candidates[$index].Path
            Source         = $candidates[$index].Source
            Adopted        = ($index -eq $adoptedIndex)
            RejectedReason = $(if ($rejected.ContainsKey($index)) { $rejected[$index] } else { $null })
        })
    }
    return [pscustomobject]@{
        Name       = $Name
        Path       = $candidates[$adoptedIndex].Path
        Directory  = (Split-Path -Parent $candidates[$adoptedIndex].Path)
        Source     = $candidates[$adoptedIndex].Source
        Detail     = $detail
        Candidates = @($listing)
    }
}

function Resolve-StnpPython {
    param([bool]$RequireImport = $true)
    return Resolve-StnpTool -Name "python" -RequireImport $RequireImport
}

function Resolve-StnpGcc {
    return Resolve-StnpTool -Name "gcc"
}

function Resolve-StnpCmake {
    return Resolve-StnpTool -Name "cmake"
}

function Resolve-StnpGit {
    return Resolve-StnpTool -Name "git"
}

function Format-StnpToolLine {
    param([pscustomobject]$Resolved)
    return ("{0} : {1} (from {2}, {3})" -f $Resolved.Name, $Resolved.Path, $Resolved.Source, $Resolved.Detail)
}

function Get-StnpOtherCandidates {
    param([pscustomobject]$Resolved)
    return @($Resolved.Candidates | Where-Object { -not $_.Adopted } | ForEach-Object {
            if ($_.RejectedReason) { "{0} (from {1}，拒绝：{2})" -f $_.Path, $_.Source, $_.RejectedReason }
            else { "{0} (from {1})" -f $_.Path, $_.Source }
        })
}

function Write-StnpToolReport {
    param([pscustomobject]$Resolved)
    Write-Host (Format-StnpToolLine -Resolved $Resolved)
    $others = @(Get-StnpOtherCandidates -Resolved $Resolved)
    if ($others.Count -gt 0) {
        Write-Host ("其它候选：{0}" -f ($others -join "; "))
    }
}

function Write-StnpToolchainDisclaimer {
    Write-Host ("[工具链] {0}" -f $script:StnpDisclaimer)
}

function Get-StnpToolchainContract {
    return [pscustomobject]@{
        order                   = @($script:StnpOrder)
        env_vars                = $script:StnpEnvVars
        failure_templates       = $script:StnpFailureTemplates
        identity_templates      = $script:StnpIdentityTemplates
        declared_invalid_template = $script:StnpDeclaredInvalidTemplate
        disclaimer              = $script:StnpDisclaimer
        min_cmake               = $script:StnpMinCmake
        python_requires         = Get-StnpRequiresPython
    }
}

# --- Direct-invocation CLI (skipped entirely when the file is dot-sourced) -----
if ($Help) {
    # Force UTF-8 stdout so the Chinese wording survives a redirected pipe; the
    # change is non-fatal by design and never aborts the diagnostic CLI.
    try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { }
    Write-Host "scripts/toolchain.ps1 - shared developer-toolchain resolver (STNP)"
    Write-Host ""
    Write-Host "Resolution order (identical to tests/_toolchain.py):"
    Write-Host "  1. environment variable STNP_PYTHON / STNP_MINGW_BIN / STNP_CMAKE_BIN / STNP_GIT"
    Write-Host "                          optional override; SET but unusable -> loud error, no fallback"
    Write-Host "  2. PATH lookup          the first match is adopted; all candidates are printed"
    Write-Host "  3. loud failure     one line of install guidance, non-zero exit"
    Write-Host ""
    Write-Host "The resolver detects and reports; it does not judge whether the adopted"
    Write-Host "toolchain suits your target platform -- verify that yourself."
    Write-Host ("[工具链] {0}" -f $script:StnpDisclaimer)
    exit 0
}

if ($Contract) {
    # Force UTF-8 stdout so the Chinese wording survives a redirected pipe; the
    # change is non-fatal by design and never aborts the diagnostic CLI.
    try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { }
    Write-Output ((Get-StnpToolchainContract) | ConvertTo-Json -Depth 5 -Compress)
    exit 0
}

if ($Tool) {
    try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { }
    $resolved = $null
    try {
        $resolved = Resolve-StnpTool -Name $Tool
    } catch {
        [Console]::Error.WriteLine($_.Exception.Message)
        exit 2
    }
    if ($AsJson) {
        Write-Output ($resolved | ConvertTo-Json -Depth 5 -Compress)
    } else {
        Write-StnpToolReport -Resolved $resolved
    }
    exit 0
}
