# STNP V1.0

> **ARCHIVE / 历史资料：** 本文可能与当前 0.5.0 修复版冲突；当前规范请从 [`docs/README.md`](../README.md) 进入。


> **Serial Task & Notification Protocol**  
> 版本：V1.0  
> 日期：2026-07-20  
> 适用：ROCK5B ↔ STM32 串口通信  
> 设计核心：简洁、解耦、全双工、模块内聚、可扩展


## 一、协议定位

STNP 是专为串口全双工物理特性设计的轻量级通信协议。

**核心特征：**

| 特征          | 说明                                                         |
| :------------ | :----------------------------------------------------------- |
| 全双工利用    | TX/RX 独立，Task（控制）与 Notify（通知）并行，互不阻塞      |
| 控制/通知解耦 | ROCK5B 发 Task，STM32 发 Notify，无强绑定                    |
| 极简帧格式    | Task 帧 7~71 字节，Notify 帧 4~68 字节                       |
| 广播通知      | Notify 不归属任何 Task，STM32 随时可发                       |
| 会话入口      | SESSION 是独立模块，上电后先建立会话                         |
| 模块内聚      | 每个模块（SESSION/SYSTEM/CHASSIS/LIFT/EXTENSION/GRIPPER）自己定义命令集，各自维护状态 |
| 自由扩展      | 协议层固定，业务层在 D 字段任意扩展                          |


## 二、协议架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ROCK5B (上位机)                            │
├─────────────────────────────────┬───────────────────────────────────┤
│      TX Task 通道              │      RX Notify 通道              │
│  ┌─────────────────────────┐   │   ┌─────────────────────────┐    │
│  │  AA55 | SEQ | TARGET    │   │   │  A | B | C | D          │    │
│  │  | CODE | LEN | PAYLOAD │   │   │  1B  2B  1B  CB         │    │
│  └─────────────────────────┘   │   └─────────────────────────┘    │
│              │                  │              ▲                    │
│              ▼                  │              │                    │
│         ┌──────────────────────────────────────┐                    │
│         │         串口 (全双工)                 │                    │
│         │  TX 发 Task   RX 收 Notify           │                    │
│         └──────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         STM32 (下位机)                             │
├─────────────────────────────────┬───────────────────────────────────┤
│      RX 接收 Task              │      TX 发送 Notify              │
│  ┌─────────────────────────┐   │   ┌─────────────────────────┐    │
│  │  执行 Task              │   │   │  主动推送 Notify         │    │
│  │  按 TARGET + CODE 调度  │   │   │  执行完成/状态变化即发   │    │
│  └─────────────────────────┘   │   └─────────────────────────┘    │
└─────────────────────────────────┴───────────────────────────────────┘
```


## 三、Task 帧（ROCK5B → STM32）

### 3.1 格式

```
┌──────┬────────┬────────┬────────┬────────┬──────────────────┐
│ AA55 │  SEQ   │ TARGET │  CODE  │  LEN   │     PAYLOAD      │
│ 2B   │  2B    │  1B    │  1B    │  1B    │     N B          │
└──────┴────────┴────────┴────────┴────────┴──────────────────┘
```

| 字段      | 长度  | 说明                               |
| :-------- | :---: | :--------------------------------- |
| `AA 55`   |  2B   | 固定帧头，标识 Task 帧起始         |
| `SEQ`     |  2B   | 序列号，`uint16` 小端，ROCK5B 自增 |
| `TARGET`  |  1B   | 目标模块（见 6.1）                 |
| `CODE`    |  1B   | 命令码（见 6.2）                   |
| `LEN`     |  1B   | PAYLOAD 字节数（0~64）             |
| `PAYLOAD` | LEN B | 命令参数（格式由各模块定义）       |

**帧大小**：最小 7 字节（LEN=0），最大 71 字节（LEN=64）

### 3.2 SEQ 规则

- ROCK5B 每发一帧 `SEQ += 1`
- 初始值 `0x0001`，`0xFFFF` 后回绕到 `0x0001`
- `0x0000` 保留，不使用

### 3.3 Task 命令表

| TARGET              | CODE | 命令     | PAYLOAD               | 说明                                      |
| :------------------ | :--: | :------- | :-------------------- | :---------------------------------------- |
| **SYSTEM(0x00)**    |      |          |                       |                                           |
|                     | 0x01 | STOP     | 空                    | 系统级停止，所有模块停止，需重新激活      |
|                     | 0x02 | CONTINUE | 空                    | 系统恢复运行（STOP 后重新激活）           |
|                     | 0x03 | QUERY    | 空                    | 查询系统状态                              |
|                     | 0x08 | HOME_ALL | 空                    | 全部归零（伸缩→升降顺序）                 |
| **CHASSIS(0x01)**   |      |          |                       |                                           |
|                     | 0x10 | RUN      | `DIR(1B) + SPEED(1B)` | 底盘运动                                  |
|                     | 0x11 | STOP     | 空                    | 底盘停止                                  |
| **LIFT(0x02)**      |      |          |                       |                                           |
|                     | 0x21 | MOVE_TO  | `POS(4B int32)`       | 升降到目标 mm                             |
|                     | 0x22 | STOP     | 空                    | 升降停止                                  |
| **EXTENSION(0x03)** |      |          |                       |                                           |
|                     | 0x31 | MOVE_TO  | `POS(4B int32)`       | 伸缩到目标 mm                             |
|                     | 0x32 | STOP     | 空                    | 伸缩停止                                  |
| **GRIPPER(0x06)**   |      |          |                       |                                           |
|                     | 0x42 | SET      | `STATE(1B)`           | 0=OPEN, 1=GRASP                           |
| **SESSION(0x07)**   |      |          |                       | 独立会话模块，不属于 SYSTEM               |
|                     | 0x01 | REQUIRE  | 空                    | 请求建立会话；V1.0 禁止使用 PAYLOAD       |

### 3.4 SESSION.REQUIRE 规则

SESSION 是独立模块，不属于 SYSTEM。

ROCK5B 上电后必须先发送 `SESSION.REQUIRE`。STM32 收到后必须通过 Notify 通道返回会话结果。会话建立成功前，STM32 不执行普通动作命令。

V1.0 规定：

```text
TARGET = SESSION(0x07)
CODE   = SESSION_REQUIRE(0x01)
LEN    = 0
PAYLOAD = 空
```

`SESSION.REQUIRE` 的 PAYLOAD 在未来版本可用于协议版本、能力位或额外校验；**V1.0 禁止使用 PAYLOAD，LEN 必须为 0**。

**各模块 STOP 命令职责：**

| 命令             | 作用范围                          |
| :--------------- | :-------------------------------- |
| `CHASSIS.STOP`   | 仅停止底盘，升降/伸缩不受影响     |
| `LIFT.STOP`      | 仅停止升降，底盘/伸缩不受影响     |
| `EXTENSION.STOP` | 仅停止伸缩，底盘/升降不受影响     |
| `SYSTEM.STOP`    | 全局停止 + 系统进入需重新激活状态 |


## 四、Notify 帧（STM32 → ROCK5B）

### 4.1 格式

```
┌──────┬────────┬───────┬────────────┐
│  A   │   B    │   C   │     D      │
│ 1B   │  2B    │  1B   │    C B     │
└──────┴────────┴───────┴────────────┘
```

| 字段 | 长度 | 说明                                    |
| :--- | :--: | :-------------------------------------- |
| `A`  |  1B  | 通知类型 + 来源模块（组合枚举，见 4.2） |
| `B`  |  2B  | 统一返回码（见 4.3），小端              |
| `C`  |  1B  | D 的字节数（0~64）                      |
| `D`  | C B  | 自由扩展数据（内容由各模块自行约定）    |

**帧大小**：最小 4 字节（C=0），最大 68 字节（C=64）

### 4.2 A 字段：完整通知类型

`A` 是 1 字节完整通知类型，不拆成两个线上字段。

STNP 使用“模块基值 + 通知种类”的编码规则生成完整通知类型，最终线上仍然只传输一个 `A` 字节。例如 `EVENT_LIFT` 是完整通知类型，不是两个字段。

```text
A = MODULE_BASE | NOTIFY_KIND
```

通知种类：

| 值 | 名称 |
|---:|:---|
| `0x0A` | `NOTIFY_KIND_ACCEPT` |
| `0x0B` | `NOTIFY_KIND_REJECT` |
| `0x0C` | `NOTIFY_KIND_EVENT` |

模块基值：

| 值 | 模块 |
|---:|:---|
| `0x10` | SYSTEM |
| `0x20` | CHASSIS |
| `0x30` | LIFT |
| `0x40` | EXTENSION |
| `0x60` | GRIPPER |
| `0x70` | SESSION |

示例：

```text
ACCEPT_LIFT = 0x30 | 0x0A = 0x3A
REJECT_LIFT = 0x30 | 0x0B = 0x3B
EVENT_LIFT  = 0x30 | 0x0C = 0x3C
```

SESSION 是独立模块，不与 SYSTEM 通知交叉。V1.0 只定义 `ACCEPT_SESSION`，其成功或拒绝原因由 `B` 字段表达。

### 4.2.1 A 字段合法集合

|   值   | 名称               | 语义                      |
| :----: | :----------------- | :------------------------ |
| `0x7A` | `ACCEPT_SESSION`   | SESSION 请求结果          |
| `0x1A` | `ACCEPT_SYSTEM`    | SYSTEM Task 被接受        |
| `0x2A` | `ACCEPT_CHASSIS`   | CHASSIS Task 被接受       |
| `0x3A` | `ACCEPT_LIFT`      | LIFT Task 被接受          |
| `0x4A` | `ACCEPT_EXTENSION` | EXTENSION Task 被接受     |
| `0x6A` | `ACCEPT_GRIPPER`   | GRIPPER Task 被接受       |
| `0x1B` | `REJECT_SYSTEM`    | SYSTEM Task 被拒          |
| `0x2B` | `REJECT_CHASSIS`   | CHASSIS Task 被拒         |
| `0x3B` | `REJECT_LIFT`      | LIFT Task 被拒            |
| `0x4B` | `REJECT_EXTENSION` | EXTENSION Task 被拒       |
| `0x6B` | `REJECT_GRIPPER`   | GRIPPER Task 被拒         |
| `0x1C` | `EVENT_SYSTEM`     | SYSTEM 事件（含状态返回） |
| `0x2C` | `EVENT_CHASSIS`    | CHASSIS 事件              |
| `0x3C` | `EVENT_LIFT`       | LIFT 事件                 |
| `0x4C` | `EVENT_EXTENSION`  | EXTENSION 事件            |
| `0x6C` | `EVENT_GRIPPER`    | GRIPPER 事件              |

`A` 字段必须按合法集合判断，不能用 `0x1A~0x6C` 这种范围判断。

允许用编码规则动态构建合法表，但解析结果必须仍然落到上述完整通知类型，例如 `EVENT_LIFT`、`ACCEPT_CHASSIS`。

### 4.2.2 SESSION Notify

SESSION 返回走 Notify 通道，不套 `AA55`。

成功：

```text
A = ACCEPT_SESSION
B = SUCCESS
C = 0
D = 空
```

拒绝：

```text
A = ACCEPT_SESSION
B = 拒绝原因错误码
C = 0
D = 空
```

V1.0 规定 SESSION Notify 的 `C` 必须为 0，`D` 必须为空。未来版本可使用 `D` 返回协议版本、能力位或拒绝详情；V1.0 禁止使用。

### 4.3 B 字段：统一返回码

|    值    | 名称                     | 说明         |
| :------: | :----------------------- | :----------- |
| `0x0000` | `SUCCESS`                | 成功         |
| `0x0001` | `ERR_UNKNOWN_CMD`        | 未知命令     |
| `0x0002` | `ERR_PARAM_OUT_OF_RANGE` | 参数超范围   |
| `0x0003` | `ERR_AXIS_BUSY`          | 另一轴运动中 |
| `0x0004` | `ERR_NOT_HOMED`          | 未归零       |
| `0x0005` | `ERR_ESTOP_ACTIVE`       | 急停锁存     |
| `0x0006` | `ERR_FAULT_ACTIVE`       | 故障锁存     |
| `0x0007` | `ERR_MOTION_TIMEOUT`     | 运动超时     |
| `0x0008` | `ERR_HOME_TIMEOUT`       | HOME 超时    |
| `0x0009` | `ERR_INTERLOCK`          | 互锁冲突     |
| `0x000A` | `ERR_SESSION_REQUIRED`   | 会话未建立   |
| `0xFFFF` | `ERR_INTERNAL`           | 内部错误     |

### 4.4 C/D 使用规则

- **C = D 的字节数**（0~64）
- **D = 扩展数据**，协议层不解析，内容由模块开发者内部约定

**典型 D 内容示例（业务层约定）：**

| 场景         | A               | B                    | C    | D                      |
| :----------- | :-------------- | :------------------- | :--- | :--------------------- |
| 升降到达目标 | `EVENT_LIFT`    | `SUCCESS`            | 4    | 4B int32 位置 mm       |
| 升降超时     | `EVENT_LIFT`    | `ERR_MOTION_TIMEOUT` | 0    | 空                     |
| 夹爪动作完成 | `EVENT_GRIPPER` | `SUCCESS`            | 0    | 空                     |
| 夹爪状态反馈 | `EVENT_GRIPPER` | `SUCCESS`            | 1    | 1B 状态（0/1）         |
| 状态查询响应 | `EVENT_SYSTEM`  | `SUCCESS`            | 12   | 12B 状态快照（见 9.2） |
| 细化故障     | `EVENT_CHASSIS` | `ERR_INTERNAL`       | 1    | 1B 子故障码            |
| 会话建立成功 | `ACCEPT_SESSION`| `SUCCESS`            | 0    | 空                     |
| 会话建立失败 | `ACCEPT_SESSION`| 非 `SUCCESS`         | 0    | 空                     |


## 五、数据链路规则

### 5.1 Task 帧解析

```
1. 搜索 AA 55
2. 读到 AA 55 后，读取后续 5 字节（SEQ 2B + TARGET 1B + CODE 1B + LEN 1B）
3. LEN 合法性检查：LEN > 64 → 丢弃，重新同步
4. 读取 LEN 字节 PAYLOAD
5. 按 TARGET + CODE 路由到对应模块执行
```

### 5.2 Notify 帧解析

```
1. 读取 1 字节 A
2. A 合法性检查：A 必须属于 4.2.1 合法集合，否则丢弃该字节
3. 读取 2 字节 B
4. 读取 1 字节 C
5. C 合法性检查：C > 64 → 丢弃当前 Notify，从下一字节重新同步
6. 读取 C 字节 D
7. 根据 A 路由到对应模块
8. 模块解析 B 和 D
```

`A` 可以由编码规则动态构建合法表，但实际判断必须是合法集合判断，不允许使用连续范围判断。

### 5.3 同步与错误恢复

| 场景                   | 处理方式                            |
| :--------------------- | :---------------------------------- |
| 字节错位               | 扫描 `AA 55` 重新同步               |
| A 非法                 | 丢弃当前字节，从下一字节重新同步    |
| C > 64                 | 丢弃当前 Notify，从下一字节重新同步 |
| Task 超时未收到 Notify | ROCK5B 重发或报错                   |
| STM32 无响应           | ROCK5B 超时后停止动作命令，重新执行 SESSION.REQUIRE 与启动查询流程 |


### 5.4 CRC 规则

STNP V1.0 不实现 CRC。

V1.0 约束：

```text
Task 帧不追加 CRC。
Notify 不追加 CRC。
协议中不定义 CRC 字段。
STM32 与 ROCK5B 均不得在 V1.0 私自加入 CRC。
```

V1.0 依赖 `AA55 + LEN`、Notify 合法 `A` 集合、`C` 长度、超时和重新查询进行基础错误处理。未来版本如需增强链路可靠性，应通过新版本显式定义，不在 V1.0 中隐式添加。

## 六、枚举定义

### 6.1 TARGET（Task 帧目标模块）

|   值   | 名称               | 说明 |
| :----: | :----------------- | :--- |
| `0x00` | `TARGET_SYSTEM`    | 系统 |
| `0x01` | `TARGET_CHASSIS`   | 底盘 |
| `0x02` | `TARGET_LIFT`      | 升降 |
| `0x03` | `TARGET_EXTENSION` | 伸缩 |
| `0x06` | `TARGET_GRIPPER`   | 夹爪 |
| `0x07` | `TARGET_SESSION`   | 会话 |

### 6.2 底盘方向（DIR）

|   值   | 名称          |
| :----: | :------------ |
| `0x01` | `FORWARD`     |
| `0x02` | `BACKWARD`    |
| `0x03` | `SHIFT_LEFT`  |
| `0x04` | `SHIFT_RIGHT` |
| `0x05` | `SPIN_LEFT`   |
| `0x06` | `SPIN_RIGHT`  |

### 6.3 夹爪状态（GRIPPER）

|   值   | 名称    |
| :----: | :------ |
| `0x00` | `OPEN`  |
| `0x01` | `GRASP` |


## 七、软件架构（模块化设计）

### 7.1 模块划分

```
┌─────────────────────────────────────────────────────────┐
│                    Notify 分发器                        │
│              （读 A → 路由到对应模块）                   │
└─────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  LiftModule   │   │ ExtensionMod  │   │  ChassisMod   │
│ ───────────── │   │ ───────────── │   │ ───────────── │
│ • 状态机      │   │ • 状态机      │   │ • 状态机      │
│ • Notify解析  │   │ • Notify解析  │   │ • Notify解析  │
│ • 位置缓存    │   │ • 位置缓存    │   │ • 方向/速度   │
└───────────────┘   └───────────────┘   └───────────────┘
```

### 7.2 模块职责

| 模块                | 负责 Task                           | 负责 Notify     | 状态                       |
| :------------------ | :---------------------------------- | :-------------- | :------------------------- |
| **SessionModule**   | SESSION.REQUIRE                     | ACCEPT_SESSION  | 会话是否建立               |
| **SystemModule**    | SYSTEM.STOP/CONTINUE/QUERY/HOME_ALL | EVENT_SYSTEM    | 系统运行状态、故障锁存     |
| **ChassisModule**   | CHASSIS.RUN/STOP                    | EVENT_CHASSIS   | 方向、速度、运行状态       |
| **LiftModule**      | LIFT.MOVE_TO/STOP                   | EVENT_LIFT      | 当前位置、目标位置、轴状态 |
| **ExtensionModule** | EXTENSION.MOVE_TO/STOP              | EVENT_EXTENSION | 当前位置、目标位置、轴状态 |
| **GripperModule**   | GRIPPER.SET                         | EVENT_GRIPPER   | 当前夹持状态               |

### 7.3 模块内聚原则

**每个模块自己定义自己能干什么，不搞全局抽象。**

- `CHASSIS.STOP` 只停底盘
- `LIFT.STOP` 只停升降
- `EXTENSION.STOP` 只停伸缩
- `SYSTEM.STOP` 是全局级，归 SystemModule 管
- `SESSION.REQUIRE` 是会话入口，归 SessionModule 管

新增模块时，模块内部自己定义命令集和 Notify 解析逻辑，不修改已有模块代码。


## 八、会话建立

### 8.1 请求（Task）

```text
TARGET=SESSION(0x07), CODE=0x01 (REQUIRE), LEN=0
```

V1.0 禁止 `SESSION.REQUIRE` 携带 PAYLOAD。

### 8.2 响应（Notify）

成功：

```text
A=ACCEPT_SESSION, B=SUCCESS, C=0, D=空
```

拒绝：

```text
A=ACCEPT_SESSION, B=拒绝原因错误码, C=0, D=空
```

### 8.3 会话规则

STM32 上电后默认处于会话未建立状态。会话建立前，除 `SESSION.REQUIRE` 外，普通 Task 不执行。

会话未建立时收到普通 Task，STM32 返回：

```text
A=ACCEPT_SESSION, B=ERR_SESSION_REQUIRED, C=0, D=空
```

ROCK5B 收到 `ACCEPT_SESSION + SUCCESS` 后，才允许进入启动查询和正常业务流程。

## 九、状态查询

### 9.1 请求（Task）

```
TARGET=SYSTEM, CODE=0x03 (QUERY), LEN=0
```

### 9.2 响应（Notify）

```
A=EVENT_SYSTEM, B=SUCCESS, C=12, D=状态快照（12 字节）
```

**D 字段内容（业务层约定）：**

| 偏移 | 长度 | 内容                                                         |
| :--: | :--: | :----------------------------------------------------------- |
|  0   |  2B  | `system_flags`（bit0=session_ready, bit2=estop, bit3=fault） |
|  2   |  1B  | `lift_state`（0=未归零, 1=就绪, 2=运动中, 3=故障）           |
|  3   |  1B  | `extension_state`（同上）                                    |
| 4~7  |  4B  | `lift_position_mm`（int32 小端）                             |
| 8~11 |  4B  | `extension_position_mm`（int32 小端）                        |


## 十、通信流程

### 10.1 启动流程

```
ROCK5B                                STM32
   │                                     │
   │───── SESSION.REQUIRE ──────────────>│
   │<──── ACCEPT_SESSION (SUCCESS) ─────│  会话建立
   │                                     │
   │───── SYSTEM.QUERY ─────────────────>│
   │<──── EVENT_SYSTEM (状态快照) ───────│
   │                                     │
   │───── SYSTEM.HOME_ALL ──────────────>│
   │<──── ACCEPT_SYSTEM ─────────────────│  接受，开始HOME
   │        (伸缩HOME中...)              │
   │<──── EVENT_EXTENSION (SUCCESS) ────│  伸缩HOME完成
   │        (升降HOME中...)              │
   │<──── EVENT_LIFT (SUCCESS) ─────────│  升降HOME完成
   │<──── EVENT_SYSTEM (SUCCESS) ───────│  HOME_ALL完成
   │                                     │
   │──────── 进入正常业务 ──────────────>│
```

### 10.2 正常业务（LIFT.MOVE_TO）

```
ROCK5B                                STM32
   │                                     │
   │── LIFT.MOVE_TO(12mm) ──────────────>│
   │<──── ACCEPT_LIFT ───────────────────│  接受，开始执行
   │        (升降运动中...)              │
   │<──── EVENT_LIFT (SUCCESS, C=4) ────│  到达12mm
```

### 10.3 系统停止与恢复

```
ROCK5B                                STM32
   │                                     │
   │───── SYSTEM.STOP ──────────────────>│
   │<──── ACCEPT_SYSTEM ─────────────────│  所有模块停止
   │                                     │
   │        (系统进入待激活状态)          │
   │                                     │
   │───── SYSTEM.CONTINUE ──────────────>│
   │<──── ACCEPT_SYSTEM ─────────────────│  系统恢复运行
```

SYSTEM.STOP 被接受后，系统进入 STOPPED 状态。

STOPPED 状态下仅允许：

```text
SESSION.REQUIRE
SYSTEM.QUERY
SYSTEM.CONTINUE
```

其他动作命令必须拒绝：

```text
A = REJECT_<对应模块>
B = ERR_INTERLOCK
C = 0
D = 空
```

例如 STOPPED 状态下收到 `LIFT.MOVE_TO`：

```text
A = REJECT_LIFT
B = ERR_INTERLOCK
C = 0
D = 空
```


## 十一、协议汇总

| 维度         | Task 帧（ROCK5B→STM32）                      | Notify 帧（STM32→ROCK5B） |
| :----------- | :------------------------------------------- | :------------------------ |
| **方向**     | TX 通道                                      | RX 通道                   |
| **格式**     | `AA55 + SEQ + TARGET + CODE + LEN + PAYLOAD` | `A + B + C + D`           |
| **最小帧**   | 7 字节                                       | 4 字节                    |
| **最大帧**   | 71 字节                                      | 68 字节                   |
| **帧头**     | 固定 `AA 55`                                 | 无固定帧头                |
| **序列号**   | `SEQ` 自增                                   | 无                        |
| **路由**     | 按 `TARGET + CODE`                           | 按完整通知类型 `A`        |
| **扩展方式** | 新增 `TARGET`/`CODE`                         | D 字段自由扩展            |
| **模块内聚** | 各模块定义自己的命令集                       | 各模块解析自己的 Notify   |


## 十二、设计原则回顾

1. **全双工利用**：TX/RX 独立，控制与通知并行
2. **控制/通知解耦**：无命令-回复强绑定
3. **极简帧格式**：Task 7~71B，Notify 4~68B
4. **广播通知**：STM32 随时可发，不归属任何 Task
5. **模块内聚**：每个模块自己定义命令集，各自维护状态
6. **自由扩展**：协议层固定，业务层在 D 字段任意扩展
7. **不预埋字段**：不为“可能用不到”的场景增加复杂度
8. **V1.0 不实现 CRC**：不定义 CRC 字段，不私自追加 CRC，未来版本如需增强再显式定义