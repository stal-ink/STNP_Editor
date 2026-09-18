# C API — 生成 Module

本页说明每个 Module 生成的类型、初始化、校验、回调与分发。示例名称取自期望产物 `Module/Sensor/sensor.h`（`Sensor` / `SENSOR`）；实际符号由 `.stnp` 的 Module / Command / Notify 名称生成。

配置层的 `commands[].validate_hook` 是布尔字段，不携带命令码。C 函数 `<Module>_SetValidate` **仍然携带** `STNP_U8 cmd`，按命令码绑定该命令的校验回调。二者不要混为一谈。

## 生成类型与常量

常见生成项（以 Sensor 为例）：

```c
Sensor_Command          /* 如 SENSOR_CMD_READ、SENSOR_CMD_CALIBRATE */
Sensor_Notify           /* 如 SENSOR_NOTIFY_DATA、SENSOR_NOTIFY_DONE */
Sensor_Result           /* 如 SENSOR_OK，值为该 Module 的 Return Code 分段 */
SensorHandle
Sensor_CalibratePayload /* <Pascal>_<Cmd>Payload */
SENSOR_CMD_*
SENSOR_NOTIFY_*
SENSOR_CALIBRATE_PAYLOAD_SIZE
SENSOR_DATA_PAYLOAD_SIZE
```

实例寻址统一使用 `STNP_INSTANCE_<INSTANCE>_ID`（例如 `STNP_INSTANCE_SENSORFRONT_ID`）。0.9 **已删除**单实例便捷宏（如 `<MODULE>_ID`），即使该 Module 只有一个实例也不再生成。

## `<Module>_Init`

```c
void Sensor_Init(SensorHandle *self, STNP_U8 id);
```

写入 Handle 的 Instance ID，并将 `ops` 置空。一般不必手工调用：`STNP_Instances_Init()` 会初始化 `.stnp` 中定义的全部实例。

## `<Module>_AsModule`

```c
STNP_ModuleHandle *Sensor_AsModule(SensorHandle *self);
```

把具体 Handle 适配为 Router 使用的通用 `STNP_ModuleHandle`，并挂上该 Module 的 `ops`（Task handler 与 VTL 表）。`self == STNP_NULL` 时返回 `STNP_NULL`。

## `<Module>_SetValidate`

```c
void Sensor_SetValidate(STNP_U8 cmd, Sensor_ValidateCallback fn);
```

校验回调类型：

```c
typedef Sensor_Result (*Sensor_ValidateCallback)(
    SensorHandle *self,
    STNP_U8 cmd,
    const void *payload
);
```

按 **命令码** 绑定该命令的用户校验函数。仅 `validate_hook: true` 的 Command 会执行校验；未绑定用户回调时，分发路径改走 `<Module>_ValidateGenerated`。`cmd` 对不上任何带 `validate_hook` 的命令时，setter 为空操作。

`payload` 已经过 VTL Decode，是 typed Payload 地址；无 Payload 时为 `STNP_NULL`。

## `<Module>_ValidateGenerated`

```c
Sensor_Result Sensor_ValidateGenerated(
    SensorHandle *self,
    STNP_U8 cmd,
    const void *payload
);
```

统一生成校验入口，内部按命令码 `switch` 分派，并按字段的基类型范围与 min/max 检查。生成在 `Implementation/<module>_impl.c`（用户代码区文件中的生成函数，不要删掉函数骨架）。`<Module>_OnTask` 在用户未 `SetValidate` 时调用它。

## `<Module>_OnTask`

```c
STNP_Result Sensor_OnTask(
    SensorHandle *self,
    STNP_U8 cmd,
    const STNP_U8 *payload,
    STNP_U8 len
);
```

框架 Task 分发入口：查 VTL → Decode → 校验（用户回调或 `ValidateGenerated`）→ 用户业务函数。应用通常无需直接调用。

## 用户业务函数

每个 Command 生成一个业务函数，名称只来自 CMD。弱符号兜底位于生成的 Module `.c`；强符号覆盖写在 `Implementation/<module>_impl.c` 的用户代码区。

有 Payload：

```c
void Sensor_Calibrate(
    SensorHandle *self,
    const Sensor_CalibratePayload *payload
);
```

无 Payload：

```c
void Sensor_Read(SensorHandle *self);
```

## Module Notify callback 与启用开关

```c
void Sensor_NotifyCallbackEnable(STNP_EnableState state);

void Sensor_NotifyCallback(
    SensorHandle *self,
    STNP_U8 notify_code,
    Sensor_Result result,
    const void *payload
);
```

每个 Module 一个 callback（弱符号默认空实现）。框架先按 Notify VTL Decode typed Payload，再调用 callback。`state` 使用 `STNP_ENABLE` / `STNP_DISABLE`。本端是否把收到的 Notify 送到这条路径，还受 `STNP_NotifyDispatchReceive_*` 运行时门控。

## `<Module>_NotifyDispatch`

```c
STNP_Result Sensor_NotifyDispatch(
    SensorHandle *self,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length
);
```

框架用的实例级 Notify 路由，由生成的实例登记表调用。普通用户不要手工调用。

---

[← Notify](notify.md) | [文档目录](../../README.md) | [Router / VTL →](router_vtl.md)
