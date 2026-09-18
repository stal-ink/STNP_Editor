# 多实例

本页说明一个 Module 绑定多个实例时如何寻址。0.9 已删除单实例便捷宏。

同一个 Module 可以绑定多个 Runtime Instance：

```json
"instances": [
  {"name": "SensorFront", "module": "SENSOR", "id": 3},
  {"name": "SensorRear",  "module": "SENSOR", "id": 4}
]
```

生成：

```c
#define STNP_INSTANCE_SENSORFRONT_ID 0x03U
#define STNP_INSTANCE_SENSORREAR_ID  0x04U
```

发送时明确选择实例：

```c
STNP_Task_Send(
    STNP_INSTANCE_SENSORFRONT_ID,
    SENSOR_CMD_READ,
    STNP_NULL
);
```

## 实例寻址规则

0.9 只生成实例级 ID 宏；用户统一使用实例 ID 寻址：

```c
STNP_INSTANCE_<INSTANCE>_ID
```

不存在 `<MODULE>_ID` 形式的单实例便捷宏，因此发送目标始终由实例名明确指定，不受配置顺序影响。

## Router 约束

- Instance ID 范围 `1..255`；
- `0` 不作为合法注册 ID；
- ID 全局唯一；
- Instance name 全局唯一，并且生成后的宏/handle 名也必须唯一；
- 实例总数不能超过 `router_instance_max`（默认 8）。

0.9 变更：不再生成 `<MODULE>_ID`。即使该 Module 只有一个实例，发送目标也必须写 `STNP_INSTANCE_<INSTANCE>_ID`。

---

[← Python UART](python_uart.md) | [文档目录](../README.md) | [CRC 与流式接收 →](crc_and_stream.md)
