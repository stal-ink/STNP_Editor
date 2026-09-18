/**
 ******************************************************************************
 * @file    stnp_runtime.h
 * @brief   STNP internal deferred-dispatch runtime.
 *
 * Internal header used by Core and official SDK adapters. Application code
 * should use stnp.h / stnp_core.h instead.
 ******************************************************************************
 */

#ifndef __STNP_RUNTIME_H
#define __STNP_RUNTIME_H

#include "stnp_core.h"
#include "../Module/stnp_module.h"

typedef enum
{
    STNP_RUNTIME_JOB_TASK = 0U,
    STNP_RUNTIME_JOB_NOTIFY = 1U
} STNP_RuntimeJobType;

STNP_Result STNP_Runtime_Init(void);
STNP_Result STNP_Runtime_EnqueueTask(
    STNP_U8 target,
    STNP_U8 code,
    const STNP_U8 *payload,
    STNP_U8 length
);
STNP_Result STNP_Runtime_EnqueueNotify(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length
);
STNP_Result STNP_Runtime_DispatchOne(void);

/* Internal short critical-section hooks. The Core defaults are no-op because
 * bare-metal dispatch is single-consumer. An RTOS SDK may override these weak
 * hooks so multiple worker tasks can safely claim jobs concurrently. */
STNP_U32 STNP_Runtime_Lock(void);
void STNP_Runtime_Unlock(STNP_U32 state);

/* Internal router resolve step: validates target/code before a Task becomes a
 * queued job, and snapshots the stable generated module handle. */
STNP_Result STNP_Router_ResolveTask(
    STNP_U8 target,
    STNP_U8 code,
    STNP_ModuleHandle **module
);

#endif /* __STNP_RUNTIME_H */
