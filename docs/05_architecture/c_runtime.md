# C 运行时架构

本页描述 0.9 现状的 C 延迟运行时：传输层只复制字节，协议推进与用户业务分开。取证于 `src/stnp_editor/resources/templates/c/Core/stnp_core.c.j2`、`stnp_runtime.c.j2`、`stnp_notify.c.j2`、`stnp_frame.c.j2`、`Instance/stnp_instances.c.j2` 与冻结规范 §3 / §7。C 回归夹具对应实现见 `tests/golden/C/regression_c/regression_c_STNP_C/`。

## 分层

```text
Hardware / Transport
        │ bytes
        ▼
STNP_Transport_Receive()     只做有界复制
        ▼
RX Ring
        ▼
STNP_Process()               ≤ 1 完整帧 / 次；1 字节滑动重同步
        ▼
Static Job Queue             入队时复制 Payload，不持有 RX 指针
        ▼
STNP_Dispatch()              ≤ 1 可运行 Job / 次
        ▼
Handler / Notify Callback    runtime lock 外
```

Core 不绑定 UART，也不 include FreeRTOS。介质适配在 SDK 或用户 `STNP_TransportWrite` 中。`STNP_Init(write_fn)` 保存写出函数并初始化 RX Ring / 解析缓冲 / Job Queue；`write_fn` 为 `STNP_NULL` 时返回 `STNP_ERR_PARAM`。随后应调用 `STNP_Instances_Init()` 注册全部实例。

静态容量在 `Platform/stnp_platform_config.h`：`STNP_FRAME_MAX_SIZE`、`STNP_RX_RING_SIZE`（默认 4 × 最大帧）、`STNP_JOB_QUEUE_DEPTH`（默认 8）。无 malloc。缓冲满返回 `STNP_ERR_BUFFER`，不会静默覆盖旧数据。

## `STNP_Transport_Receive` 只做有界复制

不 Parse、不 Router、不 Decode、不调用 Handler。实现是 SPSC Ring：生产者拥有 `tail`，`Process` 拥有 `head`。整块能放下才提交 `tail`；放不下返回 `STNP_ERR_BUFFER`，不做部分写入。适合 UART RX IRQ：中断里只拷贝字节。`data` 为 `STNP_NULL` 且 `length > 0` 时返回 `STNP_ERR_PARAM`。

`STNP_Transport_Write` 把已构好的帧交给 `STNP_Init` 时登记的写出函数；尚未 `Init` 时返回 `STNP_ERR_STATE`。

## `STNP_Process` ≤1 帧与 1 字节滑动重同步

`STNP_Process()` 从 RX Ring 逐字节填入 `g_parse_buf`，再尝试完整帧：

1. 缓冲不足 2 字节则 `STNP_IDLE`。
2. 当前两字节既不是 Task SOF 也不是 Notify SOF 则滑动 1 字节继续。
3. 头未齐则 `STNP_IDLE` 等待。
4. `LEN > STNP_PAYLOAD_MAX`：滑动 1 字节，返回 `STNP_ERR_LENGTH`。
5. 帧未齐则 `STNP_IDLE`。
6. `STNP_Frame_ParseTask` / `ParseNotify` 失败（含 CRC）：滑动 1 字节并返回该错误，让下次 `Process` 有机会从嵌套 SOF 恢复。
7. 入队成功则从解析缓冲移走整帧并返回；Job 满返回 `STNP_ERR_BUFFER` **且不滑动**，当前完整帧保留待重试。

单次调用最多把一个完整帧送进 Job Queue。解析缓冲涨满时也会滑动 1 字节并返回 `STNP_ERR_LENGTH`。

## Job 生命周期

`stnp_runtime.c` 用静态数组 `g_jobs[STNP_JOB_QUEUE_DEPTH]` 做成 free-list + ready-list。入队时把 Payload 复制到 Job 内的 `payload[STNP_PAYLOAD_MAX]` 快照，不保存 RX buffer 指针。后续 RX 复用 staging 不影响已入队 Job。

Task Job 在入队前先 `STNP_Router_ResolveTask(target, code, &module)`；失败则不入队，直接返回 `STNP_ERR_TARGET` / `STNP_ERR_COMMAND`。Notify Job 携带 `source` / `notify_code` / `result`，module 指针为空，分发时再走 `STNP_Notify_Dispatch`。

## active-key 并发

`STNP_Dispatch()` 只是 `STNP_Runtime_DispatchOne()`。官方 FreeRTOS Worker 可并发调用它。同一 Instance/source（Job 的 `key`，0..255）串行：`g_instance_busy[key]` 为 1 时该 key 的后续 Job 留在 ready 队列，调度器跳过它们去找其他可运行项。不同 key 可并发。Handler / Notify callback 始终在 `STNP_Runtime_Lock` 外执行；默认 weak 锁为空操作，裸机单线程安全。

无可运行 Job 时返回 `STNP_IDLE`。执行完毕后释放 busy 位。

## 发送路径与 SEQ 保留

```text
STNP_Task_Send / STNP_Notify_Send
  → Router + VTL Encode
  → Frame Build（SEQ reserve-before-write）
  → STNP_Transport_Write
```

发送不要求位于 Process/Dispatch 中。开启 SEQ 时，`STNP_Frame_ReserveSeq()` 在 `STNP_Runtime_Lock` 内读取当前 `g_stnp_tx_seq` 并推进（跳过 reserved，`0xFFFF` 回绕到 0），然后才构帧。底层写出失败允许 SEQ 空洞。Raw 路径 `STNP_Task_SendBytes` / `STNP_Notify_SendBytes` 同样走 Frame Build + Transport Write，只是跳过 VTL。

## 裸机

主循环交替 `STNP_Process()` / `STNP_Dispatch()`。IRQ 只调用 `STNP_Transport_Receive()`。耗时 Handler 不再阻塞 IRQ，但仍占用主循环：

```c
(void)STNP_Init(MyTransportWrite);
(void)STNP_Instances_Init();
for (;;)
{
    (void)STNP_Process();
    (void)STNP_Dispatch();
}
```

## FreeRTOS

```text
RX IRQ → RX Ring → Protocol Task（单执行者 Process）
                         └→ Worker Pool（多执行者 Dispatch）
```

Core 不 include FreeRTOS。官方 SDK 用 `xTaskCreateStatic` 建 1 个 Protocol Task 与 Worker Pool。Protocol Task 是解析的单执行者；Worker 并发 `STNP_Dispatch()`，仍受 active-key 约束。详见 [FreeRTOS 指南](../06_guides/freertos.md)。

## Notify 接收分发开关

`protocol.options.notify_dispatch_receive.enabled` 给出初值，写入 `stnp_notify.c` 的 `g_notify_dispatch_receive`。运行时用 `STNP_NotifyDispatchReceive_Enable` / `Disable` / `IsEnabled` 门控。

门控点在生成的 `STNP_Notify_Dispatch`（`Instance/stnp_instances.c`）：先始终调用 weak `STNP_Notify_Callback`（全局兜底），仅当开关开启时才按 `SOURCE` 把帧交给对应 Module 的 `<Module>_NotifyDispatch`。关闭后本端仍解析并入队 Notify Job，但不进入 Module callback。不改 wire 格式，也不影响发送。

---

[← 生成器](generator.md) | [文档目录](../README.md) | [Python 运行时 →](python_runtime.md)
