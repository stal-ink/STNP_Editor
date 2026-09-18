/**
 ******************************************************************************
 * @file    stnp_notify.c
 * @brief   STNP Notify structured/raw send, receive and fallback dispatch.
 ******************************************************************************
 */

#include "stnp_notify.h"
#include "stnp_frame.h"
#include "stnp_router.h"

/* Notify 接收分发运行时开关：初值来自 protocol.options.notify_dispatch_receive.enabled。 */
static STNP_U8 g_notify_dispatch_receive = 1U;

void STNP_NotifyDispatchReceive_Enable(void)
{
    g_notify_dispatch_receive = 1U;
}

void STNP_NotifyDispatchReceive_Disable(void)
{
    g_notify_dispatch_receive = 0U;
}

STNP_U8 STNP_NotifyDispatchReceive_IsEnabled(void)
{
    return g_notify_dispatch_receive;
}

STNP_Result STNP_Notify_Send(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const void *payload)
{
    STNP_U8 raw[STNP_PAYLOAD_MAX];
    STNP_U8 length = 0U;
    STNP_Result encode_result;

    encode_result = STNP_Router_EncodeNotify(source, notify_code, payload, raw, &length);
    if (encode_result != STNP_OK)
    {
        return encode_result;
    }
    return STNP_Notify_SendBytes_Impl(
        source,
        notify_code,
        result,
        (length == 0U) ? STNP_NULL : raw,
        length
    );
}

STNP_Result STNP_Notify_SendBytes_Impl(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U16 length)
{
    STNP_NotifyFrame frame;
    STNP_U8 out[STNP_NOTIFY_FIXED_SIZE + STNP_PAYLOAD_MAX + STNP_CRC_SIZE];
    STNP_U16 out_len;
    STNP_U16 i;
    STNP_Result build_result;

    if (length > STNP_PAYLOAD_MAX)
    {
        return STNP_ERR_LENGTH;
    }
    if ((payload == STNP_NULL) && (length > 0U))
    {
        return STNP_ERR_PARAM;
    }

    frame.source = source;
    frame.notify_code = notify_code;
    frame.result = result;
    frame.length = (STNP_U8)length;
    for (i = 0U; i < length; i++)
    {
        frame.payload[i] = payload[i];
    }

    build_result = STNP_Frame_BuildNotify(&frame, out, (STNP_U16)sizeof(out), &out_len);
    if (build_result != STNP_OK)
    {
        return build_result;
    }
    return STNP_Transport_Write(out, out_len);
}

STNP_WEAK void STNP_Notify_Callback(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    STNP_UNUSED(source);
    STNP_UNUSED(notify_code);
    STNP_UNUSED(result);
    STNP_UNUSED(payload);
    STNP_UNUSED(length);
}

STNP_WEAK STNP_Result STNP_Notify_Dispatch(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    STNP_Notify_Callback(source, notify_code, result, payload, length);
    return STNP_OK;
}
