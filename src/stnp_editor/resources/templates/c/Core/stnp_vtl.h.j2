/**
 ******************************************************************************
 * @file    stnp_vtl.h
 * @brief   Core VTL typed-payload codec engine.
 ******************************************************************************
 */

#ifndef __STNP_VTL_H
#define __STNP_VTL_H

#include <stddef.h>
#include "stnp_core.h"

typedef enum
{
    STNP_VTL_U8 = 0,
    STNP_VTL_U16,
    STNP_VTL_U32,
    STNP_VTL_I32
} STNP_VTL_Type;

typedef struct
{
    STNP_U16 offset;
    STNP_VTL_Type type;
} STNP_VTL_Field;

typedef struct
{
    STNP_U8 code;
    STNP_U8 wire_size;
    STNP_U8 field_count;
    const STNP_VTL_Field *fields;
} STNP_VTL_Desc;

const STNP_VTL_Desc *STNP_VTL_Find(
    const STNP_VTL_Desc *table,
    STNP_U16 count,
    STNP_U8 code
);

STNP_Result STNP_VTL_Encode(
    const STNP_VTL_Desc *desc,
    const void *payload,
    STNP_U8 *raw,
    STNP_U8 *length
);

STNP_Result STNP_VTL_Decode(
    const STNP_VTL_Desc *desc,
    const STNP_U8 *raw,
    STNP_U8 length,
    void *payload
);

#endif /* __STNP_VTL_H */
