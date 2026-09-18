# 7. 迁移指南

本页给从 0.8.2 迁到 0.9 的工程维护者：先看破坏性四点与对照表，再按清单改文件并用 `stnpe generate` / `check` 校验。更早版本的记录仅作追溯。

## 7.1 0.8.2 → 0.9：破坏性重构

0.9 是一次**破坏性重构**，不提供任何过渡路径：

- **无兼容层**：不读取旧工程、旧配置、旧字段。
- **无 shim**：不提供垫片、别名转发或双写桥接。
- **无弃用告警**：不输出「字段已弃用」「请改用某某」一类提示；旧用法直接失败。
- **`additionalProperties: false` 直接拒绝旧格式**：两份配置文件读到旧字段即校验失败。

### 旧 → 新对照

| 旧形态（0.8.2） | 0.9 处置 |
|---|---|
| `.stnp` 内的 `generation` | 迁出为独立 `stnp.build.json`；`.stnp` 只保留协议定义 |
| 复数 `targets` 与双套目标形态 | 整体删除；只认 build 顶层单一必填 `target`（`c` / `python`） |
| `modules[].handler_mode` | 删除；出现即校验失败 |
| `.stnp` 的 `groups` | 删除；出现即校验失败 |
| `notifications[].kind` | 删除；通知不再分类，接受 / 拒绝语义由 `RESULT` 槽承载 |
| `features.notify_dispatcher` | 删除；语义迁为 `options.notify_dispatch_receive.enabled`（本端行为，允许运行时切换） |
| `features.crc.runtime_toggle` | 删除；CRC 槽存在性只由 `features.crc.enabled` 决定 |
| 单实例便捷宏 | 删除；统一使用实例 ID 宏 |
| Return Code 取值 | 按分段重排：`0x0000` 工程级 `OK`；`0x0001..0x00FF` Global；`0x0100 + 256*i` 起每 Module 256 值 |
| 整数 `schema_version` | 改为 string，取值 `"stnp-schema-alpha"` |
| 根必填 `generation` | 改为 `global_results`（`minItems 1`） |
| CLI `stnpe generate <project> -o <out>`（单文件） | `stnpe generate <project.stnp> <stnp.build.json> -o <out> [-list]` |
| CLI `check <project> --golden <root>` | `stnpe check <project.stnp> <stnp.build.json> --golden <root>` |

### 迁移步骤

1. 把 `.stnp` 内的 `generation` 子树移出为同目录的 `stnp.build.json`，其顶层 `target` 取原 `generation.target`；复数 `targets` 只保留一个目标作为 `target`。
2. `.stnp` 根：删除 `generation`，新增 `global_results`（至少一条，且含名为 `OK`、值为 `0x0000` 的条目）；`schema_version` 改为字符串 `"stnp-schema-alpha"`。
3. 删除 `groups`、`modules[].handler_mode`、`notifications[].kind`。
4. 删除 `features.notify_dispatcher`，改用 `protocol.options.notify_dispatch_receive.enabled`。
5. 删除 `features.crc.runtime_toggle`。
6. 按分段重排各 Module 的 Return Code 取值，保证每 Module 的 `OK` 落在本 Module 区间。
7. 更新调用脚本为两文件命令行。

旧形式（0.8.2）：

```json
{
  "generation": {
    "target": "c",
    "c": {"build_system": "mdk_arm", "sdks": ["stm32_hal_uart"], "emit_examples": false}
  }
}
```

新形式（0.9，独立 `stnp.build.json`）：

```json
{
  "format": "stnp-build",
  "build_schema_version": "stnp-build-schema-alpha",
  "target": "c",
  "c": {"build_system": "mdk_arm", "emit_examples": false},
  "sdks": ["stm32_hal_uart"]
}
```

## 7.2 历史迁移记录

> 以下为 0.9 之前各版本的迁移记录，仅作追溯。

### 7.2.1 0.7.1 → 0.8.0：Python Target 与单目标配置

C Runtime/API 无变化。0.8.0 起 `.stnp` 使用单目标生成配置：

```json
"generation": {
  "target": "c",
  "c": {"build_system": "mdk_arm", "sdks": [], "emit_examples": false},
  "python": {"build_system": "python", "sdks": [], "emit_examples": false, "emit_user_scaffold": false}
}
```

Python 是独立生成目标，不与 C 同时输出。Python 用户业务不使用 `Implementation/`/USER CODE 区，而通过装饰器注册；可选 `User/` scaffold 仅首次创建，后续不受生成器管理。

配置文件分离为协议、Runtime、SDK 三个所有权域，详见 [Python API](04_api/python/README.md)。

### 7.2.2 0.7.0 → 0.7.1：GUI 控件外观

Runtime、Task/Notify API、`.stnp` 字段与 SDK 无变化。0.7.1 只把 GUI 从圆角扁平改为直角微斜切控件语言，配色沿用 0.7.0。

### 7.2.3 0.6.2 → 0.6.3：CMake 链接域与文件命名

Runtime/API 无行为变化。重新生成时：

```text
Module/<Module>/<module>_module.c  → Module/<Module>/<module>.c
Implementation/<module>.c        → Implementation/<module>_impl.c
```

对 manifest-owned 的旧 Implementation 文件，生成器会先改名再执行 USER CODE merge，不丢用户区域。

CMake 模式下，Implementation 不再进入 `libstnp.a`，而通过 `INTERFACE_SOURCES` 直接编译进应用 target，修复 weak/strong 静态库成员提取问题。顶层工程仍保持：

```cmake
add_subdirectory(cmake/stm32cubemx)
add_subdirectory(STNP)
target_link_libraries(${CMAKE_PROJECT_NAME} stm32cubemx stnp)
```

应用 include 推荐统一改为：

```c
#include "stnp.h"
```

选择 STM32 HAL UART / FreeRTOS SDK 后，无需再单独 include `SDK/...` 公共头。

### 7.2.4 0.6.1 → 0.6.2：CubeCLT CMake 工具链适配

Runtime、业务 API 和 `.stnp` 字段无变化。重新使用 0.6.2 生成 CMake 模式输出即可。

0.6.1 生成的：

```cmake
target_compile_features(stnp PUBLIC c_std_99)
```

在部分 STM32CubeCLT 交叉工具链中可能因为 CMake 未得到 `CMAKE_C_COMPILE_FEATURES` 而配置失败。0.6.2 改为：

```cmake
set_target_properties(stnp PROPERTIES
    C_STANDARD 99
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS OFF
)
```

如果只想临时修现有已生成工程，也可以直接按上面方式替换 `STNP/CMakeLists.txt` 中对应一行。

---

## 7.3 0.6.0 → 0.6.1：Build Integration

Runtime 与业务 API 无变化。旧工程没有 `generation.build_system` 时按：

```json
"build_system": "mdk_arm"
```

需要 CubeMX CMake 集成时改为：

```json
"build_system": "cmake"
```

重新生成后会出现 `CMakeLists.txt`。宿主工程按 [CMake / MDK-ARM 构建集成](06_guides/build_systems.md) 使用 `add_subdirectory(STNP)` + `target_link_libraries(... stnp)`。

---

## 7.4 0.5.x → 0.6.0：Deferred Runtime

这是行为级 breaking change。

旧代码：

```c
STNP_Transport_Receive(frame, len);
/* Handler 可能已经执行 */
```

0.6.0：

```c
STNP_Transport_Receive(frame, len); /* 只入 RX Ring */
STNP_Process();                    /* Parse/Router/Job */
STNP_Dispatch();                   /* Handler/Callback */
```

裸机主循环应加入：

```c
for (;;)
{
    STNP_Process();
    STNP_Dispatch();
    /* Application code */
}
```

如果选择 `stm32_hal_uart` + `freertos` 官方 SDK，则普通用户无需添加上述循环；`STNP_HAL_UART_Init()` 自动建立 Protocol Task + Worker Pool。

发送 API 不迁移：

```c
STNP_Task_Send(...);
STNP_Notify_Send(...);
```

继续可在业务代码中自由调用。

旧 PC Mock/测试如果依赖“Send/Receive 后 Handler 立即发生”，必须显式 Process + Dispatch。

0.6.0 同时移除不再需要的直接接收/直派公开入口：`STNP_Task_Receive()`、`STNP_Notify_Receive()`、`STNP_Router_Task()`。自定义 Transport 应统一调用 `STNP_Transport_Receive()`。

Task SEQ 现在在进入 Transport 前原子保留；底层发送失败时允许留下 SEQ 空洞，以保证多个 Worker 并发发送不会重复分配同一个 SEQ。

新 overload 错误：

```c
STNP_ERR_BUFFER
```

用于 RX Ring、Job Queue，以及官方 HAL TX FIFO 满。

---

## 7.5 历史 API 收敛

### 命名统一

历史概念：

```text
Request / Event
```

当前统一为：

```text
Payload
```

Task 侧 generated 名称以 Command 为唯一锚点：

```text
MODULE + COMMAND
→ Module_CommandPayload
→ Module_Command()
```

### 发送 API

历史设计中的 per-Module / per-Command send wrapper 已删除。

当前：

```c
STNP_Task_Send(...);
STNP_Notify_Send(...);

STNP_Task_SendBytes(...);
STNP_Notify_SendBytes(...);
```

### Codec

历史 per-command Pack/Decode 不再生成。

当前：

```text
Module 生成 VTL metadata
Core 提供 STNP_VTL_Encode / STNP_VTL_Decode
```

### Context

历史 `Module_SetContext`、Handle context 字段和 Instance Context API 已删除。

### 校验函数

当前由生成器按模块生成一个校验函数，内部按命令码分派；`validate_hook=true` 的 Command 进入校验。

### Notify callback

当前每个 Module 一个 Notify callback，不生成 per-notify callback setter。

### ACK / Handshake

Core 仍不维护 ACK / DONE 状态机，也不把 Task 与 Notify 作为协议原语强绑定。

0.8.2 增加可选的生成层自动通知：Module 的 `auto_notify_enabled=false` 时 `notify_on_*` 只是触发时机元数据；开启后由 C Module dispatch 元数据表或 Python decorator wrapper 执行 ACCEPT / REJECT / DONE。该行为不进入 Core。

### 多实例 ID

统一使用：

```c
STNP_INSTANCE_<INSTANCE>_ID
```

旧的单实例便捷宏在 0.9 已删除。

---

[← 使用指南](06_guides/README.md) | [文档目录](README.md) | [下一章：变更记录 →](08_changelog.md)
