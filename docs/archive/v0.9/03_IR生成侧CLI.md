# 03 IR / 生成侧 / CLI 设计方案

> 阶段一·定方案交付物。**本文件只出方案，不改任何代码或模板。**
> 目标版本：STNP 0.9；基线版本：0.8.2。
> 只读输入：`docs/IR-CLI-决策.md`、`docs/IR_CLI_0.9_DIFF.md`、`docs/STNP_SPEC_0.9.md`、`src/stnp_editor/ir/models.py`、`ir/builder.py`、`generation.py`、`cli.py`、`loader.py`、`src/stnp_editor/templates/**/*.j2`。
> 本文件凡标「现状」者取自 0.8.2 源码，凡标「方案」者为本轮定案。凡函数签名只给签名，不给实现体。

## 0. 术语与范围

| 项 | 说明 |
|---|---|
| 依据编号 | 引用 `docs/IR-CLI-决策.md` 的裁定编号（D1–D19、补充裁定 B、配置拆分补充裁定）。 |
| 引用点 | 删除/改动某 IR 字段后，所有依赖该字段的源码或模板位置；每项删除都必须给出其去向。 |
| 本轮不动 | `build_vectors` / `sample_value`（`src/stnp_editor/vectors.py`）明确不纳入本轮改动。 |
| 不在范围 | `src/stnp_editor/gui/`（随补充裁定 B 整体删除，本文件不触碰）。 |
| 契约退出码 | `0` 成功 / `1` 校验或生成失败 / `2` 用法参数错误 / `3` 内部错误。 |

行号标注格式为 `文件:行`，取自 0.8.2 基线，仅用于定位引用点。

---

## 一、IR 字段增删定案

以 `src/stnp_editor/ir/models.py` 为基准。下表为逐 dataclass 的增/删/改清单。

### 1.1 删除清单

| dataclass | 字段 | 动作 | 依据 | 备注 |
|---|---|---|---|---|
| `ProtocolIR` | `crc_runtime_toggle` | 删 | D5 | CRC 槽存在性只读 `features.crc.enabled`；运行时不变更帧布局。 |
| `ProtocolIR` | `notify_dispatcher` | 删 | D7 | 由 `notify_dispatch_receive`（默认 `false`，允许运行时切）取代，语义与归属改为 `protocol.options`。 |
| `ModuleIR` | `default_id_macro` | 删 | D3 / D12 | 单实例便捷宏回填直接删除，不做生成侧派生。 |
| `ModuleIR` | `default_id_value` | 删 | D3 / D12 | 同上；与 `default_id_macro` 成对删除。 |
| `ModuleIR` | `handler_mode`（如存在） | 删（确认不存在） | D2 / B1 | **现状 IR 无此字段**；需删的是 schema/0.9 文档/GUI 三处引用，不进 IR。 |
| `ModuleIR` | `notify_groups` | 删 | D15 | 通知去分类，分组结构整体移除。 |
| `NotificationIR` | `kind` | 删 | D15 | 接受/拒绝语义改由 Notify 帧 `RESULT` 槽承载。 |
| `NotifyGroupIR`（整类） | — | 删 | D15 | 类定义与所有实例化点一并删除。 |
| `ProjectIR` | `extras` | 删 | D12 | `generation_target` / `generation_targets` / `c_generation` / `python_generation` 四键随之消失；生成配置改由 `stnp.build.json` 承载。 |
| `ProjectIR` | `output_dir_name` | 删 | D12 / 补充裁定 C | 改为生成期局部量，不固化在 IR。 |
| `models.py` 模块级 | `NOTIFY_KINDS` | 删 | D15 | 通知去分类后无消费者。 |
| `models.py` 模块级 | `NOTIFY_KIND_VALUES` | 删 | D15 | 数值 kind 映射无 0.9 依据，且不得上 wire。 |
| `models.py` 模块级 | `NOTIFY_ON_EXPECTED_KIND` | 删 | D15 | `notify_on_*` 引用校验退化为「引用的通知存在即可」。 |
| `models.py` 模块级 | `KIND_ENUM_SUFFIX` | 删 | D15 | 仅服务于 `NotifyGroupIR` 的枚举命名。 |

删除计数：**IR dataclass 字段 8 个**（`crc_runtime_toggle`、`notify_dispatcher`、`default_id_macro`、`default_id_value`、`notify_groups`、`kind`、`extras`、`output_dir_name`）；**dataclass 1 个**（`NotifyGroupIR`）；**模块级常量 4 个**（`NOTIFY_KINDS`、`NOTIFY_KIND_VALUES`、`NOTIFY_ON_EXPECTED_KIND`、`KIND_ENUM_SUFFIX`）。`handler_mode` 不在 IR，不计入 IR 字段删除数。

### 1.2 删除项的引用点去向

| 删除项 | 现状引用点 | 去向（同步改动） |
|---|---|---|
| `crc_runtime_toggle` | `ir/models.py:178`；`ir/builder.py:252`；`schemas/protocol.schema.json:114-116`；`templates/python/stnp/protocol/constants.py.j2:13`；`templates/python/stnp/protocol/protocol.yaml.j2:13`；`templates/python/stnp/core/model.py.j2:256`；`templates/python/stnp/core/runtime.py.j2:86-87`；`templates/c/Core/stnp_crc.h.j2:17-23`；`templates/c/Core/stnp_crc.c.j2:12-29`；`templates/c/Core/stnp_frame.c.j2:16-25,140-148,251-259`；`templates/c/Core/stnp_core.c.j2:24-33,124,165` | 只保留生成期 `p.crc_enabled`。C：删 `stnp_crc.h/.c` 的 `#if p.crc_runtime_toggle` 运行期分支，`STNP_CRC_IsEnabled()` 恒 `(1U)`；删 `stnp_frame.c.j2` / `stnp_core.c.j2` 的 `_crc_extra()` 运行期判断，改用常量 `STNP_CRC_SIZE`（0/2）。Python：删 `ProtocolDefinition.crc_runtime_toggle` 字段与 `Runtime.enable_crc` 中的 toggle 分支；删 `constants.py.j2` / `protocol.yaml.j2` 对应行；`protocol.schema.json` 删 `features.crc.runtime_toggle`。 |
| `notify_dispatcher` | `ir/models.py:179`；`ir/builder.py:228,253`；`schemas/protocol.schema.json:119-126`；`templates/c/Instance/stnp_instances.c.j2:24`；0.9 文档 §8.3 | 由新增 `ProtocolIR.notify_dispatch_receive`（默认 `false`）取代。`stnp_instances.c.j2:24` 的编译期 `{% if p.notify_dispatcher %}` 改为运行时 `STNP_NotifyDispatchReceive_IsEnabled()` 门控（见 §3.3）。schema 键改到 `protocol.options.notify_dispatch_receive.enabled`。 |
| `default_id_macro` | `ir/models.py:142`；`ir/builder.py:127,413` | 直接删除，不派生。无模板引用该字段。 |
| `default_id_value` | `ir/models.py:143`；`ir/builder.py:120-128,413,514-515`；`templates/c/Module/module/module.h.j2:16-18` | 删 builder 回填块（`120-128`）、构造参数（`413`）、符号表分支（`514-515`）与 `module.h.j2:16-18` 的 `#define {{ m.name }}_ID`。用户改用已生成的 `STNP_INSTANCE_<INSTANCE>_ID`。 |
| `handler_mode` | `schemas/module.schema.json:20-26`；0.9 文档 §8.5 与附录示例；GUI 三处 | 不进 IR；schema/0.9 文档随 D2 删除；GUI 三处随补充裁定 B 整目录删除。 |
| `kind` | `ir/models.py:75`；`ir/builder.py:352,357-359,368-371`；`templates/python/stnp/protocol/modules/module.py.j2:28`；`templates/python/stnp/core/model.py.j2:111,114`；`schemas/module.schema.json:136,147-154` | 删除；`macro_name` 改为不含 kind 的 `f"{name}_NOTIFY_{nname}"`（见 §3.1）；`module.py.j2` 去掉 `kind=` 实参；`model.py.j2` 的 `NotificationDescriptor` 去掉 `kind` 形参与 `self.kind`；schema 删 `notifications[].kind` 必填与枚举。 |
| `NotifyGroupIR` / `notify_groups` | `ir/models.py:85-89,129`；`ir/builder.py:16,367-371,407` | 整类删除；删 builder 的分组循环与构造实参；`KIND_ENUM_SUFFIX` 随之删除。 |
| `extras` | `ir/models.py:195`；`ir/builder.py:152-158`；`cli.py:42,46,54,66`；`emit_python/emitter.py:29` | 生成配置改由 `stnp.build.json` 提供；CLI 直接读 build 的单一 `target`；`emit_python` 不再读 `ir.extras["python_generation"]`，改为接收 build 配置对象（见 §4.4）。 |
| `output_dir_name` | `ir/models.py:195`；`ir/builder.py:138,151`；`cli.py:60-61`；`templates/c/README.md.j2:1` | 改为生成期局部量。`emit_c/emitter.py:20` 与 `emit_python/emitter.py:16` 已各自计算 `f"{stem}_{settings.output_dir_name(TARGET)}"`；CLI `check` 的 golden 目录同样按 target 计算；`README.md.j2:1` 改为接收显式上下文变量（如 `dir_name`）。 |
| `NOTIFY_KINDS` / `NOTIFY_KIND_VALUES` / `NOTIFY_ON_EXPECTED_KIND` / `KIND_ENUM_SUFFIX` | `ir/models.py:14-21`；`ir/builder.py:14,371,571`；另 `ir/builder.py:469-470` 与 `templates/c/Core/stnp_frame.h.j2:24-26` 的 `STNP_NOTIFY_KIND_*` 宏同属该主题 | 删常量与 import；`_resolve_notify_ref` 删 kind 期望校验（`571-573`），退化为「引用的通知存在即可」；C 宏 `STNP_NOTIFY_KIND_*` 删除并同步删 `_validate_generated_c_symbols` 固定符号表（`469-470`）。 |

### 1.3 新增清单

| dataclass | 字段 | 动作 | 依据 | 备注 |
|---|---|---|---|---|
| `ModuleIR` | `enabled` | 增（默认 `true`） | D2 | 生成侧消费。现状 `loader.py:105-109` 在构建前过滤 disabled Module；方案改为 IR 全量承载 `enabled`，生成侧 emit 循环按 `m.enabled` 跳过，且 instance 必须引用 enabled Module。 |
| `ProtocolIR` | `seq_enabled` | 增（默认 `false`） | D6 | 对齐 `protocol.features.seq.enabled`；Task / Notify 共用此一处门控与同一发送方计数器。 |
| `ProtocolIR` | `notify_dispatch_receive` | 增（默认 `false`） | D7 | 对齐 `protocol.options.notify_dispatch_receive.enabled`；本端是否启用 Notify 接收分发路径，允许运行时切换。 |
| `GlobalResultIR`（新 dataclass） | `name` / `value` / `brief` | 增 | D1 / D14 | 工程级 Result 码表条目；`name` 与 `enum_member` 命名规则见 §2.2。 |
| `ProjectIR` | `global_results: list[GlobalResultIR]` | 增 | D1 / D14 | 含工程级 `OK`（值 `0x0000`）；Global Result 码表来源。 |

新增计数：**IR 新增字段 4 个**（`ModuleIR.enabled`、`ProtocolIR.seq_enabled`、`ProtocolIR.notify_dispatch_receive`、`ProjectIR.global_results`）；**新增 dataclass 1 个**（`GlobalResultIR`）。

> 说明：任务书新增项列举了前三项（`enabled`、SEQ 门控、`global_results` 载体）。`notify_dispatch_receive` 是 D7「删 `notify_dispatcher`、增 `protocol.options.notify_dispatch_receive.enabled`」在 IR 层不可回避的落点，故一并登记；`GlobalResultIR` 是 `global_results` 的载体 dataclass。

### 1.4 改动清单

| dataclass / 对象 | 字段 / 项 | 动作 | 依据 | 备注 |
|---|---|---|---|---|
| 加载处理 | `schema_version` | 改 | D4 / 配置拆分补充裁定四 | `.stnp` 必填、类型 string、取值 `"stnp-schema-alpha"`。读取并对照支持列表，读到不支持值直接抛异常；**读取保留但不进入 IR**。 |
| 加载处理 | `build_schema_version` | 改 | 配置拆分补充裁定五 | `stnp.build.json` 用 `"stnp-build-schema-alpha"`，独立维护支持列表，同样不进入 IR。 |
| `ProtocolIR` | `task_fixed_size` | 改 | D10 / D13 | 由硬编码 `7` 改为按 `(SEQ, CRC)` 组合计算：`2 + [2 SEQ] + 1 + 1 + 1` → `5/7`。 |
| `ProtocolIR` | `notify_fixed_size` | 改 | D10 / D13 | 由硬编码 `7` 改为按组合计算：`2 + [2 SEQ] + 1 + 1 + 2 + 1` → `7/9`。 |
| `ProjectIR` | `emit_examples` | 改 | D9 | 取值只来自 `stnp.build.json` 的 `<target>.emit_examples`，默认 `false`；删除 `settings.emit_examples` 回退（`ir/builder.py:145`）。 |

改后 IR 字段总览（仅列受影响 dataclass）：

```text
FieldIR          : 不变
CommonTypeIR     : 不变
ReturnCodeIR     : 不变
NotificationIR   : name pascal code macro_name fields payload_length payload_struct decode_fn brief   (删 kind)
GlobalResultIR   : name value brief                                                                (新增)
CommandIR        : 不变（notify_on_* 仍为触发时机）
ModuleIR         : ... auto_notify_enabled enabled ... commands notifications return_codes ...       (删 notify_groups/default_id_*，增 enabled)
InstanceIR       : 不变
EmbeddedFileIR   : 不变
ProtocolIR       : name version max_payload router_instance_max task_sof notify_sof
                   seq_start seq_reserved seq_enabled
                   task_fixed_size notify_fixed_size crc_enabled notify_dispatch_receive              (删 crc_runtime_toggle/notify_dispatcher，增 seq_enabled/notify_dispatch_receive)
ProjectIR        : project_name protocol modules instances emit_readme emit_examples build_system
                   sdks common_types embedded_files output_stem global_results                        (删 extras/output_dir_name，增 global_results)
```

---

## 二、构建链语义定案

按 `src/stnp_editor/ir/builder.py` 现有函数逐个给出改造要点。

### 2.1 函数改造总表

| 函数 | 现状要点 | 方案要点 | 依据 |
|---|---|---|---|
| `build_project_ir` | 单实例宏回填；`targets` 回退链；`extras`/`output_dir_name`；C-only 符号校验 | 删回填；目标改读 build 单一 `target`；删 extras/output_dir_name；符号校验按 target 分派；增 global_results；instance 引用 enabled Module | D3/D8/D12/D17 |
| `_build_common_types` | 无 | 不变 | — |
| `_build_embedded` / `_check_embedded_path` | 无 | 不变 | — |
| `_build_protocol` | 硬编码头长；`crc_runtime_toggle`/`notify_dispatcher` | 按组合计算头长；增 `seq_enabled`/`notify_dispatch_receive` | D5/D6/D7/D10/D13 |
| `_resolve_field` | min/max 元数据校验 | 不变 | — |
| `_build_fields` | 累计后已校验 `> max_payload` | 保留为生成侧唯一超限强制点 | D11 |
| `_build_return_codes` | 只校验 u16 值域 + 存在 OK | 增分段归属校验（每 Module 256 值） | D14 |
| `_build_module` | 构造 `notify_groups`；`kind`；`default_id_*` | 删 notify_groups/kind；macro_name 去 kind；增 `enabled`；传 `module_index` | D2/D15 |
| `_validate_generated_c_symbols` | C-only；含 kind 宏与 `{name}_ID` | 改为按 target 分派入口；删 kind 宏与 `{name}_ID`；新增 Python 分支 | D12 |
| `_resolve_notify_ref` | 校验 kind == expected | 退化为「引用存在即可」 | D15 |
| `_build_command` | 无 | 不变（经 `_resolve_notify_ref` 简化） | — |

### 2.2 Payload 超限

- **现状**：`_build_fields`（`ir/builder.py:288-307`）在字段逐项累计 `length` 后，已存在 `if length > max_payload: raise ValueError`（`305-306`）。差异报告 D11 所述「缺少」与 0.8.2 源码不符。
- **方案**：保留该位置为生成侧唯一强制点，在 payload 累计完成后校验 `payload_length > max_payload` 即抛错；`_build_command`（`582`）与 `_build_module` 的通知路径（`345`）均经此函数，无需另设校验点。错误类型在补充裁定 A 落地前维持 `ValueError`。

> 现状源码已符合本项要求，**D11 属确认现状，无需实施代码改动**。裁定表对应条目改注为「确认现状已符合」。

### 2.3 Return Code 分段校验

- **现状**：`_build_return_codes`（`310-328`）只校验 u16 值域 `0..65535`、同 Module 内名称/值唯一、存在名为 `OK` 的成员；无工程级 OK、无 Global 区间、无 Module 分段归属。
- **方案**：
  - 新增 `_build_global_results(raw)`：校验 `global_results` 必填且 `minItems 1`；必须存在名为 `OK` 且值为 `0x0000` 的条目；其余条目值落在 `0x0001..0x00FF`；条目数 ≤ 255。
  - `_build_return_codes(module_name, raw_list, module_index)` 增加 `module_index`：该 Module 合法区间为 `[0x0100 + 256*module_index, 0x0100 + 256*module_index + 255]`；每个 Return Code 值必须落在本区间；每 Module 强制存在名为 `OK` 的 Return Code 且落在本区间；每 Module Return Code 数 ≤ 256。
  - Module 数 ≤ 255 在 `build_project_ir` 校验（`modules[]` 顺序即 `module_index`）。
  - 值区间语义：`0x0000` 工程级 OK / `0x0001..0x00FF` Global / `0x0100 + 256*i` 起每 Module 256 值。
- **去向**：`ModuleIR.result_ok`（`builder.py:337`）仍取本 Module 的 `OK`；Global Result 码表由新增的 `ProjectIR.global_results` 提供，供生成侧 Result 码表消费。

### 2.4 帧长矩阵

- **现状**：`_build_protocol`（`249-250`）将 `task_fixed_size` 与 `notify_fixed_size` 均硬编码为 `7`。
- **方案**：改为按 `(SEQ, CRC)` 组合计算：
  - `task_fixed_size = 2 + (2 if seq_enabled else 0) + 1 (TARGET) + 1 (CMD) + 1 (LEN)` → SEQ 关 `5` / 开 `7`。
  - `notify_fixed_size = 2 + (2 if seq_enabled else 0) + 1 (SOURCE) + 1 (NOTIFY) + 2 (RESULT) + 1 (LEN)` → SEQ 关 `7` / 开 `9`。
  - CRC 尾 `0/2`（由 `crc_enabled` 决定，模板侧 `STNP_CRC_SIZE` 已为 `0/2`）。
  - 最大帧取两家族较大者：`STNP_FRAME_MAX_SIZE = max(TASK_FIXED_SIZE, NOTIFY_FIXED_SIZE) + PAYLOAD_MAX + CRC_SIZE`（`stnp_platform_config.h.j2:19-22` 已按此实现，修正头长后即自洽）。
  - RX Ring 按 4 个最大帧预留（`stnp_platform_config.h.j2:27-29` 已实现 `STNP_FRAME_MAX_SIZE * 4U`）。
- **去向**：模板 `stnp_platform_config.h.j2:15-16` 直接读 `p.task_fixed_size` / `p.notify_fixed_size`，无需再改结构；`stnp_task.c.j2:74`、`stnp_notify.c.j2:44`、`stnp_frame.c.j2`、`stnp_core.c.j2` 的 `FIXED_SIZE` 用法随常量取值自动正确。

### 2.5 CRC 覆盖范围

- **现状**：`stnp_frame.c.j2` 的 `_append_crc(out, body_len)`（`28-35`）对 `out[0..body_len)` 计算并以 `STNP_Encode_U16` 追加，`body_len = FIXED_SIZE + payload`，即 HEADER 至 PAYLOAD 的 body；`_verify_crc`（`37-49`）同理。Python `frame.py.j2` 的 `crc16_modbus(out)`（`33,46`）在追加前对 body 计算。故覆盖范围现状已为 body，非「整帧」。
- **方案**：固定表述为「HEADER 至 PAYLOAD 的 body，CRC 自身以 u16 小端追加在 body 之后，不覆盖自身」；随 D5 删除运行期开关后，`_crc_extra()` 的运行时判断移除，CRC 在 `crc_enabled` 时恒存在（`STNP_CRC_SIZE`），关闭时完全不存在。Python 侧 `Runtime._crc_enabled` 与 `StreamParser.crc_enabled` 简化为生成期常量。

> 现状源码已符合本项要求，**D16 属确认现状，无需实施代码改动**。裁定表对应条目改注为「确认现状已符合」。

### 2.6 SEQ 门控

- **现状**：`ProtocolIR` 只有 `seq_start` / `seq_reserved`，无门控；Task 帧恒带 SEQ（`stnp_task.c.j2:90-91`、`stnp_frame.c.j2:81,150`），Notify 帧**完全没有** SEQ 槽（`stnp_frame.h.j2:37-44`、`stnp_frame.c.j2:190-195`）；计数器 `g_task_seq` 仅存在于 Task 发送路径（`stnp_task.c.j2:13,33-46`）。Python `frame.py.j2` 同样：`build_task` 恒写 SEQ（`29`），`build_notify` 不写 SEQ（`41-43`）；`StreamParser` 硬编码下标（`buffer[6]`、`total = 7 + ...`，`74-80`）。
- **方案**：
  - `ProtocolIR.seq_enabled` 新增（默认 `false`）。
  - Task / Notify 共用同一门控与同一发送方计数器；关闭时 SEQ 槽完全不存在。
  - C：`STNP_TaskFrame` / `STNP_NotifyFrame` 的 `seq` 成员与写入/解析按 `p.seq_enabled` 条件生成；`g_task_seq` 计数器移出 Task 专用路径，改为 Task / Notify 共享（如 `stnp_runtime.c` 或独立 seq 辅助）；Notify 发送路径新增取号。
  - Python：`build_task` / `build_notify` 按 `protocol.seq_enabled` 决定是否写入 SEQ；`StreamParser` 按组合先算头长再定位 `LEN`（Task 帧 LEN 下标 SEQ 关/开 = `4/6`，Notify = `6/8`）。`Runtime._next_seq`（`140-147`）已是单一共享计数器，符合共用语义。
  - 帧长按 §2.4 组合推导。

### 2.7 目标解析

- **现状**：`build_project_ir`（`130-134`）读取 `gen.target`，并以 `legacy_targets = tuple(gen.get("targets") or (target,)) if "target" not in gen else (target,)` 兼容复数；`generation.py:8-15` 的 `selected_generation_target` 为 `gen.target → gen.targets[0] → "c"` 回退链。
- **方案**：删除 `gen.targets` 复数与全部回退链；目标只读 `stnp.build.json` 顶层单一必填 `target`（`enum ["c","python"]`）；非法/缺失由 Schema 枚举校验在加载期拒绝。`generation.py` 的 `selected_generation_target` 简化为直接返回 build 的 `target`（不再回退 `"c"`），`generation_config_for_target` 的 v0.7.1 legacy 回退删除。

### 2.8 单实例便捷宏回填

- **现状**：`build_project_ir:120-128` 在单实例绑定时回填 `mod.default_id_macro = f"{mod.name}_ID"` 与 `mod.default_id_value`；`module.h.j2:16-18` 据此产出 `#define {{ m.name }}_ID`。
- **方案**：**直接删除，不做生成侧派生**（D3）。删 `builder.py:120-128`、构造参数（`413`）、`_validate_generated_c_symbols:514-515` 的 `{name}_ID` 声明与 `module.h.j2:16-18`。用户统一使用 `STNP_INSTANCE_<INSTANCE>_ID`（由 `stnp_instances.h.j2` 生成）。

### 2.9 符号校验按 target 分派

- **现状**：`_validate_generated_c_symbols`（`418-556`）为 C-only，在 `build_project_ir:136` 无条件调用；固定符号表含 `STNP_NOTIFY_KIND_*`（`469-470`）与 `{name}_ID`（`514-515`）。
- **方案**：设统一入口 `validate_generated_symbols(ir, *, target, validations)`，按 `target` 分派到 `_validate_generated_c_symbols`（C 分支，删上述两处）与新增 `_validate_generated_python_symbols`（Python 分支）；规则清单来自 `stnp.build.json` 的 `validations` 段（字段 `id` / `level`），默认从生成器导出、全列全启用。调用点由 `builder.py:136` 改为分派入口。

---

## 三、生成侧设计定案

### 3.1 通知去分类

**语义定案**：`ACCEPT` / `REJECT` / `PUSH` 不再分类；接受/拒绝语义由 Notify 帧的 `RESULT` 槽承载。`notify_on_done` / `notify_on_accept` / `notify_on_reject` 保留为**触发时机**，引用校验退化为「引用的通知存在即可」。

**宏名新规**：现状 `macro_name = f"{name}_{kind}_{nname}"`（`builder.py:359`）去掉 kind，改为 `f"{name}_NOTIFY_{nname}"`。此命名同时用于 C 枚举成员（`module.h.j2:30`）、VTL 表（`module.c.j2:105,297`）与 C 符号表（`builder.py:525`），必须三处一致。

**C 侧删除位置清单**

| 文件:行 | 现状内容 | 处置 |
|---|---|---|
| `templates/c/Core/stnp_frame.h.j2:9` | 注释 `ACCEPT / REJECT / PUSH 仅为配置与 C 分组` | 删除该分类表述 |
| `templates/c/Core/stnp_frame.h.j2:24-26` | `STNP_NOTIFY_KIND_ACCEPT/REJECT/PUSH` 宏 | 删除 |
| `ir/builder.py:469-470` | 固定 C 公开符号表含上述三个宏 | 删除 |
| `ir/builder.py:352,357-359` | `kind = n["kind"]`、`macro_name` 含 kind | 删 kind；macro_name 改新规 |
| `ir/builder.py:367-371,407` | `notify_groups` 构建与构造实参 | 删除 |
| `ir/builder.py:571-573` | `_resolve_notify_ref` 的 kind 期望校验 | 删除，仅校验引用存在 |
| `ir/models.py:14-21,75,85-89,129` | kind 常量、`NotificationIR.kind`、`NotifyGroupIR`、`ModuleIR.notify_groups` | 删除 |

**Python 侧删除位置清单**

| 文件:行 | 现状内容 | 处置 |
|---|---|---|
| `templates/python/stnp/core/model.py.j2:111` | `NotificationDescriptor.__init__(..., kind: str, ...)` | 删 `kind` 形参 |
| `templates/python/stnp/core/model.py.j2:114` | `self.kind = kind` | 删属性 |
| `templates/python/stnp/protocol/modules/module.py.j2:28` | `kind={{ n.kind \| repr }}` | 删 `kind=` 实参 |
| `schemas/module.schema.json:136,147-154` | `notifications[].kind` 必填与 `enum` | 删除（schema 侧） |

**保留不动**：`module.c.j2` 的 `AUTO_NOTIFY_ACCEPT/REJECT/DONE` 阶段常量与 `AutoNotifySend`（`16-82`）是**触发时机**的生成代码，不属分类信息，保留；`notify_on_*` 零载荷约束（`builder.py:391-402`）保留。

### 3.2 校验函数

**定案**：按模块一个校验函数，`switch(cmd)` 分派，由生成器自动生成；`validate_hook = true` 时按字段类型与 `min` / `max` 自动产出校验代码；生成到 Implementation；**USER 区段本轮不开放**。

**C 侧函数签名**（生成到 `Implementation/<snake>_impl.c`，与现有 `{Pascal}_ValidateCallback` 签名一致）：

```c
STNP_Result {Pascal}_Validate(
    {Pascal}Handle *self,
    STNP_U8 cmd,
    const void *payload);
```

- 生成体为 `switch (cmd)`：每个 `case {NAME}_CMD_{CMD}:` 将 `payload` 转为对应 `{Pascal}_{Cmd}Payload *`，按字段基础类型值域（`TYPE_RANGES`）与 `min` / `max` 校验；通过返回 `{Module}_OK`，失败返回该 Module 的拒绝码 / `STNP_ERR_PARAM`。
- 接线改动：`module.c.j2:13` 的 `g_validate_<ops>` 指针、`121-132` 的 `{Pascal}_SetValidate`、`171-181` 与 `204-214` 的校验调用点，改为调用生成的 `{Pascal}_Validate`。
- 本轮不生成 USER CODE 区段（D21 记录为后续工作）。

**Python 侧函数签名**（生成到 `stnp/protocol/modules/<snake>.py`；Python 无 Implementation 目录，生成到模块定义文件内）：

```python
def {snake}_validate(instance, command, payload) -> int:
    ...
```

- 生成体为按 `command.code` 的 `if/elif` 分派，字段值域与 `min` / `max` 校验；通过返回 `{Pascal}Result.OK`，失败返回拒绝码。
- 接线改动：`runtime.py.j2:229-234` 的 `_dispatch_task` 校验分支改调用生成的模块校验函数；`model.py.j2` 的 `@cmd.validate` decorator 仍保留供用户覆盖（生成侧默认实现由生成器提供）。

### 3.3 Notify 分发 API

**配置**：新增 `protocol.options.notify_dispatch_receive.enabled`（boolean，默认 `false`，允许运行时切换）。语义：**本端是否启用 Notify 接收分发路径**。

**组级区分**：`features` 是 Capability（改 wire format、两端一致、禁运行时切）；`options` 是本端行为（不改 wire format、两端可不同、允许运行时切）。`notify_dispatch_receive` 属 `options`。

**C 侧精确签名**（生成到 `Core/stnp_notify.h` / `stnp_notify.c`）：

```c
void    STNP_NotifyDispatchReceive_Enable(void);
void    STNP_NotifyDispatchReceive_Disable(void);
STNP_U8  STNP_NotifyDispatchReceive_IsEnabled(void);
```

**Python 侧精确签名**（生成到 `stnp/core/runtime.py`，并在 `stnp/__init__.py` 同名导出）：

```python
def NotifyDispatchReceive_Enable() -> None: ...
def NotifyDispatchReceive_Disable() -> None: ...
def NotifyDispatchReceive_IsEnabled() -> bool: ...
```

**消费点**：
- C：`stnp_instances.c.j2:24` 的编译期 `{% if p.notify_dispatcher %}` 改为运行时 `STNP_NotifyDispatchReceive_IsEnabled()` 门控；`stnp_notify.c.j2` 的 `STNP_Notify_Dispatch` / `STNP_Notify_Callback` 分发路径按该开关放行。
- Python：`runtime.py.j2` 的 `_dispatch_notify` 分发分支按 `NotifyDispatchReceive_IsEnabled()` 放行。
- 初值来自 `ProtocolIR.notify_dispatch_receive`（生成期默认写入，运行时可切）。

### 3.4 符号校验按 target 分派

**统一入口**：

```python
def validate_generated_symbols(
    ir: ProjectIR,
    *,
    target: str,
    validations: dict[str, dict],
) -> None: ...
```

- 按 `target` 分派到对应目标的校验模块：C → `_validate_generated_c_symbols`（沿用现有实现，删 kind 宏与 `{name}_ID`）；Python → 新增 `_validate_generated_python_symbols`。
- 校验规则清单来自 `stnp.build.json` 的 `validations` 段（字段 `id` / `level`），默认从生成器导出、全列全启用；未在清单中启用的规则不执行。
- 调用点：`ir/builder.py:136` 改为调用统一入口。

### 3.5 `build_vectors` / `sample_value`

**本轮不动，明确标注。** 现状位于 `src/stnp_editor/vectors.py`（`sample_value` 在 `25`，`build_vectors` 在 `96`）。其与协议 IR 的解耦、是否迁入测试工具，留待后续轮次，不纳入本次定案。

---

## 四、CLI 设计定案

### 4.1 子命令与参数

子命令保持 `generate` / `check`，两者都**新增参数指定 `stnp.build.json` 路径**。

| 子命令 | 参数 | 必填 | 说明 |
|---|---|---|---|
| `generate` | `<project.stnp>` | 是 | `.stnp` 工程路径 |
| `generate` | `--build <stnp.build.json>`（`-b`） | 是 | 生成配置路径；新增 |
| `generate` | `-o/--output <dir>` | 是 | 生成输出父目录 |
| `check` | `<project.stnp>` | 是 | `.stnp` 工程路径 |
| `check` | `--build <stnp.build.json>`（`-b`） | 是 | 生成配置路径；新增 |
| `check` | `--golden <dir>` | 是 | 金样本根目录 |

### 4.2 目标分派

- CLI 只按 build 文件的**单一 `target`** 分派（D17）。
- 删除 `ensure_supported_generation_targets` 复数校验与 `"c"` 回退（D18）。
- 删除「目标不支持 → 退出码 2」分支（D19）；非法目标由 Schema 枚举校验（`enum ["c","python"]`）在加载期拒绝。

### 4.3 退出码

严格遵守契约，不自创：

| 退出码 | 含义 | 触发场景 |
|---:|---|---|
| `0` | 成功 | 生成完成；`check` 比对一致 |
| `1` | 校验或生成失败 | Schema/语义校验失败、Payload 超限、`check` 比对不一致、生成期异常 |
| `2` | 用法参数错误 | 缺参、参数类型错误等 argparse 用法错误 |
| `3` | 内部错误 | 非预期内部异常 |

> 现状 `cli.py:45,57` 将目标校验失败返回 `2`，该分支随 D19 删除；目标非法改由加载期 Schema 拒绝，归入退出码 `1`。

### 4.4 `extras` 取用点改造

`ProjectIR.extras` 删除后，`cli.py` 中原 `ir.extras.get("generation_target"/"generation_targets")` 的取用点改为直接读 build 配置：

| 文件:行 | 现状 | 方案 |
|---|---|---|
| `cli.py:42` | `ensure_supported_generation_targets(ir.extras.get("generation_targets", ("c",)))` | 删除；目标由 build Schema 枚举保证 |
| `cli.py:46` | `target = ir.extras.get("generation_target", "c")` | `target = build["target"]`（读 `stnp.build.json` 顶层） |
| `cli.py:54` | `ensure_supported_generation_targets(...)` | 删除 |
| `cli.py:66` | `target = ir.extras.get("generation_target", "c")` | `target = build["target"]` |
| `cli.py:60-61` | `ir.output_dir_name` 参与 golden 路径 | 由 target 计算：`f"{ir.output_stem}_{settings.output_dir_name(target)}"` |
| `emit_python/emitter.py:29` | `pycfg = dict(ir.extras.get("python_generation") or {})` | `emit_python(ir, out, build=build)`，`pycfg = build["python"]` |

分派实现示意（签名级，不含实现体）：

```python
def main(argv: list[str] | None = None) -> int: ...
def _load_build(path: Path) -> dict[str, Any]: ...
```

- `generate`：`ir = load_project(project)` → `build = _load_build(args.build)` → `target = build["target"]` → `emit_python(...) if target == "python" else emit_c(...)` → `return 0`。
- `check`：同法取 `target` 与生成结果，与 `golden_root / f"{ir.output_stem}_{settings.output_dir_name(target)}"` 比对；一致 `0`，有差异 `1`。
- `generation.py`：删除 `ensure_supported_generation_targets`；`selected_generation_target` 简化为只读单一 `target`；`generation_config_for_target` 的 legacy 回退删除。

---

## 五、汇总与验收

### 5.1 计数

| 项 | 数量 | 明细 |
|---|---:|---|
| IR 删除字段 | 8 | `crc_runtime_toggle`、`notify_dispatcher`、`default_id_macro`、`default_id_value`、`notify_groups`、`kind`、`extras`、`output_dir_name` |
| IR 删除 dataclass | 1 | `NotifyGroupIR` |
| IR 删除模块级常量 | 4 | `NOTIFY_KINDS`、`NOTIFY_KIND_VALUES`、`NOTIFY_ON_EXPECTED_KIND`、`KIND_ENUM_SUFFIX` |
| IR 新增字段 | 4 | `ModuleIR.enabled`、`ProtocolIR.seq_enabled`、`ProtocolIR.notify_dispatch_receive`、`ProjectIR.global_results` |
| IR 新增 dataclass | 1 | `GlobalResultIR` |
| IR 改动字段 | 2（+1 处理项） | `task_fixed_size`、`notify_fixed_size`；`schema_version` 为加载处理项（不进入 IR） |

### 5.2 验收清单

- [ ] 四节齐全：IR 字段增删定案 / 构建链语义定案 / 生成侧设计定案 / CLI 设计定案。
- [ ] 每项删除均给出引用点去向（模板或函数），无「只说删除」。
- [ ] C 与 Python 的校验函数、Notify 分发 API 均给出精确签名。
- [ ] 退出码严格取 `0/1/2/3`，未自创。
- [ ] 未修改任何代码或模板；未写函数实现体。
- [ ] `build_vectors` / `sample_value` 标注为本轮不动。
- [ ] 未触碰 `src/stnp_editor/gui/`。
