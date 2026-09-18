# C API — FreeRTOS SDK

本页说明官方 FreeRTOS SDK。C 回归夹具不含该 SDK，签名取自模板 `templates/c/SDK/FreeRTOS/stnp_freertos.h.j2` / `stnp_freertos.c.j2`。

## 生成条件

当 `stnp.build.json` 的 `sdks` 包含 `"freertos"` 时生成 `SDK/FreeRTOS/stnp_freertos.h` 与 `stnp_freertos.c`。常与 `stm32_hal_uart` 同时选择。需要 `configSUPPORT_STATIC_ALLOCATION == 1`。

## `STNP_FreeRTOS_Start`

```c
STNP_Result STNP_FreeRTOS_Start(void);
```

创建 1 个 Protocol Task 和静态 Worker Pool（`xTaskCreateStatic`）。重复调用幂等，返回 `STNP_OK`。与 HAL UART 同时生成时，`STNP_HAL_UART_Init()` 会自动调用它，普通用户不必显式调用。

## `STNP_FreeRTOS_NotifyRx` / `NotifyRxFromISR`

```c
void STNP_FreeRTOS_NotifyRxFromISR(void);
void STNP_FreeRTOS_NotifyRx(void);
```

分别供 ISR transport 与任务上下文的自定义 transport 在 `STNP_Transport_Receive()` 之后唤醒 Protocol Task。官方 HAL 适配器已自动调用 ISR 版本。

## 调度语义

- Protocol Task 是协议解析的单执行者：循环调用 `STNP_Process()`，并把 Job 交给 Worker。
- Worker 可多执行者，并发调用 `STNP_Dispatch()`。
- 同一 Instance/source 串行；不同 key 可并发。
- Handler / Notify callback 在 runtime lock 外执行。
- 用户业务仍只使用 `STNP_Task_Send()` / `STNP_Notify_Send()`，签名不变。
- Core 不 include FreeRTOS；本 SDK 只提供静态任务与锁适配。自定义调度时必须提供与 weak `STNP_Runtime_Lock` / `Unlock` 等价的临界区。

## 编译期宏

| 宏 | 默认 | 约束 |
|---|---|---|
| `STNP_FREERTOS_WORKER_COUNT` | `4` | `1..16` |
| `STNP_FREERTOS_PROTOCOL_STACK_WORDS` | `256` | Protocol Task 栈 |
| `STNP_FREERTOS_WORKER_STACK_WORDS` | `256` | 每个 Worker 栈 |
| `STNP_FREERTOS_PROTOCOL_PRIORITY` | `tskIDLE_PRIORITY + 2` | Protocol Task 优先级 |
| `STNP_FREERTOS_WORKER_PRIORITY` | `tskIDLE_PRIORITY + 1` | Worker 优先级 |

使用说明见 [FreeRTOS 指南](../../06_guides/freertos.md)。

---

[← STM32 HAL UART SDK](sdk_stm32_hal_uart.md) | [文档目录](../../README.md) | [Python API →](../python/README.md)
