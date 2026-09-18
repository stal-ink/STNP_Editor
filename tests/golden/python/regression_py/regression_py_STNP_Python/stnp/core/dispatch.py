from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

LOG = logging.getLogger("stnp.dispatch")


class Dispatcher:
    def __init__(self, handler: Callable[[object], None], *, max_queue: int = 1024):
        self._handler = handler
        self._queue: queue.Queue[object] = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="stnp-dispatch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def put(self, frame: object) -> bool:
        try:
            self._queue.put_nowait(frame)
            return True
        except queue.Full:
            return False

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                continue
            self._handler(item)
