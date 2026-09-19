# ============================================================================
# dual_multi_c_py —— 双端示例：只生成两端，不在 PC 上假装运行
#
# 这个脚本做什么：
#   用同一个 dual_multi.stnp 生成两端工程：
#     1. C 端（STM32 下位机）  -> stnp.build.c.json      -> dual_multi_STNP_C
#     2. Python 端（PC 上位机）-> stnp.build.python.json -> dual_multi_STNP_Python
#
# 为什么不运行：
#   C 端需要 STM32 HAL 与硬件；Python 端需要真实/虚拟串口（pyserial）。
#   没有串口时脚本不会伪造"运行成功"，只打印两条后续路径。
#
# 需要什么前提：
#   - Python（已 `python -m pip install -e ".[dev]"`）；
#   - Python 端真正联调时还需要 `pip install pyserial` 和一个串口设备。
# ============================================================================
[CmdletBinding()]
param(
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"

$ExampleRoot = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ExampleRoot "..\..")).Path
if (-not $OutputRoot) { $OutputRoot = Join-Path $ExampleRoot "_out" }
$Stnp = Join-Path $ExampleRoot "dual_multi.stnp"
$BuildC = Join-Path $ExampleRoot "stnp.build.c.json"
$BuildPython = Join-Path $ExampleRoot "stnp.build.python.json"

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

Write-Host "== 1/2 生成 C 端（STM32 下位机，stnp.build.c.json） =="
Push-Location -LiteralPath $RepoRoot
try {
    & $Python "main.py" generate $Stnp $BuildC -o (Join-Path $OutputRoot "c")
    if ($LASTEXITCODE -ne 0) {
        Fail "C 端生成失败（退出码 $LASTEXITCODE）。请确认已在仓库根目录执行 python -m pip install -e `".[dev]`"。"
    }

    Write-Host ""
    Write-Host "== 2/2 生成 Python 端（PC 上位机，stnp.build.python.json） =="
    & $Python "main.py" generate $Stnp $BuildPython -o (Join-Path $OutputRoot "python")
    if ($LASTEXITCODE -ne 0) {
        Fail "Python 端生成失败（退出码 $LASTEXITCODE）。"
    }
} finally {
    Pop-Location
}

$GenC = Join-Path $OutputRoot "c\dual_multi_STNP_C"
$GenPy = Join-Path $OutputRoot "python\dual_multi_STNP_Python"
Write-Host ""
Write-Host "C 端生成目录:      $GenC"
Write-Host "Python 端生成目录: $GenPy"

Write-Host ""
Write-Host "后续路径（脚本不代替你运行）:"
Write-Host "  [PC 侧上位机] 需要真实或虚拟串口："
Write-Host "    - pip install pyserial（生成的 pyproject.toml 已声明依赖）；"
Write-Host "    - 在 $GenPy 下按 stnp/sdk/uart/uart.yaml 配置 port/baudrate（或 stnp.init(port=...))；"
Write-Host "    - 编写并运行上位机脚本：stnp.task(...) 下发 Task，装饰器回调打印 Notify。"
Write-Host "  [C 侧下位机] 进 CubeMX："
Write-Host "    - 打开 UART 全局中断，add_subdirectory($GenC)（位于 stm32cubemx target 之后）；"
Write-Host "    - STNP_HAL_UART_Init(&huart1) + STNP_Instances_Init()，主循环 STNP_Process()/STNP_Dispatch()；"
Write-Host "    - 业务实现写在 $GenC\Implementation\{led_impl.c,motor_impl.c}。"
Write-Host "详见本目录 README.md 的端到端自查步骤。"

exit 0
