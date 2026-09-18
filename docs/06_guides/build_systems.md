# CMake / MDK-ARM 构建集成

本页说明 `c.build_system` 取值、CubeMX + CMake 顶层写法，以及 CMake 与 MDK-ARM 之间切换时的 manifest 行为。

`stnp.build.json` 的 `c.build_system` 可选：

- `mdk_arm`：默认；不生成 `CMakeLists.txt`。
- `cmake`：生成 STNP 根目录 `CMakeLists.txt`，创建 `stnp` 静态库 target。

## CubeMX + CMake

CubeMX 顶层工程在创建 `stm32cubemx` target 后加入：

```cmake
add_subdirectory(cmake/stm32cubemx)
add_subdirectory(STNP)

target_link_libraries(${CMAKE_PROJECT_NAME}
    stm32cubemx
    stnp
)
```

`add_subdirectory(STNP)` 把 STNP 纳入同一构建图；应用链接 `stnp` 后，CMake 自动处理依赖，无需手工维护 STNP 源文件列表。

### 0.6.3 的链接边界

生成代码分成两个 link domain：

```text
Core / Module / Instance / SDK
        ↓
    libstnp.a

Implementation/*_impl.c
Implementation/stnp_notify_callback.c
        ↓
application objects
        ↓
      final ELF
```

具体实现使用 CMake `target_sources(stnp INTERFACE ...)`：这些用户实现文件不会归档进 `libstnp.a`，而会由链接 `stnp` 的应用 target 直接编译。因此用户 strong Handler/Callback 能稳定覆盖库内 weak fallback，不受静态库成员提取顺序影响。

生成的 CMake 还保持：

- `C_STANDARD 99` / `C_STANDARD_REQUIRED YES`，不使用 `target_compile_features(... c_std_99)`，适配部分 STM32CubeCLT 交叉工具链；
- 路径仅使用 `${CMAKE_CURRENT_LIST_DIR}`，不绑定 `${CMAKE_SOURCE_DIR}`；
- 选择 STM32 HAL UART / FreeRTOS SDK 时，通过 `stm32cubemx` target 继承 HAL/RTOS 依赖。

因此选择官方 STM32 HAL / FreeRTOS SDK 时，`add_subdirectory(STNP)` 要位于 `stm32cubemx` target 创建之后。

## CubeMX + MDK-ARM

MDK-ARM 模式继续由 CubeMX / Keil 管理工程源文件。0.6.3 命名为：

```text
Module/Motor/motor.c
Implementation/motor_impl.c
```

两者语义对应且 basename 不冲突。

## 公共 include

普通应用代码只需：

```c
#include "stnp.h"
```

CMake 的 `stnp` target 已公开 Core include 路径；`stnp.h` 会进一步包含生成的 Module/Instance 与已选择 SDK 的公共头。

## 切换构建系统

manifest 会管理生成的 `CMakeLists.txt`；CMake → MDK-ARM 时删除该生成文件。Implementation USER CODE merge 不受构建系统切换影响。

---

[← FreeRTOS](freertos.md) | [文档目录](../README.md) | [迁移指南 →](../07_migration.md)
