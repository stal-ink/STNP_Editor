/**
 ******************************************************************************
 * @file    chassis_impl.c
 * @brief   Chassis user business implementation.
 ******************************************************************************
 */

#include "../Instance/stnp_instances.h"

/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* USER CODE BEGIN Private */

/* USER CODE END Private */

/**
 ******************************************************************************
 * @brief Generated Chassis validator. Dispatches by command code and
 *        checks payload fields against their base type range and min/max.
 ******************************************************************************
 */
Chassis_Result Chassis_ValidateGenerated(ChassisHandle *self, STNP_U8 cmd, const void *payload)
{
    STNP_UNUSED(self);
    switch (cmd)
    {
    case CHASSIS_CMD_MOVE:
    {
        const Chassis_MovePayload *typed = (const Chassis_MovePayload *)payload;
        STNP_UNUSED(typed);
        if (typed->speed < 1) return CHASSIS_PARAM;
        if (typed->speed > 100) return CHASSIS_PARAM;
        return CHASSIS_OK;
    }
    default:
        return CHASSIS_OK;
    }
}
/**
 ******************************************************************************
 * @brief 底盘按方向与速度运动
 ******************************************************************************
 */
void Chassis_Move(ChassisHandle *self, const Chassis_MovePayload *payload)
{
    /* USER CODE BEGIN Chassis_Move */
    STNP_UNUSED(self); STNP_UNUSED(payload);
    /* USER CODE END Chassis_Move */
}

/**
 ******************************************************************************
 * @brief 底盘停止
 ******************************************************************************
 */
void Chassis_Stop(ChassisHandle *self)
{
    /* USER CODE BEGIN Chassis_Stop */
    STNP_UNUSED(self);
    /* USER CODE END Chassis_Stop */
}

