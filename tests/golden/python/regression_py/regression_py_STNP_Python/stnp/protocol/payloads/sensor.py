from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SetRatePayload:
    hz: int
    def to_display(self) -> str:
        return " ".join((
            f"hz={self.hz}",
        ))

@dataclass(frozen=True, slots=True)
class DataNotifyPayload:
    value: int
    def to_display(self) -> str:
        return " ".join((
            f"value={self.value}",
        ))

