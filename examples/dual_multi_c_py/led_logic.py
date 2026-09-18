"""User-owned Led logic scaffold.

Created once by STNP Editor. Regeneration never overwrites or deletes this file.

The Python side of this example is the upper computer: it sends LED Tasks and
decodes STATE_CHANGED notifications, so no command implementation is required.
Copy this file into ``<generated>/User/`` and import it when the host also has
to answer LED commands (for example during a loopback test).
"""

from stnp.protocol import Led

# Uncomment and implement when needed:
# @Led.cmd.SET.func
# def led_set(self, payload):
#     pass

# @Led.cmd.SET.validate
# def validate_led_set(self, payload):
#     return Led.OK

# Uncomment and implement when needed:
# @Led.cmd.GET.func
# def led_get(self):
#     pass

# Uncomment and implement when needed:
# @Led.cmd.BLINK.func
# def led_blink(self, payload):
#     pass

# @Led.cmd.BLINK.validate
# def validate_led_blink(self, payload):
#     return Led.OK
