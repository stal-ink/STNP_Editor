from __future__ import annotations

from dataclasses import dataclass

from .crc import crc16_modbus
from .errors import ProtocolError


@dataclass(frozen=True, slots=True)
class ParseError:
    reason: str    # "sof" | "len" | "crc"
    data: bytes


@dataclass(frozen=True, slots=True)
class TaskFrame:
    seq: int
    target: int
    code: int
    payload: bytes
    raw: bytes = b""


@dataclass(frozen=True, slots=True)
class NotifyFrame:
    seq: int
    source: int
    notify_code: int
    result: int
    payload: bytes
    raw: bytes = b""


def build_task(frame: TaskFrame, protocol) -> bytes:
    if len(frame.payload) > protocol.max_payload:
        raise ProtocolError("task payload exceeds max_payload")
    out = bytearray(protocol.task_sof)
    out += bytes((int(frame.target) & 0xFF, int(frame.code) & 0xFF, len(frame.payload)))
    out += frame.payload
    if protocol.crc_enabled:
        out += crc16_modbus(out).to_bytes(2, "little")
    return bytes(out)


def build_notify(frame: NotifyFrame, protocol) -> bytes:
    if len(frame.payload) > protocol.max_payload:
        raise ProtocolError("notify payload exceeds max_payload")
    out = bytearray(protocol.notify_sof)
    out += bytes((int(frame.source) & 0xFF, int(frame.notify_code) & 0xFF))
    out += int(frame.result).to_bytes(2, "little")
    out += bytes((len(frame.payload),))
    out += frame.payload
    if protocol.crc_enabled:
        out += crc16_modbus(out).to_bytes(2, "little")
    return bytes(out)


class StreamParser:
    """Streaming parser. Header slots follow the SEQ/CRC capability combination."""

    def __init__(self, protocol):
        self.protocol = protocol
        self.buffer = bytearray()
        self.crc_errors = 0
        self.protocol_errors = 0
        self.report_sof = False

    def _header_size(self, is_task: bool) -> int:
        return self.protocol.task_fixed_size if is_task else self.protocol.notify_fixed_size

    def feed(self, data: bytes) -> list[TaskFrame | NotifyFrame | ParseError]:
        self.buffer.extend(data)
        out: list[TaskFrame | NotifyFrame | ParseError] = []
        while True:
            if len(self.buffer) < 2:
                return out
            prefix = bytes(self.buffer[:2])
            is_task = prefix == bytes(self.protocol.task_sof)
            is_notify = prefix == bytes(self.protocol.notify_sof)
            if (not is_task) and (not is_notify):
                dropped = self.buffer[0]
                del self.buffer[0]
                if self.report_sof:
                    out.append(ParseError("sof", bytes([dropped])))
                continue
            header = self._header_size(is_task)
            if len(self.buffer) < header:
                return out
            payload_len = self.buffer[header - 1]
            if payload_len > self.protocol.max_payload:
                self.protocol_errors += 1
                out.append(ParseError("len", bytes(self.buffer[:header])))
                del self.buffer[0]
                continue
            crc_extra = 2 if self.protocol.crc_enabled else 0
            total = header + payload_len + crc_extra
            if len(self.buffer) < total:
                return out
            raw = bytes(self.buffer[:total])
            if crc_extra:
                got = int.from_bytes(raw[-2:], "little")
                expect = crc16_modbus(raw[:-2])
                if got != expect:
                    self.crc_errors += 1
                    out.append(ParseError("crc", bytes(self.buffer[:total])))
                    del self.buffer[0]
                    continue
            body = raw[:header + payload_len]
            payload = body[header:]
            if is_task:
                out.append(TaskFrame(
                    seq=0,
                    target=body[2], code=body[3], payload=payload, raw=raw,
                ))
            else:
                out.append(NotifyFrame(
                    seq=0,
                    source=body[2], notify_code=body[3],
                    result=int.from_bytes(body[4:6], "little"), payload=payload, raw=raw,
                ))
            del self.buffer[:total]
