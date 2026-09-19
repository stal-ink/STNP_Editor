/**
 ******************************************************************************
 * @file    sensor.c
 * @brief   Generated Sensor VTL metadata and dispatch implementation.
 ******************************************************************************
 */

#include "sensor.h"
#include "../../Core/stnp_notify.h"
#include "../../Core/stnp_debug.h"
#include "../../Core/stnp_vtl.h"

static Sensor_ValidateCallback g_validate_calibrate = STNP_NULL;
static STNP_EnableState g_notify_callback_enabled = STNP_DISABLE;

/* VTL metadata only: codec algorithm lives in Core/stnp_vtl.c. */
static const STNP_VTL_Field g_sensor_task_calibrate_fields[] =
{
    { (STNP_U16)offsetof(Sensor_CalibratePayload, offset), STNP_VTL_I32 },
    { (STNP_U16)offsetof(Sensor_CalibratePayload, gain), STNP_VTL_U16 }
};

static const STNP_VTL_Desc g_sensor_task_vtl[] =
{
    {
        SENSOR_CMD_READ,
        0U,
        0U,
        STNP_NULL
    },
    {
        SENSOR_CMD_CALIBRATE,
        6U,
        2U,
        g_sensor_task_calibrate_fields
    }
};

static const STNP_VTL_Field g_sensor_notify_data_fields[] =
{
    { (STNP_U16)offsetof(Sensor_DataPayload, value), STNP_VTL_U16 }
};

static const STNP_VTL_Desc g_sensor_notify_vtl[] =
{
    {
        SENSOR_NOTIFY_DATA,
        2U,
        1U,
        g_sensor_notify_data_fields
    },
    {
        SENSOR_NOTIFY_DONE,
        0U,
        0U,
        STNP_NULL
    }
};

void Sensor_Init(SensorHandle *self, STNP_U8 id)
{
    if (self == STNP_NULL)
    {
        return;
    }
    self->base.id = id;
    self->base.ops = STNP_NULL;
}

void Sensor_SetValidate(STNP_U8 cmd, Sensor_ValidateCallback fn)
{
    switch (cmd)
    {
    case SENSOR_CMD_CALIBRATE:
        g_validate_calibrate = fn;
        break;
    default:
        break;
    }
}

void Sensor_NotifyCallbackEnable(STNP_EnableState state)
{
    g_notify_callback_enabled = state;
}

STNP_U8 Sensor_NotifyCallbackIsEnabled(void)
{
    return (STNP_U8)(g_notify_callback_enabled == STNP_ENABLE);
}

STNP_Result Sensor_OnTask(SensorHandle *self, STNP_U8 cmd, const STNP_U8 *payload, STNP_U8 len)
{
    const STNP_VTL_Desc *desc = STNP_VTL_Find(
        g_sensor_task_vtl,
        (STNP_U16)(sizeof(g_sensor_task_vtl) / sizeof(g_sensor_task_vtl[0])),
        cmd
    );
    if (self == STNP_NULL)
    {
        return STNP_ERR_PARAM;
    }
    STNP_BP_ON_TASK();
    if (desc == STNP_NULL)
    {
        return STNP_ERR_COMMAND;
    }
    switch (cmd)
    {
    case SENSOR_CMD_READ:
    {
        STNP_Result dr = STNP_VTL_Decode(desc, payload, len, STNP_NULL);

        if (dr != STNP_OK)
        {
            return dr;
        }
        Sensor_Read(self);
        return STNP_OK;
    }
    case SENSOR_CMD_CALIBRATE:
    {
        Sensor_CalibratePayload typed_payload;
        Sensor_Result vr;
        STNP_Result dr = STNP_VTL_Decode(desc, payload, len, &typed_payload);

        if (dr != STNP_OK)
        {
            return dr;
        }
        if (g_validate_calibrate != STNP_NULL)
        {
            vr = g_validate_calibrate(self, cmd, &typed_payload);
        }
        else
        {
            vr = Sensor_ValidateGenerated(self, cmd, &typed_payload);
        }
        if (vr != SENSOR_OK)
        {
            return STNP_ERR_PARAM;
        }
        Sensor_Calibrate(self, &typed_payload);
        return STNP_OK;
    }
    default:
        return STNP_ERR_COMMAND;
    }
}

static STNP_Result Sensor_TaskHandler(STNP_ModuleHandle *base, STNP_U8 code, const STNP_U8 *payload, STNP_U16 length)
{
    if (length > 255U)
    {
        return STNP_ERR_LENGTH;
    }
    return Sensor_OnTask((SensorHandle *)base, code, payload, (STNP_U8)length);
}

static const STNP_ModuleOps g_sensor_module_ops =
{
    Sensor_TaskHandler,
    g_sensor_task_vtl,
    (STNP_U16)(sizeof(g_sensor_task_vtl) / sizeof(g_sensor_task_vtl[0])),
    g_sensor_notify_vtl,
    (STNP_U16)(sizeof(g_sensor_notify_vtl) / sizeof(g_sensor_notify_vtl[0]))
};

STNP_ModuleHandle *Sensor_AsModule(SensorHandle *self)
{
    if (self == STNP_NULL)
    {
        return STNP_NULL;
    }
    self->base.ops = &g_sensor_module_ops;
    return &self->base;
}

STNP_WEAK void Sensor_NotifyCallback(SensorHandle *self, STNP_U8 notify_code, Sensor_Result result, const void *payload)
{
    STNP_UNUSED(self);
    STNP_UNUSED(notify_code);
    STNP_UNUSED(result);
    STNP_UNUSED(payload);
}

STNP_Result Sensor_NotifyDispatch(SensorHandle *self, STNP_U8 notify_code, STNP_U16 result, const STNP_U8 *payload, STNP_U8 length)
{
    const STNP_VTL_Desc *desc = STNP_VTL_Find(
        g_sensor_notify_vtl,
        (STNP_U16)(sizeof(g_sensor_notify_vtl) / sizeof(g_sensor_notify_vtl[0])),
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
    case SENSOR_NOTIFY_DATA:
    {
        Sensor_DataPayload typed_payload;
        STNP_Result dr = STNP_VTL_Decode(desc, payload, length, &typed_payload);

        if (dr != STNP_OK)
        {
            return dr;
        }
        if (g_notify_callback_enabled == STNP_ENABLE)
        {
            Sensor_NotifyCallback(self, notify_code, (Sensor_Result)result, &typed_payload);
        }
        return STNP_OK;
    }
    case SENSOR_NOTIFY_DONE:
    {
        STNP_Result dr = STNP_VTL_Decode(desc, payload, length, STNP_NULL);

        if (dr != STNP_OK)
        {
            return dr;
        }
        if (g_notify_callback_enabled == STNP_ENABLE)
        {
            Sensor_NotifyCallback(self, notify_code, (Sensor_Result)result, STNP_NULL);
        }
        return STNP_OK;
    }
    default:
        return STNP_ERR_COMMAND;
    }
}

STNP_WEAK void Sensor_Read(SensorHandle *self)
{
    STNP_UNUSED(self);
}
STNP_WEAK void Sensor_Calibrate(SensorHandle *self, const Sensor_CalibratePayload *payload)
{
    STNP_UNUSED(self);
    STNP_UNUSED(payload);
}
