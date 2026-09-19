# 9. 未来计划（TODO）

本页只收「尚未做、且打算做」的事项；`- [ ]` 表示未完成。已完成与历史变更见 [8. 变更记录](08_changelog.md)；永久不做的见冻结规范 §9.2，本页不重复。

## 1. 协议与设计层

- [ ] 定义 Task 与 Notify 的关联机制 —— 冻结规范 §10 的待定项；定义完成前 `SEQ` 只提供事务标识基础，协议不表达任何自动关联
- [ ] SEQ 超时重发
- [ ] 重复 Task 检测
- [ ] 重复执行防护
- [ ] 全局自动通知关闭字段
- [ ] payload 校验函数选项，以及编辑器的默认校验函数清单
- [ ] 编辑器侧工程内唯一 Result ID 管理
- [ ] 开放校验函数的用户代码区（归档决策 D21：本轮不开放，记为后续工作）
- [ ] stnp多开 option（例如 debug 是否启用）：既能在 `.stnp` 里快捷配置，也能运行期配置；等价于把「能力清单」显式列出来
- [ ] Python 生成代码后期抽象为统一配置的 class；C 端目前没有同等规模的功能增量

## 2. C 端 SDK、示例与调度模型

示例与 SDK：

- [ ] 示例写清两种形态并都补上：**裸机直跑**与 **UART 定时器分拍**
- [ ] C 端 SDK 三档并列且各自隔离，不互相借用、不把 UART 当公共底层：裸机 UART、定时器节拍 UART、RTOS UART
- [ ] 每个 SDK 写明具体支持面（例如 `rtos_uart_hal` 到底覆盖什么）
- [ ] 评估库 RING 是否加入优先级策略（priority 高的先取出），以及与 RTOS 能力是否冲突
- [ ] 补全 API 文档覆盖（当前可能不全）
- [ ] 提供可直接使用的完整 STM32 测试工程（当前 `examples/` 太少，C 端测试链路不便，后期补）

要写进官方文档的口径：

- [ ] **Handler 原则：立刻返回，但不是不能写业务** —— 业务可以是校验、改 PWM、记目标速度、启动一次运动；不要写等结果（`while`、`HAL_Delay`、死等到位）；启动后立刻 `return`，让后续 STOP / READ 能进 Dispatch；完成时再 `STNP_Notify_Send`
- [ ] **裸机 + 定时器不是 RTOS**（能力边界对照表）：
  - 慢动作进行中还能收别的命令：裸机 + 定时器可以，RTOS 可以；
  - Handler 里同步死等时还能干别的：裸机不行，RTOS 可以；
  - 真正抢占式多任务：裸机不行，RTOS 可以。
- [ ] **裸机 tick SDK 的合适形态**：TIM/SysTick 提供固定节拍（例如 1ms）；节拍 ISR 只置位或投递，不跑 Handler、不发 Notify；主循环为 `STNP_Process()` → `STNP_Dispatch()` → `STNP_Tick_Poll()`；Module 提供 `on_tick(elapsed_ms)` 做减速、超时与到位检测；完成时仍在主循环里 `STNP_Notify_Send`
- [ ] **不接管 SysTick 中断**（用户口径）：不改 `SysTick_Handler`、不占 TIM、不与 HAL 抢配置、ISR 里什么都不跑；主循环为 `Process` → `Dispatch` → `Tick_Poll(STNP_Tick_Now())`；Handler 启动动作、记下截止时间、立刻 return，`Tick_Poll` 到期再收尾
- [ ] 时间源优先用 `HAL_GetTick()`；若读 `SysTick->VAL` 做亚毫秒插值，必须处理 24 位倒计数回绕与 HAL 时基问题
- [ ] 写明结论：裸机可实现**协作式、按时间推进**的多任务（时间片思想，但由业务让出 CPU，不是 OS 抢占）；`Tick_Poll` 也在主循环里，Handler 阻塞则节拍照停；阻塞等待交给 RTOS



## 3. 测试与回归

- [ ] 回归测试分类整理并明确覆盖项：当前漏得多，需要给出明确清单
- [ ] **新增一份「测试项清单」文档** —— 不只列生成器的测试，还要覆盖**生成出来的代码逻辑各部分是否正常**（例如已发现：Notify 不是上报屏蔽《这是举例，这个问题已经修复了》）
- [ ] 立规矩：加一个功能就补对应测试，否则事后无法确认当初实现了什么
- [ ] C 端测试链路补齐（依赖 §2 那份可直接使用的 STM32 工程）
- [x] debug和断点验证清单 —— 0.9.1 已落地（C `STNP_DEBUG` 宏，Python `stnp.trace.debug` / `trace.format`）；站点与用法见 [链路验证](06_guides/trace_and_breakpoints.md)，不再单列待做



## 4. CLI 与配置管理

- [ ] **统一设计 CLI、运行开关与预编译管理功能的承载方式** —— 避免「什么功能都往同一处塞」导致混乱
- [ ] 预编译管理功能的方式定案：放在哪里、如何开启
- [ ] 为 CLI 变更补专属章节



## 5. 工程与工具链

**必须修的行为缺陷（实现偏离冻结规范，需回归）**

- [x] `notify_dispatch_receive`（DR）语义回归规范：DR 是「本端是否启用 Notify 接收分发路径」的**总门** —— 关闭时**模块 typed 认领路径与全局 fallback 都不投递**，C 与 Python 两端一致。依据：`05_architecture/spec_0.9.md:466-475`（§8.3）。
- [x] 「全局上报」并行问题：独占语义已落地。DR 关 → 全局也不收；DR 开且模块认领成功 → 全局不收；未认领 → 进全局。

**工具链与工程**

- [x] 清理硬编码本机绝对路径：14 处 / 6 文件已清零 —— 统一走 `scripts/toolchain.ps1`（`tests/_toolchain.py` 为同顺序的 Python 实现），入口见 [快速开始](01_getting_started.md)「环境准备」；`grep -r -F 'E:\' scripts/ tests/ examples/` 命中 0
- [x] 环境与路径硬编码改为**明确失败**：解析顺序为 `STNP_*` 环境变量（可选覆盖，值不可用即报错、不回退）-> `PATH`（取第一个命中并列出全部候选）-> 明确失败（带一行安装指引）；脚本缺 `gcc`/`cmake` 直接非 0 退出，pytest 侧的工具链 skip 不再匹配设计跳过名单，`-FailOnSkip` 判红
- [ ] 补一个「环境检查脚本」：绝对路径、编码、编译器可用性 —— 现有 `scripts/check_bundle_integrity.py` 与 `tests/test_resource_tracking.py` 都不是这类 lint
- [ ] 修冻结规范与 schema 的 2 处不一致：`global_results[].value` 上限（规范 `maximum 255` / schema `65535`）、`features.crc.enabled` 默认值（规范默认 `false` / schema 未写默认）
- [ ] 未来新增错误码时，替换 `E2113` / `E2103` 的临时复用码位
- [ ] 文档写明工具链需用户自备：仓库不捆绑编译器，最小 C 示例需要 `gcc` 与 `objcopy`



## 6. 打包与分发

- [ ] 真机冒烟远程安装：`pip install "git+https://github.com/stal-ink/STNP_Editor.git"`，确认模板被打进 wheel
- [ ] 验证 `pip install -r requirements-build.txt` 可跑通（当前 UNVERIFIED）
- [ ] 在第二台机器实测构建可复现性（当前 UNVERIFIED）
- [ ] 解释单文件 exe 与目录版体积差异（11,149,520 与 8,618,276 字节）
- [ ] 发布到 PyPI（当前 `stnp-editor` 不存在）
- [ ] 决定单文件 exe 默认运行的退出码 5 是否维持（现记录为 wontfix）



## 7. 遥远的未来再定

- [ ] `archive/` 文档与不宜公开的文档是否随仓库保留（当前归档已在库内）
- [ ] 大后期统一修文档措辞（当前仍有「§5 冻结文档」这类引用字迹）
- [ ] Python 侧考虑做成真正的软件库：生成的 Python 端代码是否提供两种用法，业务框架是否也生成 —— 需要专门想办法
- [ ] ID 分配：现状是用户手写，生成器只做碰撞与范围校验（E2105、E2115、E2118、E2120、E3004）；后期考虑自动分配、把 ID 权限收回，或提供「是否允许手动分配」的可选项 —— 若做，更适合 CLI 助手（如 `stnpe suggest-ids`），不必拉回 GUI
- [ ] golded后期需要改成详细的覆盖每一个点的测试
- [ ] 把所有脚本改成python脚本，变相跨平台了



## 8. 写作与实现注意（不作为 TODO）

- 生成协议代码不可手改；`User/` 脚手架只创建一次，重新生成不覆盖。
- `tests/golden/C/multi_demo/vectors.json` 是手写测试数据，不能当生成物删除；改模板必须同步重建 golden。
- 规范措辞不等于函数签名：签名以模板与 golden 为准（`<Module>_SetValidate` 携带 `cmd`）。
- 子进程退出码 `3221225785`（`0xC0000139` = STATUS_ENTRYPOINT_NOT_FOUND）多是 PATH / DLL 问题，不是代码回归：MinGW `-pthread` 链接的测试 exe 运行时需要 `libwinpthread`；并发夹具改用 `-static` 链接（该 DLL 依赖在链接期消失），`conftest.py` 另按共享解析器把解析到的 gcc 目录前置到 `PATH` 兜底，不写死盘符。

---

[← 变更记录](08_changelog.md) | [文档目录](README.md) | [归档登记表 →](archive/README.md)