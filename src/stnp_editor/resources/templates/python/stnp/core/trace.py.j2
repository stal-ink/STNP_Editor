from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

LOG = logging.getLogger("stnp.trace")


@dataclass(frozen=True, slots=True)
class TraceCmd:
    kind: str
    path: str
    owner: str
    instance: object
    descriptor: object
    result: object = None


class Debug:
    enabled = False
    trap = None
    def bp(self, site: str) -> None:
        if self.enabled and self.trap is not None:
            self.trap(site)


class Format:
    enabled = False
    commands: set[str] = set()
    notifications: set[str] = set()
    overrides: dict = {}
    sink = print

    def __call__(self, path: str):
        def deco(fn):
            self.overrides[path] = fn
            return fn
        return deco

    def should(self, cmd) -> bool:
        if self.enabled:
            return True
        if cmd.kind == "notify":
            return cmd.path in self.notifications
        return cmd.path in self.commands

    def maybe(self, cmd, payload) -> None:
        if not self.should(cmd):
            return
        if self.sink is None:
            return
        fn = self.overrides.get(cmd.path, default_format)
        try:
            text = fn(cmd, payload)
            if text:
                self.sink(text)
        except Exception:
            try:
                self.sink(f"STNP TRACE format failed: {cmd.path}")
            except Exception:
                pass


debug = Debug()
format = Format()


def default_format(cmd, payload) -> str:
    kind = "TASK" if cmd.kind == "task" else "NOTIFY"
    parts = [f"STNP {kind} {cmd.owner} {cmd.path}"]
    if cmd.kind == "notify" and cmd.result is not None:
        name = cmd.result.name if isinstance(cmd.result, IntEnum) else str(cmd.result)
        parts.append(f"result={name}")
    if payload is None:
        return " ".join(parts)
    if isinstance(payload, (bytes, bytearray)):
        if len(payload) == 0:
            return " ".join(parts)
        parts.append(bytes(payload).hex())
        return " ".join(parts)
    text = payload.to_display()
    if text:
        parts.append(text)
    return " ".join(parts)


def configure(*, debug_enabled=None, format_enabled=None, commands=None,
              notifications=None, sink=None, trap=None) -> None:
    if debug_enabled is not None:
        debug.enabled = bool(debug_enabled)
    if format_enabled is not None:
        format.enabled = bool(format_enabled)
    if commands is not None:
        format.commands = set(commands)
    if notifications is not None:
        format.notifications = set(notifications)
    if sink is not None:
        format.sink = sink
    if trap is not None:
        debug.trap = trap


def _known_paths() -> set[str] | None:
    try:
        from ..protocol.registry import REGISTRY
    except Exception:
        return None
    known: set[str] = set()
    for module in REGISTRY.modules.values():
        for command in module.cmd.values():
            known.add(f"{module.name}.{command.name}")
        for notification in module.notify.values():
            known.add(f"{module.name}.{notification.name}")
    return known


def _warn_unknown(names) -> None:
    known = _known_paths()
    if known is None:
        return
    for name in names:
        if name not in known:
            LOG.warning("unknown trace path %s", name)


def _apply_loaded(data: dict) -> None:
    trace_cfg = data.get("trace")
    if not isinstance(trace_cfg, dict):
        return
    debug_cfg = trace_cfg.get("debug")
    if isinstance(debug_cfg, dict) and "enabled" in debug_cfg:
        debug.enabled = bool(debug_cfg.get("enabled"))
    format_cfg = trace_cfg.get("format")
    if not isinstance(format_cfg, dict):
        return
    if "enabled" in format_cfg:
        format.enabled = bool(format_cfg.get("enabled"))
    if "commands" in format_cfg and format_cfg["commands"] is not None:
        commands = list(format_cfg["commands"])
        _warn_unknown(commands)
        format.commands = set(commands)
    if "notifications" in format_cfg and format_cfg["notifications"] is not None:
        notifications = list(format_cfg["notifications"])
        _warn_unknown(notifications)
        format.notifications = set(notifications)


def load(path: str | Path | None = None) -> None:
    import yaml

    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    env_path = os.environ.get("STNP_TRACE_CONFIG")
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend([
        Path.cwd() / "config" / "trace.yaml",
        Path(__file__).resolve().parents[2] / "config" / "trace.yaml",
    ])
    for candidate in candidates:
        if candidate.is_file():
            data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                _apply_loaded(data)
            return
