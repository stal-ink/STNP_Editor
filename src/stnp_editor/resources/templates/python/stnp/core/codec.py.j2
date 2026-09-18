from __future__ import annotations

import struct
from dataclasses import fields as dataclass_fields, is_dataclass
from typing import Any

from .errors import ProtocolError

_FORMAT = {"u8": "B", "u16": "H", "u32": "I", "i32": "i"}
_LIMITS = {
    "u8": (0, 0xFF),
    "u16": (0, 0xFFFF),
    "u32": (0, 0xFFFFFFFF),
    "i32": (-0x80000000, 0x7FFFFFFF),
}


def validate_value(field, value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"{field.name}: expected integer-compatible value, got {value!r}") from exc
    lo, hi = _LIMITS[field.type_name]
    if number < lo or number > hi:
        raise ProtocolError(f"{field.name}: {number} out of {field.type_name} range {lo}..{hi}")
    if field.min_value is not None and number < field.min_value:
        raise ProtocolError(f"{field.name}: {number} < configured minimum {field.min_value}")
    if field.max_value is not None and number > field.max_value:
        raise ProtocolError(f"{field.name}: {number} > configured maximum {field.max_value}")
    return number


def encode_payload(descriptor, payload: Any | None) -> bytes:
    if not descriptor.fields:
        if payload is not None:
            raise ProtocolError(f"{descriptor.name}: command/notify has no payload")
        return b""
    if payload is None:
        raise ProtocolError(f"{descriptor.name}: payload is required")
    values = []
    for field in descriptor.fields:
        try:
            value = getattr(payload, field.name)
        except AttributeError as exc:
            raise ProtocolError(f"{descriptor.name}: payload missing field {field.name}") from exc
        values.append(validate_value(field, value))
    fmt = "<" + "".join(_FORMAT[field.type_name] for field in descriptor.fields)
    return struct.pack(fmt, *values)


def decode_payload(descriptor, raw: bytes) -> Any | None:
    if len(raw) != descriptor.payload_length:
        raise ProtocolError(
            f"{descriptor.name}: payload length {len(raw)} != expected {descriptor.payload_length}"
        )
    if not descriptor.fields:
        return None
    fmt = "<" + "".join(_FORMAT[field.type_name] for field in descriptor.fields)
    values = struct.unpack(fmt, raw)
    return descriptor.payload_type(**{field.name: value for field, value in zip(descriptor.fields, values)})
