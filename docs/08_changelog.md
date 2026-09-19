# 8. 变更记录

## 0.9.1 — Notify 独占与运行时诊断

材料：`docs/archive/v0.9.1/`（01–05）、现行 `docs/05_architecture/spec_0.9.1.md`。Wire 十槽与 `.stnp` options 键不变。

### 破坏性变更

- Notify 接收由「全局 + 模块并行」改为 **module XOR global**：模块认领后全局不再收同一帧。
- `notify_dispatch_receive` 仍是冻结规范 §8.3 的整条接收分发总门（关闭时模块与全局都不投递）。0.9.1 不改该管辖范围。
- Python 全局 `@stnp.on_notify` 不再收到 dataclass / `NotificationDescriptor`，只剩两种 raw 形。
- Python 未知 target/cmd 不再 `raise ProtocolError` 计入 `callback_errors`；两闸都开时走 unknown `task`。

### 新增

- 未知 / 不可路由帧：同一回调 + 使能，两道闸默认关；SOF 另有第二开关默认关。C `STNP_UNKNOWN_NOTIFY` 枚举保留但 **不触发**。
- Python `stnp.trace.debug` + `stnp.trace.format`（`config/trace.yaml`，`stnp.init()` → `trace.load()`）；payload `to_display()`。
- C 预编译 `STNP_DEBUG` 0/1 断点宏（`STNP_BP_*`），只验证链路；golden 按 0 生成。
- C `<Module>_NotifyCallbackIsEnabled`；Python SOF 猎寻改为逐字节滑动。

### 明确不做（本版本）

- C 全局 `STNP_Notify_Callback` 可空函数指针（留给 0.9.2）。
- 日志子系统、`STNP_LOGx`、`on_log`、第三 SOF、`.stnp` options 新键。

## 0.9.0 — 配置拆分、统一报错与单目标生成

材料交叉核对：`git log --oneline --reverse 0af4fa9..dca406d`（22 个提交）、`docs/archive/v0.9/0.9_规格变更清单.md`、冻结规范 `docs/05_architecture/spec_0.9.md`。

### 破坏性变更

- 工程拆成两份文件：`.stnp` 只承载协议定义，生成配置独立为 `stnp.build.json`；根对象 `additionalProperties: false`，读到旧字段即失败（`664561f`）。
- 生成目标改为顶层单数字段 `target`（`c` / `python`），不再接受复数 `targets`。
- `.stnp` 的 `schema_version` 改为字符串；`global_results` 必填，工程级 `OK` 必须为 `0x0000`。
- Module Return Code 按模块分段（第 n 个启用模块占用 `0x(n+1)00..0x(n+1)FF`）。
- GUI 及全部 GUI 专用字段移除；命令行可执行文件名为 `stnpe`。
- 删除单实例便捷宏（如 `<MODULE>_ID`），实例寻址统一 `STNP_INSTANCE_<INSTANCE>_ID`。
- 删除 `notifications[].kind`、`features.notify_dispatcher`、`features.crc.runtime_toggle`、`generation` 内嵌块、`handler_mode`、`groups`。

### 新增

- 统一报错机制：错误码按 E1/E2/E3/E4/E9 分段，诊断为编译器风格，退出码 `0/1/2/3`（`664561f`）。
- Notify 接收分发运行时 API：C 端 `STNP_NotifyDispatchReceive_Enable/Disable/IsEnabled`，Python 端 `stnp.notify_dispatch_receive_*`（`664561f`）。
- 按模块生成的校验函数：C 的 `<Module>_ValidateGenerated`，Python 的 `validate_<module>`（用户 `@...validate` 可覆盖）。
- CLI `-list` 文件清单，以及 `version` / 帮助自述（`664561f`、`dca406d`）。

### 修复

- 构建脚本不再污染调用方 `PATH`（`63602dd`）。
- 测试运行器可找到 venv 旁的解释器 / `stnpe`（`268b0bb`）。
- 回归夹具不再借用其他工程名（`8624bfd`）。
- 跳过提示只打印实际生效项（`8c7fbe0`、`0f1e8fa`）。
- 示例运行器的 Python 解析与测试运行器一致（`b46d90a`）。

### 工程与打包

- 包结构重排（`src/stnp_editor/emit/**` 等）（`cb75bde`）。
- 单文件 exe 打包与完整性校验（`cb75bde`、`ee8e357`）。
- 版本号单一来源（`677e627`）。
- CI 与测试自动化、golden 独立夹具化（`cb75bde`、`29e1e4d`、`1d8488c`）。
- 内部规划文档移出索引（`0b2358a`、`f5119c4`）。

### 文档与示例

- `examples/` 重建为三个可运行工程（`759fd09`）。
- 生成 README 模板中文化（`851d742`）。
- 仓库首页与 CLI 文案对齐（`80fa02b`、`dca406d`）。

## 0.8.2 — Optional Auto Notify

- 保持 0.8.1 的平级 Module Tree 与“返回码 / 命令 / 通知”Tab 布局，不改 Tree 层级。
- “启用自动通知”放在 Module 的“命令”Tab 内容顶部；关闭时隐藏 ACCEPT / REJECT / DONE 配置，开启时展开。
- C 端使用 Module 级 AutoNotify Descriptor 表 + 通用 lookup/send helper；不生成每 Command Wrapper。
- Python 端自动通知全部由 `.validate` / `.func` decorator wrapper 完成，Runtime dispatch 不直接发送自动通知。
- 自动通知仅允许零 Payload Notify；默认关闭，旧工程行为保持不变。

## 0.8.1 — GUI 布局调整与 Python 文档整理

证据：`15c83f9`（`ver0.8.1 GUI布局修改`）、`702c0e9`（`优化python端文档`）。

- GUI：集合表格、属性面板、工程树与 i18n 布局调整；保持 0.8.0 的平级 Module Tree 与 Tab 组织。
- Python 文档：补齐 Python API、使用指南、UART SDK、运行时架构与快速开始中的 Python 路径说明。

## 0.8.0 — Python Target

- Split examples and golden regression fixtures by language: `examples/C`, `examples/python`, `tests/golden/C`, `tests/golden/python`.
- Added a full Python generated-output golden fixture and regression test.

- 工程树去掉 Command / Notification / Return Code / Common Type / Instance 的单项展开，改为在属性面板用表格添加、删除和编辑；模块页用 Tab 组织返回码、命令与通知。
- Generation Target 改为 C/Python 单选下拉，并按语言显示独立配置面板。
- 新增 Python emitter，生成统一 `stnp.core / stnp.sdk / stnp.protocol` 命名空间。
- Python Module/Instance 分离，支持多 Instance 共享 Module 协议定义。
- 新增 `@Module.cmd.CMD.func`、`@Instance.cmd.CMD.func`、校验函数与 Notify callback 装饰器。
- 初始化时检查缺失 CMD 实现并提示受影响 Module/Command/Instance。
- 新增 `stnp.task(instance, cmd, ...)`、`stnp.task.<Instance>.<CMD>(...)` 与 TaskSet 多帧发送；TaskSet 合并为一次 transport write。
- Python Runtime 使用 caller-thread TX + RX thread + Dispatch thread，并隔离 callback 异常。
- 新增 CRC16-Modbus、stream resync、运行统计。
- 新增 `stnp.sdk.uart`：先校验 `pyserial` distribution，再导入 `serial`；支持 YAML 默认值、串口自动扫描和用户覆盖端口/波特率。
- 协议 YAML、Runtime YAML、UART YAML 分离。
- Python Example 与用户脚手架独立可选；用户脚手架 create-once，重新生成永不覆盖/删除。
- 新增独立 Python demo：握手、两个 Module、多 Instance、MockSerial、TaskSet、校验函数/notify callback。
- C 端生成结构、Deferred Runtime、HAL/FreeRTOS SDK 与 USER CODE merge 保持兼容。

## 0.7.1 — Angular GUI Controls

- GUI 改为直角、细线、微斜切控件语言：按钮、输入框、下拉、Tab、GroupBox、表格、Tree 与 Live Preview 卡片取消圆角。
- 启动时使用 Fusion 样式，避免 Windows 原生圆角盖住 QSS。
- 输入控件为 inset 斜切，按钮为 raised 斜切；Generate 主按钮使用内侧双线直角块。
- 补齐布尔字段（如校验 Hook）直角复选框描边与选中填充，避免 QSS 只设尺寸导致指示器不绘制。
- 配色沿用 0.7.0；Deferred Runtime、wire format、Task/Notify API、`.stnp` 与 SDK 行为不变。

## 0.7.0 — GUI Live Preview & Editing UX

- GUI 新增常驻 Live Preview：编辑 Common Type/Enum、Module Command/Notification/Return Code、Instance 与协议固定字段时，可实时查看关键生成形态。
- Instance 的 `module` 字段改为当前工程 Modules 动态下拉选择，避免手输模块名造成拼写/引用错误。
- 新建 Instance 默认绑定当前工程第一个已有 Module。
- 更新 GUI 整体样式，包括 Tree、Tab、属性编辑器、预览卡片、按钮与输入控件。
- 新增 `STNP_Notify_Send()` 调试打点指南：用于无调试器环境下验证代码执行路径；明确其不依赖 RX/Process/Dispatch 链，但依赖 TX transport。
- 新增 Debug Trace 宏 TODO 文档；0.7.0 不实现该宏、不改变 Runtime/API。
- Deferred Runtime、wire format、Task/Notify API 与 SDK 协议行为不变。

## 0.6.3 — Link-Safe CMake & Unified Public Header

- 修复 CMake 静态库中 weak fallback 可能遮蔽同一 archive 内 strong `Implementation` Handler/Callback 的问题。
- `Implementation/*_impl.c` 与 `stnp_notify_callback.c` 改为 CMake `INTERFACE_SOURCES`，由应用 target 直接编译，不进入 `libstnp.a`。
- Module 框架源统一为 `Module/<Module>/<module>.c`；用户实现统一为 `Implementation/<module>_impl.c`，继续保证 Keil `.c` basename 唯一。
- 重新生成 manifest-owned 0.6.2 输出时，自动迁移旧 `Implementation/<module>.c` 并保留 USER CODE。
- 扩展现有 `Core/stnp.h` 为应用唯一推荐 include 入口：同时暴露生成的 Module/Instance 与已选择官方 SDK 公共 API。
- 文档示例移除容易误解为 STNP API 的 `App_Process()` 占位函数。
- Deferred Runtime、Task/Notify 发送语义、FreeRTOS Worker 模型不变。

## 0.6.2 — CubeCLT CMake Compatibility

- 修复 STM32CubeCLT / Arm GNU 交叉工具链下 `target_compile_features(stnp PUBLIC c_std_99)` 可能报 `no known features for C compiler` 的配置失败。
- 生成的 `STNP/CMakeLists.txt` 改用 target `C_STANDARD 99`、`C_STANDARD_REQUIRED YES`、`C_EXTENSIONS OFF` 属性。
- 新增 CMake 回归场景：显式清空 `CMAKE_C_COMPILE_FEATURES` 后仍可 configure/build `stm32cubemx → stnp → application`。
- Runtime、Task/Notify API、HAL UART SDK、FreeRTOS Worker 模型均不改变。

## 0.6.1 — Build Integration

- 新增 `generation.build_system`：`mdk_arm` / `cmake`。
- 旧 `.stnp` 缺省按 `mdk_arm` 处理，不改变既有输出。
- CMake 模式生成根 `CMakeLists.txt`，创建独立 `stnp` 静态库 target。
- CMake 源路径全部基于 `${CMAKE_CURRENT_LIST_DIR}`，不绑定宿主 `${CMAKE_SOURCE_DIR}`。
- STM32 HAL / FreeRTOS SDK 在 CMake 模式通过已存在的 `stm32cubemx` target 获取外部依赖。
- 从 CMake 切回 MDK-ARM 时，manifest 自动清理由生成器拥有的 `CMakeLists.txt`。
- GUI 新增 Build System 单选；默认 MDK-ARM。
- 新增真实 CMake configure/build 自动测试，覆盖 `stm32cubemx → stnp → application ELF` 依赖链。
- Runtime、Task/Notify API、FreeRTOS Worker 模型均不改变。

## 0.6.0 — Deferred Runtime

- `STNP_Transport_Receive()` 改为只复制 bytes 到静态 RX Ring，不再 Parse/Router/执行用户 Handler。
- 新增 `STNP_Process()`：单次最多推进一个完整 Frame，完成 Parse/CRC/Router 并生成 Job。
- 新增 `STNP_Dispatch()`：单次最多执行一个可运行 Job。
- 新增静态 Job runtime；Payload 入队时完整复制，不保存 RX buffer 指针。
- RX Ring / Job Queue 满统一返回 `STNP_ERR_BUFFER`；旧数据/Job 不覆盖；Job 满时完整 Frame 保留等待重试。
- CRC bad-frame resync 继续保持单字节滑动恢复。
- 多 Worker 调度语义确定为：不同 Instance/source 可并发，同一 Instance/source 串行。
- Handler/Notify Callback 始终在 runtime lock 外执行。
- `STNP_Task_Send()` / `STNP_Notify_Send()` 继续保持自由调用；Core 仍无 RTOS/HAL/malloc 依赖。
- 收敛旧接收/直派入口：不再公开 `STNP_Task_Receive()`、`STNP_Notify_Receive()`、`STNP_Router_Task()`；接收统一走 `Transport_Receive → Process → Dispatch`。
- Task SEQ 在 Transport 前以 runtime lock 原子保留；并发发送安全，底层发送失败时允许产生 SEQ 空洞。
- STM32 HAL UART SDK 的 RX IRQ 路径改为静态 ping-pong re-arm + RX Ring copy，避免新字节覆盖已完成 buffer；TX IT FIFO 与 Error Recovery 保持。
- STM32 HAL TX FIFO 满返回 `STNP_ERR_BUFFER`；新增 `STNP_HAL_UART_GetRxStatus()` 读取最近 RX Ring 结果。
- 新增可选 `freertos` 官方 SDK：静态 Protocol Task + Worker Pool，默认 4 Worker，使用 `xTaskCreateStatic()`。
- 同时选择 `stm32_hal_uart` + `freertos` 时，用户仍只需 `STNP_HAL_UART_Init(&huartX)`；SDK 自动启动调度并从 RX IRQ 唤醒 Protocol Task。
- PC Mock 不再隐藏架构：只 loopback bytes，不自动调用 Process/Dispatch。
- 示例、测试、Golden、README、API/架构/迁移/SDK 文档同步更新。
- 产品版本升级为 0.6.0。

## 0.5.0 — 当前修复版补强

- Module 框架源文件由 `<module>.c` 改为 `<module>_module.c`，避免 Keil MDK 与 `Implementation/<module>.c` 产生同名对象覆盖。
- 生成器新增大小写不敏感的 `.c` basename 全局唯一性检查。
- `emit_examples` 默认值改为 `false`；PC Mock 示例改为显式 opt-in。
- 新增可选官方 SDK 生成层与 GUI 多选下拉；当前提供 `stm32_hal_uart`，默认不勾选。
- STM32 HAL UART SDK 生成 `SDK/STM32_HAL/stnp_hal_uart.h/.c`，用户初始化 UART/NVIC 后只需 `STNP_HAL_UART_Init(&huartX)`。
- STM32 HAL UART SDK 升级为高频友好的非阻塞实现：Receive-to-Idle 先重挂 RX，TX 使用 `HAL_UART_Transmit_IT()` + 固定 FIFO，并增加 UART Error/ORE 接收恢复。

本 docs 对应的 0.5.0 修复基线额外包含逻辑与安全修复；未另行提升产品版本号：

- Generated C Symbol Registry 扩展到 Runtime、Common Type、Module、Payload、Instance 等命名空间；
- `EnableState` 等 Runtime 类型/宏冲突在生成前拒绝；
- Task / Notify VTL table count 使用 `STNP_U16`，完整支持 256 个 code；
- 多实例 Module 不再生成含糊的 `<MODULE>_ID`；
- `output_stem`、Embedded path、生成路径 containment 与 symlink 防护加强；
- Base64 Embedded 内容严格校验；
- 请求 Python 或 C+Python 时明确拒绝，避免 partial generation；
- CRC/结构错误的 stream resync 改为单字节滑动，避免吞掉嵌套有效帧；
- Router 拒绝 Instance ID 0；
- CLI golden check 正确比较 binary Embedded 文件。
- 生成的 PC `TransportMock` 改为内部自动回环，业务 Demo 不再手动 `GetLast + STNP_Transport_Receive`；
- Mock 使用内部 FIFO，避免 Handler/Callback 再发送时递归进入 RX；
- 早期 STM32 HAL UART 薄适配示例升级为可选官方 SDK，并保留使用指南；
- 根 `README.md` 重写为项目总入口，并与当前 0.5 修复行为对齐。
- `Implementation/*.c` 统一增加 `Includes` / `Private` / 函数体三类 USER CODE 保留区，便于安全加入 `stdio.h`、HAL、RTOS 和私有实现依赖。
- 用户业务实现统一只包含 `Instance/stnp_instances.h`；该头汇总 `Core/stnp.h`、所有 Module 声明和实例 ID，使任意业务函数/Raw Notify callback 可直接跨 Module、跨实例调用 `STNP_Task_Send()` / `STNP_Notify_Send()`。

## 0.5.0 — Payload 表格化与 GUI 编辑能力

- Command / Notification Payload fields 改为 inline table；
- Return Codes 改为 Module-level table；
- 修复 Tree 删除后的无效 list path；
- Generation Targets 改为 C / Python multi-select；
- Python target 仅预留配置，Generator 尚未实现；
- 保留中英文 GUI 与 HEX 显示行为。

## 0.4.0 — 中英切换与语义 HEX 编辑

- 增加简体中文 / English 运行时切换；
- GUI label 与稳定 JSON key 分离；
- 未知未来字段继续保留；
- SOF、SEQ reserved、Command / Notify code、Return Code、common enum 增加语义 HEX editor；
- `.stnp` 存储仍为 JSON integer。

## 0.3.0 — PySide6 GUI 与 Schema 编辑器

- 增加 PySide6 GUI 入口；
- 增加 raw `ProjectDocument`；
- Schema-driven Tree / Property editor / Protocol JSON / Full JSON；
- Protocol JSON import/export；
- CLI 与 GUI 共用 Core/IR/Generator；
- 支持只有 Return Codes、无 Commands/Notifications 的 Module。

## 0.2.0 — 架构收敛

- Task / Notify 统一 STNP structured send；
- Raw byte array 使用 SendBytes；
- VTL Encode/Decode 进入 Core；
- Module 只生成 VTL metadata；
- 删除 Module/Instance send wrapper；
- 校验函数收敛到 `Module_SetValidate(cmd, fn)`；
- Notify callback 收敛到每 Module 一个；
- 删除 Context；
- ACK / handshake 明确归业务层。

---

[← 迁移指南](07_migration.md) | [文档目录](README.md) | [未来计划 →](09_future_plan.md)
