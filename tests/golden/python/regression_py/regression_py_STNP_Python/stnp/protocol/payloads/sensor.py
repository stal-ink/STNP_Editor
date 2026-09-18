from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SetRatePayload:
    hz: int

@dataclass(frozen=True, slots=True)
class DataNotifyPayload:
    value: int

