# USER CODE 与重新生成

本页说明 C 用户代码区如何在重新生成时保留，以及 manifest / symlink / Embedded 边界。实现取证于 `src/stnp_editor/emit/c/merge.py` 与 `emit/manifest.py`。

业务实现主要放在：

```text
Implementation/<module>_impl.c
Implementation/stnp_notify_callback.c
```

生成器重新执行时，会读取已有文件并合并保留标记区域中的用户内容。

## Implementation 文件结构

每个用户业务 `.c` 文件统一提供三类保留区：

```c
#include "../Instance/stnp_instances.h"

/* USER CODE BEGIN Includes */
#include <stdio.h>
#include "main.h"
/* USER CODE END Includes */

/* USER CODE BEGIN Private */
static STNP_U8 g_led_state = 0U;
/* USER CODE END Private */

void Led_Turn(LedHandle *self)
{
    /* USER CODE BEGIN Led_Turn */
    STNP_UNUSED(self);
    printf("LED turn\r\n");
    /* USER CODE END Led_Turn */
}
```

- `stnp_instances.h`：由生成器自动包含；它提供所有 Module 声明、实例 ID，以及 `STNP_Task_Send()` / `STNP_Notify_Send()` 公共发送 API。
- `Includes`：只放用户自己的业务或平台依赖，例如 `stdio.h`、STM32 HAL、RTOS 头文件；
- `Private`：私有宏、静态变量、静态函数等实现细节；
- 函数名区域：具体 Command 业务实现。

合并正则同时识别 `USER CODE` 与 `USER DESC`。新模板里仍存在的 id 保留旧块全文；旧文件有、新模板没有的块追加到文件末尾：

```c
/* USER ORPHAN BEGIN */
/* USER CODE BEGIN DeletedCmd */
...
/* USER CODE END DeletedCmd */
/* USER ORPHAN END */
```

用户业务 `.c` 不需要再手动包含 Module 头或 Core 发送头。不要为了在 `.c` 中使用 `printf()`、HAL 或 RTOS API 而把这些实现依赖加入生成的 Module `.h`。公共头文件只包含其 API 声明真正需要的依赖。

## 推荐原则

- `Core/`、`Module/`、`Instance/`、`Platform/` 视为生成文件；
- 业务依赖写入 `Includes`，私有实现写入 `Private`，业务逻辑写入对应函数 USER CODE 区域；
- 不要在生成文件中做无法通过 merge 保存的手改；
- 删除 Module / Command 后先检查 orphan Implementation，再决定是否人工删除。

## Manifest cleanup

`.stnp-manifest.json`（version 1）记录生成器管理的相对路径与 `kind`。重新生成时会清理不再需要的 generated 文件；`kind == "implementation"` 的用户实现不直接删除，而是移到 orphan 目录。清单损坏上报 warning（E4011）并忽略，不阻断本次生成。

当前实现还会拒绝通过 symlink 将生成路径或 manifest 清理路径导向输出根目录之外。`.c` 基名大小写不敏感全局唯一（Keil-safe）；冲突在写出前以 E4007 拒绝。

## Embedded

`embedded_files` 不参与 USER CODE merge，按配置写入 `Embedded/`。二进制使用严格 Base64 解码（失败为 E4012）。路径必须落在输出树内，生成器拒绝 symlink 逃逸。

---

[← CRC 与流式接收](crc_and_stream.md) | [文档目录](../README.md) | [STM32 HAL UART →](stm32_hal_uart.md)
