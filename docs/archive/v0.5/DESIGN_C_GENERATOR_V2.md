# STNP C Generator Architecture Design Specification

> **ARCHIVE / 历史资料：** 本文可能与当前 0.5.0 修复版冲突；当前规范请从 [`docs/README.md`](../README.md) 进入。


版本：V1.0

------------------------------------------------------------------------

# 1. 文档目的

本文档定义 STNP 协议生成器 C 端输出规范。

目标：

-   一个协议定义生成多语言代码。
-   C端不依赖 HAL、RTOS、标准库之外的额外组件。
-   协议层和业务层严格分离。
-   支持主从模式。
-   支持 Module 多实例。
-   支持 Task / Notify。
-   支持自动生成接口和用户实现框架。

------------------------------------------------------------------------

# 2. 总体架构

                     STNP Definition
                            |
                            v
                           IR
                            |
            +---------------+---------------+
            |                               |
            v                               v

        C Generator                  Python Generator

            |
            v

         STNP_C

    Application

        |
        v

    Implementation

        |
        v

    Instance

        |
        v

    Module

        |
        v

    Core

        |
        v

    Platform

------------------------------------------------------------------------

# 3. C工程目录规范

    STNP_C/

    ├── README.md
    ├── STNP_DESIGN.md

    ├── Platform/
    │
    │   ├── stnp_platform.h
    │   │       # 基础类型、编译器适配
    │   │
    │   └── stnp_platform_config.h
    │           # 用户配置


    ├── Core/
    │
    │   ├── stnp.h
    │   │       # 用户唯一include入口
    │
    │   ├── stnp_core.h
    │   ├── stnp_core.c
    │   │       # STNP核心初始化
    │
    │   ├── stnp_frame.h
    │   ├── stnp_frame.c
    │   │       # 帧解析、组包
    │
    │   ├── stnp_task.h
    │   ├── stnp_task.c
    │   │       # Task协议处理
    │
    │   ├── stnp_notify.h
    │   ├── stnp_notify.c
    │   │       # Notify协议处理
    │
    │   ├── stnp_router.h
    │   ├── stnp_router.c
    │   │       # TARGET/SOURCE路由
    │
    │   ├── stnp_codec.h
    │   └── stnp_codec.c
    │           # Payload编解码


    ├── Module/

    │   ├── stnp_module.h
    │   ├── stnp_module.c

    │   └── Chassis/
    │
    │       ├── chassis.h
    │       └── chassis.c


    ├── Instance/

    │   ├── stnp_instances.h
    │   └── stnp_instances.c


    ├── Implementation/

    │   └── chassis.c


    └── Examples/

        ├── main.c
        └── transport_mock.c

------------------------------------------------------------------------

# 4. 注释规范

生成代码采用 HAL 风格。

## 4.1 文件头

``` c
/**
 ******************************************************************************
 * @file    stnp_task.c
 * @brief   STNP Task协议处理实现。
 *
 * 本文件负责：
 *      - Task帧解析
 *      - Task路由调用
 *      - Task发送接口
 *
 * 用户禁止修改协议代码。
 ******************************************************************************
 */
```

## 4.2 枚举

必须同行注释。

正确：

``` c
typedef enum
{
    STNP_OK          = 0x0000U, /* 操作成功 */
    STNP_ERR_LENGTH  = 0x0001U, /* 数据长度错误 */
    STNP_ERR_TARGET  = 0x0002U, /* 目标不存在 */
    STNP_ERR_COMMAND = 0x0003U  /* 命令不存在 */

} STNP_Result;
```

禁止：

``` c
/**
 * 错误长度
 */
STNP_ERR_LENGTH;
```

------------------------------------------------------------------------

# 5. Platform层设计

Platform只负责：

-   类型
-   编译器
-   基础宏

示例：

``` c
#ifndef STNP_PLATFORM_H
#define STNP_PLATFORM_H


#include <stdint.h>


typedef uint8_t  STNP_U8;   /* 无符号8位类型 */
typedef uint16_t STNP_U16;  /* 无符号16位类型 */
typedef uint32_t STNP_U32;  /* 无符号32位类型 */


#endif
```

禁止加入：

``` c
HAL_UART_Transmit()

CAN_Send()

GPIO_Write()
```

------------------------------------------------------------------------

# 6. Frame设计

## 6.1 Task Frame

    +--------+
    | Header |
    +--------+
    | SEQ    |
    +--------+
    |TARGET  |
    +--------+
    | CODE   |
    +--------+
    | LENGTH |
    +--------+
    |PAYLOAD |
    +--------+

## 6.2 Notify Frame

固定：

    0x33

结构：

    HEADER
    SOURCE
    EVENT
    RESULT
    LENGTH
    PAYLOAD

------------------------------------------------------------------------

# 7. Task设计

Task属于Core。

流程：

    Byte Stream

        |

    Frame Parser

        |

    Task Decoder

        |

    Router

        |

    Module

        |

    Implementation

Task接口：

``` c
/**
 ******************************************************************************
 * @brief 接收Task数据。
 *
 * @param data    接收缓存。
 * @param length  数据长度。
 *
 * @retval STNP_OK           成功。
 * @retval STNP_ERR_LENGTH   长度错误。
 ******************************************************************************
 */
STNP_Result STNP_Task_Receive(
    const STNP_U8 *data,
    STNP_U16 length);
```

------------------------------------------------------------------------

# 8. Module设计

Module不是协议层。

Module负责：

-   Command
-   Payload解析
-   Ops调用

示例：

``` c
typedef struct
{
    void (*move)(
        ChassisHandle *,
        STNP_U8,
        STNP_U8);

} ChassisOps;
```

------------------------------------------------------------------------

# 9. Command Table设计

不推荐：

``` c
if(code==1)
{

}
else if(code==2)
{

}
```

推荐：

``` c
typedef struct
{
    STNP_U8 command;

    STNP_U16 length;

    STNP_Result (*handler)(
        const STNP_U8 *);

} STNP_CommandEntry;
```

示例：

``` c
static const STNP_CommandEntry g_commands[] =
{

    {
        CHASSIS_CMD_MOVE,
        2U,
        Chassis_ParseMove
    },

    {
        CHASSIS_CMD_STOP,
        0U,
        Chassis_ParseStop
    }

};
```

------------------------------------------------------------------------

# 10. Instance设计

Module模板：

    Motor
     |
     +-- Motor1 ID 0x10
     |
     +-- Motor2 ID 0x11

实例：

``` c
typedef struct
{

    STNP_U8 id;

    void *context;

    const STNP_ModuleOps *ops;


} STNP_ModuleHandle;
```

------------------------------------------------------------------------

# 11. C语言模拟OOP

C没有class。

使用：

    结构体
    +
    函数指针

示例：

``` c
struct ChassisHandle
{

    STNP_ModuleHandle base;


    const ChassisOps *ops;


    void *context;

};
```

调用：

``` c
self->ops->move(
    self,
    direction,
    speed);
```

------------------------------------------------------------------------

# 12. Notify设计

Notify用于：

-   状态变化
-   故障
-   完成事件

示例：

``` c
STNP_Notify_Send(
    CHASSIS_ID,
    CHASSIS_EVENT_DONE,
    STNP_OK,
    payload,
    length);
```

------------------------------------------------------------------------

# 13. 用户代码隔离

生成：

``` c
void Chassis_Move(...)
{

    /* USER CODE BEGIN Chassis_Move */


    /* 用户填写 */


    /* USER CODE END Chassis_Move */

}
```

重新生成：

保留 USER CODE。

------------------------------------------------------------------------

# 14. 返回码设计

Core：

``` c
STNP_Result
```

Module：

``` c
Chassis_Result
Motor_Result
Lift_Result
```

示例：

``` c
typedef enum
{

    CHASSIS_OK = 0,

    CHASSIS_ERR_BUSY,

    CHASSIS_ERR_LIMIT


} Chassis_Result;
```

------------------------------------------------------------------------

# 15. Generator规则

Generator生成：

-   类型
-   ID
-   Frame
-   Parser
-   Router
-   Module接口
-   Instance

用户维护：

-   控制算法
-   硬件调用
-   业务逻辑

------------------------------------------------------------------------

# 16. 设计原则总结

1.  Task/Notify属于Core。
2.  Router统一管理通信分发。
3.  Module不处理帧。
4.  Instance实现多实例。
5.  Implementation隔离用户代码。
6.  所有生成代码可重复生成。
7.  不允许生成器覆盖用户逻辑。
