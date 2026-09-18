# C API — STM32 HAL UART SDK

本页说明官方 STM32 HAL UART SDK 的生成条件与接口。C 回归夹具不含该 SDK，签名取自模板 `templates/c/SDK/STM32_HAL/stnp_hal_uart.h.j2` / `stnp_hal_uart.c.j2`。

## 生成条件与文件位置

当 `stnp.build.json` 的 `sdks` 数组包含 `"stm32_hal_uart"` 时生成：

- `SDK/STM32_HAL/stnp_hal_uart.h`
- `SDK/STM32_HAL/stnp_hal_uart.c`

C SDK 可选值来自生成器内部注册表（`src/stnp_editor/resources/config.json` 的 `sdk_registry`），当前为 `stm32_hal_uart` 与 `freertos`。

## `STNP_HAL_UART_Init`

```c
STNP_Result STNP_HAL_UART_Init(UART_HandleTypeDef *huart);
```

绑定 UART、调用 `STNP_Init(STNP_HAL_UART_Write)` 与 `STNP_Instances_Init()`，并启动 Receive-to-Idle。若同时生成 FreeRTOS SDK，成功后再调用 `STNP_FreeRTOS_Start()`。

## HAL callback 桥

```c
void STNP_HAL_UART_RxEventCallback(UART_HandleTypeDef *huart, uint16_t size);
void STNP_HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart);
void STNP_HAL_UART_ErrorCallback(UART_HandleTypeDef *huart);
```

- RX：两块静态 ping-pong 缓冲。先切换并 re-arm 另一块 Receive-to-Idle，再把已完成缓冲复制给 `STNP_Transport_Receive()`。此路径不执行用户 Handler / Notify callback。若已启动 FreeRTOS，RX 成功后调用 `STNP_FreeRTOS_NotifyRxFromISR()`。
- TX：`HAL_UART_Transmit_IT()` + 静态 FIFO。
- Error：恢复接收（`HAL_UART_ErrorCallback` 路径调用 `STNP_HAL_UART_StartReceive()`）。

## `STNP_HAL_UART_USE_GLOBAL_CALLBACKS` 与转发

默认 `STNP_HAL_UART_USE_GLOBAL_CALLBACKS` 为 `1`，SDK 提供 `HAL_UARTEx_RxEventCallback` / `HAL_UART_TxCpltCallback` / `HAL_UART_ErrorCallback` 并转发到上述桥函数。工程里已有同名 HAL 回调时，把该宏设为 `0`，在用户回调中转发到 `STNP_HAL_UART_*Callback`。

## `STNP_HAL_UART_GetRxStatus`

```c
STNP_Result STNP_HAL_UART_GetRxStatus(void);
```

返回最近一次 HAL RX 路径写入 RX Ring 的结果。Ring 满为 `STNP_ERR_BUFFER`；重新挂接失败为 `STNP_ERR_STATE`。

## ping-pong RX 与 TX FIFO

TX 队列深度由 `STNP_HAL_UART_TX_QUEUE_DEPTH` 决定（默认 `4`，合法 `1..255`）。队列满时新的发送返回 `STNP_ERR_BUFFER`。

## 编译期宏

| 宏 | 默认 | 作用 |
|---|---|---|
| `STNP_HAL_UART_HAL_HEADER` | `"main.h"` | 包含的 HAL 头 |
| `STNP_HAL_UART_RX_BUFFER_SIZE` | `256` | 每块 RX ping-pong 缓冲 |
| `STNP_HAL_UART_TX_QUEUE_DEPTH` | `4` | TX FIFO 深度 |
| `STNP_HAL_UART_USE_GLOBAL_CALLBACKS` | `1` | 是否生成全局 HAL 回调 |

集成步骤见 [STM32 HAL UART 指南](../../06_guides/stm32_hal_uart.md)。

---

[← Platform / CRC](platform.md) | [文档目录](../../README.md) | [FreeRTOS SDK →](sdk_freertos.md)
