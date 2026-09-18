# 示例工程

0.9 起，示例与普通工程同构：一份 `<project>.stnp` 协议定义，加一份或多份
`stnp.build*.json` 生成配置。两份文件各自独立校验、互不引用；命令统一为
`stnpe generate` / `stnpe check`（源码运行时用 `python main.py generate/check`
等价）。

## 共同前提

在仓库根目录安装开发依赖（同时得到 `stnpe` 命令）：

```bash
python -m pip install -e ".[dev]"
```

## 三个示例

| 目录 | 覆盖什么 | 能在 PC 上跑吗 |
|---|---|---|
| [`handshake_c/`](handshake_c/README.md) | 最小 C 工程：typed Payload 的 `CONNECT_REQ` / `CONNECT_ACCEPT` / `CONNECT_CONFIRM` 用户级握手，mock transport，手写用户码 `handshake_user.c` | ✅ 能：`run.ps1` 生成 → gcc 编译 → 运行校验（无需硬件） |
| [`stm32_hal_uart_c/`](stm32_hal_uart_c/README.md) | C + `stm32_hal_uart` SDK + `cmake` 构建；3 个 Module / 4 个 Instance 的协议内容；CubeMX 集成说明 | ❌ 不能：需要 STM32 HAL 与硬件；`run.ps1` 只生成 |
| [`dual_multi_c_py/`](dual_multi_c_py/README.md) | 一个 `.stnp`、两种 target：LED / MOTOR 两个 Module、LedFront / LedRear / MotorLeft / MotorRight 四个 Instance；Python 上位机 + STM32 下位机 | ❌ 不能：需要串口与 STM32；`run.ps1` 生成两端并打印后续路径，不伪造运行 |

每个示例目录都包含：

- `<project>.stnp`：协议定义（Module / Instance / Protocol / `global_results`）；
- `stnp.build*.json`：生成配置（`target`、构建系统、SDK、输出布局、校验清单）；
- 手写用户码（C 的 `*_user.c` 或 Python 的 `*_logic.py`，只放在 `handshake_c/` 与 `dual_multi_c_py/`）；
- `run.ps1`：可重复执行的冒烟脚本；
- `README.md`：生成命令、配置要点、运行/集成步骤。

生成物（`*_STNP_C/`、`*_STNP_Python/`）不入库，请在 `-o` 指定的输出目录里查看。
