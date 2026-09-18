/**
 ******************************************************************************
 * @file    motor.c
 * @brief   Generated Motor VTL metadata and dispatch implementation.
 ******************************************************************************
 */

#include "motor.h"
#include "../../Core/stnp_notify.h"
#include "../../Core/stnp_vtl.h"

static Motor_ValidateCallback g_validate_set_speed = STNP_NULL;
static STNP_EnableState g_notify_callback_enabled = STNP_DISABLE;

/* VTL metadata only: codec algorithm lives in Core/stnp_vtl.c. */
static const STNP_VTL_Field g_motor_task_set_speed_fields[] =
{
    { (STNP_U16)offsetof(Motor_SetSpeedPayload, speed), STNP_VTL_U16 },
    { (STNP_U16)offsetof(Motor_SetSpeedPayload, accel), STNP_VTL_U8 }
};

static const STNP_VTL_Field g_motor_task_hold_fields[] =
{
    { (STNP_U16)offsetof(Motor_HoldPayload, torque), STNP_VTL_U16 }
};

static const STNP_VTL_Desc g_motor_task_vtl[] =
{
    {
        MOTOR_CMD_SET_SPEED,
        3U,
        2U,
        g_motor_task_set_speed_fields
    },
    {
        MOTOR_CMD_HOLD,
        2U,
        1U,
        g_motor_task_hold_fields
    }
};

static const STNP_VTL_Desc g_motor_notify_vtl[] =
{
    {
        MOTOR_NOTIFY_DONE,
        0U,
        0U,
        STNP_NULL
    },
    {
        MOTOR_NOTIFY_FAULT,
        0U,
        0U,
        STNP_NULL
    }
};

void Motor_Init(MotorHandle *self, STNP_U8 id)
{
    if (self == STNP_NULL)
    {
        return;
    }
    self->base.id = id;
    self->base.ops = STNP_NULL;
}

void Motor_SetValidate(STNP_U8 cmd, Motor_ValidateCallback fn)
{
    switch (cmd)
    {
    case MOTOR_CMD_SET_SPEED:
        g_validate_set_speed = fn;
        break;
    default:
        break;
    }
}

void Motor_NotifyCallbackEnable(STNP_EnableState state)
{
    g_notify_callback_enabled = state;
}

STNP_Result Motor_OnTask(MotorHandle *self, STNP_U8 cmd, const STNP_U8 *payload, STNP_U8 len)
{
    const STNP_VTL_Desc *desc = STNP_VTL_Find(
        g_motor_task_vtl,
        (STNP_U16)(sizeof(g_motor_task_vtl) / sizeof(g_motor_task_vtl[0])),
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
    case MOTOR_CMD_SET_SPEED:
    {
        Motor_SetSpeedPayload typed_payload;
        Motor_Result vr;
        STNP_Result dr = STNP_VTL_Decode(desc, payload, len, &typed_payload);

        if (dr != STNP_OK)
        {
            return dr;
        }
        if (g_validate_set_speed != STNP_NULL)
        {
            vr = g_validate_set_speed(self, cmd, &typed_payload);
        }
        else
        {
            vr = Motor_ValidateGenerated(self, cmd, &typed_payload);
        }
        if (vr != MOTOR_OK)
        {
            return STNP_ERR_PARAM;
        }
        Motor_SetSpeed(self, &typed_payload);
        return STNP_OK;
    }
    case MOTOR_CMD_HOLD:
    {
        Motor_HoldPayload typed_payload;
        STNP_Result dr = STNP_VTL_Decode(desc, payload, len, &typed_payload);

        if (dr != STNP_OK)
        {
            return dr;
        }
        Motor_Hold(self, &typed_payload);
        return STNP_OK;
    }
    default:
        return STNP_ERR_COMMAND;
    }
}

static STNP_Result Motor_TaskHandler(STNP_ModuleHandle *base, STNP_U8 code, const STNP_U8 *payload, STNP_U16 length)
{
    if (length > 255U)
    {
        return STNP_ERR_LENGTH;
    }
    return Motor_OnTask((MotorHandle *)base, code, payload, (STNP_U8)length);
}

static const STNP_ModuleOps g_motor_module_ops =
{
    Motor_TaskHandler,
    g_motor_task_vtl,
    (STNP_U16)(sizeof(g_motor_task_vtl) / sizeof(g_motor_task_vtl[0])),
    g_motor_notify_vtl,
    (STNP_U16)(sizeof(g_motor_notify_vtl) / sizeof(g_motor_notify_vtl[0]))
};

STNP_ModuleHandle *Motor_AsModule(MotorHandle *self)
{
    if (self == STNP_NULL)
    {
        return STNP_NULL;
    }
    self->base.ops = &g_motor_module_ops;
    return &self->base;
}

STNP_WEAK void Motor_NotifyCallback(MotorHandle *self, STNP_U8 notify_code, Motor_Result result, const void *payload)
{
    STNP_UNUSED(self);
    STNP_UNUSED(notify_code);
    STNP_UNUSED(result);
    STNP_UNUSED(payload);
}

STNP_Result Motor_NotifyDispatch(MotorHandle *self, STNP_U8 notify_code, STNP_U16 result, const STNP_U8 *payload, STNP_U8 length)
{
    const STNP_VTL_Desc *desc = STNP_VTL_Find(
        g_motor_notify_vtl,
        (STNP_U16)(sizeof(g_motor_notify_vtl) / sizeof(g_motor_notify_vtl[0])),
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
    case MOTOR_NOTIFY_DONE:
    {
        STNP_Result dr = STNP_VTL_Decode(desc, payload, length, STNP_NULL);

        if (dr != STNP_OK)
        {
            return dr;
        }
        if (g_notify_callback_enabled == STNP_ENABLE)
        {
            Motor_NotifyCallback(self, notify_code, (Motor_Result)result, STNP_NULL);
        }
        return STNP_OK;
    }
    case MOTOR_NOTIFY_FAULT:
    {
        STNP_Result dr = STNP_VTL_Decode(desc, payload, length, STNP_NULL);

        if (dr != STNP_OK)
        {
            return dr;
        }
        if (g_notify_callback_enabled == STNP_ENABLE)
        {
            Motor_NotifyCallback(self, notify_code, (Motor_Result)result, STNP_NULL);
        }
        return STNP_OK;
    }
    default:
        return STNP_ERR_COMMAND;
    }
}

STNP_WEAK void Motor_SetSpeed(MotorHandle *self, const Motor_SetSpeedPayload *payload)
{
    STNP_UNUSED(self);
    STNP_UNUSED(payload);
}
STNP_WEAK void Motor_Hold(MotorHandle *self, const Motor_HoldPayload *payload)
{
    STNP_UNUSED(self);
    STNP_UNUSED(payload);
}
