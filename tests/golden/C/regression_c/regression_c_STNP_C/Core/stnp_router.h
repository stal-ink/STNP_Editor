/**
 ******************************************************************************
 * @file    stnp_router.h
 * @brief   STNP instance routing and VTL metadata lookup.
 ******************************************************************************
 */

#ifndef __STNP_ROUTER_H
#define __STNP_ROUTER_H

#include "stnp_core.h"
#include "../Module/stnp_module.h"

STNP_Result STNP_Router_Register(STNP_ModuleHandle *module);

STNP_Result STNP_Router_EncodeTask(
    STNP_U8 target,
    STNP_U8 code,
    const void *payload,
    STNP_U8 *raw,
    STNP_U8 *length
);

STNP_Result STNP_Router_EncodeNotify(
    STNP_U8 source,
    STNP_U8 notify_code,
    const void *payload,
    STNP_U8 *raw,
    STNP_U8 *length
);

#endif /* __STNP_ROUTER_H */
