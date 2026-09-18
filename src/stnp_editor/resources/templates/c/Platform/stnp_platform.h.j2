/**
 ******************************************************************************
 * @file    stnp_platform.h
 * @brief   STNP 平台基础类型与编译器适配。
 *
 * 本文件负责：
 *      - 固定宽度整数类型定义
 *      - 通用宏与 weak 适配
 *
 * 禁止在此加入 HAL / 驱动调用。
 *
 * Supported Toolchains (weak):
 *      - GNU Arm Embedded / gcc-arm-none-eabi：一等支持（含 warning 属性）
 *      - GCC / Clang（GNU 兼容链接）：支持
 *      - Keil AC5 / AC6、IAR：支持（__weak 关键字）
 *      - MSVC：不作嵌入式目标
 ******************************************************************************
 */

#ifndef __STNP_PLATFORM_H
#define __STNP_PLATFORM_H

#include <stdint.h>
#include "stnp_platform_config.h"

/* 共享类型在 stnp_types.h；此处只定义平台整数。 */

typedef uint8_t  STNP_U8;   /* 无符号8位类型 */
typedef uint16_t STNP_U16;  /* 无符号16位类型 */
typedef uint32_t STNP_U32;  /* 无符号32位类型 */
typedef int32_t  STNP_I32;  /* 有符号32位类型 */

#ifndef STNP_NULL
#define STNP_NULL ((void *)0)
#endif

#ifndef STNP_UNUSED
#define STNP_UNUSED(x) ((void)(x))
#endif

/* weak：Keil AC5（__CC_ARM）与 IAR 用 __weak；GNU 用属性；覆盖提示仅 GNU warning 属性有效 */
#if defined(__CC_ARM) || defined(__ICCARM__)
#define STNP_WEAK __weak
#define STNP_WEAK_WARN(msg)
#elif defined(__GNUC__)
#define STNP_WEAK __attribute__((weak))
#define STNP_WEAK_WARN(msg) __attribute__((warning(msg)))
#else
#define STNP_WEAK
#define STNP_WEAK_WARN(msg)
#endif

#endif /* __STNP_PLATFORM_H */
