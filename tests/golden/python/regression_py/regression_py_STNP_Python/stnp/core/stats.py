from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RuntimeStats:
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_frames: int = 0
    tx_frames: int = 0
    crc_errors: int = 0
    protocol_errors: int = 0
    dropped_frames: int = 0
    callback_errors: int = 0
