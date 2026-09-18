from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from types import SimpleNamespace
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    type_name: str
    min_value: int | None = None
    max_value: int | None = None


class CallbackSlot:
    def __init__(self) -> None:
        self.module_func: Callable[..., Any] | None = None
        self.instance_funcs: dict[int, Callable[..., Any]] = {}

    def register(self, fn: Callable[..., Any], instance_id: int | None = None):
        if instance_id is None:
            self.module_func = fn
        else:
            self.instance_funcs[int(instance_id)] = fn
        return fn

    def resolve(self, instance_id: int) -> Callable[..., Any] | None:
        return self.instance_funcs.get(int(instance_id), self.module_func)


class CommandDescriptor:
    def __init__(self, *, name: str, code: int, fields: tuple[FieldSpec, ...], payload_type, validate_hook: bool,
                 notify_on_done: int | None = None, notify_on_accept: int | None = None,
                 notify_on_reject: int | None = None):
        self.name = name
        self.code = int(code)
        self.fields = fields
        self.payload_type = payload_type
        self.payload_length = sum({"u8": 1, "u16": 2, "u32": 4, "i32": 4}[f.type_name] for f in fields)
        self.validate_hook = bool(validate_hook)
        self.notify_on_done = notify_on_done
        self.notify_on_accept = notify_on_accept
        self.notify_on_reject = notify_on_reject
        self._func = CallbackSlot()
        self._validate = CallbackSlot()
        self.module = None

    def _auto_notify(self, instance: "InstanceDefinition", code: int | None, result) -> None:
        if code is None or self.module is None or not self.module.auto_notify_enabled:
            return
        runtime = instance._runtime
        if runtime is None:
            raise RuntimeError(f"{instance.name}: STNP runtime is not bound")
        notification = instance.module.notify.by_code(code)
        if notification is None:
            raise RuntimeError(f"{self.module.name}.{self.name}: auto-notify code 0x{code:02X} not found")
        runtime.send_notify(notification.bind(instance)(result))

    def _wrap_func(self, fn):
        if self.module is None or not self.module.auto_notify_enabled:
            return fn

        @wraps(fn)
        def wrapped(instance, *args, **kwargs):
            self._auto_notify(instance, self.notify_on_accept, instance.module.OK)
            result = fn(instance, *args, **kwargs)
            self._auto_notify(instance, self.notify_on_done, instance.module.OK)
            return result

        return wrapped

    def _wrap_validate(self, fn):
        if self.module is None or not self.module.auto_notify_enabled:
            return fn

        @wraps(fn)
        def wrapped(instance, *args, **kwargs):
            result = fn(instance, *args, **kwargs)
            if int(result) != int(instance.module.OK):
                self._auto_notify(instance, self.notify_on_reject, result)
            return result

        return wrapped

    def func(self, fn):
        return self._func.register(self._wrap_func(fn))

    def validate(self, fn):
        if not self.validate_hook:
            raise RuntimeError(f"{self.module.name}.{self.name} does not enable validate_hook")
        return self._validate.register(self._wrap_validate(fn))

    def bind(self, instance: "InstanceDefinition") -> "BoundCommand":
        return BoundCommand(self, instance)

    def make_payload(self, *args, **kwargs):
        if not self.fields:
            if args or kwargs:
                raise TypeError(f"{self.module.name}.{self.name} has no payload")
            return None
        if len(args) == 1 and not kwargs and isinstance(args[0], self.payload_type):
            return args[0]
        if args:
            raise TypeError(f"{self.module.name}.{self.name}: use keyword fields or one payload object")
        return self.payload_type(**kwargs)


class NotificationDescriptor:
    def __init__(self, *, name: str, code: int, fields: tuple[FieldSpec, ...], payload_type):
        self.name = name
        self.code = int(code)
        self.fields = fields
        self.payload_type = payload_type
        self.payload_length = sum({"u8": 1, "u16": 2, "u32": 4, "i32": 4}[f.type_name] for f in fields)
        self._func = CallbackSlot()
        self.module = None

    def func(self, fn):
        return self._func.register(fn)

    def bind(self, instance: "InstanceDefinition") -> "BoundNotification":
        return BoundNotification(self, instance)

    def make_payload(self, *args, **kwargs):
        if not self.fields:
            if args or kwargs:
                raise TypeError(f"{self.module.name}.{self.name} has no payload")
            return None
        if len(args) == 1 and not kwargs and isinstance(args[0], self.payload_type):
            return args[0]
        if args:
            raise TypeError(f"{self.module.name}.{self.name}: use keyword fields or one payload object")
        return self.payload_type(**kwargs)


class DescriptorNamespace:
    def __init__(self, items):
        self._items = {item.name: item for item in items}
        for item in items:
            setattr(self, item.name, item)

    def by_code(self, code: int):
        for item in self._items.values():
            if item.code == int(code):
                return item
        return None

    def values(self):
        return tuple(self._items.values())


class ModuleDefinition:
    def __init__(self, *, name: str, results, commands, notifications, auto_notify_enabled: bool = False,
                 validator=None):
        self.name = name
        self.results = results
        self.auto_notify_enabled = bool(auto_notify_enabled)
        self.validator = validator
        self.cmd = DescriptorNamespace(commands)
        self.notify = DescriptorNamespace(notifications)
        for descriptor in (*commands, *notifications):
            descriptor.module = self
        for result in results:
            setattr(self, result.name, result)
        self.OK = getattr(results, "OK")

    def result(self, value: int):
        try:
            return self.results(int(value))
        except ValueError:
            return int(value)


@dataclass(frozen=True, slots=True)
class TaskSpec:
    instance: "InstanceDefinition"
    command: CommandDescriptor
    payload: Any | None


@dataclass(frozen=True, slots=True)
class NotifySpec:
    instance: "InstanceDefinition"
    notification: NotificationDescriptor
    result: int
    payload: Any | None


class BoundCommand:
    def __init__(self, descriptor: CommandDescriptor, instance: "InstanceDefinition"):
        self.descriptor = descriptor
        self.instance = instance

    def __call__(self, *args, **kwargs) -> TaskSpec:
        return TaskSpec(self.instance, self.descriptor, self.descriptor.make_payload(*args, **kwargs))

    def func(self, fn):
        return self.descriptor._func.register(self.descriptor._wrap_func(fn), self.instance.id)

    def validate(self, fn):
        if not self.descriptor.validate_hook:
            raise RuntimeError(f"{self.instance.name}.{self.descriptor.name} does not enable validate_hook")
        return self.descriptor._validate.register(self.descriptor._wrap_validate(fn), self.instance.id)


class BoundNotification:
    def __init__(self, descriptor: NotificationDescriptor, instance: "InstanceDefinition"):
        self.descriptor = descriptor
        self.instance = instance

    def __call__(self, result, *args, **kwargs) -> NotifySpec:
        return NotifySpec(
            self.instance,
            self.descriptor,
            int(result),
            self.descriptor.make_payload(*args, **kwargs),
        )

    def func(self, fn):
        return self.descriptor._func.register(fn, self.instance.id)


class BoundNamespace:
    def __init__(self, instance: "InstanceDefinition", source: DescriptorNamespace):
        self._instance = instance
        for item in source.values():
            setattr(self, item.name, item.bind(instance))


class InstanceDefinition:
    def __init__(self, *, name: str, id: int, module: ModuleDefinition):
        self.name = name
        self.id = int(id)
        self.module = module
        self._runtime = None
        self.cmd = BoundNamespace(self, module.cmd)
        self.task = self.cmd
        self.notify = BoundNamespace(self, module.notify)

    def __repr__(self) -> str:
        return f"<{self.module.name} instance {self.name} id=0x{self.id:02X}>"


@dataclass(frozen=True, slots=True)
class ProtocolDefinition:
    name: str
    version: str
    max_payload: int
    router_instance_max: int
    task_sof: tuple[int, int]
    notify_sof: tuple[int, int]
    seq_start: int
    seq_reserved: tuple[int, ...]
    crc_enabled: bool
    task_fixed_size: int
    notify_fixed_size: int
    seq_enabled: bool = False
    notify_dispatch_receive: bool = False
