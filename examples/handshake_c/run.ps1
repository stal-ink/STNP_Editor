# ============================================================================
# handshake_c —— 唯一可以在 PC 上端到端跑通的示例
#
# 这个脚本做什么：
#   1. 用 `python main.py generate`（等价于 `stnpe generate`）从
#      handshake.stnp + stnp.build.json 生成 C 工程（mock transport，无需硬件）；
#   2. 用 gcc 编译生成工程 + 手写用户码 handshake_user.c；
#   3. 运行可执行文件，并校验预期输出 "user handshake ok: token=4660"。
#
# 需要什么前提：
#   - Python（已 `python -m pip install -e ".[dev]"`，本仓库根目录下执行过）；
#   - gcc 与 objcopy 在 PATH 中（MinGW-w64；`objcopy` 用来把生成侧的
#     Link_ConnectReq / Link_ConnectConfirm 用户钩子兜底降级为 weak，
#     使 handshake_user.c 的强符号生效）。
#
# 找不到工具或任何一步失败时，脚本会打印可操作提示并以非 0 退出。
# 脚本不会伪造运行结果。
# ============================================================================
[CmdletBinding()]
param(
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"

$ExampleRoot = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ExampleRoot "..\..")).Path
if (-not $OutputRoot) { $OutputRoot = Join-Path $ExampleRoot "_out" }
$Stnp = Join-Path $ExampleRoot "handshake.stnp"
$Build = Join-Path $ExampleRoot "stnp.build.json"
$UserSource = Join-Path $ExampleRoot "handshake_user.c"

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "run.ps1: ERROR: $Message" -ForegroundColor Red
    exit 1
}

# 共享工具链解析器（scripts/toolchain.ps1）：全仓同一解析顺序（STNP_* 环境变量
# -> PATH -> 明确失败），不再内置任何本机路径。
. (Join-Path $RepoRoot "scripts\toolchain.ps1")
Write-StnpToolchainDisclaimer

# --- Python 解释器解析（与 scripts/test.ps1 同一条链） -----------------------
try {
    $ResolvedPython = Resolve-StnpPython
} catch {
    Fail $_.Exception.Message
}
$Python = $ResolvedPython.Path
Write-Host (Format-StnpToolLine -Resolved $ResolvedPython)
$otherPython = @(Get-StnpOtherCandidates -Resolved $ResolvedPython)
if ($otherPython.Count -gt 0) { Write-Host ("其它候选：{0}" -f ($otherPython -join "; ")) }

try {
    $ResolvedGcc = Resolve-StnpGcc
} catch {
    Fail $_.Exception.Message
}
$Gcc = $ResolvedGcc.Path
Write-Host (Format-StnpToolLine -Resolved $ResolvedGcc)
$otherGcc = @(Get-StnpOtherCandidates -Resolved $ResolvedGcc)
if ($otherGcc.Count -gt 0) { Write-Host ("其它候选：{0}" -f ($otherGcc -join "; ")) }

# objcopy 与 gcc 同目录（MinGW-w64），其次才查 PATH。
$Objcopy = Join-Path $ResolvedGcc.Directory "objcopy.exe"
if (-not (Test-Path -LiteralPath $Objcopy)) {
    $objcopyCommand = Get-Command objcopy -ErrorAction SilentlyContinue
    if ($objcopyCommand) { $Objcopy = $objcopyCommand.Source }
}
if (-not (Test-Path -LiteralPath $Objcopy)) {
    Fail "未找到 'objcopy'。objcopy 随 MinGW-w64 提供，请把它的 bin 目录加入 PATH。"
}

if (Test-Path -LiteralPath $OutputRoot) { Remove-Item -Recurse -Force -LiteralPath $OutputRoot }
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

Write-Host "== 1/3 生成 C 工程 =="
Push-Location -LiteralPath $RepoRoot
try {
    & $Python "main.py" generate $Stnp $Build -o $OutputRoot
    if ($LASTEXITCODE -ne 0) {
        Fail "生成失败（退出码 $LASTEXITCODE）。请确认已在仓库根目录执行 python -m pip install -e `".[dev]`"。"
    }
} finally {
    Pop-Location
}

$GenDir = Join-Path $OutputRoot "handshake_STNP_C"
if (-not (Test-Path -LiteralPath $GenDir)) { Fail "未找到生成目录: $GenDir" }
Write-Host "生成目录: $GenDir"

Write-Host ""
Write-Host "== 2/3 编译（含用户码弱符号处理） =="

$sources = @()
foreach ($directory in @("Core", "Module", "Instance")) {
    $sources += Get-ChildItem -LiteralPath (Join-Path $GenDir $directory) -Recurse -Filter *.c |
        ForEach-Object { $_.FullName }
}
$implSource = Get-ChildItem -LiteralPath (Join-Path $GenDir "Implementation") -Filter "*_impl.c" | Select-Object -First 1
if (-not $implSource) { Fail "生成目录缺少 Implementation/<module>_impl.c。" }

# 生成的 *_impl.c 携带 Link_ConnectReq / Link_ConnectConfirm 的用户钩子兜底和
# Link_ValidateGenerated()。先把钩子符号弱化，再让 handshake_user.c 的强符号覆盖。
$implObject = Join-Path $OutputRoot "link_impl.o"
& $Gcc "-std=c99" "-Wall" "-Wextra" "-Werror" "-pedantic" "-I$GenDir" "-c" $implSource.FullName "-o" $implObject
if ($LASTEXITCODE -ne 0) { Fail "编译 $($implSource.Name) 失败。" }
& $Objcopy "--weaken-symbol=Link_ConnectReq" "--weaken-symbol=Link_ConnectConfirm" $implObject
if ($LASTEXITCODE -ne 0) { Fail "objcopy 弱化用户钩子失败。" }

# 不编译 Examples/main.c：本示例的 main() 在 handshake_user.c 中。
$exe = Join-Path $OutputRoot "handshake.exe"
$linkArgs = @("-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I$GenDir")
$linkArgs += $sources
$linkArgs += @(
    $implObject,
    (Join-Path $GenDir "Implementation\stnp_notify_callback.c"),
    (Join-Path $GenDir "Examples\transport_mock.c"),
    $UserSource,
    "-o", $exe
)
& $Gcc @linkArgs
if ($LASTEXITCODE -ne 0) { Fail "链接失败。" }
Write-Host "可执行文件: $exe"

Write-Host ""
Write-Host "== 3/3 运行并校验预期输出 =="
$runOutput = & $exe
$runExit = $LASTEXITCODE
$runOutput | ForEach-Object { Write-Host $_ }
if ($runExit -ne 0) { Fail "可执行文件退出码 $runExit，预期 0。" }
$runText = $runOutput -join "`n"
if ($runText -notmatch "user handshake ok: token=4660") {
    Fail "输出中没有预期行 'user handshake ok: token=4660'；请检查 handshake_user.c 是否被改动。"
}

Write-Host ""
Write-Host "PASS: handshake 示例在 PC 上端到端运行成功。" -ForegroundColor Green
exit 0
