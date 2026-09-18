# C API — Router / VTL

本页面向框架与高级集成。普通业务代码优先使用 [Task](task.md) / [Notify](notify.md) 统一发送接口。签名取自 `Core/stnp_router.h`、`Core/stnp_vtl.h` 与对应 `.c`。

## `STNP_Router_Register`

```c
STNP_Result STNP_Router_Register(STNP_ModuleHandle *module);
```

注册 Module 实例。实现（`stnp_router.c`）规则：

- `module`、`module->ops`、`module->ops->task_handler` 任一为空：`STNP_ERR_PARAM`。
- 同一 Handle 指针重复注册：幂等返回 `STNP_OK`。
- 不同 Handle 使用相同 Instance ID：`STNP_ERR_STATE`。
- `g_instance_count >= STNP_ROUTER_INSTANCE_MAX`：`STNP_ERR_STATE`。

0 号 Instance ID 在规范与 schema 层被拒绝：`instances[].id` 的合法范围是 `1..255`（冻结规范 §4.5），生成器不会为 0 号实例生成登记。运行时 `STNP_Router_Register` 本身不额外判断 `id == 0`。

## `STNP_Router_EncodeTask` / `EncodeNotify`

```c
STNP_Result STNP_Router_EncodeTask(
    STNP_U8 target,
    STNP_U8 code,
    const void *payload,
    STNP_U8 *raw,
    STNP_U8 *length
);

STNP_Result STNP_Router_EncodeNotify(
    STNP_U8 source,
    STNP_U8 notify_code,
    const void *payload,
    STNP_U8 *raw,
    STNP_U8 *length
);
```

按实例找到 Module 的 Task / Notify VTL 描述，再调用 Core `STNP_VTL_Encode`。找不到实例返回 `STNP_ERR_TARGET`，找不到 code 返回 `STNP_ERR_COMMAND`。

## VTL metadata 表结构

```c
typedef enum
{
    STNP_VTL_U8 = 0,
    STNP_VTL_U16,
    STNP_VTL_U32,
    STNP_VTL_I32
} STNP_VTL_Type;

typedef struct
{
    STNP_U16 offset;
    STNP_VTL_Type type;
} STNP_VTL_Field;

typedef struct
{
    STNP_U8 code;
    STNP_U8 wire_size;
    STNP_U8 field_count;
    const STNP_VTL_Field *fields;
} STNP_VTL_Desc;
```

Module 的 VTL table count 使用 `STNP_U16`，因此完整 `0..255` 的 256 个 Command 或 Notify 都能被表示。

## `STNP_VTL_Find`

```c
const STNP_VTL_Desc *STNP_VTL_Find(
    const STNP_VTL_Desc *table,
    STNP_U16 count,
    STNP_U8 code
);
```

按 code 查找描述；找不到返回 `STNP_NULL`。

## `STNP_VTL_Encode`

```c
STNP_Result STNP_VTL_Encode(
    const STNP_VTL_Desc *desc,
    const void *payload,
    STNP_U8 *raw,
    STNP_U8 *length
);
```

将生成的 typed Payload 按 metadata 编码为 wire 字节。

## `STNP_VTL_Decode`

```c
STNP_Result STNP_VTL_Decode(
    const STNP_VTL_Desc *desc,
    const STNP_U8 *raw,
    STNP_U8 length,
    void *payload
);
```

按 metadata 解码到 typed Payload。

VTL 算法只属于 Core；Module 只生成 metadata 表，不生成 per-command Pack/Decode 函数。

---

[← Module](module.md) | [文档目录](../../README.md) | [Platform / CRC →](platform.md)
