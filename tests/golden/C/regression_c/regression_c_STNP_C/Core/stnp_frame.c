/**
 ******************************************************************************
 * @file    stnp_frame.c
 * @brief   STNP 帧解析和组包实现（SOF 由 .stnp 配置）。
 *
 * 用户禁止修改协议代码。
 ******************************************************************************
 */

#include "stnp_frame.h"
#include "stnp_debug.h"
#include "stnp_codec.h"

static STNP_U16 _crc_extra(void)
{
    return STNP_CRC_SIZE;
}



STNP_Result STNP_Frame_BuildTask(
    const STNP_TaskFrame *frame,
    STNP_U8 *out,
    STNP_U16 out_max,
    STNP_U16 *out_len)
{
    STNP_U16 need;
    STNP_U16 i;
    STNP_U16 extra;

    if ((frame == STNP_NULL) || (out == STNP_NULL) || (out_len == STNP_NULL))
    {
        return STNP_ERR_PARAM;
    }

    if (frame->length > STNP_PAYLOAD_MAX)
    {
        return STNP_ERR_LENGTH;
    }

    extra = _crc_extra();
    need = (STNP_U16)(STNP_TASK_FIXED_SIZE + frame->length + extra);
    if (out_max < need)
    {
        return STNP_ERR_LENGTH;
    }

    out[0] = STNP_TASK_HEADER0;
    out[1] = STNP_TASK_HEADER1;
    out[2] = frame->target;
    out[3] = frame->code;
    out[4] = frame->length;

    for (i = 0U; i < frame->length; i++)
    {
        out[STNP_TASK_FIXED_SIZE + i] = frame->payload[i];
    }


    *out_len = need;
    return STNP_OK;
}

STNP_Result STNP_Frame_ParseTask(
    const STNP_U8 *data,
    STNP_U16 length,
    STNP_TaskFrame *frame)
{
    STNP_U8 payload_len;
    STNP_U16 i;
    STNP_U16 extra;
    STNP_U16 need;

    if ((data == STNP_NULL) || (frame == STNP_NULL))
    {
        return STNP_ERR_PARAM;
    }

    if (length < STNP_TASK_FIXED_SIZE)
    {
        return STNP_ERR_LENGTH;
    }

    if ((data[0] != STNP_TASK_HEADER0) || (data[1] != STNP_TASK_HEADER1))
    {
        return STNP_ERR_PARAM;
    }

    payload_len = data[4];
    if (payload_len > STNP_PAYLOAD_MAX)
    {
        return STNP_ERR_LENGTH;
    }

    extra = _crc_extra();
    need = (STNP_U16)(STNP_TASK_FIXED_SIZE + payload_len + extra);
    if (length != need)
    {
        return STNP_ERR_LENGTH;
    }


    frame->target = data[2];
    frame->code = data[3];
    frame->length = payload_len;

    for (i = 0U; i < payload_len; i++)
    {
        frame->payload[i] = data[STNP_TASK_FIXED_SIZE + i];
    }

    return STNP_OK;
}

STNP_Result STNP_Frame_BuildNotify(
    const STNP_NotifyFrame *frame,
    STNP_U8 *out,
    STNP_U16 out_max,
    STNP_U16 *out_len)
{
    STNP_U16 need;
    STNP_U16 i;
    STNP_U16 extra;

    if ((frame == STNP_NULL) || (out == STNP_NULL) || (out_len == STNP_NULL))
    {
        return STNP_ERR_PARAM;
    }

    if (frame->length > STNP_PAYLOAD_MAX)
    {
        return STNP_ERR_LENGTH;
    }

    extra = _crc_extra();
    need = (STNP_U16)(STNP_NOTIFY_FIXED_SIZE + frame->length + extra);
    if (out_max < need)
    {
        return STNP_ERR_LENGTH;
    }

    out[0] = STNP_NOTIFY_HEADER0;
    out[1] = STNP_NOTIFY_HEADER1;
    out[2] = frame->source;
    out[3] = frame->notify_code;
    STNP_Encode_U16(&out[4], frame->result);
    out[6] = frame->length;

    for (i = 0U; i < frame->length; i++)
    {
        out[STNP_NOTIFY_FIXED_SIZE + i] = frame->payload[i];
    }


    *out_len = need;
    return STNP_OK;
}

STNP_Result STNP_Frame_ParseNotify(
    const STNP_U8 *data,
    STNP_U16 length,
    STNP_NotifyFrame *frame)
{
    STNP_U8 payload_len;
    STNP_U16 i;
    STNP_U16 extra;
    STNP_U16 need;

    if ((data == STNP_NULL) || (frame == STNP_NULL))
    {
        return STNP_ERR_PARAM;
    }

    if (length < STNP_NOTIFY_FIXED_SIZE)
    {
        return STNP_ERR_LENGTH;
    }

    if ((data[0] != STNP_NOTIFY_HEADER0) || (data[1] != STNP_NOTIFY_HEADER1))
    {
        return STNP_ERR_PARAM;
    }

    payload_len = data[6];
    if (payload_len > STNP_PAYLOAD_MAX)
    {
        return STNP_ERR_LENGTH;
    }

    extra = _crc_extra();
    need = (STNP_U16)(STNP_NOTIFY_FIXED_SIZE + payload_len + extra);
    if (length != need)
    {
        return STNP_ERR_LENGTH;
    }


    frame->source = data[2];
    frame->notify_code = data[3];
    frame->result = STNP_Decode_U16(&data[4]);
    frame->length = payload_len;

    for (i = 0U; i < payload_len; i++)
    {
        frame->payload[i] = data[STNP_NOTIFY_FIXED_SIZE + i];
    }

    return STNP_OK;
}
