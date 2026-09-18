/**
 ******************************************************************************
 * @file    transport_mock.c
 * @brief   PC loopback transport for deferred STNP processing.
 *
 * The mock only loops transmitted bytes back into STNP_Transport_Receive(). It
 * intentionally does not call STNP_Process()/STNP_Dispatch(), so tests/examples
 * observe the same deferred execution model as real transports.
 ******************************************************************************
 */

#include "transport_mock.h"
#include <stdio.h>

#define TRANSPORT_MOCK_BUF_MAX STNP_FRAME_MAX_SIZE

static STNP_U8 g_last_tx[TRANSPORT_MOCK_BUF_MAX];
static STNP_U16 g_last_tx_len = 0U;

static void _copy_bytes(STNP_U8 *dst, const STNP_U8 *src, STNP_U16 length)
{
    STNP_U16 i;
    for (i = 0U; i < length; i++)
    {
        dst[i] = src[i];
    }
}

STNP_Result TransportMock_Write(const STNP_U8 *data, STNP_U16 length)
{
    STNP_U16 i;
    STNP_Result result;

    if ((data == STNP_NULL) && (length > 0U))
    {
        return STNP_ERR_PARAM;
    }
    if (length > TRANSPORT_MOCK_BUF_MAX)
    {
        return STNP_ERR_LENGTH;
    }

    printf("[TX] len=%u :", (unsigned int)length);
    for (i = 0U; i < length; i++)
    {
        printf(" %02X", (unsigned int)data[i]);
    }
    printf("\n");

    _copy_bytes(g_last_tx, data, length);
    g_last_tx_len = length;

    result = STNP_Transport_Receive(data, length);
    return result;
}

const STNP_U8 *TransportMock_GetLast(STNP_U16 *length)
{
    if (length != STNP_NULL)
    {
        *length = g_last_tx_len;
    }
    return g_last_tx;
}
