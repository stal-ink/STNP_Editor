"""User-owned Motor logic scaffold.

Created once by STNP Editor. Regeneration never overwrites or deletes this file.

The Python side of this example is the upper computer: it sends MOTOR Tasks and
decodes REACHED / ERROR notifications, so no command implementation is required.
Copy this file into ``<generated>/User/`` and import it when the host also has
to answer MOTOR commands (for example during a loopback test).
"""

from stnp.protocol import Motor

# Uncomment and implement when needed:
# @Motor.cmd.MOVE.func
# def motor_move(self, payload):
#     pass

# @Motor.cmd.MOVE.validate
# def validate_motor_move(self, payload):
#     return Motor.OK

# Uncomment and implement when needed:
# @Motor.cmd.STOP.func
# def motor_stop(self):
#     pass

# Uncomment and implement when needed:
# @Motor.cmd.SET_LIMIT.func
# def motor_set_limit(self, payload):
#     pass

# @Motor.cmd.SET_LIMIT.validate
# def validate_motor_set_limit(self, payload):
#     return Motor.OK
