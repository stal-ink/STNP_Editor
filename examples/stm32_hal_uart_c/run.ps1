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
