from __future__ import annotations

import sys
import time
from pathlib import Path

# Allows `python Example/main.py` directly from the generated tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stnp
from stnp.protocol import *
from mock_serial import MockSerial


# Module-level command implementations. Instance-specific decorators can override these.
@Link.cmd.HANDSHAKE.func
def on_link_handshake(self, payload):
    print("TASK", self.name, "LINK.HANDSHAKE", payload)

@Sensor.cmd.READ.func
def on_sensor_read(self):
    print("TASK", self.name, "SENSOR.READ")

@Sensor.cmd.SET_RATE.func
def on_sensor_set_rate(self, payload):
    print("TASK", self.name, "SENSOR.SET_RATE", payload)

@Link.cmd.HANDSHAKE.validate
def validate_link_handshake(self, payload):
    return Link.OK

@Link.notify.READY.func
def on_link_ready(self, result):
    print("NOTIFY", self.name, "LINK.READY", result)

@Sensor.notify.DATA.func
def on_sensor_data(self, result, payload):
    print("NOTIFY", self.name, "SENSOR.DATA", result, payload)


def _payload_kwargs(descriptor):
    return {
        field.name: (field.min_value if field.min_value is not None else 0)
        for field in descriptor.fields
    }


def main() -> None:
    mock = MockSerial()
    stnp.init(transport=mock)

    # Build a task set. Instance.task.CMD(...) only builds; stnp.task(...) sends the batch.
    batch = []
    for instance in list(REGISTRY.instances.values())[:4]:
        commands = instance.module.cmd.values()
        if not commands:
            continue
        command = commands[0]
        batch.append(command.bind(instance)(**_payload_kwargs(command)))
    if batch:
        stnp.task(*batch)

    # Send one notification through the same mock link when available.
    for instance in REGISTRY.instances.values():
        notifications = instance.module.notify.values()
        if notifications:
            notification = notifications[0]
            stnp.notify(notification.bind(instance)(instance.module.OK, **_payload_kwargs(notification)))
            break

    time.sleep(0.15)
    print("stats:", stnp.stats)
    stnp.shutdown()


if __name__ == "__main__":
    main()
