/**
 ******************************************************************************
 * @file    stnp_unknown.h
 * @brief   STNP unknown-frame callback（两道闸，默认关）。
 *
 * 不是日志，不自动打印、不自动重传。用户回调异常由调用方自行处理。
 ******************************************************************************
 */

#ifndef __STNP_UNKNOWN_H
#define __STNP_UNKNOWN_H

#include "stnp_core.h"
#include "../Platform/stnp_types.h"

#ifndef STNP_UNKNOWN_REPORT_SOF
#define STNP_UNKNOWN_REPORT_SOF 0
#endif

typedef enum {
    STNP_UNKNOWN_SOF    = 0x01U, /* 仅当 STNP_UNKNOWN_REPORT_SOF=1 才上报 */
    STNP_UNKNOWN_LEN    = 0x02U,
    STNP_UNKNOWN_CRC    = 0x03U, /* CRC 或 Frame_Parse* 结构失败 */
    STNP_UNKNOWN_TASK   = 0x04U, /* 完整 Task 帧，Router 不可路由 */
    STNP_UNKNOWN_NOTIFY = 0x05U  /* 枚举保留；C 0.9.1 禁止触发 */
} STNP_UnknownReason;

typedef void (*STNP_UnknownFrameFn)(
    STNP_UnknownReason reason,
    const STNP_U8 *data,   /* 禁止持有指针出函数；需要则当场拷贝 */
    STNP_U16 length
);

void STNP_UnknownFrame_SetCallback(STNP_UnknownFrameFn fn); /* NULL = 清除 */
void STNP_UnknownFrameCallback_Enable(STNP_EnableState state); /* 默认 STNP_DISABLE */
STNP_U8 STNP_UnknownFrameCallback_IsEnabled(void);

/* Core 内部；用户禁止依赖。data==NULL 且 length>0 时禁止调用用户 fn。 */
void STNP_UnknownFrame_Report(
    STNP_UnknownReason reason,
    const STNP_U8 *data,
    STNP_U16 length
);

#endif /* __STNP_UNKNOWN_H */
