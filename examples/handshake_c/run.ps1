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
    [string]$Python = "",
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

function Find-Tool([string]$Name, [string]$Hint) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) { Fail "未找到 '$Name'。$Hint" }
    return $command.Source
}

# --- Python 解释器解析（与 scripts/test.ps1 同一条链） -----------------------
# 顺序：-Python 参数 -> $env:STNP_PYTHON -> 已知 conda 环境（存在性守卫）
#       -> PATH 上的 python -> PATH 上的 py。
# 本机 python 不在 PATH 上，所以不能只查 PATH。
$KnownCondaPython = "E:\develop.environment.pack\anaconda3\envs\STNP_EDITOR_ENV_py3.12\python.exe"
$TriedOrder = "-Python 参数 -> STNP_PYTHON 环境变量 -> 已知 conda 环境（$KnownCondaPython）-> PATH 上的 python -> PATH 上的 py"
$PythonExe = $null
$PythonSource = $null

if ($Python) {
    $PythonExe = $Python
    $PythonSource = "-Python 参数"
} elseif ($env:STNP_PYTHON) {
    $PythonExe = $env:STNP_PYTHON
    $PythonSource = "STNP_PYTHON 环境变量"
} elseif (Test-Path -LiteralPath $KnownCondaPython) {
    $PythonExe = $KnownCondaPython
    $PythonSource = "已知 conda 环境"
} else {
    $pythonOnPath = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonOnPath) {
        $PythonExe = & $pythonOnPath.Source -c "import sys; print(sys.executable)"
        $PythonSource = "PATH 上的 python (sys.executable)"
    } else {
        $pyOnPath = Get-Command py -ErrorAction SilentlyContinue
        if ($pyOnPath) {
            $PythonExe = & $pyOnPath.Source -c "import sys; print(sys.executable)"
            $PythonSource = "PATH 上的 py (sys.executable)"
        }
    }
}

if (-not $PythonExe) {
    Fail "未找到 Python 解释器。已依次尝试：$TriedOrder。请安装 Python 3.10+（并执行 python -m pip install -e `".[dev]`"），或先激活包含依赖的虚拟环境/conda 环境。"
}
if (-not (Test-Path -LiteralPath $PythonExe)) {
    Fail "Python 解释器不存在：$PythonExe（来源：$PythonSource）。已依次尝试：$TriedOrder。"
}
$PythonVersion = & $PythonExe -c "import sys; print(sys.version.split()[0])"
if ($LASTEXITCODE -ne 0 -or -not $PythonVersion) {
    Fail "Python 解释器无法运行：$PythonExe（来源：$PythonSource）。已依次尝试：$TriedOrder。"
}
$Python = $PythonExe
Write-Host ("python    : {0} ({1}, from {2})" -f $Python, $PythonVersion.Trim(), $PythonSource)

$Gcc = Find-Tool "gcc" "请安装 MinGW-w64 并把它的 bin 目录加入 PATH。"
$Objcopy = Find-Tool "objcopy" "objcopy 随 MinGW-w64 提供，请把它的 bin 目录加入 PATH。"

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
