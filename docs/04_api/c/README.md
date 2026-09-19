# C API 总览

本页给 C 集成者：说明生成代码的 include 关系、API 分类，以及 Core `STNP_Result` 与 Module Result 的层级区别。具体函数签名见后续各页。

## 生成代码的 include 关系

业务 `.c` 不要再手写 Core / Module 头。跨实例发送使用 `STNP_INSTANCE_<INSTANCE>_ID`，0.9 已删除 `<MODULE>_ID`。

`Implementation/*.c` 由模板自动包含实例汇总头：

```c
#include "../Instance/stnp_instances.h"
```

`stnp_instances.h` 汇总 Core 发送/接收 API、各 Module 声明和 `STNP_INSTANCE_<INSTANCE>_ID`。业务函数中可直接调用 `STNP_Task_Send()` / `STNP_Notify_Send()`，也可跨 Module、跨实例发送，不必再手写 Core 或 Module 头文件。

移植层若不需要实例信息，可以只包含 `Core/stnp.h`。该头是应用唯一推荐入口：同时暴露 Core、生成的 Module/Instance，以及已选择的官方 SDK 公共接口。

## API 分类

| 分类 | 文档 | 主要接口 |
|---|---|---|
| Core / Transport | [core.md](core.md) | `STNP_Init`、`STNP_Transport_Receive`、`STNP_Process`、`STNP_Dispatch`、`STNP_Transport_Write`、未知帧两道闸 |
| Task | [task.md](task.md) | `STNP_Task_Send`、`STNP_Task_SendBytes`、`STNP_Task_SendBytes_Impl` |
| Notify | [notify.md](notify.md) | `STNP_Notify_Send`、`STNP_Notify_SendBytes`、独占接收分发 |
| Module | [module.md](module.md) | `<Module>_Init`、`<Module>_SetValidate`、`<Module>_ValidateGenerated`、业务函数、Notify callback、`NotifyCallbackIsEnabled` |
| Router / VTL | [router_vtl.md](router_vtl.md) | `STNP_Router_Register`、`STNP_VTL_Encode` / `Decode` |
| Platform / CRC | [platform.md](platform.md) | 固定宽度类型、宏、Codec、`STNP_CRC16`、**仅** `STNP_DEBUG` 0/1 |
| SDK / STM32 HAL UART | [sdk_stm32_hal_uart.md](sdk_stm32_hal_uart.md) | `STNP_HAL_UART_Init`、RX/TX/Error 桥 |
| SDK / FreeRTOS | [sdk_freertos.md](sdk_freertos.md) | `STNP_FreeRTOS_Start`、`NotifyRx` / `NotifyRxFromISR` |

## `STNP_Result` 返回码

定义于 `Core/stnp_core.h`：

| 符号 | 值 | 含义 |
|---|---|---|
| `STNP_OK` | `0x0000` | 成功 |
| `STNP_ERR_LENGTH` | `0x0001` | 长度不合法 |
| `STNP_ERR_TARGET` | `0x0002` | 目标实例不存在 |
| `STNP_ERR_COMMAND` | `0x0003` | 命令/通知码无法解析 |
| `STNP_ERR_PARAM` | `0x0004` | 参数不合法 |
| `STNP_ERR_STATE` | `0x0005` | 状态不允许该操作 |
| `STNP_IDLE` | `0x0006` | 本次 Process/Dispatch 无可执行工作 |
| `STNP_ERR_BUFFER` | `0x0007` | 静态 RX / Job 缓冲容量不足 |

## Core Result 与 Module Result

`STNP_Result` 描述协议栈与运行时执行结果（能否入队、能否编码、缓冲是否满）。各 Module 另有 `<Module>_Result`（例如 `Sensor_Result`），取值来自该 Module 的 Return Code 分段，出现在 Notify 帧的 `RESULT` 槽与校验回调返回值中。二者不是同一枚举，不要互相赋值当同一层级使用。

工程级结果码（Global Result）中的 `OK`（`0x0000`）表示链路成功；Module 级 `OK` 表示该 Module 处理成功。二者共用 Notify 帧的 `RESULT` 槽，按值区间判定；`STNP_Result` 不上 wire。详见冻结规范 §5。

初始化顺序：先 `STNP_Init(write_fn)`，再 `STNP_Instances_Init()`。IRQ 只调用 `STNP_Transport_Receive()`；主循环或 Protocol Task 调用 `STNP_Process()` / `STNP_Dispatch()`。

---

[← API 索引](../README.md) | [文档目录](../../README.md) | [Core →](core.md)
