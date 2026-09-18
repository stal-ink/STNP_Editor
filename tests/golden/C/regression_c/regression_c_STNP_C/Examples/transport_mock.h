/**
 ******************************************************************************
 * @file    transport_mock.h
 * @brief   PC 模拟传输接口。
 ******************************************************************************
 */

#ifndef __TRANSPORT_MOCK_H
#define __TRANSPORT_MOCK_H

#include "../Core/stnp_core.h"

STNP_Result TransportMock_Write(const STNP_U8 *data, STNP_U16 length);
const STNP_U8 *TransportMock_GetLast(STNP_U16 *length);

#endif /* __TRANSPORT_MOCK_H */
