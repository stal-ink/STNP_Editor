# 归档登记表

本页是文档集**唯一**的归档登记入口。`archive/` 内存放已被现行 0.9 文档取代的历史资料，只供追溯，不能当作当前 API、协议或生成器行为的依据。

## 归档规则

判定一份历史文档应放入哪个版本目录时，按下列顺序：

1. 文档正文自称的基线或目标版本优先（例如正文写「0.2.0 中存在……」即归 `v0.2/`）。
2. 正文无版本标记时，采用文档头部归档横幅中提到的版本（例如「可能与当前 0.5.0 修复版冲突」→ `v0.5/`）。
3. 仍无法判定时放在 `archive/` 顶层，并在本表注明「版本待人工裁定」。
4. 协议版本不等于发行版本：以协议版本命名的历史文档留在 `archive/` 顶层。
5. `docs/0.9/**` 与 `docs/方案/_superseded/**` 均为 0.9 期过程资料，归入 `archive/v0.9/`。
6. **archive 正文不改**：只移动、只登记；编号、术语、错别字、内部链接一律保持原样。

`archive/v0.9/README.md` 是历史文件（原阶段一交付物索引），不是本目录的登记表。

## 登记表

登记日期：2026-09-18。

| 原路径 | 目标路径 | 版本目录 | 判定依据（文档内标记） | 内容摘要 | 登记日期 |
|---|---|---|---|---|---|
| docs/archive/DESIGN_C_GENERATOR_V2.md | docs/archive/v0.5/DESIGN_C_GENERATOR_V2.md | v0.5 | 头部「版本：V1.0」；横幅「当前 0.5.0 修复版」 | C 生成器架构设计规范（历史） | 2026-09-18 |
| docs/archive/DESIGN_RUNTIME_SECOND_ROUND_PRE_UNIFIED_SEND.md | docs/archive/v0.2/DESIGN_RUNTIME_SECOND_ROUND_PRE_UNIFIED_SEND.md | v0.2 | 正文以 0.2.0 为基线（「0.2.0 中存在……」） | 第二轮架构调整与统一发送（历史） | 2026-09-18 |
| docs/archive/PROTOCOL_STNP_V1.0.md | docs/archive/PROTOCOL_STNP_V1.0.md | 顶层（协议版本） | 标题「STNP V1.0」；「版本：V1.0」；协议版本而非发行版本 | 历史协议 V1.0 正文 | 2026-09-18 |
| docs/0.9/0.9_冻结计划.md | docs/archive/v0.9/0.9_冻结计划.md | v0.9 | 定位行：「0.9 落地的唯一入口文件」 | 0.9 落地冻结计划（含裁定表） | 2026-09-18 |
| docs/0.9/0.9_规格变更清单.md | docs/archive/v0.9/0.9_规格变更清单.md | v0.9 | 目标文档为当时的 `docs/STNP_SPEC_0.9.md` | 0.9 规范逐节变更清单 | 2026-09-18 |
| docs/方案/_superseded/README.md | docs/archive/v0.9/README.md | v0.9 | 自称「阶段一交付物（已取代）归档说明」 | 阶段一 5 份交付物的历史索引 | 2026-09-18 |
| docs/方案/_superseded/01_报错处理机制.md | docs/archive/v0.9/01_报错处理机制.md | v0.9 | 首行「阶段一·定方案交付物」 | 生成器统一报错机制设计方案 | 2026-09-18 |
| docs/方案/_superseded/02_配置拆分与Schema.md | docs/archive/v0.9/02_配置拆分与Schema.md | v0.9 | 「阶段一·定方案 交付物 02」；D4/D8/D9 | 配置拆分与 schema 设计 | 2026-09-18 |
| docs/方案/_superseded/03_IR生成侧CLI.md | docs/archive/v0.9/03_IR生成侧CLI.md | v0.9 | 「目标版本：STNP 0.9；基线版本：0.8.2」 | IR / 生成侧 / CLI 方案 | 2026-09-18 |
| docs/方案/_superseded/04_GUI清理_迁移_C2.md | docs/archive/v0.9/04_GUI清理_迁移_C2.md | v0.9 | 「阶段一『定方案』交付物」；GUI 清理属 0.9 破坏性批次 | GUI 清理、示例迁移与 C2 命名定案 | 2026-09-18 |
| docs/方案/_superseded/05_0.9文档变更清单.md | docs/archive/v0.9/05_0.9文档变更清单.md | v0.9 | 标题即 0.9 文档变更清单 | 阶段一文档变更清单 | 2026-09-18 |
| stnp-0.9-docs.md | docs/archive/v0.9/06_0.9文档重写计划.md | v0.9 | 标题「STNP 0.9 文档集重写计划（供外部执行者使用）」；开篇「自包含的执行计划」 | 把 `docs/` 整理为全中文、可验证文档集并回归仓库索引的执行计划 | 2026-09-18 |
| （新稿） | docs/archive/v0.9.1/README.md | v0.9.1 | 正文自称 0.9.1 实现规格 | 0.9.1 运行时诊断实现规格索引 | 2026-09-19 |
| （新稿） | docs/archive/v0.9.1/01_notify独占分发.md | v0.9.1 | 目标版本 0.9.1 | Notify 接收改为 module XOR global（破坏性） | 2026-09-19 |
| （新稿） | docs/archive/v0.9.1/02_未知帧回调.md | v0.9.1 | 目标版本 0.9.1 | 未知帧两道闸回调，默认关；无诊断信封 | 2026-09-19 |
| （新稿） | docs/archive/v0.9.1/03_python_trace.md | v0.9.1 | 目标版本 0.9.1 | Python `stnp.trace.debug` + `trace.format` | 2026-09-19 |
| （新稿） | docs/archive/v0.9.1/04_c断点宏.md | v0.9.1 | 目标版本 0.9.1 | C `STNP_DEBUG` 预编译断点宏，只验证链路 | 2026-09-19 |
| （新稿） | docs/archive/v0.9.1/05_改造清单.md | v0.9.1 | 目标版本 0.9.1 | 切片顺序 A→C→B+D→E 与改造清单 | 2026-09-19 |

## 特殊项

`PROTOCOL_STNP_V1.0.md` 描述的是协议版本 V1.0，不是产品发行版本 1.0。现行 wire 格式以 [2. 协议格式](../02_protocol.md) 为准，冻结规范见 [STNP 0.9 冻结规范](../05_architecture/spec_0.9.md)。

## 不在本表的内容

现行 0.9 文档在 `docs/` 根与 `04_api/`、`05_architecture/`、`06_guides/`。冻结规范现位于 [spec_0.9.md](../05_architecture/spec_0.9.md)（由 `docs/STNP_SPEC_0.9.md` 仅路径改名而来，规范正文不改写）。本表只登记 §5.2 的 11 次移动/原位保留，不收录现行页面。

## 声明

- archive 正文保持搬入时的原文，不做补链、加页脚或改标题。
- 当前文档索引见 [文档目录](../README.md)。

---

[← 变更记录](../08_changelog.md) | [文档目录](../README.md)
