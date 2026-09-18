/**
 ******************************************************************************
 * @file    main.c
 * @brief   Generated demo using unified STNP structured send APIs.
 ******************************************************************************
 */

#include <stdio.h>

#include "../Instance/stnp_instances.h"
#include "transport_mock.h"

void Chassis_NotifyCallback(
    ChassisHandle *self,
    STNP_U8 notify_code,
    Chassis_Result result,
    const void *payload
)
{
    STNP_UNUSED(self);
    STNP_UNUSED(notify_code);
    STNP_UNUSED(payload);

    printf("[typed notify] result=%u\n", (unsigned int)result);
}

static void STNP_Demo_Pump(void)
{
    STNP_U8 i;
    for (i = 0U; i < 16U; i++)
    {
        STNP_Result process_result = STNP_Process();
        STNP_Result dispatch_result = STNP_Dispatch();
        if ((process_result == STNP_IDLE) && (dispatch_result == STNP_IDLE))
        {
            break;
        }
    }
}

int main(void)
{
    Chassis_MovePayload task_payload = {0};

    if ((STNP_Init(TransportMock_Write) != STNP_OK) ||
        (STNP_Instances_Init() != STNP_OK))
    {
        return 1;
    }

    Chassis_NotifyCallbackEnable(STNP_ENABLE);

    (void)STNP_Task_Send(
        STNP_INSTANCE_CHASSISMAIN_ID,
        CHASSIS_CMD_MOVE,
        &task_payload
    );

    (void)STNP_Notify_Send(
        STNP_INSTANCE_CHASSISMAIN_ID,
        CHASSIS_NOTIFY_DONE,
        CHASSIS_OK,
        STNP_NULL
    );

    STNP_Demo_Pump();

    printf("demo ok\n");
    return 0;
}
