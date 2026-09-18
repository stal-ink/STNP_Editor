# 2. 协议格式

本页给集成者：STNP 0.9 冻结规范的通俗版 wire 说明。规范正文见 [冻结规范](05_architecture/spec_0.9.md) §3–§5。实现取证于 `src/stnp_editor/resources/templates/c/Core/stnp_frame.h.j2`、`stnp_frame.c.j2`、`stnp_crc.c.j2` 与 Python `stnp/core/frame.py.j2`。

## 字节序

只支持 little-endian。`byte_order` 在 schema 中为 `const "little"`。`u16` / `u32` / `i32` 一律小端；`SEQ`、`RESULT`、`CRC` 三个多字节槽位同样是 u16 小端。单字节槽位（`TARGET` / `CMD` / `SOURCE` / `NOTIFY` / `LEN`）为 u8 直出。SOF 两个字节按 `.stnp` 配置原样写出，不做端序转换。

## Task 帧槽位

```text
SOF[2] | SEQ[0/2] | TARGET[1] | CMD[1] | LEN[1] | PAYLOAD[LEN] | CRC[0/2]
```

| 槽 | 宽度 | 存在条件 | 含义 |
|---|---:|---|---|
| SOF | 2 B | 恒存在 | `protocol.task.sof`，与 Notify SOF 必须不同 |
| SEQ | 0/2 B | `features.seq.enabled` | u16 小端；Task 与 Notify 共用同一门控与同一发送方计数器 |
| TARGET | 1 B | 恒存在 | 目标 Instance ID，`1..255` |
| CMD | 1 B | 恒存在 | Module 内 Command code（历史别名 CODE） |
| LEN | 1 B | 恒存在 | Payload 字节数，`0` 表示无 Payload，且 ≤ `max_payload` |
| PAYLOAD | LEN | 恒存在（可空） | VTL 编码或原始字节 |
| CRC | 0/2 B | `features.crc.enabled` | CRC16-Modbus，覆盖帧头到 Payload 的 body |

`LEN` 的字节下标随 SEQ 开关变化：关闭时为下标 4，开启时为下标 6。解析器必须先按 Capability 算出固定头长，再读 `LEN`。C 模板把固定头长写成 `STNP_TASK_FIXED_SIZE`（5 或 7）。

无 SEQ 时 Task 固定头 5 字节；有 SEQ 时为 7 字节（另加 CRC 则再加 2）。冻结规范把这组组合称为 Capability 矩阵：SEQ 与 CRC 相互独立，可分别开关，两端必须由同一份 `.stnp` 生成。运行时既不协商、也不切换帧布局。

历史别名：槽位正式名是 `CMD`；旧文档里的 `CODE` 指同一字节。文档与生成头同时出现时，以 `CMD` / `CHASSIS_CMD_MOVE` 这类符号为准。C 结构体字段在模板中仍叫 `frame->code`，与 wire 槽 `CMD` 是同一字节。

## Notify 帧槽位

```text
SOF[2] | SEQ[0/2] | SOURCE[1] | NOTIFY[1] | RESULT[2] | LEN[1] | PAYLOAD[LEN] | CRC[0/2]
```

| 槽 | 宽度 | 存在条件 | 含义 |
|---|---:|---|---|
| SOF | 2 B | 恒存在 | `protocol.notify.sof` |
| SEQ | 0/2 B | 与 Task 同一 `features.seq.enabled` | 与 Task 共用计数器 |
| SOURCE | 1 B | 恒存在 | 来源 Instance ID，`1..255` |
| NOTIFY | 1 B | 恒存在 | Module 内 Notify code |
| RESULT | 2 B | 恒存在 | u16 小端；工程级结果码与 Module Result 共用此槽 |
| LEN | 1 B | 恒存在 | Payload 长度 |
| PAYLOAD | LEN | 恒存在（可空） | VTL 编码或原始字节 |
| CRC | 0/2 B | 与 Task 同一 `features.crc.enabled` | CRC16-Modbus |

`LEN` 下标：SEQ 关闭时为 6，开启时为 8。无 SEQ 时 Notify 固定头 7 字节；有 SEQ 时为 9 字节。C 模板对应 `STNP_NOTIFY_FIXED_SIZE`。

## SEQ 门控与共用计数器

`protocol.features.seq.enabled` 同时决定 Task 与 Notify 是否带 SEQ 槽。默认 `false`。开启时：

- `task.seq.type` 固定 `u16`；`start` 属于 `1..65535` 且不得落在 `reserved`。
- 发送方在 Transport 写出前 reserve-before-write：临界区内先推进计数器再返回推进前的值，随后才构帧与写出。C 实现为 `STNP_Frame_ReserveSeq()`（`STNP_Runtime_Lock` 内推进 `g_stnp_tx_seq`）；Python 实现为 `Runtime._next_seq()`（`_seq_lock`）。
- `0xFFFF` 回绕到 0 后继续跳过 reserved。构帧或写出失败时序号已被消耗，允许 SEQ 空洞。
- Core 不定义确认、关联或可靠性语义；SEQ 只是可选的事务标识基础。Task 与 Notify 的关联机制见冻结规范 §10，不在本页展开。

关闭 SEQ 时，Python `TaskFrame.seq` / `NotifyFrame.seq` 解析为 `0`，线上不占用字节。

## CRC 覆盖与生成期开关

CRC 是否出现在线上只由 `features.crc.enabled` 决定，默认 `false`。**没有**运行时开关（0.9 删除 `features.crc.runtime_toggle`）。算法 CRC16-Modbus：初值 `0xFFFF`、多项式 `0xA001`；覆盖从 SOF 到 Payload 的全部 body，自身以 u16 小端追加。C 仅在开启时生成 `stnp_crc.h` / `stnp_crc.c`，函数名为 `STNP_CRC16`。Python 使用 `crc16_modbus()`。

关闭 CRC 时尾部完全不存在该槽，解析器不得再读 2 字节校验。两端必须由同一份 `.stnp` 生成，否则一边带 CRC、一边不带会在流式解析中持续 1 字节滑动。

## Payload / VTL 与 padding

Payload 字段按 Module VTL metadata 顺序编码，类型仅 `u8/u16/u32/i32`（各 1/2/4/4 字节）。common alias / enum 最终仍映射到这四种基础宽度，不引入新的 wire 宽度。结构体按字段自然对齐由生成器给出 `offsetof`，线上 **无隐式 padding 字节**：`sizeof(struct)` 不是 wire size，禁止把 C 结构体整体拷贝上线。

`LEN=0` 且无字段时 Payload 为空，不附带空结构字节。字段 wire size 之和超过 `protocol.max_payload`（schema `1..255`）时生成失败。解析侧 `LEN > max_payload` 判为非法长度并触发 1 字节滑动。

C 的 typed 发送走 `STNP_Task_Send` / `STNP_Notify_Send`（内部 `STNP_Router_Encode*` → VTL Encode）；Raw 发送走 `SendBytes` 宏，长度在数组退化前取 `sizeof`。Python codec 在发送时检查整数可转换性、基础类型范围与 `.stnp` 的 min/max；接收先按长度反序列化为 dataclass，业务范围由校验函数执行。

## Stream 重同步

流式接收在缓冲区内寻找 Task / Notify 两个 2 字节 SOF 中更靠前的一个。缓冲不足 2 字节时等待；没有任何 SOF 且缓冲多于 1 字节时只保留末字节继续。CRC 或结构错误、以及 `LEN > max_payload` 时一律 **1 字节滑动** 重同步，避免按错误候选帧的推测长度整段丢弃、从而吞掉嵌套有效帧。

C 与 Python 的推进粒度不同，规则相同：

- C：`STNP_Transport_Receive()` 只把字节整块复制进 RX Ring（放不下则 `STNP_ERR_BUFFER`，不做部分写入）。`STNP_Process()` 从 Ring 逐字节填入解析缓冲，单次调用至多推进一帧；Job 满时返回 `STNP_ERR_BUFFER` 并保留当前完整帧待重试。
- Python：`StreamParser.feed()` 把新字节追加到内部 `bytearray`，一次调用可吐出多帧，但仍按同一 SOF/滑动规则。CRC 失败计入 `crc_errors`，结构失败计入 `protocol_errors`。

不要假设一次 UART 回调正好一帧。半帧等待更多字节；粘包一次可产出多帧。

## 路由 TARGET / SOURCE

寻址粒度是实例（Instance）。运行时路由链为：

```text
Instance ID → Instance → Module → Command/Notify
```

Task 的 `TARGET` 与 Notify 的 `SOURCE` 都是 Instance ID。接收端按 ID 找到本地实例，再进入其 Module 的 Command / Notify 表。Command 与 Notify 属不同码表，允许使用相同数值。ID 全局唯一，合法生成配置范围 `1..255`（schema `minimum 1`）。Router 实例数上限为 `protocol.router_instance_max`（默认 8，范围 `1..255`）；该上限限制实例总数，不收窄单个 ID 的取值范围。

一个 Module 可被多个 Instance 绑定；没有 Instance 的 Module 不出现在任何路由路径上。码表、Payload、Result 归属只属于 Module；Instance 只负责身份与绑定。实现层允许 Instance 覆盖 Module 默认的处理函数 / 校验函数 / callback，这不改变 wire 定义。

找不到实例时 C 返回 `STNP_ERR_TARGET`，找不到 code 返回 `STNP_ERR_COMMAND`。`STNP_Router_Register` 本身不在运行时检查 `id==0`；`0` 被 schema / 冻结规范排除在合法生成配置之外。

## 三类 Result 与 RESULT 槽

Notify 的 `RESULT` 槽承载工程级结果码与 Module Result，二者共用同一个 u16，按值区间判定语义。Core Status（如 `STNP_OK` / `STNP_ERR_BUFFER`）只出现在 Runtime / API 返回路径，**不上 wire**。

| 区间 | 语义 |
|---|---|
| `0x0000` | 工程级 `OK`，由顶层 `global_results` 中名为 `OK` 的条目声明 |
| `0x0001..0x00FF` | 其余工程级结果码（Global Result），最多 255 个 |
| `0x0100..0xFFFF` | Module Return Code：`modules[]` 中第 i 个启用 Module（从 0 计）占用 `0x0100 + 256*i` 到该段末 255 |

每个 Module 必须含本段名为 `OK` 的 Return Code。工程级 `OK` 与 Module 级 `OK` 并存：前者表示整条链路成功，后者表示该 Module 处理成功。通知不再用 `kind` 分类；接受/拒绝语义由 `RESULT` 表达。运行时路径上的协议错误（例如校验失败后的自动拒绝通知）也写入同一 `RESULT` 槽。

历史协议 V1.0 见 [归档](archive/README.md)，与现行槽位不同。

---

[← 快速开始](01_getting_started.md) | [文档目录](README.md) | [JSON 与生成配置 →](03_json_format.md)
