# STM32 HAL UART SDK 集成

本页说明如何启用官方 STM32 HAL UART SDK，以及裸机最小循环、RX/TX 与 CubeMX + CMake 要点。API 签名见 [C API / sdk_stm32_hal_uart.md](../04_api/c/sdk_stm32_hal_uart.md)。仓库示例：`examples/stm32_hal_uart_c`。

- RX：`HAL_UARTEx_ReceiveToIdle_IT()`；
- TX：`HAL_UART_Transmit_IT()` + 固定静态 FIFO；
- UART Error/ORE 自动恢复；
- RX IRQ **不再执行 Parse/Handler/Notify Callback**。

## 1. 启用

在 `stnp.build.json` 中选择：

```json
{
  "format": "stnp-build",
  "build_schema_version": "stnp-build-schema-alpha",
  "target": "c",
  "c": {"build_system": "mdk_arm", "emit_examples": false},
  "sdks": ["stm32_hal_uart"]
}
```

## 2. 裸机最小使用

应用无需再单独添加 `SDK/STM32_HAL` include 路径；选择该 SDK 后，公共 `stnp.h` 会导出 HAL UART API。

```c
#include "stnp.h"

(void)STNP_HAL_UART_Init(&huart1);

for (;;)
{
    (void)STNP_Process();
    (void)STNP_Dispatch();
    /* Application code */
}
```

业务发送仍然只有：

```c
(void)STNP_Task_Send(...);
(void)STNP_Notify_Send(...);
```

## 3. RX 路径

```text
HAL UART IRQ
  ↓
切换到另一块 RX ping-pong buffer 并重新挂接 Receive-to-Idle
  ↓
把已完成 buffer 复制到 STNP_Transport_Receive(bytes)
  ↓
RX Ring
  ↓
return IRQ
```

`STNP_HAL_UART_GetRxStatus()` 可读取最近一次 RX 路径结果；Core Ring 满时为 `STNP_ERR_BUFFER`，重新挂接失败时为 `STNP_ERR_STATE`。两块静态 RX buffer 避免“先重挂后复制”时新字节覆盖刚完成的数据。

不承诺固定微秒数；保证的是 IRQ 路径只执行有界缓冲操作，不进入用户 Handler/Callback。

## 4. TX FIFO

默认：

```c
#define STNP_HAL_UART_TX_QUEUE_DEPTH 4U
```

满时新的 Send 返回 `STNP_ERR_BUFFER`，旧帧不会覆盖。FIFO 操作使用很短的 IRQ 临界区，可安全承受 IRQ + RTOS Worker 并发发送。

## 5. Error Recovery

`HAL_UART_ErrorCallback()`：

```text
HAL_UART_AbortReceive
→ HAL_UARTEx_ReceiveToIdle_IT
```

## 6. 已有 HAL callbacks

设置：

```c
#define STNP_HAL_UART_USE_GLOBAL_CALLBACKS 0
```

然后转发：

```c
STNP_HAL_UART_RxEventCallback(huart, size);
STNP_HAL_UART_TxCpltCallback(huart);
STNP_HAL_UART_ErrorCallback(huart);
```

## 7. 与 FreeRTOS SDK 组合

同时选择：

```json
"sdks": ["stm32_hal_uart", "freertos"]
```

仍只调用：

```c
(void)STNP_HAL_UART_Init(&huart1);
```

HAL SDK 会自动启动 FreeRTOS Protocol Task + Worker Pool，并在 RX IRQ 后通知 Protocol Task；应用无需手写 STNP 调度任务。

## CubeMX + CMake 要点

`c.build_system` 选 `cmake` 时，在 CubeMX 创建 `stm32cubemx` target 之后 `add_subdirectory(STNP)` 并链接 `stnp`。详见 [构建系统](build_systems.md) 与 `examples/stm32_hal_uart_c/README.md`。PC 上没有 HAL 时 `run.ps1` 只生成。

---

[← USER CODE](user_code.md) | [文档目录](../README.md) | [FreeRTOS →](freertos.md)
