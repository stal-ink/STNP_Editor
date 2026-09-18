# regression_c

本目录由 STNP Editor 0.9.0 从 `regression_c` 生成。

## 运行模型

```text
Transport RX
  ↓
STNP_Transport_Receive()   只入 RX Ring
  ↓
STNP_Process()             最多推进 1 帧
  ↓
Job Queue
  ↓
STNP_Dispatch()            最多执行 1 个 Job
  ↓
Handler / Notify Callback
```

`STNP_Task_Send()` / `STNP_Notify_Send()` 的自由调用语义不变；发送不要求位于 Process/Dispatch 中。

## 构建系统

当前选择：**MDK-ARM**。

MDK-ARM 模式不生成 `CMakeLists.txt`。继续由 CubeMX/Keil 管理工程，生成器保持 `.c` basename 唯一，避免 MDK 对象文件冲突。

## 裸机

```c
(void)STNP_Init(MyTransportWrite);
(void)STNP_Instances_Init();

for (;;)
{
    (void)STNP_Process();
    (void)STNP_Dispatch();
    /* Application code */
}
```

底层收到任意碎片/粘包 bytes：

```c
(void)STNP_Transport_Receive(rx, rx_len);
```

Receive 不执行用户 Handler/Callback。

## 静态容量

`Platform/stnp_platform_config.h`：

```c
STNP_FRAME_MAX_SIZE
STNP_RX_RING_SIZE       /* 默认 4 × max frame */
STNP_JOB_QUEUE_DEPTH    /* 默认 8 */
```

无 malloc。缓冲满返回 `STNP_ERR_BUFFER`，不会静默覆盖旧数据/Job。Job Queue 满时，`STNP_Process()` 保留当前完整帧，等待后续重试。

## 发送

类型化 Task：

```c
Module_CommandPayload payload = {0};
STNP_Task_Send(instance_id, MODULE_CMD_COMMAND, &payload);
```

类型化 Notify：

```c
STNP_Notify_Send(instance_id, MODULE_NOTIFY_EVENT, MODULE_OK, &payload);
```

原始字节数组使用 `STNP_Task_SendBytes()` / `STNP_Notify_SendBytes()`；payload 必须为数组或 `STNP_NULL`。

## Notify 回调

全局原始字节回调：

```c
void STNP_Notify_Callback(...);
```

Module 类型化回调默认关闭，按需启用：

```c
Module_NotifyCallbackEnable(STNP_ENABLE);
```

两类回调都在 `STNP_Dispatch()` / RTOS Worker context 执行，不在 Transport RX IRQ 执行。

## Notify 接收分发开关

Notify 接收分发路径的初值来自 `protocol.options.notify_dispatch_receive.enabled`，运行时可切换：

```c
STNP_NotifyDispatchReceive_Enable();
STNP_NotifyDispatchReceive_Disable();
(void)STNP_NotifyDispatchReceive_IsEnabled();
```

## USER CODE

用户业务文件：

```text
Implementation/<module>_impl.c
Implementation/stnp_notify_callback.c
```

生成器保留 Includes / Private / Handler USER CODE 区域。业务 `.c` 自动包含 `Instance/stnp_instances.h`，因此可以跨 Module/Instance 自由调用 Task/Notify Send。

## Keil 工程

Module 框架源：

```text
Module/<Module>/<module>.c
```

用户业务源：

```text
Implementation/<module>_impl.c
```

basename 保持唯一，避免 Keil 对象文件冲突。

## PC Mock 示例

`Examples/` 默认关闭。启用后 `TransportMock` 只把 TX bytes 回灌到 `STNP_Transport_Receive()`；它不会自动调用 Process/Dispatch，因此不会掩盖真实的延迟执行模型。

## Wire 格式

- Task：`SOF[2] | TARGET | CODE | LEN | PAYLOAD`
- Notify：`SOF[2] | SOURCE | NOTIFY_CODE | RESULT(u16 LE) | LEN | PAYLOAD`
