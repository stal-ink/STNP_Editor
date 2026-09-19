/**
 ******************************************************************************
 * @file    stnp_notify_callback.c
 * @brief   Optional raw fallback Notify callback.
 *
 * Known notify codes claimed by a module with NotifyCallbackIsEnabled do not
 * enter this fallback. Unclaimed frames (unknown instance/code, or module
 * enable off) still reach this function. Re-generation preserves the USER
 * CODE regions.
 ******************************************************************************
 */

#include "../Instance/stnp_instances.h"

/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* USER CODE BEGIN Private */

/* USER CODE END Private */

void STNP_Notify_Callback(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    /* USER CODE BEGIN STNP_Notify_Callback */
    STNP_UNUSED(source);
    STNP_UNUSED(notify_code);
    STNP_UNUSED(result);
    STNP_UNUSED(payload);
    STNP_UNUSED(length);
    /* USER CODE END STNP_Notify_Callback */
}
