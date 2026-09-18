/**
 ******************************************************************************
 * @file    stnp_module.h
 * @brief   STNP Module routing and VTL metadata.
 ******************************************************************************
 */

#ifndef __STNP_MODULE_H
#define __STNP_MODULE_H

#include "../Core/stnp_core.h"
#include "../Core/stnp_vtl.h"
#include "../Platform/stnp_types.h"

typedef struct STNP_ModuleHandle STNP_ModuleHandle;

typedef struct
{
    STNP_Result (*task_handler)(
        STNP_ModuleHandle *self,
        STNP_U8 code,
        const STNP_U8 *payload,
        STNP_U16 length
    );
    const STNP_VTL_Desc *task_vtl;
    STNP_U16 task_vtl_count;
    const STNP_VTL_Desc *notify_vtl;
    STNP_U16 notify_vtl_count;
} STNP_ModuleOps;

struct STNP_ModuleHandle
{
    STNP_U8 id;
    const STNP_ModuleOps *ops;
};

#endif /* __STNP_MODULE_H */
