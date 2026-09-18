from __future__ import annotations

import importlib.metadata
from pathlib import Path

from ...core import Transport, TransportError
from .config import load_uart_config


class UARTTransport(Transport):
    def __init__(self, *, port=None, baudrate=None, config=None, timeout=None, write_timeout=None):
        self._config_path = config
        self._port_override = port
        self._baudrate_override = baudrate
        self._timeout_override = timeout
        self._write_timeout_override = write_timeout
        self._serial = None

    @staticmethod
    def check_pyserial() -> str:
        try:
            return importlib.metadata.version("pyserial")
        except importlib.metadata.PackageNotFoundError as exc:
            raise TransportError(
                "STNP UART SDK requires the 'pyserial' distribution. Install it with: pip install pyserial"
            ) from exc

    def open(self) -> None:
        # Do not use `import serial` as the dependency check: another distribution named
        # `serial` can exist. Verify the pyserial distribution first.
        self.check_pyserial()
        import serial
        from serial.tools import list_ports

        cfg = load_uart_config(self._config_path)
        port = self._port_override if self._port_override is not None else cfg.port
        baudrate = int(self._baudrate_override if self._baudrate_override is not None else cfg.baudrate)
        timeout = float(self._timeout_override if self._timeout_override is not None else cfg.timeout)
        write_timeout = float(self._write_timeout_override if self._write_timeout_override is not None else cfg.write_timeout)
        if port is None:
            ports = list(list_ports.comports())
            if not ports:
                raise TransportError("No serial ports detected. Specify port=... after connecting a device.")
            port = ports[0].device
            print(f"[STNP] Auto selected serial port: {port}, baudrate: {baudrate}")
        self._serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=write_timeout,
        )

    def close(self) -> None:
        serial_port = self._serial
        self._serial = None
        if serial_port is not None and getattr(serial_port, "is_open", False):
            serial_port.close()

    def read(self, size: int = 4096) -> bytes:
        if self._serial is None:
            return b""
        waiting = int(getattr(self._serial, "in_waiting", 0))
        return bytes(self._serial.read(max(1, min(size, waiting or 1))))

    def write(self, data: bytes) -> int:
        if self._serial is None:
            raise TransportError("UART transport is not open")
        # No per-frame flush: batched STNP frames remain a single high-frequency write.
        return int(self._serial.write(data))
