# C API — Core / Transport

本页说明运行时生命周期与接收、推进、分发接口。签名取自生成头 `Core/stnp_core.h` 与期望产物 `tests/golden/C/regression_c/regression_c_STNP_C/Core/stnp_core.c`。

## `STNP_Init`

```c
STNP_Result STNP_Init(STNP_TransportWrite write_fn);
```

`STNP_TransportWrite` 定义为：

```c
typedef STNP_Result (*STNP_TransportWrite)(const STNP_U8 *data, STNP_U16 length);
```

注册底层发送回调，并重置 RX Ring、parser staging 与 Job runtime。`write_fn == STNP_NULL` 时返回 `STNP_ERR_PARAM`。

应用在调用接收循环之前，通常还需要 `STNP_Instances_Init()` 注册 `.stnp` 中声明的全部实例。官方 STM32 HAL UART SDK 会在 `STNP_HAL_UART_Init()` 内完成这两步。

## `STNP_Transport_Receive`

```c
STNP_Result STNP_Transport_Receive(
    const STNP_U8 *data,
    STNP_U16 length
);
```

只把字节复制进有界 RX Ring，然后返回。不解析帧，不执行用户 Handler / Notify callback，因此适合放在短的传输中断路径。`STNP_DEBUG=1` 时成功发布 `tail` 之后打 `STNP_BP_RX_COPY`；禁止在此构帧、回调、发送。

- 整块可容纳：`STNP_OK`。发布 `tail` 前先复制完整输入块，Process 看不到半截提交。
- RX Ring 空间不足：`STNP_ERR_BUFFER`，本输入块不做部分写入。
- `data == STNP_NULL && length > 0`：`STNP_ERR_PARAM`。

## `STNP_Process`

```c
STNP_Result STNP_Process(void);
```

至多推进一个完整接收帧：Parse / CRC / Router / Job 入队。不执行 Handler / Notify callback。

| 返回 | 含义 |
|---|---|
| `STNP_OK` | 一个帧已进入 Job Queue |
| `STNP_IDLE` | 当前没有完整帧可推进 |
| `STNP_ERR_BUFFER` | Job Queue 满；当前完整帧保留等待重试 |
| 其他错误 | 当前帧解析或路由错误，按规则消费或 1 字节滑动重同步 |

## `STNP_Dispatch`

```c
STNP_Result STNP_Dispatch(void);
```

至多执行一个可运行 Job。无可执行 Job 时返回 `STNP_IDLE`。

Job 在极短的 runtime lock 内认领，Handler / Callback 在锁外执行。官方 FreeRTOS SDK 可让多个 Worker 并发调用；同一 Instance/source 串行，不同 key 可并发。`g_instance_busy[key]` 保证同一 key 不会被两个 Worker 同时执行。

Notify 接收分发另受 `STNP_NotifyDispatchReceive_IsEnabled()` 门控：关闭时 Dispatch 仍可能认领 Notify Job，但 `STNP_Notify_Dispatch` 直接返回 —— 不走模块、也不调全局 `STNP_Notify_Callback`。发送路径不受该开关影响。0.9.1 在 DR 开且模块已认领时全局不再收同一帧。

## `STNP_Transport_Write`

```c
STNP_Result STNP_Transport_Write(
    const STNP_U8 *data,
    STNP_U16 length
);
```

通过 `STNP_Init()` 注册的底层发送回调写出数据。尚未 Init 时返回 `STNP_ERR_STATE`；`data == STNP_NULL && length > 0` 返回 `STNP_ERR_PARAM`。

## 返回码

见 [C API 总览](README.md) 中的 `STNP_Result` 表。本页函数常用 `STNP_OK`、`STNP_IDLE`、`STNP_ERR_PARAM`、`STNP_ERR_STATE`、`STNP_ERR_BUFFER`。

## 裸机最小循环

```c
if ((STNP_Init(MyWrite) != STNP_OK) ||
    (STNP_Instances_Init() != STNP_OK))
{
    /* error */
}

for (;;)
{
    (void)STNP_Process();
    (void)STNP_Dispatch();
    /* Application code */
}
```

ISR 或轮询路径只调用 `STNP_Transport_Receive()`；协议推进与用户业务留在主循环（或 FreeRTOS Protocol Task / Worker）。

## 未知帧回调（两道闸，默认关）

头文件 `Core/stnp_unknown.h`（经 `stnp.h` 包含）：

```c
void STNP_UnknownFrame_SetCallback(STNP_UnknownFrameFn fn); /* NULL = 清除 */
void STNP_UnknownFrameCallback_Enable(STNP_EnableState state); /* 默认 STNP_DISABLE */
STNP_U8 STNP_UnknownFrameCallback_IsEnabled(void);
```

`SetCallback` **并且** `Enable` 都要，缺一则真零调用。reason：`STNP_UNKNOWN_SOF` / `LEN` / `CRC` / `TASK` / `NOTIFY`。SOF 仅当预编译 `STNP_UNKNOWN_REPORT_SOF=1`（默认 0）才上报。`STNP_UNKNOWN_NOTIFY` 枚举保留，C 0.9.1 **禁止触发**。`data` 指针禁止持有出函数。队列满（`STNP_ERR_BUFFER`）不是 unknown。合法业务帧即使已 enable 也不进本回调。

## `STNP_DEBUG`

仅预编译 0/1，见 [platform.md](platform.md) 与 [链路验证](../../06_guides/trace_and_breakpoints.md)。不是日志，无 `STNP_LOG*`。

---

[← C API 索引](README.md) | [文档目录](../../README.md) | [Task →](task.md)
