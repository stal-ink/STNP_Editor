/**
 ******************************************************************************
 * @file    stnp_core.c
 * @brief   STNP transport buffering and bounded deferred protocol processing.
 ******************************************************************************
 */

#include "stnp_core.h"
#include "stnp_frame.h"
#include "stnp_runtime.h"


#define STNP_RX_STORAGE_SIZE (STNP_RX_RING_SIZE + 1U)

static STNP_TransportWrite g_transport_write = STNP_NULL;
static STNP_U8 g_rx_ring[STNP_RX_STORAGE_SIZE];
static volatile STNP_U16 g_rx_head = 0U;
static volatile STNP_U16 g_rx_tail = 0U;
static STNP_U8 g_parse_buf[STNP_FRAME_MAX_SIZE];
static STNP_U16 g_parse_len = 0U;

static STNP_U16 _crc_extra(void)
{
    return STNP_CRC_SIZE;
}

static STNP_U16 _rx_next(STNP_U16 index)
{
    index++;
    if (index >= (STNP_U16)STNP_RX_STORAGE_SIZE)
    {
        index = 0U;
    }
    return index;
}

static STNP_U16 _rx_free(void)
{
    STNP_U16 head = g_rx_head;
    STNP_U16 tail = g_rx_tail;

    if (tail >= head)
    {
        return (STNP_U16)(STNP_RX_RING_SIZE - (tail - head));
    }
    return (STNP_U16)(head - tail - 1U);
}

static STNP_U8 _rx_pop(STNP_U8 *value)
{
    STNP_U16 head = g_rx_head;
    STNP_U16 tail = g_rx_tail;

    if (head == tail)
    {
        return 0U;
    }
    *value = g_rx_ring[head];
    g_rx_head = _rx_next(head);
    return 1U;
}

static void _parse_shift(STNP_U16 count)
{
    STNP_U16 i;

    if (count >= g_parse_len)
    {
        g_parse_len = 0U;
        return;
    }
    g_parse_len = (STNP_U16)(g_parse_len - count);
    for (i = 0U; i < g_parse_len; i++)
    {
        g_parse_buf[i] = g_parse_buf[count + i];
    }
}

static STNP_Result _try_complete_frame(STNP_U8 *complete)
{
    STNP_U8 is_task;
    STNP_U8 is_notify;
    STNP_U8 payload_len;
    STNP_U16 need;
    STNP_Result result;
    STNP_TaskFrame task_frame;
    STNP_NotifyFrame notify_frame;

    *complete = 0U;

    while (g_parse_len >= 2U)
    {
        is_task = (STNP_U8)((g_parse_buf[0] == STNP_TASK_HEADER0) &&
                            (g_parse_buf[1] == STNP_TASK_HEADER1));
        is_notify = (STNP_U8)((g_parse_buf[0] == STNP_NOTIFY_HEADER0) &&
                              (g_parse_buf[1] == STNP_NOTIFY_HEADER1));
        if ((is_task == 0U) && (is_notify == 0U))
        {
            _parse_shift(1U);
            continue;
        }

        if (is_task != 0U)
        {
            if (g_parse_len < STNP_TASK_FIXED_SIZE)
            {
                return STNP_IDLE;
            }
            payload_len = g_parse_buf[4];
            if (payload_len > STNP_PAYLOAD_MAX)
            {
                _parse_shift(1U);
                *complete = 1U;
                return STNP_ERR_LENGTH;
            }
            need = (STNP_U16)(STNP_TASK_FIXED_SIZE + payload_len + _crc_extra());
            if (g_parse_len < need)
            {
                return STNP_IDLE;
            }

            result = STNP_Frame_ParseTask(g_parse_buf, need, &task_frame);
            if (result != STNP_OK)
            {
                /* CRC/structural failure: slide one byte so a valid nested SOF
                 * can still be recovered on the next Process call. */
                _parse_shift(1U);
                *complete = 1U;
                return result;
            }
            result = STNP_Runtime_EnqueueTask(
                task_frame.target,
                task_frame.code,
                task_frame.payload,
                task_frame.length
            );
            if (result == STNP_ERR_BUFFER)
            {
                return result;
            }
            _parse_shift(need);
            *complete = 1U;
            return result;
        }

        if (g_parse_len < STNP_NOTIFY_FIXED_SIZE)
        {
            return STNP_IDLE;
        }
        payload_len = g_parse_buf[6];
        if (payload_len > STNP_PAYLOAD_MAX)
        {
            _parse_shift(1U);
            *complete = 1U;
            return STNP_ERR_LENGTH;
        }
        need = (STNP_U16)(STNP_NOTIFY_FIXED_SIZE + payload_len + _crc_extra());
        if (g_parse_len < need)
        {
            return STNP_IDLE;
        }

        result = STNP_Frame_ParseNotify(g_parse_buf, need, &notify_frame);
        if (result != STNP_OK)
        {
            _parse_shift(1U);
            *complete = 1U;
            return result;
        }
        result = STNP_Runtime_EnqueueNotify(
            notify_frame.source,
            notify_frame.notify_code,
            notify_frame.result,
            notify_frame.payload,
            notify_frame.length
        );
        if (result == STNP_ERR_BUFFER)
        {
            return result;
        }
        _parse_shift(need);
        *complete = 1U;
        return result;
    }

    return STNP_IDLE;
}

STNP_Result STNP_Init(STNP_TransportWrite write_fn)
{
    if (write_fn == STNP_NULL)
    {
        return STNP_ERR_PARAM;
    }
    g_transport_write = write_fn;
    g_rx_head = 0U;
    g_rx_tail = 0U;
    g_parse_len = 0U;
    return STNP_Runtime_Init();
}

STNP_Result STNP_Transport_Write(const STNP_U8 *data, STNP_U16 length)
{
    if (g_transport_write == STNP_NULL)
    {
        return STNP_ERR_STATE;
    }
    if ((data == STNP_NULL) && (length > 0U))
    {
        return STNP_ERR_PARAM;
    }
    return g_transport_write(data, length);
}

STNP_Result STNP_Transport_Receive(const STNP_U8 *data, STNP_U16 length)
{
    STNP_U16 i;
    STNP_U16 tail;

    if ((data == STNP_NULL) && (length > 0U))
    {
        return STNP_ERR_PARAM;
    }
    if (length > _rx_free())
    {
        return STNP_ERR_BUFFER;
    }

    /* SPSC transport ring: producer owns tail, Process owns head. Publish tail
     * only after the entire chunk has been copied, so Process never sees a
     * partially committed input chunk. */
    tail = g_rx_tail;
    for (i = 0U; i < length; i++)
    {
        g_rx_ring[tail] = data[i];
        tail = _rx_next(tail);
    }
    g_rx_tail = tail;
    return STNP_OK;
}

STNP_Result STNP_Process(void)
{
    STNP_Result result;
    STNP_U8 complete;
    STNP_U8 byte;

    for (;;)
    {
        result = _try_complete_frame(&complete);
        if ((complete != 0U) || (result == STNP_ERR_BUFFER))
        {
            return result;
        }

        if (_rx_pop(&byte) == 0U)
        {
            return STNP_IDLE;
        }
        if (g_parse_len >= STNP_FRAME_MAX_SIZE)
        {
            _parse_shift(1U);
            return STNP_ERR_LENGTH;
        }
        g_parse_buf[g_parse_len] = byte;
        g_parse_len++;
    }
}

STNP_Result STNP_Dispatch(void)
{
    return STNP_Runtime_DispatchOne();
}
