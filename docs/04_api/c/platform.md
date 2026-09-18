# C API — Platform / CRC

本页说明固定宽度类型、公共宏、工程配置宏、编解码与 CRC。类型定义在 `Platform/stnp_platform.h`；`STNP_EnableState` 与 `common_types` 生成在 `Platform/stnp_types.h`。

## 固定宽度类型

```c
typedef uint8_t  STNP_U8;
typedef uint16_t STNP_U16;
typedef uint32_t STNP_U32;
typedef int32_t  STNP_I32;
```

## 公共宏

```c
STNP_NULL
STNP_UNUSED(x)
STNP_WEAK
STNP_WEAK_WARN(msg)
```

- Keil AC5 / IAR：`STNP_WEAK` 为 `__weak`。
- GNU：`__attribute__((weak))`；`STNP_WEAK_WARN` 仅 GNU warning 属性有效。
- 禁止在 `stnp_platform.h` 加入 HAL / 驱动调用。

## `STNP_EnableState`

```c
typedef enum {
    STNP_DISABLE = 0,
    STNP_ENABLE = 1
} STNP_EnableState;
```

用于 Module Notify callback 启用开关等。

## 工程配置宏

生成到 `stnp_platform_config.h`，取值来自协议与生成配置（例如 `max_payload`、`router_instance_max`、帧头/固定槽尺寸、CRC 宽度）：

```c
STNP_PAYLOAD_MAX
STNP_ROUTER_INSTANCE_MAX
STNP_TASK_FIXED_SIZE
STNP_NOTIFY_FIXED_SIZE
STNP_CRC_SIZE
STNP_FRAME_MAX_SIZE
```

另有可编译期覆盖的 `STNP_RX_RING_SIZE`、`STNP_JOB_QUEUE_DEPTH`。CRC 关闭时 `STNP_CRC_SIZE` 为 `0U`。

## Codec

```c
void STNP_Encode_U16(STNP_U8 *buf, STNP_U16 value);
STNP_U16 STNP_Decode_U16(const STNP_U8 *buf);
void STNP_Encode_U32(STNP_U8 *buf, STNP_U32 value);
STNP_U32 STNP_Decode_U32(const STNP_U8 *buf);
void STNP_Encode_I32(STNP_U8 *buf, STNP_I32 value);
STNP_I32 STNP_Decode_I32(const STNP_U8 *buf);
```

小端编码，供 Frame / VTL 使用。无 `STNP_Encode_U8`：单字节直接写入。

## CRC

仅当 `protocol.features.crc.enabled=true` 时生成 `Core/stnp_crc.h` 与 `stnp_crc.c`。回归夹具默认关闭 CRC，因此该 golden 目录中没有这两份文件；接口以模板为准：

```c
STNP_U16 STNP_CRC16(const STNP_U8 *data, STNP_U16 length);
```

算法为 CRC16-Modbus。存在性只由生成期开关决定，**没有**运行时 `runtime_toggle`。

---

[← Router / VTL](router_vtl.md) | [文档目录](../../README.md) | [STM32 HAL UART SDK →](sdk_stm32_hal_uart.md)
