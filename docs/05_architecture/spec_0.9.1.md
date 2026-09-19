# STNP 0.9.1 运行时增量（delta）

本页是 **0.9.1 相对冻结规范的运行时增量**，不是重写。以下内容仍以 [spec_0.9.md](spec_0.9.md) 为准，其正文不改写：

- wire 十槽与两家族 SOF；
- Capability 模型；
- `.stnp` 与 `stnp.build.json` 的 schema；
- `protocol.options.notify_dispatch_receive.enabled` 的**管辖范围**（§8.3：本端是否启用 Notify 接收分发路径）。

0.9.1 **不增加**第三 SOF、诊断信封、`protocol.options` 新键或日志子系统。

来源与落地口径：设计原稿在 [archive/v0.9.1](../archive/v0.9.1/README.md)（过程资料，只追溯）；落地后以本页与现行 `docs/` 为准。

## 1. 相对 0.9.0 改变的行为

| # | 主题 | 0.9.0 | 0.9.1 |
|---|---|---|---|
| 1 | Notify 接收 | 全局与模块**可并行**收到同一帧 | **module XOR global**：模块认领后全局不再收 |
| 2 | Python `notify_dispatch_receive` | 关则 `_dispatch_notify` 直接返回（typed 与 `@stnp.on_notify` 都不跑） | **不变**：仍是整条接收分发总门（§8.3）；关则模块与全局都不投递 |
| 3 | Python `@stnp.on_notify` 签名 | 已知码可收到 dataclass / `NotificationDescriptor` | 全局**只剩两种 raw 形**（见 §2.3） |
| 4 | 非法 / 不可路由帧 | 静默丢或只记内部计数 | 可选**两道闸**回调，默认关（见 §3） |
| 5 | Python 观察 | 无 | `stnp.trace.debug` + `stnp.trace.format`，默认关（见 §4） |
| 6 | C 链路打点 | 无（0.7 起曾写「无 Debug Trace 宏计划」） | 预编译 `STNP_DEBUG` 0/1，宏只打规格站点（见 §5） |

关于第 2 行（DR）：schema 键 `protocol.options.notify_dispatch_receive.enabled` **不改** —— 仍是生成初值 + 运行时 `Enable` / `Disable` / `IsEnabled`。**本批次不改 DR 的管辖范围**（冻结规范 §8.3 已定：本端是否启用 Notify 接收分发路径）；0.9.1 只做两件事：**补齐独占**，以及**纠正曾把 DR 收窄成「只覆盖 typed 认领」的实现偏离**。

## 2. Notify 独占（破坏性）

发送侧完全不动：`STNP_Notify_Send` / `stnp.notify`、Job 入队、wire。**只改接收分发。**

### 2.1 C 认领（以下全部成立，才只走模块）

1. DR 开（`STNP_NotifyDispatchReceive_IsEnabled() != 0`）；
2. `SOURCE` 命中已登记 Instance；
3. `<Module>_NotifyCallbackIsEnabled() != 0`；
4. VTL 找到码（`NotifyDispatch` 返回值不是 `STNP_ERR_COMMAND`）；
5. Decode 成功。

- 未知码：`STNP_ERR_COMMAND` 是**唯一**允许 fall through 的返回值 → 落入全局。
- 已知码但 Decode 失败：属**模块路径错误**，**禁止**转全局。
- C **不**增加 `STNP_Notify_CallbackEnable`；生成工程里全局 `STNP_Notify_Callback` 恒可调用。

### 2.2 Python 认领（以下全部成立，才只走 typed `.func`）

1. DR 开；
2. `SOURCE` 命中 registry；
3. `by_code` 非 None；
4. `_func.resolve` 非 None。

- `fn is None` 时**禁止**为模块路径 decode，全局收到 raw。
- Python **没有** C 那种模块 Enable → C enable-off 与 Python「已有 typed func」**有意不对称**。

### 2.3 全局 `@stnp.on_notify` 的合法形（只有两种）

| 条件 | 调用 |
|---|---|
| 未知 Instance | `(source_id, code, result, raw bytes)` |
| 已知 Instance（未知码，或已知码但 `fn is None`） | `(instance, code, result, raw bytes)` |

## 3. 未知帧两道闸（默认关）

一个用户回调 + 一个使能开关；**两者都开**才可能被调用（`SetCallback` **且** `Enable`，缺一则真零调用）。

- 运行时不自动打印、不自动重传。
- SOF 另有**第二开关**（不是主开关）：C `STNP_UNKNOWN_REPORT_SOF` 默认 `0`；Python `runtime.unknown_report_sof` 默认 `False`。

| reason | C / Python 枚举 | 何时触发 |
|---|---|---|
| `sof` | `STNP_UNKNOWN_SOF` | 仅第二开关打开且两闸都开；次数 = 滑掉的字节数 |
| `len` | `STNP_UNKNOWN_LEN` | `LEN > max_payload`，或解析缓冲涨满 |
| `crc` | `STNP_UNKNOWN_CRC` | CRC 或 Frame_Parse 结构失败 |
| `task` | `STNP_UNKNOWN_TASK` | 完整 Task 不可路由（C：Enqueue 失败且不是 `STNP_ERR_BUFFER`；Python：未知 target/cmd） |
| `notify` | `STNP_UNKNOWN_NOTIFY` | **仅 Python**：独占链末端仍无人认领。C 枚举保留，**0.9.1 禁止触发** |

上表之外的边界同样是规格：

- 合法业务帧（含已认领、或已落入全局的 Notify）即使 unknown 已 enable，也**不进**本回调。
- 队列满（`STNP_ERR_BUFFER`）**不是** unknown：禁止 Report、禁止滑窗。
- 用户 unknown 回调异常隔离：**禁止**计入 `callback_errors`。
- Python 未知 target/cmd **不再** `raise ProtocolError`。
- Parser 仍只认两个协议 SOF；Python 的 SOF 猎寻与 C 对齐 —— 每次只滑 **1 字节**（禁止 `del buffer[:-1]` 整段丢前缀）。

## 4. Python `stnp.trace`

定位：**不是**日志产品层。禁止 `on_log` / `stnp.log` / `STNP_LOGx`。

### 4.1 `trace.debug`（站点打点）

站点：`rx_read` / `parse_ok` / `parse_resync` / `enqueue` / `dispatch` / `on_task` / `on_notify` / `seq_reserve` / `transport_write`。

- `parse_resync` 对每个 `ParseError("len"|"crc")` 打一次；**SOF 禁止打**。

### 4.2 `trace.format`（Dispatch 上只读语义化）

- Task 顺序：`decode → validate → format.maybe → fn is None 检查 → func`。
- Notify：只对**实际走的那条**（typed 或全局 fallback）`maybe` 一次；无人认领**禁止** format。

### 4.3 配置

- 配置在 `config/trace.yaml`，**不进** `stnp.yaml`。
- `stnp.init()` 调用 `trace.load()`。
- 装饰器 `@stnp.trace.format(path)` 只登记 formatter，**不写入** yaml 名单。
- 默认 `debug` / `format` 都关。

## 5. C `STNP_DEBUG`（预编译宏）

- 取值 `0` / `1`，默认 **0**；`0` 时宏为空，`1` 时才调用 weak `STNP_Debug_Trap`。
- 禁止：运行时 `Enable()`、`STNP_LOG*`、默认 BKPT；`stnp_platform_config.h` **禁止** `#define STNP_DEBUG 1`。
- 站点与 Python `debug.bp` 同意图。
- `STNP_BP_ON_NOTIFY` 在独占后**实际认领**路径打恰好一次。
- `PARSE_RESYNC` **禁止**打进 SOF 猎寻的 `continue` 循环。
- `STNP_Transport_Receive` 只拷贝字节；唯一允许的附加是 `STNP_BP_RX_COPY`（在 `g_rx_tail` 发布之后）。

## 6. 明确不在 0.9.1

| 项 | 说明 |
|---|---|
| 把 C 全局 `STNP_Notify_Callback` 改成可空函数指针 | 归 **0.9.2**。因此 C 独占只消除「模块已处理还再进全局」；空 USER CODE 对未认领 Notify 仍会进该函数 |
| C `STNP_UNKNOWN_NOTIFY` 上报 | 不做 |
| 日志、诊断信封、第三 SOF、`.stnp` options 新键 | 不做 |

## 附 A. 本批次的工程与工具链改造（非运行时语义）

与 §1–§6 的运行时语义无关，但属于 0.9.1 批次的交付范围；完整计划见 `.omo/plans/stnp-toolchain-resolve.md`。

**问题**（三症状一病根）：

- 硬编码维护者机器路径 **14 处 / 6 文件**：`scripts/test.ps1` ×5、`scripts/build_exe.ps1` ×5、`tests/test_resource_tracking.py` ×1、`examples/*/run.ps1` ×3；
- 工具链不可见时**静默跳过 19 处**（`gcc` 18 + `cmake` 1；`pytest.skip` 站点共 22）；
- MinGW `-pthread` 产物运行时缺 `libwinpthread-1.dll`（表现为 `3221225785` = `0xC0000139`）。
- 病根：解析逻辑**四份复制**，且每份都把机器路径当默认值。

**约定**：

- **解析顺序（全仓唯一，三级）**：环境变量（`STNP_PYTHON` / `STNP_MINGW_BIN` / `STNP_CMAKE_BIN`，可选覆盖；值不可用即报错、不回退）→ `PATH` 查找（取第一个命中并采用，其余候选全部列出）→ **明确失败 + 安装指引**。
- **形态**：一个**解析器**（`scripts/toolchain.ps1` + `tests/_toolchain.py`：一套顺序、两个薄实现 + 一致性测试）。**不引入**仓库内保存机器路径的配置文件。
- **入口必须全改**：`scripts/test.ps1`、`scripts/build_exe.ps1`、`examples/*/run.ps1` ×3、`conftest.py`、CI。
- **禁止静默**：找不到即报错；测试侧由 `-FailOnSkip` 把非预期跳过判红。
- **多命中全列出**：`PATH` 上若有多个候选，全部打印并标注采用哪一个；命中多个时**不做智能选择**。
- **最低可用性校验**：候选要能运行并通过最低检查（`gcc -dumpmachine` 可执行并给出三元组、`cmake --version` 可执行且不低于最低版本、python 版本符合 `requires-python` 且能 `import stnp_editor`）；校验不通过的候选不被采用，但**不做主机/交叉目标判断** —— 交叉或外来 gcc 会被采用并打印其三元组，是否合适由用户判断。
- **输出实际使用的工具**：每次运行打印 `工具 : <路径> (from <来源>, <版本/三元组>)`。
- **责任边界**：解析器只做"按顺序查找 + 可用性校验 + 来源打印"，**不保证命中的工具链与用户目标平台一致** —— 工具链由本机环境决定，**软件不保证其正确或匹配，请用户自行确认**；跨平台/交叉编译请在 `PATH` 前放好所需工具链，或用 `STNP_MINGW_BIN` 指定目录。此提示同时出现在脚本输出头部与 `docs/01_getting_started.md`「环境准备」。
- **DLL 兜底与根治**：测试夹具加 `-static`（全仓唯一 `-pthread` 编译点在 `tests/test_generate_multi.py:1965`）；运行时 PATH 前置降级为兜底。

**验收**：`grep -r -F 'E:\' scripts/ tests/ examples/` 命中 **0**；**无 `STNP_*` 且 `PATH` 上无工具链**时必须明确报错并给出安装指引（脚本 exit≠0）；**无 `STNP_*` 但 `PATH` 上有工具链**时两个测试口径 0 failed（skip 数 2 / 1）；同一工具多候选时全部列出并标注采用项；交叉/外来 gcc 置于 `PATH` 首位时**被采用并打印其三元组**，不做拒绝。

> 代价说明：不把机器路径写进仓库，换来的是"工具链需自己放进 `PATH`，或用 `STNP_*` 声明"（都没有则明确报错，绝不静默回退）。

## 附 B. 本页记录

- 内容来自 0.9.1 设计原稿（[archive/v0.9.1](../archive/v0.9.1/README.md)）与实现结论；2026-09-19 由编排者**按原内容重写版式**（技术事实未增删），并补入附 A。
- 相关现行文档：[03_json_format.md](../03_json_format.md) 的 DR 行、[04_api/c/notify.md](../04_api/c/notify.md)、[04_api/c/core.md](../04_api/c/core.md)、[04_api/c/module.md](../04_api/c/module.md)、[c_runtime.md](c_runtime.md)、[python_runtime.md](python_runtime.md)、[trace_and_breakpoints.md](../06_guides/trace_and_breakpoints.md)。
- 与冻结规范的关系：DR 的**管辖范围从未改变**（§8.3）；曾出现的「只门控 typed 认领」表述属实现偏离，已在实现与文档两侧纠正。

---

[← 冻结规范](spec_0.9.md) | [文档目录](../README.md) | [架构说明](README.md)
