# stm32_hal_uart_c —— STM32 HAL UART SDK 集成示例（不在 PC 上运行）

## 覆盖什么

- C target + `c.build_system = cmake` + `sdks = ["stm32_hal_uart"]`；
- 协议内容是 3 个 Module / 4 个 Instance（`CHASSIS`/`MOTOR`/`SENSOR`，`ChassisMain`/`MotorMain`/`SensorFront`/`SensorRear`），
  用来展示 SDK 生成后一个有真实业务形状的工程长什么样；
- 生成 `SDK/STM32_HAL/stnp_hal_uart.{c,h}`：RX 用 `HAL_UARTEx_ReceiveToIdle_IT()`
  静态 ping-pong buffer，TX 用 `HAL_UART_Transmit_IT()` + 静态 FIFO，带 UART Error/ORE 自动恢复；
- 生成根目录 `CMakeLists.txt`，把生成代码做成独立 `stnp` 静态库 target。

本示例**没有提交任何 `.c`/`.h`**：SDK 由生成器产出、用户业务写在生成文件的 USER CODE 区域，
仓库里再放一份拷贝只会与生成物漂移。用法以本 README 的内联片段为准。

## 要配什么

`stnp.build.json` 关键字段：

```json
{
  "target": "c",
  "c": { "build_system": "cmake", "emit_examples": true },
  "sdks": ["stm32_hal_uart"]
}
```

CubeMX 侧：

- 选择/启用一个 UART（示例按 `huart1` 书写；`python` 端默认 115200 8N1，两边保持一致）；
- 打开该 UART 的全局中断（NVIC），`HAL_UARTEx_ReceiveToIdle_IT()` 依赖 RX 中断；
- 若 UART Error/ORE 需要自动恢复，保留 HAL 的 Error 回调链路（SDK 内部实现恢复）；
- 若工程里已有自己的 HAL callback，定义 `STNP_HAL_UART_USE_GLOBAL_CALLBACKS 0`，
  再转发 `STNP_HAL_UART_RxEventCallback()` / `STNP_HAL_UART_TxCpltCallback()` /
  `STNP_HAL_UART_ErrorCallback()`。

## 生成

```bash
stnpe generate examples/stm32_hal_uart_c/stm32_hal_uart.stnp examples/stm32_hal_uart_c/stnp.build.json -o _out
# 源码运行时等价：python main.py generate ...
```

生成目录：`_out/stm32_hal_uart_STNP_C/`。

或只生成、不编译：

```powershell
.\examples\stm32_hal_uart_c\run.ps1
```

## 把这段放进你 CubeMX 工程的 main.c

选择 `stm32_hal_uart` 后，公共 `stnp.h` 会导出 HAL UART API，无需单独添加 `SDK/STM32_HAL` include 路径：

```c
#include "stnp.h"

/* CubeMX 生成的 UART 初始化之后 */
MX_USART1_UART_Init();                 /* 你的 CubeMX 初始化代码 */
(void)STNP_HAL_UART_Init(&huart1);     /* 接管 RX/TX；同时完成 Core 传输绑定 */
(void)STNP_Instances_Init();

for (;;)
{
    (void)STNP_Process();              /* 最多推进 1 帧 */
    (void)STNP_Dispatch();             /* 最多执行 1 个 Job（Handler / Notify Callback） */
    App_Process();                     /* 你的业务 */
}
```

若同时选择 FreeRTOS：

```json
"sdks": ["stm32_hal_uart", "freertos"]
```

则仍只需 `(void)STNP_HAL_UART_Init(&huart1);`：官方 SDK 会自动创建静态 Protocol Task +
Worker Pool；**不要**再手工写 `STNP_Process()/STNP_Dispatch()` 调度循环，业务代码继续自由调用
`STNP_Task_Send()` / `STNP_Notify_Send()`。

CMake 工程顶层：

```cmake
add_subdirectory(cmake/stm32cubemx)   # 必须在前：提供 stm32cubemx target
add_subdirectory(<生成目录>)           # 即 _out/stm32_hal_uart_STNP_C
target_link_libraries(${CMAKE_PROJECT_NAME} stm32cubemx stnp)
```

## 生成物里会得到什么

```text
_out/stm32_hal_uart_STNP_C/
├─ CMakeLists.txt                 # 独立 stnp 静态库 target
├─ Core/ Module/ Instance/ Platform/
├─ Implementation/                # chassis_impl.c / motor_impl.c / sensor_impl.c / stnp_notify_callback.c
├─ SDK/STM32_HAL/stnp_hal_uart.h  # STNP_HAL_UART_Init / RxEvent / TxCplt / Error callback
├─ SDK/STM32_HAL/stnp_hal_uart.c
└─ README.md                      # 生成说明（本示例的展开版）
```

业务实现写在 `Implementation/<module>_impl.c` 的 `USER CODE` 区域，重新生成不会覆盖。

## 为什么没有提交 `.c`/`.h`，也不能在 PC 上跑

- SDK 文件、`main.c` 骨架与 CMakeLists 都由生成器按 `.stnp` + build 配置产出，手写副本只会与
  生成结果不一致；
- 生成代码依赖 `UART_HandleTypeDef`、`HAL_UARTEx_ReceiveToIdle_IT()` 等 STM32 HAL 符号和真实硬件；
  PC 上没有 CubeMX HAL，无法编译/运行，所以 `run.ps1` 只生成并打印下一步。
