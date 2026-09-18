/**
 ******************************************************************************
 * @file    stnp_core.h
 * @brief   STNP core transport and deferred-processing API.
 ******************************************************************************
 */

#ifndef __STNP_CORE_H
#define __STNP_CORE_H

#include "../Platform/stnp_platform.h"

typedef enum
{
    STNP_OK          = 0x0000U,
    STNP_ERR_LENGTH  = 0x0001U,
    STNP_ERR_TARGET  = 0x0002U,
    STNP_ERR_COMMAND = 0x0003U,
    STNP_ERR_PARAM   = 0x0004U,
    STNP_ERR_STATE   = 0x0005U,
    STNP_IDLE        = 0x0006U, /* 本次 Process/Dispatch 无可执行工作 */
    STNP_ERR_BUFFER  = 0x0007U  /* 静态 RX/Job 缓冲容量不足 */
} STNP_Result;

typedef STNP_Result (*STNP_TransportWrite)(const STNP_U8 *data, STNP_U16 length);

STNP_Result STNP_Init(STNP_TransportWrite write_fn);
STNP_Result STNP_Transport_Write(const STNP_U8 *data, STNP_U16 length);

/**
 * @brief Copy transport bytes into the bounded RX ring and return.
 *
 * This function never parses frames and never executes user Handler/Callback
 * code. It is therefore suitable for a short transport interrupt path.
 * If the whole input chunk does not fit, nothing from that chunk is copied.
 */
STNP_Result STNP_Transport_Receive(const STNP_U8 *data, STNP_U16 length);

/**
 * @brief Advance receive protocol processing by at most one complete frame.
 *
 * Parser/router work happens here. A valid receive event is copied into the
 * static Job queue; user business code is not executed by this function.
 *
 * @retval STNP_OK          One frame was accepted into the Job queue.
 * @retval STNP_IDLE        No complete frame is currently available.
 * @retval STNP_ERR_BUFFER  Job queue full; the complete frame is retained for retry.
 * @retval other            The encountered frame error; rejected bytes are consumed/resynced.
 */
STNP_Result STNP_Process(void);

/**
 * @brief Execute at most one runnable queued receive event.
 *
 * The Job is claimed under a very short runtime lock, then Handler/Callback
 * code runs outside that lock. Official RTOS SDKs override the internal lock
 * hooks so multiple worker tasks may call this concurrently. Jobs belonging to
 * the same instance/source remain serialized.
 */
STNP_Result STNP_Dispatch(void);

#endif /* __STNP_CORE_H */
