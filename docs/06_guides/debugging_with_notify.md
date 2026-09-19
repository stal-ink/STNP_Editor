# 用 `STNP_Notify_Send()` 做运行路径打点

本页说明如何临时用 Notify 发送确认代码是否执行到某一层。发送 API 见 [C API / notify.md](../04_api/c/notify.md)。它不依赖 RX → Process → Dispatch，但依赖 TX 可用。

## 适用场景

例如要判断 STM32 HAL UART 接收回调是否真正触发，可以临时写：

```c
void STNP_HAL_UART_RxEventCallback(UART_HandleTypeDef *huart, uint16_t size)
{
    (void)STNP_Notify_Send(
        STNP_INSTANCE_CHASSISMAIN_ID,
        0x02,
        (STNP_U16)size,
        STNP_NULL
    );

    /* 原有 RX 处理继续执行 */
}
```

如果 PC 端收到包含 `size` 的 Notify，就能证明执行路径已经到达这个回调。

同理，可以把临时 Notify 放在：

- UART RX callback：确认 HAL 接收事件是否到达 STNP adapter；
- `STNP_Process()` 周围：确认 RX 数据是否进入 Core；
- Module handler（如 `Led_Turn()`）：确认 Task 已完成 Parse / Router / Dispatch；
- 用户业务关键分支：确认状态机实际走到了哪个路径。

## 它依赖什么

直接调用 `STNP_Notify_Send()` **不依赖 STNP 的 RX → Process → Dispatch 接收调度路径**。因此它适合拿来验证接收链路中的某个中间节点。

但它仍然依赖发送方向已经可用：

```text
STNP_Notify_Send()
        ↓
Notify frame build
        ↓
STNP Transport Write
        ↓
UART / other transport TX
```

因此，“收到调试 Notify”证明的是：代码执行到了打点位置，并且 TX 通道可用；它不能单独证明 RX 的其他阶段也正常。

## 使用限制

这种方式用于临时诊断，不建议作为正式日志系统。0.9.1 链路站点请用 C `STNP_DEBUG` / Python `stnp.trace.debug`，见 [链路验证](trace_and_breakpoints.md)；Notify 打点仍只是临时手段。

- 不要在高频 ISR 中持续发送大量 Notify；
- UART 中断发送可能遇到 TX FIFO 满或 `HAL_BUSY`；
- 调试发送本身会改变一定的执行时序；
- 定位完成后应删除临时打点，避免污染正式协议流量。

---

[← STM32 HAL UART](stm32_hal_uart.md) | [文档目录](../README.md) | [FreeRTOS →](freertos.md)
