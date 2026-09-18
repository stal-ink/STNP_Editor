/**
 ******************************************************************************
 * @file    stnp_router.c
 * @brief   STNP instance routing and Core VTL metadata lookup.
 ******************************************************************************
 */

#include "stnp_router.h"
#include "stnp_vtl.h"
#include "stnp_runtime.h"

static STNP_ModuleHandle *g_instances[STNP_ROUTER_INSTANCE_MAX];
static STNP_U8 g_instance_count = 0U;

static STNP_ModuleHandle *STNP_Router_Find(STNP_U8 id)
{
    STNP_U8 i;

    for (i = 0U; i < g_instance_count; i++)
    {
        if ((g_instances[i] != STNP_NULL) && (g_instances[i]->id == id))
        {
            return g_instances[i];
        }
    }
    return STNP_NULL;
}

STNP_Result STNP_Router_Register(STNP_ModuleHandle *module)
{
    STNP_U8 i;

    if ((module == STNP_NULL) || (module->ops == STNP_NULL) ||
        (module->ops->task_handler == STNP_NULL))
    {
        return STNP_ERR_PARAM;
    }

    for (i = 0U; i < g_instance_count; i++)
    {
        if (g_instances[i] == module)
        {
            return STNP_OK;
        }
        if ((g_instances[i] != STNP_NULL) && (g_instances[i]->id == module->id))
        {
            return STNP_ERR_STATE;
        }
    }

    if (g_instance_count >= STNP_ROUTER_INSTANCE_MAX)
    {
        return STNP_ERR_STATE;
    }

    g_instances[g_instance_count] = module;
    g_instance_count++;
    return STNP_OK;
}

STNP_Result STNP_Router_ResolveTask(
    STNP_U8 target,
    STNP_U8 code,
    STNP_ModuleHandle **module)
{
    STNP_ModuleHandle *found;

    if (module == STNP_NULL)
    {
        return STNP_ERR_PARAM;
    }
    found = STNP_Router_Find(target);
    if (found == STNP_NULL)
    {
        return STNP_ERR_TARGET;
    }
    if (STNP_VTL_Find(found->ops->task_vtl, found->ops->task_vtl_count, code) == STNP_NULL)
    {
        return STNP_ERR_COMMAND;
    }
    *module = found;
    return STNP_OK;
}

STNP_Result STNP_Router_EncodeTask(
    STNP_U8 target,
    STNP_U8 code,
    const void *payload,
    STNP_U8 *raw,
    STNP_U8 *length)
{
    STNP_ModuleHandle *module = STNP_Router_Find(target);
    const STNP_VTL_Desc *desc;

    if (module == STNP_NULL)
    {
        return STNP_ERR_TARGET;
    }
    desc = STNP_VTL_Find(module->ops->task_vtl, module->ops->task_vtl_count, code);
    if (desc == STNP_NULL)
    {
        return STNP_ERR_COMMAND;
    }
    return STNP_VTL_Encode(desc, payload, raw, length);
}

STNP_Result STNP_Router_EncodeNotify(
    STNP_U8 source,
    STNP_U8 notify_code,
    const void *payload,
    STNP_U8 *raw,
    STNP_U8 *length)
{
    STNP_ModuleHandle *module = STNP_Router_Find(source);
    const STNP_VTL_Desc *desc;

    if (module == STNP_NULL)
    {
        return STNP_ERR_TARGET;
    }
    desc = STNP_VTL_Find(module->ops->notify_vtl, module->ops->notify_vtl_count, notify_code);
    if (desc == STNP_NULL)
    {
        return STNP_ERR_COMMAND;
    }
    return STNP_VTL_Encode(desc, payload, raw, length);
}
