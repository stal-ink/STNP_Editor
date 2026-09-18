from enum import IntEnum

from stnp.core import CommandDescriptor, FieldSpec, ModuleDefinition, NotificationDescriptor
from ..payloads.link import (
    HandshakePayload,
)

class LinkResult(IntEnum):
    OK = 256
    REJECTED = 257

_commands = [
    CommandDescriptor(
        name='HANDSHAKE', code=1,
        fields=(FieldSpec('token', 'u16', 1, 65535),),
        payload_type=HandshakePayload,
        validate_hook=True,
        notify_on_done=1,
        notify_on_accept=2,
        notify_on_reject=3,
    ),
]

_notifications = [
    NotificationDescriptor(
        name='READY', code=1,
        fields=(),
        payload_type=None,
    ),
    NotificationDescriptor(
        name='ACCEPTED', code=2,
        fields=(),
        payload_type=None,
    ),
    NotificationDescriptor(
        name='REJECTED', code=3,
        fields=(),
        payload_type=None,
    ),
]


def validate_link(instance, code, payload):
    """Generated per-module validator, dispatched by command code.

    User validators registered with @Link.cmd.<COMMAND>.validate override this function.
    """
    if code == 1:
        if payload.token < 1:
            return LinkResult.REJECTED
        return LinkResult.OK
    return LinkResult.OK


Link = ModuleDefinition(
    name='LINK',
    results=LinkResult,
    commands=_commands,
    notifications=_notifications,
    auto_notify_enabled=False,
    validator=validate_link,
)
