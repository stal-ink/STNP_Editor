/**
 ******************************************************************************
 * @file    stnp_task.h
 * @brief   STNP unified Task send/receive API.
 ******************************************************************************
 */

#ifndef __STNP_TASK_H
#define __STNP_TASK_H

#include "stnp_core.h"

/* Main structured API. Payload is a generated typed Payload, or STNP_NULL. */
STNP_Result STNP_Task_Send(
    STNP_U8 target,
    STNP_U8 code,
    const void *payload
);

/* Internal implementation behind STNP_Task_SendBytes(). */
STNP_Result STNP_Task_SendBytes_Impl(
    STNP_U8 target,
    STNP_U8 code,
    const STNP_U8 *payload,
    STNP_U16 length
);

#if defined(__GNUC__) || defined(__clang__)
#define STNP__BYTE_ARRAY_POINTER_CHECK(payload) \
    ((void)sizeof(char[((__builtin_types_compatible_p(__typeof__(payload), STNP_U8 *) || \
                        __builtin_types_compatible_p(__typeof__(payload), const STNP_U8 *)) ? -1 : 1)]))
#else
#define STNP__BYTE_ARRAY_POINTER_CHECK(payload) ((void)0)
#endif

/* Raw-byte API. `payload` must be an array (or STNP_NULL); length is automatic. */
#define STNP_Task_SendBytes(target, code, payload) \
    (STNP__BYTE_ARRAY_POINTER_CHECK(payload), \
     STNP_Task_SendBytes_Impl( \
        (target), \
        (code), \
        (payload), \
        (STNP_U16)(((payload) == STNP_NULL) ? 0U : sizeof(payload))))

#endif /* __STNP_TASK_H */
