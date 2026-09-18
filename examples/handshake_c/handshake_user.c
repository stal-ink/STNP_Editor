/**
 * @file handshake_user.c
 * @brief User-owned handshake state machine using unified STNP send APIs.
 *
 * This file supplies the LINK command implementations for the demo. The generated
 * Implementation/link_impl.c defines the same user hooks plus Link_ValidateGenerated();
 * run_demo.sh weakens the generated hook copies before linking so these strong symbols
 * win, while Link_ValidateGenerated() stays strong and must be linked.
 */
#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"

#include <stdio.h>

typedef enum
{
    APP_DISCONNECTED = 0,
    APP_CONNECTING,
    APP_ACCEPTED,
    APP_CONNECTED
} AppLinkState;

static AppLinkState g_state = APP_DISCONNECTED;
static STNP_U16 g_token = 0U;

static Link_Result App_ValidateConnectReq(
    LinkHandle *self,
    STNP_U8 cmd,
    const void *payload
)
{
    STNP_UNUSED(self);
    STNP_UNUSED(cmd);
    STNP_UNUSED(payload);

    return LINK_OK;
}

void Link_ConnectReq(
    LinkHandle *self,
    const Link_ConnectReqPayload *payload
)
{
    Link_ConnectAcceptPayload accept;

    STNP_UNUSED(self);

    if (payload == STNP_NULL)
    {
        return;
    }

    accept.token = payload->token;
    g_token = payload->token;

    (void)STNP_Notify_Send(
        STNP_INSTANCE_LINKPEER_ID,
        LINK_NOTIFY_CONNECT_ACCEPT,
        LINK_OK,
        &accept
    );
}

void Link_ConnectConfirm(
    LinkHandle *self,
    const Link_ConnectConfirmPayload *payload
)
{
    STNP_UNUSED(self);

    if ((payload != STNP_NULL) && (payload->token == g_token))
    {
        g_state = APP_CONNECTED;
    }
}

void Link_NotifyCallback(
    LinkHandle *self,
    STNP_U8 notify_code,
    Link_Result result,
    const void *payload
)
{
    Link_ConnectConfirmPayload confirm;
    const Link_ConnectAcceptPayload *accept =
        (const Link_ConnectAcceptPayload *)payload;

    STNP_UNUSED(self);

    if ((notify_code != LINK_NOTIFY_CONNECT_ACCEPT) ||
        (result != LINK_OK) ||
        (accept == STNP_NULL) ||
        (g_state != APP_CONNECTING) ||
        (accept->token != g_token))
    {
        return;
    }

    g_state = APP_ACCEPTED;
    confirm.token = accept->token;

    (void)STNP_Task_Send(
        STNP_INSTANCE_LINKPEER_ID,
        LINK_CMD_CONNECT_CONFIRM,
        &confirm
    );
}

static void App_PumpProtocol(void)
{
    unsigned i;
    for (i = 0U; i < 32U; i++)
    {
        STNP_Result pr = STNP_Process();
        STNP_Result dr = STNP_Dispatch();
        if ((pr == STNP_IDLE) && (dr == STNP_IDLE))
        {
            break;
        }
    }
}

int main(void)
{
    Link_ConnectReqPayload payload;

    if ((STNP_Init(TransportMock_Write) != STNP_OK) ||
        (STNP_Instances_Init() != STNP_OK))
    {
        return 1;
    }

    Link_SetValidate(LINK_CMD_CONNECT_REQ, App_ValidateConnectReq);
    Link_NotifyCallbackEnable(STNP_ENABLE);

    g_token = 0x1234U;
    g_state = APP_CONNECTING;
    payload.token = g_token;

    if (STNP_Task_Send(
            STNP_INSTANCE_LINKPEER_ID,
            LINK_CMD_CONNECT_REQ,
            &payload
        ) != STNP_OK)
    {
        return 2;
    }

    App_PumpProtocol();

    if (g_state != APP_CONNECTED)
    {
        return 3;
    }

    printf("user handshake ok: token=%u\n", (unsigned int)g_token);
    return 0;
}
