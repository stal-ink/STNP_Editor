from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class UARTConfig:
    port: str | None = None
    baudrate: int = 115200
    timeout: float = 0.02
    write_timeout: float = 1.0


def load_uart_config(path: str | Path | None = None) -> UARTConfig:
    config_path = Path(path) if path is not None else Path(__file__).with_name("uart.yaml")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"UART config root must be a mapping: {config_path}")
    port = data.get("port")
    if port in (None, "", "auto", "AUTO"):
        port = None
    return UARTConfig(
        port=str(port) if port is not None else None,
        baudrate=int(data.get("baudrate", 115200)),
        timeout=float(data.get("timeout", 0.02)),
        write_timeout=float(data.get("write_timeout", 1.0)),
    )
