from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class HandshakePayload:
    token: int
    def to_display(self) -> str:
        return " ".join((
            f"token={self.token}",
        ))

