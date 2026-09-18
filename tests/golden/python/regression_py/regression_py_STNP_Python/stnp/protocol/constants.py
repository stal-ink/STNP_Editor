from stnp.core import ProtocolDefinition

PROTOCOL = ProtocolDefinition(
    name='STNP',
    version='2.3',
    max_payload=64,
    router_instance_max=8,
    task_sof=(170, 85),
    notify_sof=(170, 51),
    seq_start=1,
    seq_reserved=(0,),
    crc_enabled=True,
    task_fixed_size=5,
    notify_fixed_size=7,
    seq_enabled=False,
    notify_dispatch_receive=True,
)
