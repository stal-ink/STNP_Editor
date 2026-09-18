from __future__ import annotations

import threading
import time

from stnp.core import Transport


class MockSerial(Transport):
    """Thread-safe loopback serial transport for the generated tutorial."""

    def __init__(self):
        self._cv = threading.Condition()
        self._rx = bytearray()
        self._open = False

    def open(self) -> None:
        with self._cv:
            self._open = True

    def close(self) -> None:
        with self._cv:
            self._open = False
            self._cv.notify_all()

    def write(self, data: bytes) -> int:
        with self._cv:
            if not self._open:
                raise RuntimeError("mock serial is closed")
            self._rx.extend(data)
            self._cv.notify_all()
        return len(data)

    def read(self, size: int = 4096) -> bytes:
        with self._cv:
            if self._open and not self._rx:
                self._cv.wait(timeout=0.05)
            if not self._rx:
                return b""
            n = min(size, len(self._rx))
            out = bytes(self._rx[:n])
            del self._rx[:n]
            return out
