/**
 ******************************************************************************
 * @file    stnp_frame.h
 * @brief   STNP 帧结构、帧头常量与组包拆包接口。
 *
 * Task:   SOF[2] TARGET | CODE | LEN | PAYLOAD
 * Notify: SOF[2] SOURCE | NOTIFY_CODE | RESULT | LEN | PAYLOAD
 *
 * CRC 槽由 protocol.features 门控。
 * 用户禁止修改协议代码。
 ******************************************************************************
 */

#ifndef __STNP_FRAME_H
#define __STNP_FRAME_H

#include "stnp_core.h"

#define STNP_TASK_HEADER0     0xAAU /* Task帧头第1字节 */
#define STNP_TASK_HEADER1     0x55U /* Task帧头第2字节 */
#define STNP_NOTIFY_HEADER0   0xAAU /* Notify帧头第1字节 */
#define STNP_NOTIFY_HEADER1   0x33U /* Notify帧头第2字节 */

typedef struct
{
    STNP_U8  target;                      /* 目标实例 */
    STNP_U8  code;                        /* 命令码 */
    STNP_U8  length;                      /* Payload长度 */
    STNP_U8  payload[STNP_PAYLOAD_MAX];   /* Payload数据 */
} STNP_TaskFrame;

typedef struct
{
    STNP_U8  source;                      /* 来源实例 */
    STNP_U8  notify_code;                 /* 模块内通知码 */
    STNP_U16 result;                      /* 模块返回码 */
    STNP_U8  length;                      /* Payload长度 */
    STNP_U8  payload[STNP_PAYLOAD_MAX];   /* Payload数据 */
} STNP_NotifyFrame;


STNP_Result STNP_Frame_BuildTask(
    const STNP_TaskFrame *frame,
    STNP_U8 *out,
    STNP_U16 out_max,
    STNP_U16 *out_len);

STNP_Result STNP_Frame_ParseTask(
    const STNP_U8 *data,
    STNP_U16 length,
    STNP_TaskFrame *frame);

STNP_Result STNP_Frame_BuildNotify(
    const STNP_NotifyFrame *frame,
    STNP_U8 *out,
    STNP_U16 out_max,
    STNP_U16 *out_len);

STNP_Result STNP_Frame_ParseNotify(
    const STNP_U8 *data,
    STNP_U16 length,
    STNP_NotifyFrame *frame);

#endif /* __STNP_FRAME_H */
