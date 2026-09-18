/**
 ******************************************************************************
 * @file    stnp_codec.c
 * @brief   STNP Payload 基础类型编解码实现（小端）。
 *
 * 用户禁止修改协议代码。
 ******************************************************************************
 */

#include "stnp_codec.h"

void STNP_Encode_U16(STNP_U8 *buf, STNP_U16 value)
{
    buf[0] = (STNP_U8)(value & 0x00FFU);
    buf[1] = (STNP_U8)((value >> 8) & 0x00FFU);
}

STNP_U16 STNP_Decode_U16(const STNP_U8 *buf)
{
    return (STNP_U16)((STNP_U16)buf[0] | ((STNP_U16)buf[1] << 8));
}

void STNP_Encode_U32(STNP_U8 *buf, STNP_U32 value)
{
    buf[0] = (STNP_U8)(value & 0x000000FFUL);
    buf[1] = (STNP_U8)((value >> 8) & 0x000000FFUL);
    buf[2] = (STNP_U8)((value >> 16) & 0x000000FFUL);
    buf[3] = (STNP_U8)((value >> 24) & 0x000000FFUL);
}

STNP_U32 STNP_Decode_U32(const STNP_U8 *buf)
{
    return (STNP_U32)buf[0]
         | ((STNP_U32)buf[1] << 8)
         | ((STNP_U32)buf[2] << 16)
         | ((STNP_U32)buf[3] << 24);
}

void STNP_Encode_I32(STNP_U8 *buf, STNP_I32 value)
{
    STNP_U32 u = (STNP_U32)value;

    buf[0] = (STNP_U8)(u & 0x000000FFUL);
    buf[1] = (STNP_U8)((u >> 8) & 0x000000FFUL);
    buf[2] = (STNP_U8)((u >> 16) & 0x000000FFUL);
    buf[3] = (STNP_U8)((u >> 24) & 0x000000FFUL);
}

STNP_I32 STNP_Decode_I32(const STNP_U8 *buf)
{
    return (STNP_I32)STNP_Decode_U32(buf);
}
