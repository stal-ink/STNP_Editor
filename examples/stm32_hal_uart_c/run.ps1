# ============================================================================
# stm32_hal_uart_c —— 只生成，不在 PC 上编译/运行
#
# 这个脚本做什么：
#   用 `python main.py generate`（等价于 `stnpe generate`）从
#   stm32_hal_uart.stnp + stnp.build.json 生成 C 工程。生成物包含
#   SDK/STM32_HAL/stnp_hal_uart.{c,h} 与 CMakeLists.txt。
#
# 为什么不能在 PC 上运行：
#   本示例选择 stm32_hal_uart SDK，生成代码依赖 STM32 HAL
#   （UART_HandleTypeDef、HAL_UARTEx_ReceiveToIdle_IT 等）和真实/仿真 STM32
#   工程，PC 上没有这些符号。脚本只做生成，并打印下一步要做的事。
#
# 需要什么前提：
#   - Python（已 `python -m pip install -e ".[dev]"`）。
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
$Stnp = Join-Path $ExampleRoot "stm32_hal_uart.stnp"
$Build = Join-Path $ExampleRoot "stnp.build.json"

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "run.ps1: ERROR: $Message" -ForegroundColor Red
    exit 1
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

if (Test-Path -LiteralPath $OutputRoot) { Remove-Item -Recurse -Force -LiteralPath $OutputRoot }
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

Write-Host "== 生成 C 工程（stm32_hal_uart SDK + CMake） =="
Push-Location -LiteralPath $RepoRoot
try {
    & $Python "main.py" generate $Stnp $Build -o $OutputRoot
    if ($LASTEXITCODE -ne 0) {
        Fail "生成失败（退出码 $LASTEXITCODE）。请确认已在仓库根目录执行 python -m pip install -e `".[dev]`"。"
    }
} finally {
    Pop-Location
}

$GenDir = Join-Path $OutputRoot "stm32_hal_uart_STNP_C"
if (-not (Test-Path -LiteralPath $GenDir)) { Fail "未找到生成目录: $GenDir" }

Write-Host ""
Write-Host "生成目录: $GenDir"
Write-Host "生成物中的 SDK:"
Get-ChildItem -LiteralPath (Join-Path $GenDir "SDK\STM32_HAL") -File | ForEach-Object { Write-Host "  SDK/STM32_HAL/$($_.Name)" }

Write-Host ""
Write-Host "下一步（本示例需要 STM32 HAL，PC 上无法运行）:"
Write-Host "  1. 在 CubeMX 工程里配置 UART（建议 115200 8N1）并打开 UART 全局中断；"
Write-Host "  2. 在 CubeMX CMake 工程中 add_subdirectory(<生成目录>)（要在 stm32cubemx target 之后）;"
Write-Host "  3. 在 main.c 中调用 STNP_HAL_UART_Init(&huart1) 与 STNP_Instances_Init()，"
Write-Host "     裸机主循环里调用 STNP_Process()/STNP_Dispatch()；"
Write-Host "  4. 业务代码写在 Implementation/<module>_impl.c 的 USER CODE 区域。"
Write-Host "详见本目录 README.md 与生成目录内的 README.md。"

exit 0
