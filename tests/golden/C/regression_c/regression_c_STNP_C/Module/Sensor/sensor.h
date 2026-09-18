/**
 ******************************************************************************
 * @file    sensor.h
 * @brief   Sensor typed Payload and module-level API.
 *
 * This header exposes Payload types and receive-side Module APIs only.
 * Sending is unified in Core: STNP_Task_Send/STNP_Notify_Send for typed Payload,
 * and STNP_Task_SendBytes/STNP_Notify_SendBytes for raw byte arrays.
 ******************************************************************************
 */

#ifndef __SENSOR_H
#define __SENSOR_H

#include "../stnp_module.h"

typedef enum
{
    SENSOR_CMD_READ = 0x05U,
    SENSOR_CMD_CALIBRATE = 0x06U
} Sensor_Command;

typedef enum
{
    SENSOR_NOTIFY_DATA = 0x01U,
    SENSOR_NOTIFY_DONE = 0x02U
} Sensor_Notify;

typedef enum
{
    SENSOR_OK = 0x0300U
} Sensor_Result;

typedef struct
{
    STNP_I32 offset;
    STNP_U16 gain;
} Sensor_CalibratePayload;

typedef struct
{
    STNP_U16 value;
} Sensor_DataPayload;

enum
{
    SENSOR_CALIBRATE_PAYLOAD_SIZE = 6U,
    SENSOR_DATA_PAYLOAD_SIZE = 2U,
};

typedef struct SensorHandle SensorHandle;
typedef Sensor_Result (*Sensor_ValidateCallback)(
    SensorHandle *self,
    STNP_U8 cmd,
    const void *payload
);

struct SensorHandle
{
    STNP_ModuleHandle base;
};

/* Framework lifecycle / routing. */
void Sensor_Init(SensorHandle *self, STNP_U8 id);
STNP_ModuleHandle *Sensor_AsModule(SensorHandle *self);
STNP_Result Sensor_OnTask(
    SensorHandle *self,
    STNP_U8 cmd,
    const STNP_U8 *payload,
    STNP_U8 len
);
void Sensor_SetValidate(STNP_U8 cmd, Sensor_ValidateCallback fn);
/* Generated module validator: dispatch by command code, auto-check field ranges. */
Sensor_Result Sensor_ValidateGenerated(
    SensorHandle *self,
    STNP_U8 cmd,
    const void *payload
);

/* Module-level Notify callback. One callback per Module, optional at runtime. */
void Sensor_NotifyCallbackEnable(STNP_EnableState state);
void Sensor_NotifyCallback(
    SensorHandle *self,
    STNP_U8 notify_code,
    Sensor_Result result,
    const void *payload
);

/* User business functions, named only from CMD. */
void Sensor_Read(SensorHandle *self);
void Sensor_Calibrate(
    SensorHandle *self,
    const Sensor_CalibratePayload *payload
);

/* Framework Notify route used by generated instance registry. */
STNP_Result Sensor_NotifyDispatch(
    SensorHandle *self,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length
);
#endif /* __SENSOR_H */
