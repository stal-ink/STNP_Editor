# C API — Task 发送

本页说明任务（Task）发送 API。签名取自 `Core/stnp_task.h` 与期望产物 `Core/stnp_task.c`。

## `STNP_Task_Send`

```c
STNP_Result STNP_Task_Send(
    STNP_U8 target,
    STNP_U8 code,
    const void *payload
);
```

发送生成的 typed Payload。

| 参数 | 说明 |
|---|---|
| `target` | 目标实例（Instance）ID，使用 `STNP_INSTANCE_<INSTANCE>_ID` |
| `code` | 目标 Module 的 Command code，例如 `CHASSIS_CMD_MOVE` |
| `payload` | 对应生成的 Payload 结构体指针；无 Payload 时传 `STNP_NULL` |

内部链路：

```text
STNP_Task_Send
  → STNP_Router_EncodeTask（按实例查 Module VTL）
  → STNP_VTL_Encode
  → STNP_Task_SendBytes_Impl
  → Frame + SEQ 保留 + STNP_Transport_Write
```

示例（名称来自 C 回归夹具）：

```c
Chassis_MovePayload p = {
    .direction = 1U,
    .speed = 50U,
};

STNP_Task_Send(
    STNP_INSTANCE_CHASSISMAIN_ID,
    CHASSIS_CMD_MOVE,
    &p
);
```

## `STNP_Task_SendBytes`

```c
#define STNP_Task_SendBytes(target, code, payload) \
    (STNP__BYTE_ARRAY_POINTER_CHECK(payload), \
     STNP_Task_SendBytes_Impl( \
        (target), \
        (code), \
        (payload), \
        (STNP_U16)(((payload) == STNP_NULL) ? 0U : sizeof(payload))))
```

原始字节数组发送。宏在数组退化成指针之前用 `sizeof` 取长度，再调用内部 `_Impl`。

```c
STNP_U8 raw[] = {0x01U, 0x32U};
STNP_Task_SendBytes(
    STNP_INSTANCE_CHASSISMAIN_ID,
    CHASSIS_CMD_MOVE,
    raw
);
```

无 Payload：

```c
STNP_Task_SendBytes(target, code, STNP_NULL);
```

不要把普通 `STNP_U8 *` 指针当作 `payload`。GCC/Clang 下 `STNP__BYTE_ARRAY_POINTER_CHECK` 对常见 byte pointer 误用提供编译期拒绝。

## `STNP_Task_SendBytes_Impl`

```c
STNP_Result STNP_Task_SendBytes_Impl(
    STNP_U8 target,
    STNP_U8 code,
    const STNP_U8 *payload,
    STNP_U16 length
);
```

框架真实 Raw 发送入口。普通应用优先使用 `STNP_Task_SendBytes()` 宏。

## SEQ 保留与并发语义

当 `protocol.features.seq.enabled` 为 true 时，SEQ 在进入 Transport 写出之前通过 runtime lock 原子保留并推进，并自动跳过 `task.seq.reserved`。多个 FreeRTOS Worker 可并发发送；若底层写出失败，序列中允许出现空洞（冻结规范 §3.9：reserve-before-write）。

---

[← Core](core.md) | [文档目录](../../README.md) | [Notify →](notify.md)
