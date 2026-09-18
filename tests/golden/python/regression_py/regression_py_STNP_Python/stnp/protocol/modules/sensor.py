from enum import IntEnum

from stnp.core import CommandDescriptor, FieldSpec, ModuleDefinition, NotificationDescriptor
from ..payloads.sensor import (
    SetRatePayload,
    DataNotifyPayload,
)

class SensorResult(IntEnum):
    OK = 512
    BUSY = 513

_commands = [
    CommandDescriptor(
        name='READ', code=1,
        fields=(),
        payload_type=None,
        validate_hook=False,
        notify_on_done=1,
        notify_on_accept=None,
        notify_on_reject=None,
    ),
    CommandDescriptor(
        name='SET_RATE', code=2,
        fields=(FieldSpec('hz', 'u16', 1, 1000),),
        payload_type=SetRatePayload,
        validate_hook=True,
        notify_on_done=None,
        notify_on_accept=None,
        notify_on_reject=2,
    ),
]

_notifications = [
    NotificationDescriptor(
        name='DATA', code=1,
        fields=(FieldSpec('value', 'u16', None, None),),
        payload_type=DataNotifyPayload,
    ),
    NotificationDescriptor(
        name='REJECTED', code=2,
        fields=(),
        payload_type=None,
    ),
]


def validate_sensor(instance, code, payload):
    """Generated per-module validator, dispatched by command code.

    User validators registered with @Sensor.cmd.<COMMAND>.validate override this function.
    """
    if code == 2:
        if not (1 <= payload.hz <= 1000):
            return SensorResult.BUSY
        return SensorResult.OK
    return SensorResult.OK


Sensor = ModuleDefinition(
    name='SENSOR',
    results=SensorResult,
    commands=_commands,
    notifications=_notifications,
    auto_notify_enabled=False,
    validator=validate_sensor,
)
