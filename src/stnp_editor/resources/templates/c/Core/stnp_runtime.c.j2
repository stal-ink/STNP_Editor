/**
 ******************************************************************************
 * @file    stnp_runtime.c
 * @brief   Static deferred job queue and bounded dispatch implementation.
 ******************************************************************************
 */

#include "stnp_runtime.h"
#include "stnp_notify.h"

#define STNP_RUNTIME_INDEX_NONE 0xFFU
#define STNP_RUNTIME_KEY_COUNT  256U

typedef struct
{
    STNP_U8 next;
    STNP_U8 type;
    STNP_U8 key;
    STNP_U8 code;
    STNP_U16 result;
    STNP_U8 length;
    STNP_ModuleHandle *module;
    STNP_U8 payload[STNP_PAYLOAD_MAX];
} STNP_RuntimeJob;

static STNP_RuntimeJob g_jobs[STNP_JOB_QUEUE_DEPTH];
static STNP_U8 g_free_head = STNP_RUNTIME_INDEX_NONE;
static STNP_U8 g_ready_head = STNP_RUNTIME_INDEX_NONE;
static STNP_U8 g_ready_tail = STNP_RUNTIME_INDEX_NONE;
static STNP_U8 g_instance_busy[STNP_RUNTIME_KEY_COUNT];

STNP_WEAK STNP_U32 STNP_Runtime_Lock(void)
{
    return 0U;
}

STNP_WEAK void STNP_Runtime_Unlock(STNP_U32 state)
{
    STNP_UNUSED(state);
}

static void _copy_payload(STNP_U8 *dst, const STNP_U8 *src, STNP_U8 length)
{
    STNP_U8 i;
    for (i = 0U; i < length; i++)
    {
        dst[i] = src[i];
    }
}

static STNP_Result _enqueue(
    STNP_RuntimeJobType type,
    STNP_U8 key,
    STNP_U8 code,
    STNP_U16 result,
    STNP_ModuleHandle *module,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    STNP_U32 state;
    STNP_U8 index;
    STNP_RuntimeJob *job;

    if (length > STNP_PAYLOAD_MAX)
    {
        return STNP_ERR_LENGTH;
    }
    if ((payload == STNP_NULL) && (length > 0U))
    {
        return STNP_ERR_PARAM;
    }

    state = STNP_Runtime_Lock();
    index = g_free_head;
    if (index == STNP_RUNTIME_INDEX_NONE)
    {
        STNP_Runtime_Unlock(state);
        return STNP_ERR_BUFFER;
    }

    job = &g_jobs[index];
    g_free_head = job->next;
    job->next = STNP_RUNTIME_INDEX_NONE;
    job->type = (STNP_U8)type;
    job->key = key;
    job->code = code;
    job->result = result;
    job->length = length;
    job->module = module;
    _copy_payload(job->payload, payload, length);

    if (g_ready_tail == STNP_RUNTIME_INDEX_NONE)
    {
        g_ready_head = index;
        g_ready_tail = index;
    }
    else
    {
        g_jobs[g_ready_tail].next = index;
        g_ready_tail = index;
    }
    STNP_Runtime_Unlock(state);
    return STNP_OK;
}

STNP_Result STNP_Runtime_Init(void)
{
    STNP_U16 i;

    for (i = 0U; i < (STNP_U16)STNP_JOB_QUEUE_DEPTH; i++)
    {
        g_jobs[i].next = (STNP_U8)((i + 1U < (STNP_U16)STNP_JOB_QUEUE_DEPTH) ?
            (i + 1U) : STNP_RUNTIME_INDEX_NONE);
    }
    for (i = 0U; i < STNP_RUNTIME_KEY_COUNT; i++)
    {
        g_instance_busy[i] = 0U;
    }
    g_free_head = 0U;
    g_ready_head = STNP_RUNTIME_INDEX_NONE;
    g_ready_tail = STNP_RUNTIME_INDEX_NONE;
    return STNP_OK;
}

STNP_Result STNP_Runtime_EnqueueTask(
    STNP_U8 target,
    STNP_U8 code,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    STNP_ModuleHandle *module = STNP_NULL;
    STNP_Result result = STNP_Router_ResolveTask(target, code, &module);

    if (result != STNP_OK)
    {
        return result;
    }
    return _enqueue(
        STNP_RUNTIME_JOB_TASK,
        target,
        code,
        0U,
        module,
        payload,
        length
    );
}

STNP_Result STNP_Runtime_EnqueueNotify(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    return _enqueue(
        STNP_RUNTIME_JOB_NOTIFY,
        source,
        notify_code,
        result,
        STNP_NULL,
        payload,
        length
    );
}

static STNP_U8 _claim_runnable(STNP_RuntimeJob *out)
{
    STNP_U32 state;
    STNP_U8 previous;
    STNP_U8 current;
    STNP_U8 next;
    STNP_RuntimeJob *job;

    state = STNP_Runtime_Lock();
    previous = STNP_RUNTIME_INDEX_NONE;
    current = g_ready_head;

    while (current != STNP_RUNTIME_INDEX_NONE)
    {
        job = &g_jobs[current];
        if (g_instance_busy[job->key] == 0U)
        {
            next = job->next;
            if (previous == STNP_RUNTIME_INDEX_NONE)
            {
                g_ready_head = next;
            }
            else
            {
                g_jobs[previous].next = next;
            }
            if (g_ready_tail == current)
            {
                g_ready_tail = previous;
            }

            *out = *job;
            g_instance_busy[out->key] = 1U;

            job->next = g_free_head;
            g_free_head = current;
            STNP_Runtime_Unlock(state);
            return 1U;
        }
        previous = current;
        current = job->next;
    }

    STNP_Runtime_Unlock(state);
    return 0U;
}

static void _release_key(STNP_U8 key)
{
    STNP_U32 state = STNP_Runtime_Lock();
    g_instance_busy[key] = 0U;
    STNP_Runtime_Unlock(state);
}

STNP_Result STNP_Runtime_DispatchOne(void)
{
    STNP_RuntimeJob job;
    STNP_Result result;

    if (_claim_runnable(&job) == 0U)
    {
        return STNP_IDLE;
    }

    if (job.type == (STNP_U8)STNP_RUNTIME_JOB_TASK)
    {
        result = job.module->ops->task_handler(
            job.module,
            job.code,
            job.payload,
            job.length
        );
    }
    else
    {
        result = STNP_Notify_Dispatch(
            job.key,
            job.code,
            job.result,
            job.payload,
            job.length
        );
    }

    _release_key(job.key);
    return result;
}
