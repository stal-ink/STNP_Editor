/**
 ******************************************************************************
 * @file    stnp_instances.c
 * @brief   Generated instances and receive routing only.
 ******************************************************************************
 */

#include "stnp_instances.h"
#include "../Core/stnp_router.h"
#include "../Core/stnp_notify.h"
#include "../Core/stnp_debug.h"
static ChassisHandle g_chassismain;
static MotorHandle g_motormain;
static SensorHandle g_sensorfront;
static SensorHandle g_sensorrear;
STNP_Result STNP_Instances_Init(void)
{
    STNP_Result result;
    Chassis_Init(&g_chassismain, STNP_INSTANCE_CHASSISMAIN_ID);
    result = STNP_Router_Register(Chassis_AsModule(&g_chassismain));
    if (result != STNP_OK) return result;
    Motor_Init(&g_motormain, STNP_INSTANCE_MOTORMAIN_ID);
    result = STNP_Router_Register(Motor_AsModule(&g_motormain));
    if (result != STNP_OK) return result;
    Sensor_Init(&g_sensorfront, STNP_INSTANCE_SENSORFRONT_ID);
    result = STNP_Router_Register(Sensor_AsModule(&g_sensorfront));
    if (result != STNP_OK) return result;
    Sensor_Init(&g_sensorrear, STNP_INSTANCE_SENSORREAR_ID);
    result = STNP_Router_Register(Sensor_AsModule(&g_sensorrear));
    if (result != STNP_OK) return result;
    return STNP_OK;
}
STNP_Result STNP_Notify_Dispatch(STNP_U8 source, STNP_U8 notify_code, STNP_U16 result, const STNP_U8 *payload, STNP_U8 length)
{
    if (STNP_NotifyDispatchReceive_IsEnabled() == 0U)
    {
        return STNP_OK;
    }
    if (source == STNP_INSTANCE_CHASSISMAIN_ID)
    {
        if (Chassis_NotifyCallbackIsEnabled() != 0U)
        {
            STNP_Result r = Chassis_NotifyDispatch(&g_chassismain, notify_code, result, payload, length);
            if (r != STNP_ERR_COMMAND)
            {
                if (r == STNP_OK)
                {
                    STNP_BP_ON_NOTIFY();
                }
                return r;
            }
        }
    }
    else if (source == STNP_INSTANCE_MOTORMAIN_ID)
    {
        if (Motor_NotifyCallbackIsEnabled() != 0U)
        {
            STNP_Result r = Motor_NotifyDispatch(&g_motormain, notify_code, result, payload, length);
            if (r != STNP_ERR_COMMAND)
            {
                if (r == STNP_OK)
                {
                    STNP_BP_ON_NOTIFY();
                }
                return r;
            }
        }
    }
    else if (source == STNP_INSTANCE_SENSORFRONT_ID)
    {
        if (Sensor_NotifyCallbackIsEnabled() != 0U)
        {
            STNP_Result r = Sensor_NotifyDispatch(&g_sensorfront, notify_code, result, payload, length);
            if (r != STNP_ERR_COMMAND)
            {
                if (r == STNP_OK)
                {
                    STNP_BP_ON_NOTIFY();
                }
                return r;
            }
        }
    }
    else if (source == STNP_INSTANCE_SENSORREAR_ID)
    {
        if (Sensor_NotifyCallbackIsEnabled() != 0U)
        {
            STNP_Result r = Sensor_NotifyDispatch(&g_sensorrear, notify_code, result, payload, length);
            if (r != STNP_ERR_COMMAND)
            {
                if (r == STNP_OK)
                {
                    STNP_BP_ON_NOTIFY();
                }
                return r;
            }
        }
    }
    STNP_BP_ON_NOTIFY();
    STNP_Notify_Callback(source, notify_code, result, payload, length);
    return STNP_OK;
}
