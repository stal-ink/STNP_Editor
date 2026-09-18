/**
 ******************************************************************************
 * @file    sensor_impl.c
 * @brief   Sensor user business implementation.
 ******************************************************************************
 */

#include "../Instance/stnp_instances.h"

/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* USER CODE BEGIN Private */

/* USER CODE END Private */

/**
 ******************************************************************************
 * @brief Generated Sensor validator. Dispatches by command code and
 *        checks payload fields against their base type range and min/max.
 ******************************************************************************
 */
Sensor_Result Sensor_ValidateGenerated(SensorHandle *self, STNP_U8 cmd, const void *payload)
{
    STNP_UNUSED(self);
    switch (cmd)
    {
    case SENSOR_CMD_CALIBRATE:
    {
        const Sensor_CalibratePayload *typed = (const Sensor_CalibratePayload *)payload;
        STNP_UNUSED(typed);
        if (typed->gain < 1) return (Sensor_Result)STNP_ERR_PARAM;
        if (typed->gain > 100) return (Sensor_Result)STNP_ERR_PARAM;
        return SENSOR_OK;
    }
    default:
        return SENSOR_OK;
    }
}
/**
 ******************************************************************************
 * @brief 读取传感器当前值
 ******************************************************************************
 */
void Sensor_Read(SensorHandle *self)
{
    /* USER CODE BEGIN Sensor_Read */
    STNP_UNUSED(self);
    /* USER CODE END Sensor_Read */
}

/**
 ******************************************************************************
 * @brief 写入标定参数
 ******************************************************************************
 */
void Sensor_Calibrate(SensorHandle *self, const Sensor_CalibratePayload *payload)
{
    /* USER CODE BEGIN Sensor_Calibrate */
    STNP_UNUSED(self); STNP_UNUSED(payload);
    /* USER CODE END Sensor_Calibrate */
}

