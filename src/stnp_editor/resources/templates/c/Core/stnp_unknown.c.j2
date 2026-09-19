/**
 ******************************************************************************
 * @file    stnp_unknown.c
 * @brief   STNP unknown-frame 两道闸：函数指针默认 NULL，使能默认关。
 ******************************************************************************
 */

#include "stnp_unknown.h"

static STNP_UnknownFrameFn g_unknown_fn = STNP_NULL;
static STNP_EnableState g_unknown_enabled = STNP_DISABLE;

void STNP_UnknownFrame_SetCallback(STNP_UnknownFrameFn fn)
{
    g_unknown_fn = fn;
}

void STNP_UnknownFrameCallback_Enable(STNP_EnableState state)
{
    g_unknown_enabled = state;
}

STNP_U8 STNP_UnknownFrameCallback_IsEnabled(void)
{
    return (STNP_U8)(g_unknown_enabled == STNP_ENABLE);
}

void STNP_UnknownFrame_Report(
    STNP_UnknownReason reason,
    const STNP_U8 *data,
    STNP_U16 length)
{
    if ((g_unknown_fn == STNP_NULL) || (STNP_UnknownFrameCallback_IsEnabled() == 0U))
    {
        return;
    }
    if ((data == STNP_NULL) && (length > 0U))
    {
        return;
    }
    g_unknown_fn(reason, data, length);
}
