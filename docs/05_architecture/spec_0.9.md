# STNP 0.9 结构规范（冻结版）

本规范规定 STNP 0.9 的结构：分层模型、Wire 格式、路由模型、Result 模型、Capability 定义位置、Transport 抽象与可选性总表。文中所有陈述均为 STNP 0.9 的规范内容。

## 1. 定位与术语表

### 1.1 文档定位

- 本文档是 STNP 0.9 的结构规范，规定 STNP 0.9 的分层模型、wire 槽位、路由、Result、Capability 与 Transport。
- 本文档不包含实现指引。
- 本文档覆盖以下内容：
  - 九层分层模型（§2）；
  - 两种帧家族的完整 Wire 格式，含 10 个槽位的字段目录、Capability 组合矩阵、Payload 预算、编码规则与流式重同步（§3）；
  - 路由模型（§4）；
  - Result 模型（§5）；
  - Capability 的定义位置（§6）；
  - Transport 抽象（§7）；
  - 可选性总表（§8）；
  - 生成配置规范（`stnp.build.json`，§8.2）；
  - 非目标与不变量（§9）；
  - 待定项（§10）。
- 本规范采用单一破坏性取向：不设过渡层、不设双读路径、不设转发垫片、不输出弃用告警；`additionalProperties: false` 直接拒绝旧格式，读到旧格式即失败，不做适配。规范、schema 与示例在同一破坏性批次内一次落地，不产生中间态。

### 1.2 术语表

| 术语 | 定义 |
|---|---|
| `CMD` / `CODE` | `CMD` 是本规范全文使用的名称，指 Task 帧中 1 字节命令码槽位；`CODE` 是同一 wire 槽位的历史别名。 |
| Protocol Profile | 一个 `.stnp` 工程内声明的、命名的一组帧结构 / Capability / 参数组合，正式定义见 §2。 |
| Capability | 控制帧内可选槽位（`[SEQ]`、`[CRC]`）是否存在的独立开关。首批 Capability 为 `SEQ` 与 `CRC`，二者相互独立，可分别开启或关闭。 |
| Frame | 帧家族共两种：Task 帧与 Notify 帧。 |
| Route | Task 的 `TARGET` 与 Notify 的 `SOURCE` 到接收实体的映射；寻址粒度为 Instance 级，`TARGET` = Instance ID，`SOURCE` = Instance ID。 |
| Instance | Module 的具体在线实体，只负责身份与绑定关系；Instance 不覆盖 Module 的 Command / Notify 定义。 |
| Module | 一类可复用功能定义，含 Command、Notify、Payload、Module Result。一个 Module 可对应多个 Instance。 |
| Command | Module 内 1 字节命令码，经 Task 帧的 `CMD` 槽位下行。 |
| Notify | Module 主动上报的帧家族，`NOTIFY` 占 1 字节。 |
| Payload | 帧内由 `LEN`（1 B）给出长度、由 `PAYLOAD` 承载的数据。 |
| Result（三类） | 三个语义类 `Core Status` / `Global Result` / `Module Result` 共用同一个 u16 wire `RESULT` 槽位，由 Editor 统一管理 ID。 |
| Transport | 协议 Core 之外的传输抽象；STNP Core 不绑定 UART，UART 只是默认实现之一。 |
| generation-time config | Capability 与帧结构的确定方式：生成期写入 `.stnp` / Schema，双端同源。 |
| `protocol.options` | 本端运行时行为开关容器，与 Capability 相对：不改 wire format、两端可不同、允许运行时切换。组级区分见 §2.2，字段见 §8.3。 |

本规范采用的分层术语链为（顺序固定，由 §2 展开）：

```text
Project → Protocol Profile → Capability → Frame → Route(Instance) → Module → Command/Notify → Payload/Result → Transport
```

## 2. 分层模型

```text
Project → Protocol Profile → Capability → Frame → Route(Instance) → Module → Command/Notify → Payload/Result → Transport
```

其中 Project / Protocol Profile / Capability 三层是生成期概念，决定帧长什么样；Frame 至 Payload/Result 五层描述 wire 与运行时的结构分工；Transport 是协议 Core 之外的字节通道抽象。

### 2.1 九层职责

| # | 层 | 一行职责 |
|---|---|---|
| 1 | Project | 一份 `.stnp` JSON 工程，是帧结构、Capability 与 Module 定义的单一事实源 |
| 2 | Protocol Profile | 工程内声明的一组帧结构 / Capability / 参数的命名组合；生成期把 wire 形态确定为一套唯一布局，双端同源 |
| 3 | Capability | 门控帧内可选槽位（`[SEQ]`、`[CRC]`）是否存在的独立开关，二者相互独立 |
| 4 | Frame | 定义 Task / Notify 两种帧家族及其固定槽位顺序 |
| 5 | Route(Instance) | 把 Task 的 `TARGET` / Notify 的 `SOURCE` 解析为接收实体；按 Instance 级寻址 |
| 6 | Module | 一类可复用功能定义，含 Command、Notify、Payload、Module Result；一个 Module 可对应多个 Instance |
| 7 | Command/Notify | 两个事务方向：Module 内 1 字节命令码经 Task 帧下行，Notify 帧家族自 Module 上行上报 |
| 8 | Payload/Result | 帧内数据语义槽位：`PAYLOAD` 承载数据且长度由 1 字节 `LEN` 给出，`RESULT` 为 2 字节 u16 结果码 |
| 9 | Transport | 字节流收发抽象，位于协议 Core 之外；UART 只是默认实现之一 |

两点说明：

- Payload 与 Result 并为一层，因为二者同为帧内数据语义槽位，不参与帧结构决策；其语义拆分（三类 Result）见 §5。
- Module 层与 Route(Instance) 层的分工：Module 层管定义，Instance 层管身份与绑定。

### 2.2 Capability 与帧布局的确定时机

- Capability（`SEQ` / `CRC`）的选择是生成期 Protocol Profile 的事。两端的帧布局由同一份配置各自生成而天然一致，不依赖任何运行时对齐步骤。
- STNP 不定义 Session/Profile 运行时机制：运行时不协商、不动态切换。Capability 固定在 Schema，不属于运行时状态。
- 变更 Capability 等价于变更 Protocol Profile 后重新生成，不是运行时行为。

**明确否定**：STNP 0.9 不定义、不引用、不预留任何 Session/Profile 状态机、运行时协商步骤或动态 Capability 切换；帧布局在生成期由 Protocol Profile 唯一确定，运行时零协商。

**组级区分**：`protocol.features` 是 Capability —— 改 wire format、两端必须一致、禁止运行时切换；`protocol.options` 是本端行为 —— 不改 wire format、两端可不同、允许运行时切换。二者不混同。

### 2.3 业务层模式（非协议行为）

- 协议本身不提供会话、ACK、握手或任何请求/响应语义。
- 若业务需要 "Session 式" 或 "ACK 式" 行为，惯用模式是：用户在 Module 里自定义一个握手/确认类 Command，对端业务代码处理该 Command 后，通过同一 Module 的 Notify 上报结果，发起方业务代码在自己的逻辑中核对该上报。
- 协议在其中提供的全部能力仅是：Task / Notify 两个异步方向的帧通道、每 Module 一个 Notify 回调入口，以及可选的 `SEQ` 事务标识；Task 与 Notify 的关联机制不在协议内（见 §10）。
- 业务代码与生成的协议代码分离。

## 3. Wire 格式

本节给出 STNP 0.9 的完整 wire 格式：两种帧家族的槽位语法（§3.1-3.3）、10 个槽位的字段目录（§3.4）、Capability 四组合布局矩阵（§3.5）、Payload 预算（§3.6）、编码规则（§3.7）、流式输入与重同步（§3.8），以及 SEQ 与 CRC 两个 Capability 的语义（§3.9-3.10）。

### 3.1 通用帧语法

- STNP 帧是线性字节序列，共两个帧家族：Task 帧与 Notify 帧。槽位语法中 `[...]` 表示由 Capability 控制的可选槽，不带方括号的槽位恒存在。
- `HEADER` 是帧家族的 2 字节 SOF：Task 帧取 `protocol.task.sof`，Notify 帧取 `protocol.notify.sof`（各 2 字节，每项 `0..255`）；两个 SOF 必须不同。
- SEQ 与 CRC 是首批 Capability，二者相互独立，可分别开启或关闭。

```text
Task   : HEADER | [SEQ] | TARGET | CMD | LEN | PAYLOAD | [CRC]
Notify : HEADER | [SEQ] | SOURCE | NOTIFY | RESULT | LEN | PAYLOAD | [CRC]
```

- 帧内除 `PAYLOAD` 外全部为定长槽位，`PAYLOAD` 长度由 `LEN` 给出。不存在任何未在本节登记的帧字段；每个 wire 字节都属于某个已声明槽位。
- SEQ 关闭时 SEQ 字段完全不存在。

### 3.2 Task 帧

Task 帧布局：

```text
Task   : HEADER | [SEQ] | TARGET | CMD | LEN | PAYLOAD | [CRC]
```

- `HEADER`：Task 家族 SOF，取 `task.sof`（2 B）。
- `[SEQ]`：SEQ Capability 开启时存在；关闭时完全不存在（语义见 §3.9）。
- `TARGET`：目标 Instance ID，1 B（路由语义见 §4）。
- `CMD`：Module 内 Command code，1 B。
- `LEN` + `PAYLOAD`：长度前缀 + 数据（预算见 §3.6）。
- `[CRC]`：CRC Capability 开启时存在（语义见 §3.10）。

### 3.3 Notify 帧

Notify 帧布局：

```text
Notify : HEADER | [SEQ] | SOURCE | NOTIFY | RESULT | LEN | PAYLOAD | [CRC]
```

- `HEADER`：Notify 家族 SOF，取 `notify.sof`（2 B）。
- `[SEQ]`：可选槽；由与 Task 相同的 SEQ Capability 开关统一门控（Task/Notify 同开同关，不设独立开关）；开启时其取值来自与 Task 相同的发送方计数器；不存在独立的 `notify.seq` 生成期配置键。
- `SOURCE`：来源 Instance ID，1 B（路由语义见 §4）。
- `NOTIFY`：Module 内 Notify code，1 B。
- `RESULT`：u16 wire 结果槽，2 B；三类 Result 共用此槽（见 §5）。
- `LEN` + `PAYLOAD`、`[CRC]`：同 Task 帧。
- 通知不再分类：接受／拒绝语义由 `RESULT` 槽承载（wire 布局不变）。

### 3.4 字段目录（10 槽位）

下表列出 10 个槽位的宽度、取值范围、存在条件、语义与约束。

| 槽位 | 宽度 | 取值范围 | 存在条件 | 语义 | 约束 |
|---|---|---|---|---|---|
| `HEADER` | 2 B | 每字节 `0x00..0xFF`，取自 `task.sof` / `notify.sof` | 恒存在（两家族各自的第一个槽） | 帧家族起始标志（SOF），流解析据此定位帧边界（§3.8） | 两个 SOF 必须不同 |
| `SEQ` | 2 B | wire `0x0000..0xFFFF`（u16 小端）；初值 `task.seq.start ∈ 1..65535` | SEQ Capability 开启时存在；关闭时完全不存在（Task/Notify 同门控） | 可选的事务标识基础（§3.9） | `task.seq.type` 固定 `u16`；`start` 不得属于 `task.seq.reserved`；`0xFFFF` 回绕到 0 后继续跳过 reserved（§3.9） |
| `TARGET` | 1 B | 生成配置合法范围 `1..255` | 仅 Task 帧，恒存在 | 目标 Instance ID（路由见 §4） | 须对应接收端存在的 Instance；`router_instance_max`（默认 8，范围 `1..255`）约束 Router 实例数 |
| `CMD` | 1 B | `0x00..0xFF` | 仅 Task 帧，恒存在 | Module 内 Command code | Module 内唯一 |
| `SOURCE` | 1 B | 生成配置合法范围 `1..255` | 仅 Notify 帧，恒存在 | 来源 Instance ID（路由见 §4） | 同 `TARGET` |
| `NOTIFY` | 1 B | `0x00..0xFF` | 仅 Notify 帧，恒存在 | Module 内 Notify code | Module 内唯一 |
| `RESULT` | 2 B | `0x0000..0xFFFF`（u16 小端） | 仅 Notify 帧，恒存在 | Global Result 与 Module Result 的 wire 承载；三类 Result 共用此 u16 槽（见 §5） | 值区间分配见 §5.4 |
| `LEN` | 1 B | `0x00..0xFF`，且 ≤ `max_payload` | 恒存在（两家族） | `PAYLOAD` 的字节长度 | `max_payload ∈ 1..255`；`LEN=0` 表示无 Payload |
| `PAYLOAD` | `0..255 B` | 变长，长度 = `LEN` | `LEN > 0` | Command / Notify 数据，VTL 编码或 Raw bytes | 不超过 `max_payload`；C struct padding 不上 wire（§3.7） |
| `CRC` | 2 B | `0x0000..0xFFFF`（u16 小端） | CRC Capability 开启时存在；关闭时完全不存在 | CRC16-Modbus 帧完整性校验 | 覆盖帧头到 Payload 的全部 body，CRC 自身以 u16 小端追加 |

### 3.5 Capability 组合矩阵

各槽位宽度为：`HEADER` 2 B、`SEQ` 2 B、`TARGET` / `SOURCE` / `NOTIFY` / `CMD` 各 1 B、`RESULT` 2 B、`LEN` 1 B、`CRC` 2 B。矩阵取 `max_payload` 的 Schema 上界 255；工程配置了更小的 `max_payload` 时，把实际值代入同一公式。

逐槽相加的推导：

```text
Task 头   = 2 (HEADER) + [2 SEQ] + 1 (TARGET) + 1 (CMD) + 1 (LEN)
              → SEQ 关 = 5 B；SEQ 开 = 7 B
Notify 头 = 2 (HEADER) + [2 SEQ] + 1 (SOURCE) + 1 (NOTIFY) + 2 (RESULT) + 1 (LEN)
              → SEQ 关 = 7 B；SEQ 开 = 9 B
尾部      = [2 CRC]     → CRC 关 = 0 B；CRC 开 = 2 B
最大帧    = 头 + max_payload (255) + 尾
```

| SEQ | CRC | Task 头 (B) | Task 尾 (B) | Task 最大帧 (B) | Notify 头 (B) | Notify 尾 (B) | Notify 最大帧 (B) |
|---|---|---:|---:|---:|---:|---:|---:|
| 关 | 关 | 2+1+1+1 = 5 | 0 | 5+255+0 = 260 | 2+1+1+2+1 = 7 | 0 | 7+255+0 = 262 |
| 关 | 开 | 2+1+1+1 = 5 | 2 | 5+255+2 = 262 | 2+1+1+2+1 = 7 | 2 | 7+255+2 = 264 |
| 开 | 关 | 2+2+1+1+1 = 7 | 0 | 7+255+0 = 262 | 2+2+1+1+2+1 = 9 | 0 | 9+255+0 = 264 |
| 开 | 开 | 2+2+1+1+1 = 7 | 2 | 7+255+2 = 264 | 2+2+1+1+2+1 = 9 | 2 | 9+255+2 = 266 |

帧最大尺寸按 `max(Task 最大帧, Notify 最大帧)` 计算；RX Ring 按 4 个最大帧预留。

### 3.6 Payload 预算

- `LEN` 为 1 字节 → 可表达的长度为 `0..255`；`max_payload` 被 Schema 限制在 `1..255`。因此单帧 Payload 的上限恒为 255 字节：1 字节长度前缀无法表达更大的值，帧内也不存在扩展长度槽位。最大帧 = 头 + `max_payload` + 尾。
- `LEN=0` 表示无 Payload；空载荷帧不附带任何空结构字节（不变量见 §9.1）。
- 边界强制：生成侧超限即报错（`len(payload) > max_payload` 抛 `ProtocolError`）；解析侧 `LEN > max_payload` 判为非法长度并触发 1 字节滑动重同步。

### 3.7 编码规则

- 字节序：小端，固定值。`byte_order` 在 Schema 中为 `const "little"`；`u16/u32/i32` 统一使用小端编码。
- 基础 wire 类型恰四种：`u8` = 1 B、`u16` = 2 B、`u32` = 4 B、`i32` = 4 B。
- common alias / enum 最终仍映射到上述固定宽度基础类型；alias / enum 不引入新的 wire 宽度。
- 多字节槽位映射：`SEQ` / `RESULT` / `CRC` 均为 u16 小端；`HEADER` 为 2 字节配置直出；单字节槽位为 u8 直出。
- padding 永不上 wire：typed struct 的 `sizeof(struct)` 不是 wire size；Core VTL 按 metadata 中的字段 offset / wire type / wire size 逐字段编码，因此 C padding 不进入 wire。禁止把 C struct 原样整体拷贝上 wire（不变量见 §9.1）。

### 3.8 流式输入与重同步

- 接收入口只复制字节：接收原语将 bytes 复制进静态 RX Ring，不做 Parse / Router / Handler 调用；解析在 Process 阶段进行，单次调用最多推进一个完整帧。
- SOF 扫描：运行时在缓冲区内寻找 Task / Notify 两个 2 字节 SOF 中位置更靠前者；缓冲不足 2 字节时等待，无任何 SOF 且缓冲多于 1 字节时仅保留末字节继续。
- 支持半帧与多帧粘包：候选帧不完整则等待更多字节；一次 feed 可产出多帧。
- 错误恢复一律 1 字节滑动：`LEN` 非法（> `max_payload`）丢弃 1 字节继续扫描；CRC / 结构校验失败同样 1 字节滑动，避免错误候选帧吞掉其内部已到达的有效帧。
- 可选 SEQ 使 `LEN` 槽位的字节下标不再恒定：Task 帧在 SEQ 关/开时分别为下标 4 / 6，Notify 帧为下标 6 / 8。解析器须按 Capability 组合先算头长再定位 `LEN`。

### 3.9 SEQ：事务标识基础

- SEQ 启用后是可选的事务标识（transaction identity）基础：给上层一个可区分先后帧的 u16 序号。Core 不定义任何传输层可靠性语义；SEQ 不提供确认、关联或任何可靠性语义；Task 与 Notify 的关联机制见 §10。
- 计数器在 Transport 写出之前保留并递增（reserve-before-write）：在发送临界区内先推进计数器再返回推进前的值，随后才构帧与写出。构帧或写出失败时序号已被消耗，允许产生 SEQ 空洞；并发发送安全。
- 计数器规则：初值 `task.seq.start`（`1..65535`）；`0xFFFF` 后回绕到 `0`、再跳过 `task.seq.reserved` 中的值；`start` 本身不得属于 reserved。Task 与 Notify 共用该计数器与同一门控。

### 3.10 CRC 完整性校验

- 算法参数：CRC16-Modbus，初值 `0xFFFF`、多项式 `0xA001`；覆盖帧头到 Payload 的全部 body，CRC 自身以 u16 小端追加。
- CRC 是 Integrity Capability，启用后用于帧完整性校验；关闭后 CRC 字段完全不存在。
- 生成期开关：`protocol.features.crc.enabled` 决定 CRC 槽位是否存在（默认 `false`）。
- STNP 0.9 不包含 `features.crc.runtime_toggle` 字段。CRC 槽位的存在性只由生成期 Capability 集合（Schema 中的 SEQ / CRC 配置）唯一决定，运行时不改变帧布局。

## 4. 路由模型

### 4.1 路由链

Task / Notify 的路由终点是具体的 Instance。运行时路由链为：

```text
Instance ID → Instance → Module → Command/Notify
```

| 环节 | 一行说明 |
|---|---|
| `Instance ID` | 1 字节 wire 标识：Task 帧的 `TARGET` 槽 / Notify 帧的 `SOURCE` 槽承载，取值 `1..255` 且全局唯一 |
| `Instance` | Module 的具体在线实体：`.stnp` 中 `instances[]` 的一项，`name` 全局唯一，并通过 `module` 字段绑定到一个已启用 Module |
| `Module` | 一类可复用的协议定义集合：持有 Command 码表、Notify 码表、Payload 定义与 Module Result |
| `Command/Notify` | Module 内 1 字节业务码：接收方解析出 Instance 后，按该 Instance 所绑 Module 的码表解释 `CMD` / `NOTIFY` 槽；Command 与 Notify 属不同码表，可使用相同数值 |

按帧家族展开：

- **Task 方向**：发送方在 `TARGET` 填目的 Instance ID；接收端按 ID 定位本地 Instance，再进入其 Module 的 Command 表分发。
- **Notify 方向**：发送方在 `SOURCE` 填自身 Instance ID；`NOTIFY` 码按发送方 Instance 所绑 Module 解释。`RESULT` 槽的语义归属见 §5。

### 4.2 TARGET 与 SOURCE

- Task 帧 `TARGET` 槽是「Instance ID，合法生成配置范围 `1..255`」；Notify 帧 `SOURCE` 槽是「来源 Instance ID」。
- 两个槽位承载 Instance ID；路由链见 §4.1。宽度与存在条件见 §3.4。

### 4.3 1 Module → N Instances

- 一个 Module 定义可同时被任意多个 Instance 绑定：`instances[]` 的每一项独立声明 `module` 引用（必须引用 enabled Module）；数组与构建器均不限制多个 Instance 指向同一 Module。
- 一个 Module 若没有任何 Instance 绑定，它就不出现在任何路由路径上。

### 4.4 Instance 不覆盖 Module 定义

- 码表、Payload、Result 归属等协议定义只属于 Module 层；Instance 只负责身份与绑定关系。
- 实现层允许 Instance 覆盖 Module 默认的处理函数 / validator / callback。这是代码实现层的覆盖，发生在生成的行为代码中，不改变 Module 的 wire 定义（码表、Payload 结构、Result 语义）。

### 4.5 Instance ID 空间与 router_instance_max

| 项 | 取值 |
|---|---|
| Instance ID 取值范围 | `1..255`（1 字节 `TARGET` / `SOURCE` 槽内） |
| Instance ID 唯一性 | 全局唯一（跨全部实例，含跨 Module 的实例） |
| 实例数量上限 | `protocol.router_instance_max`：schema 允许 `1..255`，默认 `8`；实例总数不得超过该值 |

说明：

- `router_instance_max` 是配置值，可以低于 ID 空间上限 255；其实际作用是限制实例总数，而非收窄单个 ID 的取值范围。
- Instance ID 的 wire 承载宽度（`TARGET` 1 B / `SOURCE` 1 B）见 §3.4。

## 5. Result 模型

### 5.1 三类 Result

Result 分为三类：

| 类 | 语义 | wire 是否出现 | 承载位置 |
|---|---|---|---|
| `Core Status` | STNP Runtime / API 自身返回状态 | **不上 wire** | 无帧内槽位；仅存在于 Runtime / API 的返回路径 |
| `Global Result` | 工程级共享业务结果 | **上 wire** | Notify 帧 `RESULT` 槽，与 Module Result 共用（见 5.2） |
| `Module Result` | 某个 Module 专属业务结果 | **上 wire** | Notify 帧 `RESULT` 槽，与 Global Result 共用（见 5.2） |

`Global Result` 不属于任何 Module，也不通过额外的 SYSTEM Module 表达；STNP 不引入、不暗示任何 SYSTEM Module 或等价机制。

### 5.2 Global Result 与 Module Result 共用同一个 u16 RESULT 槽

- 两类语义复用同一个 2 字节 `RESULT` 槽：不新增槽位、不加宽字段、不引入第二结果字段。
- 「共用」只是槽位复用；一个 `RESULT` 值在某一帧中到底是 Global 语义还是 Module 语义，按值区间判定（见 §5.4）。

### 5.3 Core Status 不上 wire

- 三类中只有 Global Result 与 Module Result 被定义为共用同一个 wire `RESULT` 字段；`Core Status` 是「STNP Runtime / API 自身返回状态」，被定义在 Runtime / API 的返回路径上，而非任何帧结构中。
- `Core Status` 无帧内承载槽位。

### 5.4 Result ID 区间分配

| 项 | 内容 |
|---|---|
| 工程级 `OK` | `0x0000`，由顶层 `global_results` 中名为 `OK` 的条目声明 |
| Global Result 区间 | `0x0001..0x00FF`，最多 255 个 |
| Module Result 区间 | `0x0100..0xFFFF`，每 Module 256 个连续值，最多 255 个 Module |
| 语义区分方式 | 按值区间判定 |

分配规则：

- `0x0000` 保留为工程级 `OK`；工程级 `OK` 由顶层 `global_results` 中名为 `OK`、值为 `0x0000` 的条目声明。
- `0x0001..0x00FF` 为 Global Result，由 `.stnp` 顶层 `global_results` 数组声明，最多 255 个。
- `0x0100..0xFFFF` 为 Module Result：按 `modules[]` 顺序每 Module 分配 256 个连续值，第 i 个 Module（从 0 起）占用 `0x0100 + 256*i` 到 `0x0100 + 256*i + 255`；最多支持 255 个 Module，每 Module 最多 256 个 Return Code。
- 语义区分按值区间判定。
- 每个 Module 内强制存在名为 `OK` 的 Return Code，其值落在该 Module 的区间内。
- 工程级 `OK`（`0x0000`）与 Module 级 `OK` 并存，语义不同：前者表示整条链路成功，后者表示该 Module 处理成功。
- 示例：`modules[]` 中第 0 个 Module 的区间为 `0x0100..0x01FF`，第 1 个为 `0x0200..0x02FF`。
- 两类 Result 的 ID 由 Editor 统一管理。

## 6. Capability 定义位置

### 6.1 Capability 固定于 Schema

- Capability 集合固定在 Schema，不属于运行时状态。运行时既不需要发现对端的 Capability 集合，也不存在任何切换帧布局的动作。
- `SEQ` 与 `CRC` 是 `.stnp` 的生成期配置；双端由同一份配置生成，帧结构天然一致。

### 6.2 生成期决策模型

Capability 的确定流程是纯生成期的：

1. 用户在 `.stnp` 工程中写定 Capability 开关集合（决定哪些可选槽位存在，槽位本身见 §3）。
2. 该配置经 Schema 校验后进入 IR（`.stnp` 是单一事实源）。
3. 通信双端各自由同一份配置生成协议代码。

帧布局匹配不需要任何运行时动作来保证：它是同源生成的构造性结果（by construction）。两端之间没有需要协商的对象，运行时不协商；也不存在动态切换 Capability 的机制，帧布局在一份配置的生命周期内保持不变。

生成期 Capability 恰有两项独立开关：`protocol.features.seq.enabled` 与 `protocol.features.crc.enabled`，均为 boolean，默认 `false`；不存在其他 Capability 键。

## 7. Transport 抽象

### 7.1 Core 与传输介质解耦

- STNP Core 不绑定 UART。Runtime 统一通过 Transport Interface 工作：

```text
STNP Runtime
    ↓
Transport Interface
    ├─ UART
    ├─ USB CDC
    ├─ TCP
    └─ Custom
```

- UART 保留为默认实现之一，而不是协议本身的一部分。Transport Interface 是协议 Core 之外的抽象层。

### 7.2 Transport Interface 契约

本节只在契约层描述 Transport Interface 必须提供什么；不指定任何具体库、SDK、运行时，也不给出任何 API 签名或类设计。契约共三项：

| 契约项 | 契约要求（必须提供） |
|---|---|
| 收字节 | 将传输介质到达的字节流交给 Core，且只搬运字节、不做协议处理 |
| 发字节 | 将 Core 组好的完整帧字节交给传输介质发送，发送时机由调用方掌握 |
| 处理驱动 / 唤醒钩子 | 提供字节到达后驱动 Core 推进处理的时机（轮询或唤醒均可，契约不限定形式） |

契约要点：

- **Core 是传输无关的（transport-agnostic）**：Core 只依赖上表三项契约，不感知具体介质；Core 无 RTOS / HAL / malloc 依赖，也不 include 任何 RTOS 头文件。
- **四种实现对 Core 可互换**：对 Core 而言它们没有语义差别。
- **传输层不参与协议语义**：Capability 与帧布局在生成期已经固定（§6），传输层没有可协商的内容，运行时不协商；Transport 不理解帧内容，只负责收发字节与驱动处理。帧语法、路由与 Result 语义分别见 §3、§4、§5。

### 7.3 四种 Transport 与默认实现

- Transport Interface 下挂四种实现：**UART / USB CDC / TCP / Custom**。
- **UART：默认实现**。
- **USB CDC / TCP / Custom**：本规范不规定其形态、缓冲策略或错误语义；其具体化属于实现层工作，不进入本结构规范。
- **非目标**：本节不指定任何具体串口库、网络栈或运行时，不定义 Transport Interface 的函数签名。

## 8. 可选性总表

本节是全文唯一的字段与槽位可选性清单，按 8.1 至 8.5 五个小节分组呈现，五张分表共用同一列契约（列名与列序完全一致）。本表登记 STNP 0.9 的冻结字段集与 10 个 wire 槽位；字段语义、wire 编码分别见 §3、§4、§5。

列契约：

- 路径/槽位：`.stnp config` 行写 schema 点分路径；`build config` 行写 `stnp.build.json` 的点分路径；wire 行写槽位名。
- 层：`wire slot` 指帧内字节槽位；`.stnp config` 指 `.stnp` 工程文件中的配置字段；`build config` 指 `stnp.build.json` 构建配置文件中的字段。
- 必填?：`.stnp config` 行逐字取自所属对象的 `required` 数组（`必填` 或 `可选`）；wire slot 行写存在条件。
- 默认值：schema 字面 `default` 逐字引用；schema 未给出时记 `无`。
- 约束/取值：逐字引用 `const` / `enum` / 范围 / `pattern` / 数组约束 / `$ref`。
- 说明：一句话语义。

### 8.1 根对象字段

`stnp` 根对象 `additionalProperties: false`；根 `required` 数组为 `["format", "schema_version", "project_name", "protocol", "modules", "instances", "global_results"]`。

| 路径/槽位 | 层 | 必填? | 默认值 | 约束/取值 | 说明 |
|---|---|---|---|---|---|
| `format` | .stnp config | 必填 | 无 | `const "stnp"` | 文件格式标识 |
| `schema_version` | .stnp config | 必填 | 无 | string；`const "stnp-schema-alpha"` | 生成器可解析的文件格式版本，与 `protocol.version`（用户定义、通信层标识）完全解耦；生成器维护支持列表，读到列表外的值直接失败；不进入 IR |
| `project_name` | .stnp config | 必填 | 无 | `minLength 1` | 工程名 |
| `protocol` | .stnp config | 必填 | 无 | object（逐字段见 8.3） | 协议配置容器 |
| `common_types` | .stnp config | 可选 | 无 | object（逐字段见 8.5） | 通用类型容器 |
| `modules` | .stnp config | 必填 | 无 | `minItems 1`；items object（逐字段见 8.5） | Module 定义数组 |
| `instances` | .stnp config | 必填 | 无 | `minItems 1`；item `additionalProperties false`；item required `["name","module","id"]` | 可路由实例数组 |
| `instances[].name` | .stnp config | 必填 | 无 | `pattern ^[A-Za-z][A-Za-z0-9_]*$` | 实例名 |
| `instances[].module` | .stnp config | 必填 | 无 | `pattern ^[A-Z][A-Z0-9_]*$` | 引用的 Module 名，指向 8.5 中已定义的 Module |
| `instances[].id` | .stnp config | 必填 | 无 | `minimum 1`，`maximum 255` | Instance ID，全局唯一；wire 上由 8.4 的 TARGET / SOURCE 槽承载 |
| `global_results` | .stnp config | 必填 | 无 | `minItems 1`；item `additionalProperties false`；item required `["name","value"]` | Global Result 码表，区间见 §5.4 |
| `global_results[].name` | .stnp config | 必填 | 无 | `pattern ^[A-Z][A-Z0-9_]*$` | Result 码名；必须存在名为 `OK` 的条目 |
| `global_results[].value` | .stnp config | 必填 | 无 | `minimum 0`，`maximum 255` | Result 码值；`0x0000` 为工程级 `OK`，`0x0001..0x00FF` 为其余 Global Result |
| `global_results[].brief` | .stnp config | 可选 | 无 | string | Result 简述 |
| `embedded_files` | .stnp config | 可选 | 无 | 动态键 object；值 `additionalProperties false`；值 required `["content","encoding"]` | 内嵌文件表，键名为文件名 |
| `embedded_files.*.content` | .stnp config | 必填 | 无 | string | 文件内容 |
| `embedded_files.*.encoding` | .stnp config | 必填 | 无 | `enum ["text","base64"]` | 内容编码 |

### 8.2 生成配置（stnp.build.json）

生成配置不再内嵌于 `.stnp`，而是独立的 `stnp.build.json` 文件；`.stnp` 只保留协议定义。`stnp.build.json` 根对象 `additionalProperties false`，`required` 至少含 `format` / `build_schema_version` / `target`；该文件由 `stnp.build.schema.json` 校验。下表字段均取自该文件。

| 路径/槽位 | 层 | 必填? | 默认值 | 约束/取值 | 说明 |
|---|---|---|---|---|---|
| `format` | build config | 必填 | 无 | `const "stnp-build"` | 构建配置文件格式标识；与 `.stnp` 的 `format` 区分 |
| `build_schema_version` | build config | 必填 | 无 | string；`const "stnp-build-schema-alpha"` | 构建配置文件格式版本；独立于 `.stnp` 的 `schema_version`，各自维护支持列表 |
| `target` | build config | 必填 | 无 | `enum ["c","python"]` | 单选生成目标；不设复数形态、不设候选兜底、不设旧版本兜底 |
| `c` | build config | 可选 | 无 | `additionalProperties false` | C 目标配置对象 |
| `c.build_system` | build config | 可选 | `"mdk_arm"` | `enum ["mdk_arm","cmake"]` | C 构建系统 |
| `c.emit_examples` | build config | 可选 | `false` | boolean | 是否生成 C 示例工程 |
| `python` | build config | 可选 | 无 | `additionalProperties false` | Python 目标配置对象 |
| `python.build_system` | build config | 可选 | `"python"` | `const "python"` | Python 构建系统 |
| `python.emit_examples` | build config | 可选 | `false` | boolean | 是否生成 Python Example |
| `python.emit_user_scaffold` | build config | 可选 | `false` | boolean | 是否生成用户 scaffold |
| `output_stem` | build config | 可选 | 无 | `minLength 1` | 输出文件名主干 |
| `emit_readme` | build config | 可选 | `true` | boolean | 是否生成 README |
| `validations` | build config | 可选 | 无 | array；item required `["id","level"]` | 校验规则清单；默认由生成器导出、全列全启用 |
| `validations[].id` | build config | 必填 | 无 | `minLength 1` | 校验项标识 |
| `validations[].level` | build config | 必填 | 无 | `enum ["error","warning","note"]` | 校验项级别 |
| `layout` | build config | 可选 | 无 | `additionalProperties false` | 布局配置容器 |
| `layout.output_dir_names` | build config | 可选 | 无 | object；键 `c` / `python` | 按目标的输出目录名 |
| `layout.output_dir_names.c` | build config | 可选 | `"STNP_C"` | `minLength 1` | C 目标的输出目录名 |
| `layout.output_dir_names.python` | build config | 可选 | `"STNP_Python"` | `minLength 1` | Python 目标的输出目录名 |
| `sdks` | build config | 可选 | 无 | array；`uniqueItems true`；items `enum ["stm32_hal_uart"]` | 用户可选 C SDK 选择列表；SDK 注册表仍是生成器内部资源，不进入构建配置文件 |
| `python_sdks` | build config | 可选 | 无 | array；`uniqueItems true`；items `enum ["uart"]` | 用户可选 Python SDK 选择列表；SDK 注册表仍是生成器内部资源，不进入构建配置文件 |

最终工程文件夹名由输出文件名主干 `output_stem` 与 `layout.output_dir_names` 中对应目标的值组合而成；二者是组合关系，不存在双重命名冲突。

`<target>.emit_examples` 的取值只来自本文件（默认 `false`）；`config.json` 保留为生成器内部资源文件，不删除，仅输出目录命名与示例产出开关迁出到本文件。

### 8.3 协议配置与 Capability（protocol）

`protocol` 根 `required` 数组为 `["name", "version", "byte_order", "max_payload", "task", "notify"]`。

| 路径/槽位 | 层 | 必填? | 默认值 | 约束/取值 | 说明 |
|---|---|---|---|---|---|
| `protocol.name` | .stnp config | 必填 | 无 | string | 协议名 |
| `protocol.version` | .stnp config | 必填 | 无 | string | 协议版本 |
| `protocol.byte_order` | .stnp config | 必填 | 无 | `const "little"` | 字节序固定小端，wire 编码规则见 §3.7 |
| `protocol.max_payload` | .stnp config | 必填 | 无 | `minimum 1`，`maximum 255` | 单帧 Payload 上限，Payload 预算见 §3.6 |
| `protocol.router_instance_max` | .stnp config | 可选 | `8` | `minimum 1`，`maximum 255` | Router 实例数上限，见 §4.5 |
| `protocol.task` | .stnp config | 必填 | 无 | `additionalProperties false`；required `["sof","seq"]` | Task 帧头配置 |
| `protocol.task.sof` | .stnp config | 必填 | 无 | `minItems 2`，`maxItems 2`；items `minimum 0`，`maximum 255` | 2 字节 SOF，8.4 的 Task HEADER 槽取值；两个 SOF 必须不同 |
| `protocol.task.seq` | .stnp config | 必填 | 无 | `additionalProperties false`；required `["type","start"]` | SEQ 计数器配置；Task 与 Notify 共用 |
| `protocol.task.seq.type` | .stnp config | 必填 | 无 | `const "u16"` | SEQ 宽度 u16，对应 8.4 的 SEQ 槽 |
| `protocol.task.seq.start` | .stnp config | 必填 | 无 | `minimum 1`，`maximum 65535` | SEQ 初值；不得属于 reserved（§3.9） |
| `protocol.task.seq.reserved` | .stnp config | 可选 | 无 | items `minimum 0`，`maximum 65535`；`uniqueItems true` | 保留 SEQ 值表（§3.9） |
| `protocol.notify` | .stnp config | 必填 | 无 | `additionalProperties false`；required `["sof"]` | Notify 帧头配置；不存在独立的 Notify SEQ 配置键 |
| `protocol.notify.sof` | .stnp config | 必填 | 无 | `minItems 2`，`maxItems 2`；items `minimum 0`，`maximum 255` | 2 字节 SOF，8.4 的 Notify HEADER 槽取值 |
| `protocol.features` | .stnp config | 可选 | 无 | `additionalProperties false`；无 `required` | Capability 开关容器，见 §6 |
| `protocol.features.seq` | .stnp config | 可选 | 无 | 无 `required` | SEQ Capability 配置 |
| `protocol.features.seq.enabled` | .stnp config | 可选 | `false` | boolean | 生成期决定 8.4 中 SEQ 槽位是否存在；Task / Notify 共用此一处门控（§6.2） |
| `protocol.features.crc` | .stnp config | 可选 | 无 | 无 `required` | CRC Capability 配置 |
| `protocol.features.crc.enabled` | .stnp config | 可选 | `false` | boolean | 生成期决定 8.4 中 CRC 槽位是否存在（§3.10） |
| `protocol.options` | .stnp config | 可选 | 无 | `additionalProperties false`；无 `required` | 本端运行时行为开关容器；不是 Capability，不改 wire format |
| `protocol.options.notify_dispatch_receive` | .stnp config | 可选 | 无 | `additionalProperties false`；无 `required` | Notify 接收分发配置对象 |
| `protocol.options.notify_dispatch_receive.enabled` | .stnp config | 可选 | `false` | boolean | 本端是否启用 Notify 接收分发路径；允许运行时切换 |

Notify 接收分发运行时接口（C 侧与 Python 侧同名），共三支：

- **启用 Notify 接收分发**：打开本端 Notify 接收分发路径；只改本端行为，不改 wire format，两端可不同。
- **禁用 Notify 接收分发**：关闭本端 Notify 接收分发路径；只改本端行为，不改 wire format，两端可不同。
- **查询 Notify 接收分发是否启用**：返回本端该开关的当前状态。

三支接口的初值来自 `protocol.options.notify_dispatch_receive.enabled`，生成期写入、运行时可切。

组级区分：`protocol.features` 组为 Capability —— 改 wire format、两端必须一致、禁止运行时切换；`protocol.options` 组为本端行为 —— 不改 wire format、两端可不同、允许运行时切换。两组字段不得混放。

### 8.4 Wire 槽位（10 槽）

本小节 10 行对应 §3.4 字段目录的全部 10 个槽位；槽位不属于任何 schema 的 `properties`，因此 `必填?` 列写存在条件。

| 路径/槽位 | 层 | 必填? | 默认值 | 约束/取值 | 说明 |
|---|---|---|---|---|---|
| `HEADER` | wire slot | 恒存在（两家族首个槽） | 无 | 2 B；每字节 `0x00..0xFF`，取 `task.sof` / `notify.sof` | 帧家族 SOF，流解析据此定位帧边界；两个 SOF 必须不同（§3.4） |
| `SEQ` | wire slot | SEQ Capability 开启时 | 无 | 2 B；u16 小端，初值 `task.seq.start ∈ 1..65535` | Task / Notify 同门控的可选槽（§3.3、§3.9） |
| `TARGET` | wire slot | 仅 Task 帧，恒存在 | 无 | 1 B；Instance ID `1..255` | 目的 Instance ID，路由见 §4（§3.4） |
| `CMD` | wire slot | 仅 Task 帧，恒存在 | 无 | 1 B；`0x00..0xFF`，Module 内唯一 | Module 内 Command code（§3.4） |
| `LEN` | wire slot | 恒存在（两家族） | 无 | 1 B；`0x00..0xFF` 且 ≤ `max_payload` | Payload 长度前缀；`LEN=0` 即无 Payload（§3.6） |
| `PAYLOAD` | wire slot | 仅 LEN > 0 时 | 无 | `0..255 B`，长度 = `LEN`，≤ `max_payload` | Command / Notify 数据，VTL 编码或 Raw bytes（§3.6、§3.7） |
| `CRC` | wire slot | CRC Capability 开启时 | 无 | 2 B；u16 小端 `0x0000..0xFFFF` | CRC16-Modbus 帧完整性校验；生成期开关 `features.crc.enabled`（§3.10） |
| `SOURCE` | wire slot | 仅 Notify 帧，恒存在 | 无 | 1 B；Instance ID `1..255` | 来源 Instance ID，路由见 §4（§3.4） |
| `NOTIFY` | wire slot | 仅 Notify 帧，恒存在 | 无 | 1 B；`0x00..0xFF`，Module 内唯一 | Module 内 Notify code（§3.4） |
| `RESULT` | wire slot | 仅 Notify 帧，恒存在 | 无 | 2 B；u16 小端 `0x0000..0xFFFF` | 三类 Result 共用的 u16 槽，语义划分见 §5（§3.4、§5.1） |

### 8.5 定义模型（modules[] 与 common_types）

`modules[]` 根 `required` 为 `["name", "return_codes"]`；`common_types` 顶层没有 `required` 数组。

| 路径/槽位 | 层 | 必填? | 默认值 | 约束/取值 | 说明 |
|---|---|---|---|---|---|
| `modules[].name` | .stnp config | 必填 | 无 | `pattern ^[A-Z][A-Z0-9_]*$` | Module 名 |
| `modules[].enabled` | .stnp config | 可选 | `true` | boolean | Module 启用开关 |
| `modules[].auto_notify_enabled` | .stnp config | 可选 | `false` | boolean | Module 级自动通知开关 |
| `modules[].return_codes` | .stnp config | 必填 | 无 | `minItems 1` | Module Result 码表；值区间见 §5.4 |
| `modules[].return_codes[].name` | .stnp config | 必填 | 无 | `pattern ^[A-Z][A-Z0-9_]*$` | Result 码名；必须存在名为 `OK` 的条目 |
| `modules[].return_codes[].value` | .stnp config | 必填 | 无 | integer | Result 码值；落在该 Module 的 256 值区间内（§5.4） |
| `modules[].return_codes[].brief` | .stnp config | 可选 | 无 | string | Result 简述 |
| `modules[].commands` | .stnp config | 可选 | `[]` | array | Command 定义数组 |
| `modules[].commands[].name` | .stnp config | 必填 | 无 | `pattern ^[A-Z][A-Z0-9_]*$` | Command 名 |
| `modules[].commands[].code` | .stnp config | 必填 | 无 | `minimum 0`，`maximum 255` | Command 码，wire 承载见 8.4 的 `CMD` 槽 |
| `modules[].commands[].payload` | .stnp config | 必填 | 无 | array | Command Payload 字段定义数组 |
| `modules[].commands[].payload[].name` | .stnp config | 必填 | 无 | `pattern ^[a-z][a-z0-9_]*$` | 字段名 |
| `modules[].commands[].payload[].type` | .stnp config | 必填 | 无 | string | 字段类型；最终映射到四种基础 wire 类型（§3.7） |
| `modules[].commands[].payload[].min` | .stnp config | 可选 | 无 | integer | 仅元数据，不上 wire |
| `modules[].commands[].payload[].max` | .stnp config | 可选 | 无 | integer | 仅元数据，不上 wire |
| `modules[].commands[].doc` | .stnp config | 可选 | 无 | object | 文档对象 |
| `modules[].commands[].doc.brief` | .stnp config | 可选 | 无 | string | 一句话简述 |
| `modules[].commands[].doc.detail` | .stnp config | 可选 | 无 | string | 详细说明 |
| `modules[].commands[].validate_hook` | .stnp config | 可选 | `false` | boolean | 是否生成 validator |
| `modules[].commands[].notify_on_done` | .stnp config | 可选 | 无 | `$ref "#/$defs/notify_ref"` | 完成时自动 Notify 的触发时机；引用校验退化为「引用的通知存在即可」，不再按分类匹配 |
| `modules[].commands[].notify_on_accept` | .stnp config | 可选 | 无 | `$ref "#/$defs/notify_ref"` | 受理时自动 Notify 的触发时机；引用校验退化为「引用的通知存在即可」，不再按分类匹配 |
| `modules[].commands[].notify_on_reject` | .stnp config | 可选 | 无 | `$ref "#/$defs/notify_ref"` | 拒绝时自动 Notify 的触发时机；引用校验退化为「引用的通知存在即可」，不再按分类匹配 |
| `modules[].notifications` | .stnp config | 可选 | 无 | array | 自动通知定义数组 |
| `modules[].notifications[].name` | .stnp config | 必填 | 无 | `pattern ^[A-Z][A-Z0-9_]*$` | 通知名 |
| `modules[].notifications[].code` | .stnp config | 必填 | 无 | `minimum 0`，`maximum 255` | Notify 码，wire 承载见 8.4 的 `NOTIFY` 槽 |
| `modules[].notifications[].brief` | .stnp config | 可选 | 无 | string | 通知简述 |
| `modules[].notifications[].payload` | .stnp config | 必填 | 无 | array | 通知 Payload 字段定义数组 |
| `modules[].notifications[].payload[].name` | .stnp config | 必填 | 无 | `pattern ^[a-z][a-z0-9_]*$` | 字段名 |
| `modules[].notifications[].payload[].type` | .stnp config | 必填 | 无 | string | 字段类型 |
| `modules[].notifications[].payload[].min` | .stnp config | 可选 | 无 | integer | 仅元数据，不上 wire |
| `modules[].notifications[].payload[].max` | .stnp config | 可选 | 无 | integer | 仅元数据，不上 wire |
| `$defs.notify_ref.notify` | .stnp config | 必填 | 无 | string | `notify_on_*` 的 `$ref` 展开目标，唯一属性 |
| `common_types.types` | .stnp config | 可选 | 无 | array | 通用类型定义数组；`common_types` 顶层无 required 数组 |
| `common_types.types[].name` | .stnp config | 必填 | 无 | `pattern ^[A-Z][A-Za-z0-9]*$` | 类型名 |
| `common_types.types[].kind` | .stnp config | 必填 | 无 | `enum ["alias","enum"]` | 类型种类 |
| `common_types.types[].type` | .stnp config | 必填 | 无 | `enum ["u8","u16","u32","i32"]` | 底层类型，恰为四种基础 wire 类型（§3.7） |
| `common_types.types[].values` | .stnp config | 可选 | 无 | array | 仅 enum 型类型使用 |
| `common_types.types[].values[].name` | .stnp config | 必填 | 无 | `pattern ^[A-Z][A-Z0-9_]*$` | 枚举值名 |
| `common_types.types[].values[].value` | .stnp config | 必填 | 无 | integer | 枚举值 |

**payload `min` / `max` 的仅元数据声明**：上表中 4 行 `min` 与 `max` 是编辑器与文档层的元数据，仅用于输入校验与文档生成，从不映射到 wire 上的任何字节；帧内不存在承载它们的任何槽位（槽位全集见 8.4 与 §3.4）。

可选性之外的槽位语义见 §3，路由与 Instance 见 §4，Result 三类见 §5，Capability 归属见 §6。

## 9. 不变量与非目标

### 9.1 协议不变量

下表登记 STNP 协议的结构不变量，共 14 条。STNP 0.9 延续全部不变量，不删除、不弱化任何一条。

| # | 不变量 | 一句话陈述 |
|---|---|---|
| 1 | 只有核心发送原语 | 发送面只有核心原语：Task 为 `STNP_Task_Send` / `STNP_Task_SendBytes`，Notify 为 `STNP_Notify_Send` / `STNP_Notify_SendBytes`（Python 对应 `stnp.task` 与 `stnp.notify.<Module>.<NAME>`），此外不存在任何发送通道 |
| 2 | Task 与 Notify 解耦 | 两者是两个独立帧家族，Command code 与 Notify code 分属不同表、可取相同数值；Notify 是独立协议原语，不隶属于任何 Command，协议不在两者之间内建关联 |
| 3 | Core 不维护 ACK/DONE/握手状态机 | STNP Core 不在协议内建立 Task→ACK→DONE 状态机；ACK / handshake 明确归业务层 |
| 4 | `notify_on_*` 只是可选业务元数据 | `notify_on_done` / `notify_on_accept` / `notify_on_reject` 均为非必填字段，`auto_notify_enabled` 默认 `false`；该能力只存在于生成的 Module / Decorator 层，不进入 Core，也不改变帧语法 |
| 5 | Validator 可选且统一 | 每 Module 只有一个统一校验入口；该校验函数由生成器按模块生成、内部按命令码分派，绑定入口不再携带命令码参数，默认不绑定；`validate_hook` 默认 `false`，`min/max` 只是元数据，需显式绑定 Module 校验函数才有运行时检查 |
| 6 | 无 per-Command / per-Notify 发送 wrapper | Module / Instance 级的逐 Command、逐 Notify 发送函数不存在，生成器不产出任何此类 API |
| 7 | `CMD` 是命令的唯一命名锚点 | wire 上标识一条 Command 的只有 1 字节 `CMD` 槽；命令名只存在于配置与生成代码，不占用 wire 字段 |
| 8 | 每 Module 一个 Notify callback | Notify callback 收敛到每 Module 一个，不存在逐 Notify 注册的回调 API |
| 9 | Payload 是唯一概念，Raw 与 Typed 是两种编写方式 | Command 与 Notification 的 `payload[]` 使用同一字段格式，共用同一 `LEN` / `PAYLOAD` 槽位；Raw bytes 与 VTL typed struct 是同一 Payload 的两种编写入口，不构成两套结构 |
| 10 | 禁止把 C struct 原样上 wire，Typed 必须先 Pack | typed struct 的 `sizeof(struct)` 不是 wire size；Core VTL 按 metadata 的字段 offset / wire type / wire size 逐字段编码，C padding 永不进入 wire，因此 Typed 数据必须先 Pack 成 raw bytes 再进入发送原语 |
| 11 | `LEN=0` 即无 Payload，且无空结构字节 | `LEN` 槽为 `00` 时其后没有任何字节，不附带空 struct；发送侧无 Payload 以 `STNP_NULL` 表达 |
| 12 | 每个 wire 字节都属于已声明字段 | 两个帧家族的布局逐槽定长登记；帧内除 `PAYLOAD` 外均为定长槽位，不存在任何未登记的帧字段 |
| 13 | 字节序恒为小端 | `u16/u32/i32` 统一小端；Schema 将 `byte_order` 固定为 `const "little"`，不是可配置项 |
| 14 | 基础 wire 类型恰四种 | 只有 `u8`（1 B）、`u16`（2 B）、`u32`（4 B）、`i32`（4 B）；alias / enum 最终仍映射回这四种基础类型，不引入新的 wire 宽度 |

两条补充说明：

- 第 2、4 条共同划清「关联」的边界：Task 与 Notify 之间的一切联系（自动通知、业务关联）都止步于生成配置层，协议本身不表达关联；Task / Notify 关联的定义见 §10。
- 第 9、10、11 条是同一主题的三个侧面：Payload 在 wire 上只有一种形态（`LEN` 前缀的字节序列），Raw 与 Typed 是作者侧的两种视角，Pack 是 Typed 通向发送原语的唯一桥梁（编码细节见 §3.6 与 §3.7）。

### 9.2 非目标

以下三条是 STNP 协议的非目标：它们不是被延后的功能，在任何版本里 Core 都不提供这些语义。需要这些行为的系统应在业务层自行实现（与 §9.1 第 3 条同一边界）。

- **不是 RPC。** STNP 不把 Command 抽象为远程过程调用：不存在请求/响应配对语义，没有「每条命令一个发送函数」的调用面（§9.1 第 1、6 条已确立发送面边界）；调用方发出 Task 之后，协议层不配对、不等待任何回执。
- **不强制 ACK。** 协议不引入强制 ACK 语义。确认类行为若业务需要，由业务层基于 Notify 自行定义，协议不预设任何确认帧或确认规则。
- **无同步握手。** 协议不定义同步握手流程，Core 不维护握手状态；ACK / handshake 明确归业务层。

## 10. 待定项

本节列出 STNP 0.9 的待定项。原第 1 条「`schema_version` 的最终取值」已定案，改写为已定陈述；第 2 条仍为待定项。除此之外，本规范其余内容均为已定陈述。

1. **`schema_version` 的最终取值**：已定。`.stnp` 顶层 `schema_version` 为必填字段，类型为 `string`，取值为 `"stnp-schema-alpha"`（见 §8.1）；与 `protocol.version` 完全解耦，不进入 IR。
2. **Task / Notify 关联**：STNP 0.9 不定义。`SEQ` 只提供事务标识基础，不构成 Task 与 Notify 之间的关联机制。关联的定义（归属 `SEQ` 还是 Editor / 业务层、是否构成任何自动关联机制）未定；定义完成前，`SEQ` 只提供事务标识基础，协议不表达任何自动关联机制。

## 附录：字段 ↔ Schema 交叉参照

本附录只覆盖 §3.4 登记的 10 个 wire 槽位，以及 §4 路由与 §5 Result 所引用的 Schema 字段。语义正文以 §3-§8 为准。

映射类型（每行恰标其一）：

- `schema path`：存在直接配置该字段 / 槽位的具体 Schema 键。
- `wire-only`：仅存在于 wire，无同名 Schema 键，其取值或存在性由所列 Schema 字段间接约束。

| 槽位 | 映射类型 | Schema 锚点 / 间接约束 |
|---|---|---|
| `HEADER` | `schema path` | Task 家族取 `protocol.task.sof`，Notify 家族取 `protocol.notify.sof`（各 2 项、每项 `0..255`） |
| `SEQ` | `schema path` | 配置对象 `protocol.task.seq`：`type` 固定 `u16`、`start` `1..65535`、`reserved` 保留表；存在性由 `protocol.features.seq.enabled` 门控 |
| `TARGET` | `wire-only` | 无同名 Schema 键；取值域由 `instances[].id`（`1..255`）约束 |
| `CMD` | `wire-only` | 无同名 Schema 键；取值由 `modules[].commands[].code`（`0..255`）供给 |
| `SOURCE` | `wire-only` | 无同名 Schema 键；取值域由 `instances[].id` 约束 |
| `NOTIFY` | `wire-only` | 无同名 Schema 键；取值由 `modules[].notifications[].code`（`0..255`）供给 |
| `RESULT` | `wire-only` | 无同名 Schema 键；Module 侧取值由 `modules[].return_codes[].value` 供给，Global 侧取值由 `global_results[].value` 供给 |
| `LEN` | `wire-only` | 无同名 Schema 键；上界由 `protocol.max_payload`（`1..255`）约束（§3.6） |
| `PAYLOAD` | `wire-only` | 无同名 Schema 键；结构由 `modules[].commands[].payload` / `modules[].notifications[].payload` 定义，其中 `min` / `max` 仅元数据、不上 wire |
| `CRC` | `wire-only` | 无同名 Schema 键；存在性由 `protocol.features.crc.enabled` 门控（§3.10） |

| 字段 | 映射类型 | 说明 |
|---|---|---|
| `instances[].id` | `schema path` | `1..255`；`TARGET` / `SOURCE` 槽的取值域 |
| `instances[].module` | `schema path` | 绑定 Module，须引用 enabled Module |
| `modules[].commands[].code` | `schema path` | `CMD` 槽的取值源 |
| `modules[].notifications[].code` | `schema path` | `NOTIFY` 槽的取值源 |
| `modules[].return_codes[].value` | `schema path` | Module Result 取值源；落在该 Module 的 256 值区间内（§5.4） |
| `global_results[].value` | `schema path` | Global Result 取值源；`0x0000` 为工程级 `OK`，`0x0001..0x00FF` 为其余 Global Result（§5.4） |
| `protocol.max_payload` | `schema path` | `LEN` / `PAYLOAD` 的上界（§3.6） |
| `protocol.features.seq.enabled` / `protocol.features.crc.enabled` | `schema path` | 两个生成期 Capability 门控（§6.2） |

## 附录：最小示例工程

以下是一份完整的 `.stnp` 工程，体现本规范的全部结构：SEQ 开关形态（Task / Notify 共用一处门控）、Global Result 码表、Module Result 按 256 值分段、一个 Module 对多个 Instance、Command / Notify 定义与 Payload 字段，以及本端运行时行为开关。示例工程不内嵌生成配置；生成配置见紧随其后的 `stnp.build.json`。

示例中 `schema_version` 取 `"stnp-schema-alpha"`。

```json
{
  "format": "stnp",
  "schema_version": "stnp-schema-alpha",
  "project_name": "min_demo",
  "protocol": {
    "name": "STNP",
    "version": "0.9",
    "byte_order": "little",
    "max_payload": 64,
    "router_instance_max": 8,
    "task": {
      "sof": [170, 85],
      "seq": {
        "type": "u16",
        "start": 1,
        "reserved": [0]
      }
    },
    "notify": {
      "sof": [170, 51]
    },
    "features": {
      "seq": {
        "enabled": true
      },
      "crc": {
        "enabled": true
      }
    },
    "options": {
      "notify_dispatch_receive": {
        "enabled": false
      }
    }
  },
  "global_results": [
    {
      "name": "OK",
      "value": 0,
      "brief": "整条链路成功"
    },
    {
      "name": "INTERNAL_ERROR",
      "value": 1,
      "brief": "内部错误"
    },
    {
      "name": "ESTOP_ACTIVE",
      "value": 2,
      "brief": "急停生效"
    }
  ],
  "common_types": {
    "types": [
      {
        "name": "Speed",
        "kind": "alias",
        "type": "u8"
      }
    ]
  },
  "modules": [
    {
      "enabled": true,
      "name": "MOTION",
      "return_codes": [
        {"name": "OK", "value": 256, "brief": "Module 处理成功"},
        {"name": "BUSY", "value": 257, "brief": "忙"},
        {"name": "PARAM", "value": 258, "brief": "参数错误"}
      ],
      "commands": [
        {
          "name": "MOVE",
          "code": 1,
          "doc": {"brief": "按方向与速度运动"},
          "validate_hook": true,
          "payload": [
            {"name": "direction", "type": "u8"},
            {"name": "speed", "type": "Speed", "min": 1, "max": 100}
          ]
        }
      ],
      "notifications": []
    },
    {
      "enabled": true,
      "name": "SENSOR",
      "return_codes": [
        {"name": "OK", "value": 512, "brief": "Module 处理成功"},
        {"name": "FAULT", "value": 513, "brief": "传感器故障"}
      ],
      "commands": [
        {
          "name": "READ",
          "code": 1,
          "doc": {"brief": "读取指定通道当前值"},
          "validate_hook": false,
          "payload": [
            {"name": "channel", "type": "u8", "min": 0, "max": 3}
          ]
        }
      ],
      "notifications": [
        {
          "name": "DATA",
          "code": 1,
          "brief": "采样数据上报",
          "payload": [
            {"name": "value", "type": "u16"},
            {"name": "status", "type": "u8"}
          ]
        }
      ]
    }
  ],
  "instances": [
    {"name": "MotionMain", "module": "MOTION", "id": 1},
    {"name": "SensorFront", "module": "SENSOR", "id": 2},
    {"name": "SensorRear", "module": "SENSOR", "id": 3}
  ]
}
```

配套的最小 `stnp.build.json`：

```json
{
  "format": "stnp-build",
  "build_schema_version": "stnp-build-schema-alpha",
  "target": "c",
  "c": {
    "build_system": "cmake",
    "emit_examples": false
  },
  "output_stem": "min_demo",
  "emit_readme": true,
  "layout": {
    "output_dir_names": {
      "c": "STNP_C",
      "python": "STNP_Python"
    }
  }
}
```

| 示例要素 | 规范位置 |
|---|---|
| `protocol.features.seq.enabled` = `true` | SEQ 槽存在；Task 与 Notify 共用该一处门控（§3.3、§6.2） |
| `global_results` | `0x0000` 工程级 `OK`；`0x0001..0x00FF` 为 Global Result（§5.4） |
| `MOTION` 的 Return Code 256 / 257 / 258 | 第 0 个 Module 的区间 `0x0100..0x01FF`（§5.4） |
| `SENSOR` 的 Return Code 512 / 513 | 第 1 个 Module 的区间 `0x0200..0x02FF`（§5.4） |
| `SENSOR` 绑定 `SensorFront`（id 2）与 `SensorRear`（id 3） | 一个 Module 对多个 Instance（§4.3） |
| `MOVE` / `READ` 与 `DATA` | 2 个 Command、1 个 Notify，均含 Payload 字段（§3.6、§3.7） |
| `schema_version` = `"stnp-schema-alpha"` | `.stnp` 必填的文件格式版本（§8.1） |
| `protocol.options.notify_dispatch_receive.enabled` = `false` | 本端 Notify 接收分发默认关闭；不改 wire format（§8.3） |
| `stnp.build.json` | 生成配置独立成文件：`target` / `c` / `emit_readme` / `output_stem`（§8.2） |

---

[← 架构说明](README.md) | [文档目录](../README.md) | [生成器架构 →](generator.md)
