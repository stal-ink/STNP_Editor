/**
 ******************************************************************************
 * @file    chassis.c
 * @brief   Generated Chassis VTL metadata and dispatch implementation.
 ******************************************************************************
 */

#include "chassis.h"
#include "../../Core/stnp_notify.h"
#include "../../Core/stnp_vtl.h"

static Chassis_ValidateCallback g_validate_move = STNP_NULL;
static STNP_EnableState g_notify_callback_enabled = STNP_DISABLE;

/* VTL metadata only: codec algorithm lives in Core/stnp_vtl.c. */
static const STNP_VTL_Field g_chassis_task_move_fields[] =
{
    { (STNP_U16)offsetof(Chassis_MovePayload, direction), STNP_VTL_U8 },
    { (STNP_U16)offsetof(Chassis_MovePayload, speed), STNP_VTL_U8 }
};

static const STNP_VTL_Desc g_chassis_task_vtl[] =
{
    {
        CHASSIS_CMD_MOVE,
        2U,
        2U,
        g_chassis_task_move_fields
    },
    {
        CHASSIS_CMD_STOP,
        0U,
        0U,
        STNP_NULL
    }
};

static const STNP_VTL_Desc g_chassis_notify_vtl[] =
{
    {
        CHASSIS_NOTIFY_DONE,
        0U,
        0U,
        STNP_NULL
    },
    {
        CHASSIS_NOTIFY_TASK_ACCEPTED,
        0U,
        0U,
        STNP_NULL
    },
    {
        CHASSIS_NOTIFY_TASK_REJECTED,
        0U,
        0U,
        STNP_NULL
    }
};

void Chassis_Init(ChassisHandle *self, STNP_U8 id)
{
    if (self == STNP_NULL)
    {
        return;
    }
    self->base.id = id;
    self->base.ops = STNP_NULL;
}

void Chassis_SetValidate(STNP_U8 cmd, Chassis_ValidateCallback fn)
{
    switch (cmd)
    {
    case CHASSIS_CMD_MOVE:
        g_validate_move = fn;
        break;
    default:
        break;
    }
}

void Chassis_NotifyCallbackEnable(STNP_EnableState state)
{
    g_notify_callback_enabled = state;
}

STNP_Result Chassis_OnTask(ChassisHandle *self, STNP_U8 cmd, const STNP_U8 *payload, STNP_U8 len)
{
    const STNP_VTL_Desc *desc = STNP_VTL_Find(
        g_chassis_task_vtl,
        (STNP_U16)(sizeof(g_chassis_task_vtl) / sizeof(g_chassis_task_vtl[0])),
        cmd
    );
    if (self == STNP_NULL)
    {
        return STNP_ERR_PARAM;
    }
    if (desc == STNP_NULL)
    {
        return STNP_ERR_COMMAND;
    }
    switch (cmd)
    {
    case CHASSIS_CMD_MOVE:
    {
        Chassis_MovePayload typed_payload;
        Chassis_Result vr;
        STNP_Result dr = STNP_VTL_Decode(desc, payload, len, &typed_payload);

        if (dr != STNP_OK)
        {
            return dr;
        }
        if (g_validate_move != STNP_NULL)
        {
            vr = g_validate_move(self, cmd, &typed_payload);
        }
        else
        {
            vr = Chassis_ValidateGenerated(self, cmd, &typed_payload);
        }
        if (vr != CHASSIS_OK)
        {
            return STNP_ERR_PARAM;
        }
        Chassis_Move(self, &typed_payload);
        return STNP_OK;
    }
    case CHASSIS_CMD_STOP:
    {
        STNP_Result dr = STNP_VTL_Decode(desc, payload, len, STNP_NULL);

        if (dr != STNP_OK)
        {
            return dr;
        }
        Chassis_Stop(self);
        return STNP_OK;
    }
    default:
        return STNP_ERR_COMMAND;
    }
}

static STNP_Result Chassis_TaskHandler(STNP_ModuleHandle *base, STNP_U8 code, const STNP_U8 *payload, STNP_U16 length)
{
    if (length > 255U)
    {
        return STNP_ERR_LENGTH;
    }
    return Chassis_OnTask((ChassisHandle *)base, code, payload, (STNP_U8)length);
}

static const STNP_ModuleOps g_chassis_module_ops =
{
    Chassis_TaskHandler,
    g_chassis_task_vtl,
    (STNP_U16)(sizeof(g_chassis_task_vtl) / sizeof(g_chassis_task_vtl[0])),
    g_chassis_notify_vtl,
    (STNP_U16)(sizeof(g_chassis_notify_vtl) / sizeof(g_chassis_notify_vtl[0]))
};

STNP_ModuleHandle *Chassis_AsModule(ChassisHandle *self)
{
    if (self == STNP_NULL)
    {
        return STNP_NULL;
    }
    self->base.ops = &g_chassis_module_ops;
    return &self->base;
}

STNP_WEAK void Chassis_NotifyCallback(ChassisHandle *self, STNP_U8 notify_code, Chassis_Result result, const void *payload)
{
    STNP_UNUSED(self);
    STNP_UNUSED(notify_code);
    STNP_UNUSED(result);
    STNP_UNUSED(payload);
}

STNP_Result Chassis_NotifyDispatch(ChassisHandle *self, STNP_U8 notify_code, STNP_U16 result, const STNP_U8 *payload, STNP_U8 length)
{
    const STNP_VTL_Desc *desc = STNP_VTL_Find(
        g_chassis_notify_vtl,
        (STNP_U16)(sizeof(g_chassis_notify_vtl) / sizeof(g_chassis_notify_vtl[0])),
        notify_code
    );

    if (self == STNP_NULL)
    {
        return STNP_ERR_PARAM;
    }
    if (desc == STNP_NULL)
    {
        return STNP_ERR_COMMAND;
    }
    switch (notify_code)
    {
    case CHASSIS_NOTIFY_DONE:
    {
        STNP_Result dr = STNP_VTL_Decode(desc, payload, length, STNP_NULL);

        if (dr != STNP_OK)
        {
            return dr;
        }
        if (g_notify_callback_enabled == STNP_ENABLE)
        {
            Chassis_NotifyCallback(self, notify_code, (Chassis_Result)result, STNP_NULL);
        }
        return STNP_OK;
    }
    case CHASSIS_NOTIFY_TASK_ACCEPTED:
    {
        STNP_Result dr = STNP_VTL_Decode(desc, payload, length, STNP_NULL);

        if (dr != STNP_OK)
        {
            return dr;
        }
        if (g_notify_callback_enabled == STNP_ENABLE)
        {
            Chassis_NotifyCallback(self, notify_code, (Chassis_Result)result, STNP_NULL);
        }
        return STNP_OK;
    }
    case CHASSIS_NOTIFY_TASK_REJECTED:
    {
        STNP_Result dr = STNP_VTL_Decode(desc, payload, length, STNP_NULL);

        if (dr != STNP_OK)
        {
            return dr;
        }
        if (g_notify_callback_enabled == STNP_ENABLE)
        {
            Chassis_NotifyCallback(self, notify_code, (Chassis_Result)result, STNP_NULL);
        }
        return STNP_OK;
    }
    default:
        return STNP_ERR_COMMAND;
    }
}

STNP_WEAK void Chassis_Move(ChassisHandle *self, const Chassis_MovePayload *payload)
{
    STNP_UNUSED(self);
    STNP_UNUSED(payload);
}
STNP_WEAK void Chassis_Stop(ChassisHandle *self)
{
    STNP_UNUSED(self);
}
