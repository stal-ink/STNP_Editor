from __future__ import annotations

from dataclasses import dataclass, field

TYPE_SIZES: dict[str, int] = {"u8": 1, "u16": 2, "u32": 4, "i32": 4}
TYPE_RANGES: dict[str, tuple[int, int]] = {
    "u8": (0, 0xFF), "u16": (0, 0xFFFF), "u32": (0, 0xFFFFFFFF),
    "i32": (-0x80000000, 0x7FFFFFFF),
}
C_TYPES: dict[str, str] = {
    "u8": "STNP_U8", "u16": "STNP_U16", "u32": "STNP_U32", "i32": "STNP_I32",
}


def to_pascal(name: str) -> str:
    """CHASSIS / MOVE / chassis_main / SensorFront -> Chassis / Move / ChassisMain / SensorFront."""
    parts = name.replace("-", "_").split("_")
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.isupper():
            out.append(part[:1].upper() + part[1:].lower())
        else:
            out.append(part[:1].upper() + part[1:])
    return "".join(out)


def to_snake_lower(name: str) -> str:
    return name.replace("-", "_").lower()


@dataclass
class FieldIR:
    name: str
    type_name: str
    c_type: str
    size: int
    min_value: int | None = None
    max_value: int | None = None
    declared_type: str = ""

    @property
    def needs_min_check(self) -> bool:
        """A configured ``min`` strictly above the base-type floor is meaningful.

        ``x < lo`` is always false because the wire type cannot hold smaller
        values, so emitting it is dead code (and trips ``-Wtype-limits`` under
        ``-Werror``).  Only a bound above ``lo`` can ever reject a payload.
        """
        lo, _ = TYPE_RANGES[self.type_name]
        return self.min_value is not None and self.min_value > lo

    @property
    def needs_max_check(self) -> bool:
        """A configured ``max`` strictly below the base-type ceiling is meaningful."""
        _, hi = TYPE_RANGES[self.type_name]
        return self.max_value is not None and self.max_value < hi


@dataclass
class CommonTypeIR:
    name: str
    kind: str
    base_type: str
    c_type: str
    size: int
    values: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class ReturnCodeIR:
    name: str
    value: int
    enum_member: str
    brief: str


@dataclass
class GlobalResultIR:
    name: str
    value: int
    enum_member: str
    brief: str


@dataclass
class NotificationIR:
    name: str
    pascal: str
    code: int
    macro_name: str
    fields: list[FieldIR]
    payload_length: int
    payload_struct: str | None
    decode_fn: str | None
    brief: str = ""


@dataclass
class CommandIR:
    name: str
    pascal: str
    code: int
    fields: list[FieldIR]
    payload_length: int
    payload_struct: str | None
    user_symbol: str
    user_brief: str
    user_description: str
    validate_hook: bool
    ops_member: str
    decode_fn: str
    doc_brief: str
    doc_detail: str
    notify_on_done: NotificationIR | None = None
    notify_on_accept: NotificationIR | None = None
    notify_on_reject: NotificationIR | None = None

    @property
    def has_auto_notify(self) -> bool:
        return any((self.notify_on_accept, self.notify_on_reject, self.notify_on_done))


@dataclass
class ModuleIR:
    name: str
    pascal: str
    snake: str
    auto_notify_enabled: bool
    dir_name: str
    header_guard: str
    handle_type: str
    ops_type: str
    commands: list[CommandIR]
    notifications: list[NotificationIR]
    return_codes: list[ReturnCodeIR]
    result_type: str
    result_ok: str
    notify_desc_type: str
    notify_table_var: str
    notify_count_var: str
    notify_dispatch_fn: str
    validator_typedef: str
    validator_setter: str
    notify_callback_fn: str
    notify_callback_enable_fn: str
    on_task_fn: str
    enabled: bool = True


@dataclass
class InstanceIR:
    name: str
    pascal: str
    macro: str
    module_name: str
    module: ModuleIR
    id_value: int
    handle_var: str
    api_prefix: str


@dataclass
class EmbeddedFileIR:
    path: str
    encoding: str
    content: str


@dataclass
class ProtocolIR:
    name: str
    version: str
    max_payload: int
    router_instance_max: int
    task_sof: tuple[int, int]
    notify_sof: tuple[int, int]
    seq_start: int
    seq_reserved: tuple[int, ...]
    task_fixed_size: int
    notify_fixed_size: int
    crc_enabled: bool
    seq_enabled: bool = False
    notify_dispatch_receive: bool = False

    @property
    def crc_tail_size(self) -> int:
        return 2 if self.crc_enabled else 0

    @property
    def max_frame_size(self) -> int:
        return max(self.task_fixed_size, self.notify_fixed_size) + self.max_payload + self.crc_tail_size

    @property
    def rx_ring_size(self) -> int:
        return 4 * self.max_frame_size


@dataclass
class ProjectIR:
    project_name: str
    protocol: ProtocolIR
    modules: list[ModuleIR]
    instances: list[InstanceIR]
    global_results: list[GlobalResultIR]
    emit_readme: bool
    emit_examples: bool
    build_system: str = "mdk_arm"
    sdks: tuple[str, ...] = field(default_factory=tuple)
    common_types: list[CommonTypeIR] = field(default_factory=list)
    embedded_files: list[EmbeddedFileIR] = field(default_factory=list)
    output_stem: str = ""
