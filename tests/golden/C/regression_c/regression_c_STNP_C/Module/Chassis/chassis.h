/**
 ******************************************************************************
 * @file    chassis.h
 * @brief   Chassis typed Payload and module-level API.
 *
 * This header exposes Payload types and receive-side Module APIs only.
 * Sending is unified in Core: STNP_Task_Send/STNP_Notify_Send for typed Payload,
 * and STNP_Task_SendBytes/STNP_Notify_SendBytes for raw byte arrays.
 ******************************************************************************
 */

#ifndef __CHASSIS_H
#define __CHASSIS_H

#include "../stnp_module.h"

typedef enum
{
    CHASSIS_CMD_MOVE = 0x01U,
    CHASSIS_CMD_STOP = 0x02U
} Chassis_Command;

typedef enum
{
    CHASSIS_NOTIFY_DONE = 0x01U,
    CHASSIS_NOTIFY_TASK_ACCEPTED = 0x02U,
    CHASSIS_NOTIFY_TASK_REJECTED = 0x03U
} Chassis_Notify;

typedef enum
{
    CHASSIS_OK = 0x0100U,
    CHASSIS_PARAM = 0x0101U,
    CHASSIS_BUSY = 0x0102U
} Chassis_Result;

typedef struct
{
    STNP_U8 direction;
    STNP_Speed speed;
} Chassis_MovePayload;

enum
{
    CHASSIS_MOVE_PAYLOAD_SIZE = 2U,
};

typedef struct ChassisHandle ChassisHandle;
typedef Chassis_Result (*Chassis_ValidateCallback)(
    ChassisHandle *self,
    STNP_U8 cmd,
    const void *payload
);

struct ChassisHandle
{
    STNP_ModuleHandle base;
};

/* Framework lifecycle / routing. */
void Chassis_Init(ChassisHandle *self, STNP_U8 id);
STNP_ModuleHandle *Chassis_AsModule(ChassisHandle *self);
STNP_Result Chassis_OnTask(
    ChassisHandle *self,
    STNP_U8 cmd,
    const STNP_U8 *payload,
    STNP_U8 len
);
void Chassis_SetValidate(STNP_U8 cmd, Chassis_ValidateCallback fn);
/* Generated module validator: dispatch by command code, auto-check field ranges. */
Chassis_Result Chassis_ValidateGenerated(
    ChassisHandle *self,
    STNP_U8 cmd,
    const void *payload
);

/* Module-level Notify callback. One callback per Module, optional at runtime. */
void Chassis_NotifyCallbackEnable(STNP_EnableState state);
STNP_U8 Chassis_NotifyCallbackIsEnabled(void);
void Chassis_NotifyCallback(
    ChassisHandle *self,
    STNP_U8 notify_code,
    Chassis_Result result,
    const void *payload
);

/* User business functions, named only from CMD. */
void Chassis_Move(
    ChassisHandle *self,
    const Chassis_MovePayload *payload
);
void Chassis_Stop(ChassisHandle *self);

/* Framework Notify route used by generated instance registry. */
STNP_Result Chassis_NotifyDispatch(
    ChassisHandle *self,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length
);
#endif /* __CHASSIS_H */
