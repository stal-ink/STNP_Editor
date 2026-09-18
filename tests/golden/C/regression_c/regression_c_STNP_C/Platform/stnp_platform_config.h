/**
 ******************************************************************************
 * @file    stnp_platform_config.h
 * @brief   STNP project-level static-memory configuration.
 ******************************************************************************
 */

#ifndef __STNP_PLATFORM_CONFIG_H
#define __STNP_PLATFORM_CONFIG_H

#define STNP_PAYLOAD_MAX            64U
#define STNP_ROUTER_INSTANCE_MAX    8U
#define STNP_TASK_HEADER_SIZE       2U
#define STNP_NOTIFY_HEADER_SIZE     2U
#define STNP_TASK_FIXED_SIZE        5U
#define STNP_NOTIFY_FIXED_SIZE      7U
#define STNP_CRC_SIZE               0U
#define STNP_FRAME_MAX_SIZE         71U

/* RX ring holds transport bytes until STNP_Process() advances the protocol.
 * Four maximum frames gives useful burst tolerance while remaining static and
 * predictable. Override at compile time/project level when required. */
#ifndef STNP_RX_RING_SIZE
#define STNP_RX_RING_SIZE           284U
#endif

/* Number of decoded receive events waiting for STNP_Dispatch(). */
#ifndef STNP_JOB_QUEUE_DEPTH
#define STNP_JOB_QUEUE_DEPTH        8U
#endif

#if (STNP_RX_RING_SIZE < STNP_FRAME_MAX_SIZE) || (STNP_RX_RING_SIZE > 65534U)
#error "STNP_RX_RING_SIZE must fit at least one max frame and be <= 65534"
#endif

#if (STNP_JOB_QUEUE_DEPTH == 0U) || (STNP_JOB_QUEUE_DEPTH > 255U)
#error "STNP_JOB_QUEUE_DEPTH must be in range 1..255"
#endif

#endif /* __STNP_PLATFORM_CONFIG_H */
