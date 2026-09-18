# C API — Notify 发送

本页说明通知（Notify）发送 API，以及 Notify 帧 `RESULT` 槽的取值层级。签名取自 `Core/stnp_notify.h` 与期望产物 `Core/stnp_notify.c`。

## `STNP_Notify_Send`

```c
STNP_Result STNP_Notify_Send(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const void *payload
);
```

发送生成的 typed Notify Payload。

| 参数 | 说明 |
|---|---|
| `source` | 来源实例 ID，使用 `STNP_INSTANCE_<INSTANCE>_ID` |
| `notify_code` | Module Notify code，例如 `CHASSIS_NOTIFY_DONE` |
| `result` | 写入 Notify 帧 `RESULT` 槽的 u16；业务侧通常填该 Module 的 `<Module>_Result` |
| `payload` | 对应 typed Payload；无 Payload 时 `STNP_NULL` |

### `RESULT` 槽语义

`RESULT` 是 Notify 帧上的 2 字节小端槽，三类结果码共用（冻结规范 §5）：工程级结果码（Global Result，含 `0x0000` 的工程级 `OK`）、Module Return Code 分段、以及运行时 Core 错误在部分路径上的映射。应用发送业务通知时，应填 Module Result（例如 `CHASSIS_OK`、`SENSOR_OK`），不要填 `STNP_Result` 当业务码。

示例：

```c
STNP_Notify_Send(
    STNP_INSTANCE_CHASSISMAIN_ID,
    CHASSIS_NOTIFY_DONE,
    CHASSIS_OK,
    STNP_NULL
);
```

## `STNP_Notify_SendBytes`

```c
#define STNP_Notify_SendBytes(source, notify_code, result, payload) \
    (STNP__BYTE_ARRAY_POINTER_CHECK(payload), \
     STNP_Notify_SendBytes_Impl( \
        (source), \
        (notify_code), \
        (result), \
        (payload), \
        (STNP_U16)(((payload) == STNP_NULL) ? 0U : sizeof(payload))))
```

原始字节数组 API，长度由宏在数组退化前取得。误用 byte pointer 时，GCC/Clang 同样编译期拒绝。内部实现为 `STNP_Notify_SendBytes_Impl`。

## 接收分发运行时开关

本端是否把收到的 Notify 分发给 Module callback，由生成期 `protocol.options.notify_dispatch_receive.enabled` 给出初值，并可在运行时切换：

```c
void STNP_NotifyDispatchReceive_Enable(void);
void STNP_NotifyDispatchReceive_Disable(void);
STNP_U8 STNP_NotifyDispatchReceive_IsEnabled(void);
```

该开关不改变 wire 格式，只门控本端接收分发。发送 `STNP_Notify_Send()` 不依赖该开关，也不依赖 RX → Process → Dispatch 路径。

---

[← Task](task.md) | [文档目录](../../README.md) | [Module →](module.md)
