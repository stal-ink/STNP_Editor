/**
 ******************************************************************************
 * @file    motor.h
 * @brief   Motor typed Payload and module-level API.
 *
 * This header exposes Payload types and receive-side Module APIs only.
 * Sending is unified in Core: STNP_Task_Send/STNP_Notify_Send for typed Payload,
 * and STNP_Task_SendBytes/STNP_Notify_SendBytes for raw byte arrays.
 ******************************************************************************
 */

#ifndef __MOTOR_H
#define __MOTOR_H

#include "../stnp_module.h"

typedef enum
{
    MOTOR_CMD_SET_SPEED = 0x03U,
    MOTOR_CMD_HOLD = 0x04U
} Motor_Command;

typedef enum
{
    MOTOR_NOTIFY_DONE = 0x01U,
    MOTOR_NOTIFY_FAULT = 0x02U
} Motor_Notify;

typedef enum
{
    MOTOR_OK = 0x0200U,
    MOTOR_FAULT = 0x0201U
} Motor_Result;

typedef struct
{
    STNP_U16 speed;
    STNP_U8 accel;
} Motor_SetSpeedPayload;

typedef struct
{
    STNP_U16 torque;
} Motor_HoldPayload;

enum
{
    MOTOR_SET_SPEED_PAYLOAD_SIZE = 3U,
    MOTOR_HOLD_PAYLOAD_SIZE = 2U,
};

typedef struct MotorHandle MotorHandle;
typedef Motor_Result (*Motor_ValidateCallback)(
    MotorHandle *self,
    STNP_U8 cmd,
    const void *payload
);

struct MotorHandle
{
    STNP_ModuleHandle base;
};

/* Framework lifecycle / routing. */
void Motor_Init(MotorHandle *self, STNP_U8 id);
STNP_ModuleHandle *Motor_AsModule(MotorHandle *self);
STNP_Result Motor_OnTask(
    MotorHandle *self,
    STNP_U8 cmd,
    const STNP_U8 *payload,
    STNP_U8 len
);
void Motor_SetValidate(STNP_U8 cmd, Motor_ValidateCallback fn);
/* Generated module validator: dispatch by command code, auto-check field ranges. */
Motor_Result Motor_ValidateGenerated(
    MotorHandle *self,
    STNP_U8 cmd,
    const void *payload
);

/* Module-level Notify callback. One callback per Module, optional at runtime. */
void Motor_NotifyCallbackEnable(STNP_EnableState state);
STNP_U8 Motor_NotifyCallbackIsEnabled(void);
void Motor_NotifyCallback(
    MotorHandle *self,
    STNP_U8 notify_code,
    Motor_Result result,
    const void *payload
);

/* User business functions, named only from CMD. */
void Motor_SetSpeed(
    MotorHandle *self,
    const Motor_SetSpeedPayload *payload
);
void Motor_Hold(
    MotorHandle *self,
    const Motor_HoldPayload *payload
);

/* Framework Notify route used by generated instance registry. */
STNP_Result Motor_NotifyDispatch(
    MotorHandle *self,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length
);
#endif /* __MOTOR_H */
