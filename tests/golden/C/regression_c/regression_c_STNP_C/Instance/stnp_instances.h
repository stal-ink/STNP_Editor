/**
 ******************************************************************************
 * @file    stnp_instances.h
 * @brief   Generated instance IDs and router initialization.
 ******************************************************************************
 */

#ifndef __STNP_INSTANCES_H
#define __STNP_INSTANCES_H

#include "../Core/stnp_core.h"
#include "../Core/stnp_task.h"
#include "../Core/stnp_notify.h"
#include "../Module/Chassis/chassis.h"
#include "../Module/Motor/motor.h"
#include "../Module/Sensor/sensor.h"
#define STNP_INSTANCE_CHASSISMAIN_ID 0x01U
#define STNP_INSTANCE_MOTORMAIN_ID 0x02U
#define STNP_INSTANCE_SENSORFRONT_ID 0x03U
#define STNP_INSTANCE_SENSORREAR_ID 0x04U
STNP_Result STNP_Instances_Init(void);
#endif /* __STNP_INSTANCES_H */
