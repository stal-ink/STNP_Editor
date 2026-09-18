# STNP Editor 第二轮架构调整方案与 TodoList

> **ARCHIVE / 历史资料：** 本文可能与当前 0.5.0 修复版冲突；当前规范请从 [`docs/README.md`](../README.md) 进入。


> **当前补充定档（统一 STNP Send + Module VTL）**：后续讨论进一步收敛发送 API。结构化发送统一使用 `STNP_Task_Send()` / `STNP_Notify_Send()`，内部经 Router 调用目标/来源 Instance 对应 Module 的 VTL；Raw byte array 使用 `STNP_Task_SendBytes()` / `STNP_Notify_SendBytes()`，公开宏在数组退化前自动取得 `sizeof(array)`，真实带 len 的 `_Impl` 为内部实现。禁止生成 `Module_TaskSend()` / `Module_NotifySend()`，也不生成公开 per-command Pack。其余 Payload、CMD 唯一命名、统一 Validator、单一 Notify Callback、删除 Context、ACK/Handshake 属于用户业务层等原则继续有效。详见 `docs/API.md` 与 `docs/ARCHITECTURE.md`。


> 用途：保留第二轮架构调整的历史基线与迁移上下文。  
> 当前发送 API 与 VTL 方案以顶部“当前补充定档”、`docs/API.md` 和 `docs/ARCHITECTURE.md` 为准；主体中的旧 Pack/Send 章节仅作演进记录。

## 1. 核心定位

STNP 不是 RPC，也不是“每条命令对应一个发送函数”。

STNP 的核心发送原语始终是：

```c
STNP_Task_Send(...)
STNP_Notify_Send(...)
```

接收核心入口始终保留：

```c
STNP_Task_Receive(...)
STNP_Notify_Receive(...)
```

Module 负责解释 Command、Notify、Result、Payload 语义，以及接收后的分发和可选验证。

---

## 2. 第二轮最重要的纠偏

0.2.0 中存在：

```c
Sensor_TaskRead(...)
Sensor_TaskCalibrate(...)
Sensor_NotifyData(...)
Sensor_NotifyDone(...)

STNP_SensorFront_TaskRead(...)
STNP_SensorFront_TaskCalibrate(...)
STNP_SensorFront_NotifyData(...)
```

这些本质只是 `STNP_Task_Send()` / `STNP_Notify_Send()` 的二次封装。

问题：

- Command / Notify 越多，API 越多；
- Instance 越多，API 继续乘法膨胀；
- 用户思维从“自由发送 STNP Task / Notify”偏向 RPC / SDK / HAL；
- 与 STNP 原始设计思想不符。

因此：**第二轮要删除这类发送 wrapper。**

---

## 3. 不可变设计原则

- `STNP_Task_Send()` 是 Task 唯一核心发送原语。
- `STNP_Notify_Send()` 是 Notify 唯一核心发送原语。
- `STNP_Task_Receive()` 必须保留。
- `STNP_Notify_Receive()` 必须保留，不能被 Module Callback 替代。
- Task / Notify 完全解耦。
- Core 不维护 ACK / DONE / 握手状态机。
- `notify_on_*` 只是可选业务关联元数据。
- 用户可以利用 Module Notify Callback 自己实现 ACK、握手、重试、超时等状态机。
- Validator 是用户可选能力。
- Module / Instance 不能为每条 CMD / Notify 生成发送 API。
- 用户只编辑 `Implementation/<module>.c` 中留好的业务接口。

---

## 4. Payload 概念统一


## 4.1 CMD 是 Task 侧唯一命名锚点

这是第二轮新增的**强制命名规则**。

所有围绕 Task/CMD 生成的类型、Pack、Decode、用户行为函数等，名称都必须直接从 CMD 提取，禁止生成器再创造第二个业务名称。

### 固定前缀禁止修改

CMD 的原始格式固定为：

```text
模块_CMD_XXX
```

例如：

```text
SENSOR_CMD_READ
SENSOR_CMD_GET_TEMP
SENSOR_CMD_SET_WORK_MODE
```

其中：

- `SENSOR_CMD_` 是固定前缀；
- 用户自由编辑的是后面的 `READ / GET_TEMP / SET_WORK_MODE`；
- 生成器从 CMD 后缀提取 PascalCase 名称。

转换规则：

```text
READ
→ Read

GET_TEMP
→ GetTemp

SET_WORK_MODE
→ SetWorkMode
```

### Task 侧所有生成名称统一来自 CMD

例如：

```text
SENSOR_CMD_READ
```

必须生成：

```c
Sensor_ReadPayload
Sensor_ReadPack(...)
Sensor_ReadDecode(...)     /* internal */
Sensor_Read(...)
```

例如：

```text
SENSOR_CMD_GET_TEMP
```

必须生成：

```c
Sensor_GetTempPayload
Sensor_GetTempPack(...)
Sensor_GetTempDecode(...)  /* internal */
Sensor_GetTemp(...)
```

例如：

```text
SENSOR_CMD_SET_WORK_MODE
```

必须生成：

```c
Sensor_SetWorkModePayload
Sensor_SetWorkModePack(...)
Sensor_SetWorkModeDecode(...) /* internal */
Sensor_SetWorkMode(...)
```

统一公式：

```text
MODULE_CMD_XXX_YYY
        ↓
XxxYyy
        ↓
Module_XxxYyyPayload
Module_XxxYyyPack(...)
Module_XxxYyyDecode(...)   /* internal */
Module_XxxYyy(...)
```

### 禁止第二套业务命名

例如 CMD 是：

```text
SENSOR_CMD_READ
```

即使 Payload 字段内容是：

```text
battery
temp
status
```

也禁止生成：

```c
Sensor_StatusPayload
```

必须是：

```c
typedef struct
{
    STNP_U8 battery;
    STNP_U8 temp;
} Sensor_ReadPayload;
```

用户业务函数也必须是：

```c
void Sensor_Read(
    SensorHandle *self,
    const Sensor_ReadPayload *payload
);
```

如果该 CMD 无 Payload，则：

```c
void Sensor_Read(
    SensorHandle *self
);
```

**结论：CMD 是 Task 侧所有生成设施的唯一命名来源。**

Notify 侧同理，以 Notify Code 自己的名字为唯一命名来源；Notify 名称不得反向污染 CMD 命名。


Request / Event / Payload 统一只保留一个概念：**Payload**。

旧：

```c
Sensor_CalibrateRequest
Sensor_StatusEvent
```

新：

```c
Sensor_CalibratePayload
Sensor_StatusPayload
```

Wire 上真正存在的就是 Payload，因此命名保持一致。

---

## 5. Payload 两种使用方式

### 5.1 Raw 模式

用户直接编辑字节：

```c
STNP_U8 payload[] = {
    80U,
    35U
};

STNP_Notify_Send(
    SENSOR_FRONT_ID,
    SENSOR_NOTIFY_STATUS,
    SENSOR_OK,
    payload
);
```

### 5.2 Typed 模式

生成器为非空 Payload 生成结构体：

```c
typedef struct
{
    STNP_U8 battery;
    STNP_U8 temp;
} Sensor_StatusPayload;
```

用户：

```c
Sensor_StatusPayload status = {
    .battery = 80U,
    .temp = 35U
};

STNP_U8 raw[2];

Sensor_StatusPack(&status, raw);

STNP_Notify_Send(
    SENSOR_FRONT_ID,
    SENSOR_NOTIFY_STATUS,
    SENSOR_OK,
    raw
);
```

Raw 与 Typed 只是同一个 Payload 的两种编辑方式，不是两套协议。

---

## 6. Payload 字节语义规则

- `len = 0`：无 Payload。
- `len != 0`：每一个 wire byte 必须归属于明确字段。
- 多字节逻辑值直接定义为 `u16/u32/i32/...`。
- 只有组成部分本身具有独立语义时才拆成多个字段。

例如：

```c
typedef struct
{
    STNP_I32 offset;
    STNP_U16 gain;
} Sensor_CalibratePayload;
```

表示 wire 上 4 + 2 = 6 bytes。

---

## 7. Struct 不能直接当 Wire Payload

禁止直接：

```c
STNP_Task_Send(
    target,
    cmd,
    (STNP_U8 *)&payload
);
```

原因：C struct 可能存在 padding / alignment / endian 问题。

因此 Typed Payload 必须先 Pack：

```text
Typed struct
    ↓
Pack
    ↓
raw bytes
    ↓
STNP_Task_Send / STNP_Notify_Send
```

---

## 8. Pack / Decode 定位

### 8.1 Pack

对非空 Payload 生成：

```c
STNP_Result Sensor_CalibratePack(
    const Sensor_CalibratePayload *payload,
    STNP_U8 *raw
);
```

只负责 struct → raw，不负责发送。

### 8.2 Decode

Decode 默认放在 Module `.c` 内部：

```c
static STNP_Result Sensor_CalibrateDecode(
    const STNP_U8 *raw,
    STNP_U8 length,
    Sensor_CalibratePayload *payload
);
```

用户不直接调用。

---

## 9. Send API 自动计算长度

普通用户不再传 `len`。

目标形式：

```c
STNP_Task_Send(
    SENSOR_FRONT_ID,
    SENSOR_CMD_CALIBRATE,
    raw
);
```

Notify：

```c
STNP_Notify_Send(
    SENSOR_FRONT_ID,
    SENSOR_NOTIFY_STATUS,
    SENSOR_OK,
    raw
);
```

对 raw array，可在数组退化成 pointer 前利用 `sizeof(payload)` 自动获得长度。

内部可以有 `_Impl`，但不要暴露给普通用户：

```c
STNP_Task_Send_Impl(...)
STNP_Notify_Send_Impl(...)
```

### 无 Payload

需要支持：

```c
STNP_Task_Send(
    SENSOR_FRONT_ID,
    SENSOR_CMD_READ,
    STNP_NULL
);
```

内部自动 LEN=0。

### 约束

- 不新增用户可见的 `SendRaw()`。
- 不要求用户手工填写固定 size。
- 自动 len 只是 API 便利，不能改变 wire frame。

---

## 10. Payload Size 常量

可作为内部/高级辅助保留，但不是普通发送 API 的强制参数。

如需生成，建议集中使用：

```c
enum
{
    SENSOR_CALIBRATE_PAYLOAD_SIZE = 6U,
    SENSOR_STATUS_PAYLOAD_SIZE    = 2U
};
```

普通用户发送时不应必须显式写 size。

---

## 11. Task 接收模型

用户不能自己写 switch。

每个 Module 有一个统一 Task 分发器：

```c
STNP_Result Sensor_OnTask(
    SensorHandle *self,
    STNP_U8 cmd,
    const STNP_U8 *payload,
    STNP_U8 len
);
```

它由 Generator / Framework 维护。

内部：

```text
cmd switch
    ↓
length check
    ↓
Decode
    ↓
optional Validator
    ↓
调用对应用户业务函数
```

---

## 12. 每条 CMD 的用户业务函数

禁止为每 CMD 生成发送函数，但**允许每 CMD 有一个用户业务实现函数**。

命名直接对应行为：

```c
void Sensor_Read(
    SensorHandle *self
);
```

```c
void Sensor_Calibrate(
    SensorHandle *self,
    const Sensor_CalibratePayload *payload
);
```

不要命名为：

```c
Sensor_OnReadTask(...)
Sensor_OnCalibrateTask(...)
```

`Sensor_OnTask()` 才是统一 Task 分发器。

用户只在 `Implementation/sensor.c` 实现这些行为函数。

---

## 13. Validator 收敛

删除每 CMD 一个 setter：

```c
Sensor_SetReadValidate(...)
Sensor_SetCalibrateValidate(...)
```

改成统一：

```c
Sensor_SetValidate(
    SENSOR_CMD_CALIBRATE,
    MyValidate
);
```

建议一个 Module 一个 Validator callback type：

```c
typedef Sensor_Result (*Sensor_ValidateCallback)(
    SensorHandle *self,
    STNP_U8 cmd,
    const void *payload
);
```

规则：

- 未绑定：直接通过。
- 已绑定：由 `Module_OnTask()` 调用。
- `.stnp` 的 min/max 不自动承担业务 Validator。
- Validator Reject 时，可根据 `notify_on_reject` 元数据辅助发送 Reject Notify。
- 不生成每 CMD 一个 Validator typedef / setter。

---

## 14. 删除 Context

第二轮明确删除：

```c
Module_SetContext()
```

同时删除：

- Handle 中的 `context` 字段；
- Init 的 context 参数；
- Instance Context setter；
- README / Architecture 中的 Context 描述；
- 相关测试。

---

## 15. Notify Callback 收敛

禁止每条 Notify 一个 callback：

```c
Sensor_DataNotifyCallback on_data;
Sensor_StatusNotifyCallback on_status;
```

最终只保留：

- 全局 Notify Callback；
- 每个 Module 一个 Module Notify Callback。

### Module Callback

命名：

```c
void Sensor_NotifyCallback(
    SensorHandle *self,
    STNP_U8 notify_code,
    Sensor_Result result,
    const void *payload
);
```

Module 内部根据 `notify_code` 自动 Decode 对应 Payload，然后把 typed payload pointer 交给这个统一回调。

### 不需要绑定 API

删除：

```c
Sensor_SetNotifyCallback(...)
```

`Sensor_NotifyCallback()` 默认存在，采用 weak / empty implementation。

用户需要时在 Implementation 覆盖。

### 只保留使能函数

```c
Sensor_NotifyCallbackEnable(
    STNP_EnableState state
);
```

一个 Module 一个开关。

---

## 16. Notify Callback 与分发器命名

必须区分：

```text
Module_OnTask()
    = Framework Task 分发器

Module_NotifyCallback()
    = 用户模块级 Notify 回调
```

不要使用 `Module_OnNotify()` 作为用户 callback 名。

---

## 17. Global Notify Callback

保留全局 Notify Callback。

Module Callback 与 Global Callback 是两层机制。

典型路径：

```text
STNP_Notify_Receive()
        ↓
Core Parse
        ↓
Global Notify Callback（如设计要求）
        ↓
Module Route
        ↓
Module_NotifyCallback（如 ENABLE）
```

具体先后顺序优先兼容项目原有定义。

---

## 18. notify_on_* 元数据

继续保留：

```text
notify_on_accept
notify_on_reject
notify_on_done
```

但只是可选业务关联，不形成：

```text
Task → ACK → DONE
```

强绑定状态机。

### 用户自己实现 ACK / 握手

例如：

```text
CONNECT_REQ Task
    ↓
CONNECT_ACCEPT Notify
    ↓
CONNECT_CONFIRM Task
```

用户在：

```c
Module_NotifyCallback()
```

里推进自己的状态机。

Core 不：

- 记录握手状态；
- 自动建立 ACK；
- 用 Task SEQ 强绑定 Notify。

### Validator Reject

用户主动绑定 Validator 后，如果返回 Reject，可按 `notify_on_reject` 配置辅助发送 Reject Notify。

---

## 19. 一个 Module 的最终 API List

以 Sensor 为例。

### 类型

- `SensorHandle`：模块句柄。
- `Sensor_Command`：Task CMD 枚举。
- `Sensor_Notify`：Notify Code 枚举。
- `Sensor_Result`：Result 枚举。
- `Sensor_XXXPayload`：某条非空 Payload 的 typed struct。
- `Sensor_ValidateCallback`：统一 Validator 类型。

### API

- `Sensor_Init()`：初始化模块。
- `Sensor_OnTask()`：Framework 统一 Task 分发器。
- `Sensor_SetValidate(cmd, fn)`：为指定 CMD 配置可选 Validator。
- `Sensor_NotifyCallbackEnable(state)`：启用 / 禁用模块级 Notify Callback。
- `Sensor_NotifyCallback()`：模块唯一 Notify Callback，默认空实现。
- `Sensor_XXXPack()`：Typed Payload → raw bytes。
- `Sensor_Read()`：READ 对应的用户业务实现。
- `Sensor_Calibrate()`：CALIBRATE 对应的用户业务实现。
- `Sensor_AsModule()`：Core / Router 适配。

### 不再生成

- `Sensor_TaskXXX()`
- `Sensor_NotifyXXX()`
- `STNP_SensorFront_TaskXXX()`
- `STNP_SensorFront_NotifyXXX()`
- `Sensor_SetXXXValidate()`
- `Sensor_SetContext()`
- 每条 Notify 一个 Callback
- 每条 Notify 一个 Callback setter

---

## 20. Module `.h` 应包含

1. Command enum
2. Notify enum
3. Result enum
4. Payload struct
5. optional payload wire-size enum
6. Module Handle
7. unified Validator callback typedef
8. `Module_Init()`
9. `Module_SetValidate()`
10. `Module_NotifyCallbackEnable()`
11. `Module_NotifyCallback()`
12. `Module_XXXPack()`
13. 每条 CMD 的用户业务函数声明
14. 必要 Framework API

尽量不暴露：

- Decode
- Parse
- internal task switch
- internal notify dispatch
- internal validator map

---

## 21. Module `.c` 应包含

1. Init
2. Validator registration / storage
3. Notify callback enable state
4. Payload Pack implementation
5. static Payload Decode
6. `Module_OnTask()` + internal cmd switch
7. Validator dispatch
8. Notify decode / dispatch
9. weak/default `Module_NotifyCallback()`
10. weak/default CMD business implementation（如果 scaffold 机制需要）
11. Router adapter

用户业务强实现继续放：

```text
Implementation/<module>.c
```

---

## 22. Task 示例

定义：

```c
typedef struct
{
    STNP_I32 offset;
    STNP_U16 gain;
} Sensor_CalibratePayload;
```

### Typed 发送

```c
Sensor_CalibratePayload p = {
    .offset = -10,
    .gain = 20
};

STNP_U8 raw[6];

Sensor_CalibratePack(&p, raw);

STNP_Task_Send(
    SENSOR_FRONT_ID,
    SENSOR_CMD_CALIBRATE,
    raw
);
```

### Raw 发送

```c
STNP_U8 raw[] = {
    /* 用户自己填写 */
};

STNP_Task_Send(
    SENSOR_FRONT_ID,
    SENSOR_CMD_CALIBRATE,
    raw
);
```

### 接收

```text
STNP_Task_Receive()
    ↓
Router
    ↓
Sensor_OnTask()
    ↓
cmd switch
    ↓
Sensor_CalibrateDecode()
    ↓
Sensor_CalibratePayload
    ↓
optional Validator
    ↓
Sensor_Calibrate(self, &payload)
```

用户只实现：

```c
void Sensor_Calibrate(
    SensorHandle *self,
    const Sensor_CalibratePayload *payload
)
{
    /* USER CODE */
}
```

---

## 23. Notify 示例

定义：

```c
typedef struct
{
    STNP_U8 battery;
    STNP_U8 temp;
} Sensor_StatusPayload;
```

### 发送

```c
Sensor_StatusPayload status = {
    .battery = 85U,
    .temp = 36U
};

STNP_U8 raw[2];

Sensor_StatusPack(&status, raw);

STNP_Notify_Send(
    SENSOR_FRONT_ID,
    SENSOR_NOTIFY_STATUS,
    SENSOR_OK,
    raw
);
```

### 接收

```text
STNP_Notify_Receive()
    ↓
Core Parse
    ↓
Module Route
    ↓
Status Decode
    ↓
Sensor_StatusPayload
    ↓
Sensor_NotifyCallback()
```

用户：

```c
void Sensor_NotifyCallback(
    SensorHandle *self,
    STNP_U8 notify_code,
    Sensor_Result result,
    const void *payload
)
{
    if (notify_code == SENSOR_NOTIFY_STATUS)
    {
        const Sensor_StatusPayload *status =
            (const Sensor_StatusPayload *)payload;

        /* status->battery */
        /* status->temp */
    }
}
```

---

# 24. 从 0.2.0 必须删除 / 重构

- [ ] 删除 `Module_TaskXXX()`
- [ ] 删除 `Module_NotifyXXX()`
- [ ] 删除 `STNP_Instance_TaskXXX()`
- [ ] 删除 `STNP_Instance_NotifyXXX()`
- [ ] `XXXRequest` → `XXXPayload`
- [ ] `XXXEvent` → `XXXPayload`
- [ ] 删除每 Notify 一个 callback
- [ ] 删除 callback setter
- [ ] 删除每 CMD 一个 Validator setter
- [ ] 删除 `Module_SetContext()`
- [ ] 删除 Handle.context
- [ ] 删除 Instance Context API
- [ ] Decode / Parse 默认内部化
- [ ] 用户主 Send API 删除显式 len 参数
- [ ] 示例和 README 不再推荐 Module send wrapper
- [ ] 检查并删除任何 Task return 自动 ACCEPT / DONE 残留

---

# 25. 必须保留的现有能力

- [ ] `STNP_Task_Send()`
- [ ] `STNP_Notify_Send()`
- [ ] `STNP_Task_Receive()`
- [ ] `STNP_Notify_Receive()`
- [ ] Task / Notify 解耦
- [ ] `notify_on_*` 元数据
- [ ] USER CODE merge
- [ ] Manifest cleanup
- [ ] Implementation orphan 保护
- [ ] Embedded 隔离
- [ ] 多 Instance
- [ ] Stream 拆包 / 粘包
- [ ] RX error preservation
- [ ] Task / Notify SOF 正确解析
- [ ] SEQ reserved
- [ ] Schema / IR semantic validation
- [ ] strict gcc tests
- [ ] handshake 示例思想
- [ ] Core 不维护 ACK 状态机

---

# 26. TodoList

## Phase A — 基线

- [ ] 解压当前 0.2.0
- [ ] 跑 pytest
- [ ] 跑 Golden
- [ ] 跑 strict gcc
- [ ] 搜索所有旧 API
- [ ] 记录迁移前 public headers

## Phase B — Payload 与 CMD 命名统一

- [ ] Request → Payload
- [ ] Event → Payload
- [ ] Task 侧所有生成名称只允许从 CMD 后缀派生
- [ ] 固定解析 `MODULE_CMD_XXX_YYY → XxxYyy`
- [ ] `SENSOR_CMD_READ → Sensor_ReadPayload / Sensor_ReadPack / Sensor_ReadDecode / Sensor_Read`
- [ ] `SENSOR_CMD_GET_TEMP → Sensor_GetTempPayload / Sensor_GetTempPack / Sensor_GetTempDecode / Sensor_GetTemp`
- [ ] 禁止 CMD=READ 却生成 `StatusPayload` 等第二业务名
- [ ] Notify 侧命名只允许从 Notify Code 自身派生
- [ ] Schema / IR / templates / docs / tests 全部同步
- [ ] `len=0` 不生成空 struct

## Phase C — 删除发送 Wrapper

- [ ] 删除 Module TaskXXX
- [ ] 删除 Module NotifyXXX
- [ ] 删除 Instance TaskXXX
- [ ] 删除 Instance NotifyXXX
- [ ] 示例全部改用 Core Send API

## Phase D — Send 自动长度

- [ ] `STNP_Task_Send()` 用户 API 去掉 len
- [ ] `STNP_Notify_Send()` 用户 API 去掉 len
- [ ] raw array 自动 `sizeof(payload)`
- [ ] `STNP_NULL` 自动 len=0
- [ ] 内部 `_Impl` 隐藏
- [ ] 防止 pointer 误用
- [ ] 不新增公开 SendRaw

## Phase E — Typed Pack

- [ ] 非空 Payload 生成 struct
- [ ] 非空 Payload 生成 Pack
- [ ] Pack 不发送
- [ ] Decode internal static
- [ ] padding / endian 安全
- [ ] Pack/Decode 对称测试

## Phase F — Task Dispatch

- [ ] 每 Module 一个 `Module_OnTask()`
- [ ] 内部 cmd switch
- [ ] 自动 length check
- [ ] 自动 Decode
- [ ] 自动 Validator
- [ ] 分发到由 CMD 唯一派生的 `Module_XxxYyy()` 用户业务函数
- [ ] `MODULE_CMD_XXX_YYY → Module_XxxYyy()`
- [ ] 用户不写 switch
- [ ] 禁止生成器根据 Payload 内容另起业务函数名

## Phase G — Validator

- [ ] 删除 SetXXXValidate
- [ ] 新增 `Module_SetValidate(cmd, fn)`
- [ ] 一个 Module 一个 Validator callback type
- [ ] CMD → Validator 映射
- [ ] 未绑定直接通过
- [ ] Reject 保留 notify_on_reject 辅助
- [ ] 多 CMD Validator 测试

## Phase H — 删除 Context

- [ ] 删除 context 字段
- [ ] 删除 SetContext
- [ ] 删除 Init context 参数
- [ ] 删除 Instance Context API
- [ ] 删除 docs/tests 残留

## Phase I — Notify Callback

- [ ] 删除 per-notify callback
- [ ] 删除 callback setter
- [ ] 每 Module 一个 `Module_NotifyCallback()`
- [ ] 默认 weak/empty
- [ ] 新增 `Module_NotifyCallbackEnable(state)`
- [ ] Module 内按 notify_code Decode
- [ ] callback 接 typed payload pointer
- [ ] 无 payload 时传 NULL
- [ ] disabled 时不调用
- [ ] 保留 Global Notify Callback

## Phase J — ACK / Handshake

- [ ] `STNP_Notify_Receive()` 保留
- [ ] handshake demo 只用 Core Send
- [ ] 状态推进写在 Module Notify Callback / 用户业务
- [ ] Core 不维护握手状态
- [ ] Core 不绑定 Task SEQ 与 Notify
- [ ] token/request_id 属于用户 Payload

## Phase K — Header 瘦身

- [ ] 只保留 enum / Payload / Handle / Validator / Pack / 用户行为 / Notify callback / 必要 Framework API
- [ ] 隐藏 Decode / Parse / internal switch / notify dispatch / validator map
- [ ] 加 API 分区注释

## Phase L — Instance 层瘦身

- [ ] 删除发送 wrapper
- [ ] 保留 Instance ID
- [ ] 保留 Router 注册
- [ ] 保留必要初始化
- [ ] 删除 Context

## Phase M — Core 稳定性

- [ ] Receive API 语义不动
- [ ] Send 仍保持自由
- [ ] Wire Frame 不变化
- [ ] CRC / SEQ / Router 行为兼容
- [ ] 自动 len 仅为 API 便利

## Phase N — 测试

- [ ] Raw Task Send
- [ ] Raw Notify Send
- [ ] no-payload Task
- [ ] no-payload Notify
- [ ] Typed Pack Task
- [ ] Typed Pack Notify
- [ ] Task Decode → typed Payload
- [ ] Notify Decode → typed Payload
- [ ] one-module-one-notify-callback
- [ ] global callback
- [ ] callback enable/disable
- [ ] unified validator
- [ ] no validator
- [ ] validator reject
- [ ] handshake
- [ ] no module send wrappers
- [ ] no instance send wrappers
- [ ] no context
- [ ] `-Wall -Wextra -Werror -pedantic`
- [ ] pytest 全绿
- [ ] golden 更新

## Phase O — 文档

- [ ] README 重新定义 API 主次
- [ ] 第一优先介绍 Core Send/Receive
- [ ] 第二介绍 Payload
- [ ] 第三介绍 Typed Pack
- [ ] 第四介绍 Module 用户行为函数
- [ ] 第五介绍 unified Validator
- [ ] 第六介绍 Module Notify Callback
- [ ] 第七介绍用户 ACK / 握手
- [ ] 删除 RPC 风格描述
- [ ] 更新 Architecture
- [ ] 更新 V1_TO_CURRENT
- [ ] 更新 examples

---

# 27. 最终一句话

> **STNP Task / Notify 必须保持自由、统一和稳定；Command 只是参数，不应该生成发送 API。Payload 只有一个概念，用户既可以直接操作 raw byte，也可以使用生成的 typed struct + Pack。Task 侧所有类型、Pack、Decode、行为函数都必须以 CMD 为唯一命名锚点，例如 `SENSOR_CMD_GET_TEMP → Sensor_GetTempPayload / Sensor_GetTempPack / Sensor_GetTempDecode / Sensor_GetTemp`，禁止生成第二套业务名称。接收端由生成器自动 Decode / Dispatch，用户只实现具体业务函数。每个 Module 只有一个 Notify Callback 和一个统一 Validator 配置入口，Context 删除，ACK / 握手完全属于用户业务层。**
