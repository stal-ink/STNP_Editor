# FreeRTOS SDK 使用

本页说明官方 FreeRTOS SDK：只做调度适配，协议仍在 OS 无关的 Core 中。C SDK 可选值来自生成器内部注册表（`src/stnp_editor/resources/config.json` 的 `sdk_registry`），当前含 `stm32_hal_uart` 与 `freertos`。

## 启用

推荐与 STM32 HAL UART 一起：

在 `stnp.build.json` 中选择：

```json
{
  "format": "stnp-build",
  "build_schema_version": "stnp-build-schema-alpha",
  "target": "c",
  "c": {"build_system": "mdk_arm", "emit_examples": false},
  "sdks": ["stm32_hal_uart", "freertos"]
}
```

`STNP_HAL_UART_Init(&huart1)` 会自动调用 `STNP_FreeRTOS_Start()`。

## 运行结构

```text
RX IRQ
  ↓
Core RX Ring
  ↓ notify
Protocol Task
  ↓ STNP_Process()
Core Job Queue
  ├→ Worker 1 → STNP_Dispatch()
  ├→ Worker 2 → STNP_Dispatch()
  └→ Worker N → STNP_Dispatch()
```

Handler 在普通 FreeRTOS Task context 中运行：

- 可被更高优先级任务抢占；
- 同优先级启用 time slicing 时可轮转；
- Handler 阻塞时调度器可运行其他任务；
- 不同 Instance/source Job 可并发；
- 同一 Instance/source Job 串行。
- 不同 Instance/source 的 Handler 可能真正并发；用户共享外设/全局状态仍应按业务需要同步。

## 默认配置

```c
#define STNP_FREERTOS_WORKER_COUNT          4U
#define STNP_FREERTOS_PROTOCOL_STACK_WORDS  256U
#define STNP_FREERTOS_WORKER_STACK_WORDS    256U
#define STNP_FREERTOS_PROTOCOL_PRIORITY     (tskIDLE_PRIORITY + 2U)
#define STNP_FREERTOS_WORKER_PRIORITY       (tskIDLE_PRIORITY + 1U)
```

全部使用 `xTaskCreateStatic()`，要求：

```c
configSUPPORT_STATIC_ALLOCATION == 1
```

SDK 不使用 malloc。

## 用户业务不变

用户仍只写生成的 Handler 函数体，并自由调用：

```c
STNP_Task_Send(...);
STNP_Notify_Send(...);
```

不需要创建 STNP Worker、不需要绑定 Motor1→Worker1、不需要操作 Core Job Queue。

## 高级用户

不选择 `freertos` SDK 时，Core 仍公开：

```c
STNP_Process();
STNP_Dispatch();
```

可以由用户自己的 scheduler/task 组织。若自行实现多 Worker，必须为 Core internal runtime-lock hook 提供正确的并发保护；官方 SDK 已处理该问题。

---

[← STM32 HAL UART](stm32_hal_uart.md) | [文档目录](../README.md) | [构建系统 →](build_systems.md)
