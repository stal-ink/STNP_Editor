from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from .codec import decode_payload, encode_payload
from .dispatch import Dispatcher
from .errors import ConfigurationError, ProtocolError, TransportError
from .frame import NotifyFrame, StreamParser, TaskFrame, build_notify, build_task
from .model import CommandDescriptor, InstanceDefinition, NotificationDescriptor, NotifySpec, TaskSpec
from .stats import RuntimeStats
from .transport import Transport

LOG = logging.getLogger("stnp")


class Runtime:
    """OS-oriented STNP runtime: caller-thread TX + RX thread + dispatch thread."""

    def __init__(self, protocol=None, registry=None):
        self.protocol = protocol
        self.registry = registry
        self.transport: Transport | None = None
        self.stats = RuntimeStats()
        self._write_lock = threading.Lock()
        self._seq_lock = threading.Lock()
        self._seq = int(protocol.seq_start) if protocol is not None else 1
        self._notify_dispatch_receive = bool(protocol.notify_dispatch_receive) if protocol is not None else False
        self._stop = threading.Event()
        self._rx_thread: threading.Thread | None = None
        self._dispatcher: Dispatcher | None = None
        self._notify_callback: Callable[..., object] | None = None
        self._parser: StreamParser | None = None
        self._bind_registry_runtime()

    def _bind_registry_runtime(self) -> None:
        if self.registry is None:
            return
        for instance in self.registry.instances.values():
            instance._runtime = self

    def configure(self, protocol, registry) -> None:
        self.protocol = protocol
        self.registry = registry
        self._bind_registry_runtime()
        self._seq = protocol.seq_start
        self._notify_dispatch_receive = bool(protocol.notify_dispatch_receive)

    def init(self, transport: Transport, *, queue_size: int = 1024, warn_missing: bool = True) -> "Runtime":
        if self.protocol is None or self.registry is None:
            raise ConfigurationError("protocol registry is not configured")
        self.shutdown()
        self.transport = transport
        # Transport dependency/configuration checks happen before threads start.
        self.transport.open()
        self._stop.clear()
        self._parser = StreamParser(self.protocol)
        self._dispatcher = Dispatcher(self._dispatch_frame, max_queue=queue_size)
        self._dispatcher.start()
        self._rx_thread = threading.Thread(target=self._rx_loop, name="stnp-rx", daemon=True)
        self._rx_thread.start()
        if warn_missing:
            self.check_implementations()
        return self

    def shutdown(self) -> None:
        self._stop.set()
        if self.transport is not None:
            try:
                self.transport.close()
            except Exception:
                LOG.exception("transport close failed")
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
        if self._dispatcher is not None:
            self._dispatcher.stop()
        self._rx_thread = None
        self._dispatcher = None
        self._parser = None

    def notify_dispatch_receive_enable(self) -> None:
        self._notify_dispatch_receive = True

    def notify_dispatch_receive_disable(self) -> None:
        self._notify_dispatch_receive = False

    def notify_dispatch_receive_is_enabled(self) -> bool:
        return self._notify_dispatch_receive

    def on_notify(self, fn):
        self._notify_callback = fn
        return fn

    def check_implementations(self) -> list[str]:
        missing: list[str] = []
        for module in self.registry.modules.values():
            instances = [i for i in self.registry.instances.values() if i.module is module]
            for command in module.cmd.values():
                affected = [i.name for i in instances if command._func.resolve(i.id) is None]
                if affected:
                    message = f"{module.name}.{command.name} not implemented; instances: {', '.join(affected)}"
                    missing.append(message)
                    LOG.warning(message)
        return missing

    def send_task(self, *specs: TaskSpec) -> int:
        if not specs:
            return 0
        frames = [self._build_task_spec(spec) for spec in specs]
        return self._write_many(frames)

    def send_task_dynamic(self, instance: InstanceDefinition, command, *args, **kwargs) -> int:
        desc = self._resolve_command(instance, command)
        return self.send_task(desc.bind(instance)(*args, **kwargs))

    def send_notify(self, *specs: NotifySpec) -> int:
        if not specs:
            return 0
        frames = [self._build_notify_spec(spec) for spec in specs]
        return self._write_many(frames)

    def send_notify_dynamic(self, instance: InstanceDefinition, notification, result, *args, **kwargs) -> int:
        desc = self._resolve_notification(instance, notification)
        return self.send_notify(desc.bind(instance)(result, *args, **kwargs))

    def _write_many(self, frames: list[bytes]) -> int:
        if self.transport is None:
            raise TransportError("stnp.init() has not configured a transport")
        raw = b"".join(frames)
        with self._write_lock:
            written = int(self.transport.write(raw))
        if written != len(raw):
            raise TransportError(f"short transport write: {written}/{len(raw)}")
        self.stats.tx_bytes += written
        self.stats.tx_frames += len(frames)
        return written

    def _next_seq(self) -> int:
        with self._seq_lock:
            current = self._seq
            while True:
                self._seq = 0 if self._seq == 0xFFFF else self._seq + 1
                if self._seq not in self.protocol.seq_reserved:
                    break
            return current

    def _build_task_spec(self, spec: TaskSpec) -> bytes:
        payload = encode_payload(spec.command, spec.payload)
        return build_task(TaskFrame(self._next_seq(), spec.instance.id, spec.command.code, payload), self.protocol)

    def _build_notify_spec(self, spec: NotifySpec) -> bytes:
        payload = encode_payload(spec.notification, spec.payload)
        return build_notify(
            NotifyFrame(self._next_seq(), spec.instance.id, spec.notification.code, int(spec.result), payload),
            self.protocol,
        )

    def _resolve_command(self, instance, command) -> CommandDescriptor:
        if isinstance(command, CommandDescriptor):
            if command.module is not instance.module:
                raise ProtocolError("command does not belong to instance module")
            return command
        if isinstance(command, str):
            try:
                return getattr(instance.module.cmd, command)
            except AttributeError as exc:
                raise ProtocolError(f"unknown command {instance.module.name}.{command}") from exc
        desc = instance.module.cmd.by_code(int(command))
        if desc is None:
            raise ProtocolError(f"unknown command code {command} for {instance.module.name}")
        return desc

    def _resolve_notification(self, instance, notification) -> NotificationDescriptor:
        if isinstance(notification, NotificationDescriptor):
            if notification.module is not instance.module:
                raise ProtocolError("notification does not belong to instance module")
            return notification
        if isinstance(notification, str):
            try:
                return getattr(instance.module.notify, notification)
            except AttributeError as exc:
                raise ProtocolError(f"unknown notification {instance.module.name}.{notification}") from exc
        desc = instance.module.notify.by_code(int(notification))
        if desc is None:
            raise ProtocolError(f"unknown notification code {notification} for {instance.module.name}")
        return desc

    def _rx_loop(self) -> None:
        parser = self._parser or StreamParser(self.protocol)
        while not self._stop.is_set():
            try:
                chunk = self.transport.read(4096) if self.transport is not None else b""
            except Exception:
                if not self._stop.is_set():
                    LOG.exception("transport read failed")
                return
            if not chunk:
                continue
            self.stats.rx_bytes += len(chunk)
            frames = parser.feed(chunk)
            self.stats.crc_errors += parser.crc_errors
            self.stats.protocol_errors += parser.protocol_errors
            parser.crc_errors = 0
            parser.protocol_errors = 0
            for frame in frames:
                self.stats.rx_frames += 1
                if self._dispatcher is None or not self._dispatcher.put(frame):
                    self.stats.dropped_frames += 1

    def _dispatch_frame(self, frame) -> None:
        try:
            if isinstance(frame, TaskFrame):
                self._dispatch_task(frame)
            else:
                self._dispatch_notify(frame)
        except Exception:
            self.stats.callback_errors += 1
            LOG.exception("STNP dispatch callback failed")

    def _dispatch_task(self, frame: TaskFrame) -> None:
        instance = self.registry.instances_by_id.get(frame.target)
        if instance is None:
            raise ProtocolError(f"unknown target instance 0x{frame.target:02X}")
        command = instance.module.cmd.by_code(frame.code)
        if command is None:
            raise ProtocolError(f"unknown command 0x{frame.code:02X} for {instance.module.name}")
        payload = decode_payload(command, frame.payload)
        if command.validate_hook:
            validator = command._validate.resolve(instance.id)
            if validator is not None:
                result = validator(instance, payload) if payload is not None else validator(instance)
            elif instance.module.validator is not None:
                result = instance.module.validator(instance, command.code, payload)
            else:
                result = instance.module.OK
            if int(result) != int(instance.module.OK):
                return
        fn = command._func.resolve(instance.id)
        if fn is None:
            LOG.warning("received unimplemented command %s.%s on %s", instance.module.name, command.name, instance.name)
            return
        if payload is None:
            fn(instance)
        else:
            fn(instance, payload)

    def _dispatch_notify(self, frame: NotifyFrame) -> None:
        if not self.notify_dispatch_receive_is_enabled():
            return
        instance = self.registry.instances_by_id.get(frame.source)
        if instance is None:
            if self._notify_callback is not None:
                self._notify_callback(frame.source, frame.notify_code, frame.result, frame.payload)
            return
        notification = instance.module.notify.by_code(frame.notify_code)
        if notification is None:
            if self._notify_callback is not None:
                self._notify_callback(instance, frame.notify_code, frame.result, frame.payload)
            return
        payload = decode_payload(notification, frame.payload)
        result = instance.module.result(frame.result)
        fn = notification._func.resolve(instance.id)
        if fn is not None:
            if payload is None:
                fn(instance, result)
            else:
                fn(instance, result, payload)
        if self._notify_callback is not None:
            self._notify_callback(instance, notification, result, payload)
