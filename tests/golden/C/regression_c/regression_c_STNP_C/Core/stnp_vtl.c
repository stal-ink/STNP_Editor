/**
 ******************************************************************************
 * @file    stnp_vtl.c
 * @brief   Core VTL typed-payload codec engine.
 ******************************************************************************
 */

#include "stnp_vtl.h"
#include "stnp_codec.h"

static STNP_U8 STNP_VTL_TypeSize(STNP_VTL_Type type)
{
    switch (type)
    {
    case STNP_VTL_U8:
        return 1U;
    case STNP_VTL_U16:
        return 2U;
    case STNP_VTL_U32:
    case STNP_VTL_I32:
        return 4U;
    default:
        return 0U;
    }
}

const STNP_VTL_Desc *STNP_VTL_Find(
    const STNP_VTL_Desc *table,
    STNP_U16 count,
    STNP_U8 code)
{
    STNP_U16 i;

    if (table == STNP_NULL)
    {
        return STNP_NULL;
    }
    for (i = 0U; i < count; i++)
    {
        if (table[i].code == code)
        {
            return &table[i];
        }
    }
    return STNP_NULL;
}

STNP_Result STNP_VTL_Encode(
    const STNP_VTL_Desc *desc,
    const void *payload,
    STNP_U8 *raw,
    STNP_U8 *length)
{
    const STNP_U8 *base = (const STNP_U8 *)payload;
    STNP_U16 off = 0U;
    STNP_U8 i;

    if ((desc == STNP_NULL) || (length == STNP_NULL))
    {
        return STNP_ERR_PARAM;
    }
    if (desc->wire_size == 0U)
    {
        if (payload != STNP_NULL)
        {
            return STNP_ERR_PARAM;
        }
        *length = 0U;
        return STNP_OK;
    }
    if ((payload == STNP_NULL) || (raw == STNP_NULL) || (desc->fields == STNP_NULL))
    {
        return STNP_ERR_PARAM;
    }

    for (i = 0U; i < desc->field_count; i++)
    {
        const STNP_U8 *field = &base[desc->fields[i].offset];

        switch (desc->fields[i].type)
        {
        case STNP_VTL_U8:
            raw[off] = *(const STNP_U8 *)field;
            break;
        case STNP_VTL_U16:
            STNP_Encode_U16(&raw[off], *(const STNP_U16 *)field);
            break;
        case STNP_VTL_U32:
            STNP_Encode_U32(&raw[off], *(const STNP_U32 *)field);
            break;
        case STNP_VTL_I32:
            STNP_Encode_I32(&raw[off], *(const STNP_I32 *)field);
            break;
        default:
            return STNP_ERR_PARAM;
        }
        off = (STNP_U16)(off + STNP_VTL_TypeSize(desc->fields[i].type));
    }

    if (off != desc->wire_size)
    {
        return STNP_ERR_LENGTH;
    }
    *length = desc->wire_size;
    return STNP_OK;
}

STNP_Result STNP_VTL_Decode(
    const STNP_VTL_Desc *desc,
    const STNP_U8 *raw,
    STNP_U8 length,
    void *payload)
{
    STNP_U8 *base = (STNP_U8 *)payload;
    STNP_U16 off = 0U;
    STNP_U8 i;

    if (desc == STNP_NULL)
    {
        return STNP_ERR_COMMAND;
    }
    if (length != desc->wire_size)
    {
        return STNP_ERR_LENGTH;
    }
    if (desc->wire_size == 0U)
    {
        return (payload == STNP_NULL) ? STNP_OK : STNP_ERR_PARAM;
    }
    if ((raw == STNP_NULL) || (payload == STNP_NULL) || (desc->fields == STNP_NULL))
    {
        return STNP_ERR_PARAM;
    }

    for (i = 0U; i < desc->field_count; i++)
    {
        STNP_U8 *field = &base[desc->fields[i].offset];

        switch (desc->fields[i].type)
        {
        case STNP_VTL_U8:
            *(STNP_U8 *)field = raw[off];
            break;
        case STNP_VTL_U16:
            *(STNP_U16 *)field = STNP_Decode_U16(&raw[off]);
            break;
        case STNP_VTL_U32:
            *(STNP_U32 *)field = STNP_Decode_U32(&raw[off]);
            break;
        case STNP_VTL_I32:
            *(STNP_I32 *)field = STNP_Decode_I32(&raw[off]);
            break;
        default:
            return STNP_ERR_PARAM;
        }
        off = (STNP_U16)(off + STNP_VTL_TypeSize(desc->fields[i].type));
    }

    return (off == desc->wire_size) ? STNP_OK : STNP_ERR_LENGTH;
}
