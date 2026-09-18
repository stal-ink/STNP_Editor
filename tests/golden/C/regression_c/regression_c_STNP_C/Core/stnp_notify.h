/**
 ******************************************************************************
 * @file    stnp_notify.h
 * @brief   STNP unified Notify send/receive API.
 ******************************************************************************
 */

#ifndef __STNP_NOTIFY_H
#define __STNP_NOTIFY_H

#include "stnp_core.h"

/* Notify receive-dispatch runtime switch. The generated initial value comes from
 * protocol.options.notify_dispatch_receive.enabled and may be toggled at runtime. */
void STNP_NotifyDispatchReceive_Enable(void);
void STNP_NotifyDispatchReceive_Disable(void);
STNP_U8 STNP_NotifyDispatchReceive_IsEnabled(void);

/* Main structured API. Payload is a generated typed Payload, or STNP_NULL. */
STNP_Result STNP_Notify_Send(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const void *payload
);

/* Internal implementation behind STNP_Notify_SendBytes(). */
STNP_Result STNP_Notify_SendBytes_Impl(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U16 length
);

#ifndef STNP__BYTE_ARRAY_POINTER_CHECK
#if defined(__GNUC__) || defined(__clang__)
#define STNP__BYTE_ARRAY_POINTER_CHECK(payload) \
    ((void)sizeof(char[((__builtin_types_compatible_p(__typeof__(payload), STNP_U8 *) || \
                        __builtin_types_compatible_p(__typeof__(payload), const STNP_U8 *)) ? -1 : 1)]))
#else
#define STNP__BYTE_ARRAY_POINTER_CHECK(payload) ((void)0)
#endif
#endif

/* Raw-byte API. `payload` must be an array (or STNP_NULL); length is automatic. */
#define STNP_Notify_SendBytes(source, notify_code, result, payload) \
    (STNP__BYTE_ARRAY_POINTER_CHECK(payload), \
     STNP_Notify_SendBytes_Impl( \
        (source), \
        (notify_code), \
        (result), \
        (payload), \
        (STNP_U16)(((payload) == STNP_NULL) ? 0U : sizeof(payload))))

STNP_Result STNP_Notify_Dispatch(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length
);
void STNP_Notify_Callback(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length
);

#endif /* __STNP_NOTIFY_H */
