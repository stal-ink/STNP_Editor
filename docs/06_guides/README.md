# 6. 使用指南

本页按任务分组：C 集成、Python 集成、通用。签名以 [API](../04_api/README.md) 为准；分层原因见 [架构说明](../05_architecture/README.md)。

## C 集成

| 指南 | 一句话 |
|---|---|
| [STM32 HAL UART](stm32_hal_uart.md) | 官方 UART SDK：Receive-to-Idle、ping-pong、TX FIFO |
| [FreeRTOS](freertos.md) | Protocol Task + Worker Pool；用户仍只调用 Task/Notify 发送 |
| [构建系统](build_systems.md) | CMake / MDK-ARM、`stnp` 库与 INTERFACE_SOURCES |
| [USER CODE](user_code.md) | 重新生成时保留 Includes / Private / 函数体 |
| [用 Notify 打点](debugging_with_notify.md) | `STNP_Notify_Send()` 做临时路径确认 |

## Python 集成

| 指南 | 一句话 |
|---|---|
| [Python 使用](python_usage.md) | 从生成到实现 CMD、校验、Notify 与 UART 联调 |
| [Python UART](python_uart.md) | `stnp.sdk.uart`、pyserial、uart.yaml、一次 write |

完整签名见 [Python API](../04_api/python/README.md)。

## 通用

| 指南 | 一句话 |
|---|---|
| [多实例](multi_instance.md) | 一个 Module 多个 Instance；只用 `STNP_INSTANCE_*_ID` |
| [CRC 与流式接收](crc_and_stream.md) | 生成期 CRC、1 字节滑动重同步 |

---

[← 架构说明](../05_architecture/README.md) | [文档目录](../README.md) | [Python 使用 →](python_usage.md)
