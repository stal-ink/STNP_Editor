/**
 ******************************************************************************
 * @file    motor_impl.c
 * @brief   Motor user business implementation.
 ******************************************************************************
 */

#include "../Instance/stnp_instances.h"

/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* USER CODE BEGIN Private */

/* USER CODE END Private */

/**
 ******************************************************************************
 * @brief Generated Motor validator. Dispatches by command code and
 *        checks payload fields against their base type range and min/max.
 ******************************************************************************
 */
Motor_Result Motor_ValidateGenerated(MotorHandle *self, STNP_U8 cmd, const void *payload)
{
    STNP_UNUSED(self);
    switch (cmd)
    {
    case MOTOR_CMD_SET_SPEED:
    {
        const Motor_SetSpeedPayload *typed = (const Motor_SetSpeedPayload *)payload;
        STNP_UNUSED(typed);
        if (typed->speed > 3000) return (Motor_Result)STNP_ERR_PARAM;
        if (typed->accel > 10) return (Motor_Result)STNP_ERR_PARAM;
        return MOTOR_OK;
    }
    default:
        return MOTOR_OK;
    }
}
/**
 ******************************************************************************
 * @brief 设置电机目标转速与加速度
 ******************************************************************************
 */
void Motor_SetSpeed(MotorHandle *self, const Motor_SetSpeedPayload *payload)
{
    /* USER CODE BEGIN Motor_SetSpeed */
    STNP_UNUSED(self); STNP_UNUSED(payload);
    /* USER CODE END Motor_SetSpeed */
}

/**
 ******************************************************************************
 * @brief 以给定力矩锁定电机
 ******************************************************************************
 */
void Motor_Hold(MotorHandle *self, const Motor_HoldPayload *payload)
{
    /* USER CODE BEGIN Motor_Hold */
    STNP_UNUSED(self); STNP_UNUSED(payload);
    /* USER CODE END Motor_Hold */
}

