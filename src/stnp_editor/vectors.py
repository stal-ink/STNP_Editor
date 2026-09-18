from __future__ import annotations

from stnp_editor.errors import InternalError
from stnp_editor.ir.models import FieldIR, ProjectIR


def encode_u16(value: int) -> list[int]:
    return [value & 0xFF, (value >> 8) & 0xFF]


def encode_i32(value: int) -> list[int]:
    v = value & 0xFFFFFFFF
    return [v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF]


def encode_field(field: FieldIR, value: int) -> list[int]:
    if field.type_name == "u8":
        return [value & 0xFF]
    if field.type_name == "u16":
        return encode_u16(value)
    if field.type_name in ("u32", "i32"):
        return encode_i32(value)
    raise InternalError("E9002", message=f"unsupported wire type: {field.type_name}")


def sample_value(field: FieldIR) -> int:
    if field.min_value is not None:
        return int(field.min_value)
    return 1


def crc16_modbus(data: list[int]) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
            crc &= 0xFFFF
    return crc


def build_task_bytes(
    ir: ProjectIR,
    *,
    seq: int,
    target: int,
    code: int,
    payload: list[int],
) -> list[int]:
    p = ir.protocol
    seq_bytes = encode_u16(seq) if p.seq_enabled else []
    frame = [
        p.task_sof[0],
        p.task_sof[1],
        *seq_bytes,
        target & 0xFF,
        code & 0xFF,
        len(payload) & 0xFF,
        *payload,
    ]
    if p.crc_enabled:
        crc = crc16_modbus(frame)
        frame.extend(encode_u16(crc))
    return frame


def build_notify_bytes(
    ir: ProjectIR,
    *,
    seq: int,
    source: int,
    notify_code: int,
    result: int,
    payload: list[int],
) -> list[int]:
    p = ir.protocol
    seq_bytes = encode_u16(seq) if p.seq_enabled else []
    frame = [
        p.notify_sof[0],
        p.notify_sof[1],
        *seq_bytes,
        source & 0xFF,
        notify_code & 0xFF,
        *encode_u16(result),
        len(payload) & 0xFF,
        *payload,
    ]
    if p.crc_enabled:
        crc = crc16_modbus(frame)
        frame.extend(encode_u16(crc))
    return frame


def hex_bytes(data: list[int]) -> str:
    return " ".join(f"{b:02X}" for b in data)


def build_vectors(ir: ProjectIR) -> dict[str, object]:
    vectors: list[dict[str, object]] = []
    for inst in ir.instances:
        mod = inst.module
        for cmd in mod.commands:
            payload: list[int] = []
            samples: dict[str, int] = {}
            for field in cmd.fields:
                value = sample_value(field)
                samples[field.name] = value
                payload.extend(encode_field(field, value))
            frame = build_task_bytes(
                ir,
                seq=1,
                target=inst.id_value,
                code=cmd.code,
                payload=payload,
            )
            vectors.append(
                {
                    "kind": "task",
                    "instance": inst.name,
                    "module": mod.name,
                    "command": cmd.name,
                    "target": inst.id_value,
                    "code": cmd.code,
                    "payload": samples,
                    "hex": hex_bytes(frame),
                }
            )
        for ntf in mod.notifications:
            payload = []
            samples = {}
            for field in ntf.fields:
                value = sample_value(field)
                samples[field.name] = value
                payload.extend(encode_field(field, value))
            frame = build_notify_bytes(
                ir,
                seq=1,
                source=inst.id_value,
                notify_code=ntf.code,
                result=0,
                payload=payload,
            )
            vectors.append(
                {
                    "kind": "notify",
                    "instance": inst.name,
                    "module": mod.name,
                    "notify": ntf.name,
                    "source": inst.id_value,
                    "notify_code": ntf.code,
                    "payload": samples,
                    "hex": hex_bytes(frame),
                }
            )
    return {
        "project": ir.project_name,
        "crc_enabled": ir.protocol.crc_enabled,
        "seq_enabled": ir.protocol.seq_enabled,
        "task_fixed_size": ir.protocol.task_fixed_size,
        "notify_fixed_size": ir.protocol.notify_fixed_size,
        "vectors": vectors,
    }
