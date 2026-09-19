from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from stnp_editor.emit.python import emit_python
from stnp_editor.loader import build_project_from_data, load_build_data, load_project

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "fixtures" / "python" / "regression_py.stnp"
BUILD = ROOT / "fixtures" / "python" / "stnp.build.json"


def _load_demo_ir():
    return load_project(EXAMPLE, BUILD)


def _emit_demo_ir(ir, output: Path) -> Path:
    return emit_python(ir, output, load_build_data(BUILD))


def _subprocess_env(_tmp_path: Path) -> dict[str, str]:
    """Subprocess env for generated-package scripts. Needs real PyYAML (requirements.txt)."""
    return dict(os.environ)


def _trace_enabled_env(tmp_path: Path) -> dict[str, str]:
    """Subprocess env that forces ``trace.debug.enabled`` on via the documented hook.

    ``stnp.init()`` calls ``trace.load()``, and the generated ``config/trace.yaml``
    ships with debug disabled, so a programmatic ``configure(debug_enabled=True)``
    before init is overwritten by design -- the documented find order is explicit
    path -> ``STNP_TRACE_CONFIG`` -> cwd config -> generated config (see
    docs/06_guides/trace_and_breakpoints.md).  The trace tests need debug events, so
    they enable the documented environment override instead of relying on defaults.
    """
    cfg = tmp_path / "trace_enabled.yaml"
    cfg.write_text("trace:\n  debug:\n    enabled: true\n", encoding="utf-8")
    env = _subprocess_env(tmp_path)
    env["STNP_TRACE_CONFIG"] = str(cfg)
    return env


def test_python_emitter_tree_and_module_instance_split(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)

    assert out.name == "regression_py_STNP_Python"
    for rel in (
        "stnp/core/runtime.py",
        "stnp/core/trace.py",
        "stnp/sdk/uart/transport.py",
        "stnp/sdk/uart/uart.yaml",
        "stnp/protocol/protocol.yaml",
        "stnp/protocol/modules/link.py",
        "stnp/protocol/modules/sensor.py",
        "stnp/protocol/payloads/link.py",
        "stnp/protocol/instances.py",
        "config/stnp.yaml",
        "config/trace.yaml",
        "Example/mock_serial.py",
        "Example/main.py",
    ):
        assert (out / rel).is_file(), rel

    pyproject = (out / "pyproject.toml").read_text(encoding="utf-8")
    assert "PyYAML>=6,<7" in pyproject

    sensor = (out / "stnp/protocol/modules/sensor.py").read_text(encoding="utf-8")
    instances = (out / "stnp/protocol/instances.py").read_text(encoding="utf-8")
    assert "Sensor = ModuleDefinition" in sensor
    assert "SensorFront = InstanceDefinition" in instances
    assert "SensorRear = InstanceDefinition" in instances


def test_generated_python_example_runs(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    result = subprocess.run(
        [sys.executable, "Example/main.py"],
        cwd=out,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert "TASK LinkMain LINK.HANDSHAKE" in result.stdout
    assert "TASK SensorFront SENSOR.READ" in result.stdout
    assert "TASK SensorRear SENSOR.READ" in result.stdout
    assert "NOTIFY LinkMain LINK.READY" in result.stdout
    assert "crc_errors=0" in result.stdout


def test_task_set_uses_one_transport_write(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import LinkMain, SensorFront, SensorRear
from stnp.core import Transport

class T(Transport):
    def __init__(self): self.writes=[]
    def open(self): pass
    def close(self): pass
    def read(self, size=4096): return b""
    def write(self, data): self.writes.append(bytes(data)); return len(data)

t=T(); stnp.init(transport=t, warn_missing=False)
stnp.task(LinkMain.task.HANDSHAKE(token=1), SensorFront.task.READ(), SensorRear.task.READ())
stnp.shutdown()
assert len(t.writes) == 1, len(t.writes)
print(len(t.writes[0]))
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert int(result.stdout.strip()) > 0


def test_user_scaffold_is_create_once_and_never_overwritten(tmp_path: Path) -> None:
    build = load_build_data(BUILD)
    build["python"]["emit_user_scaffold"] = True
    ir = _load_demo_ir()
    out = emit_python(ir, tmp_path, build)
    user_file = out / "User/sensor_logic.py"
    assert user_file.is_file()
    user_file.write_text("# mine\n", encoding="utf-8")
    emit_python(ir, tmp_path, build)
    assert user_file.read_text(encoding="utf-8") == "# mine\n"


def test_generated_dynamic_and_decorator_apis(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys, time
sys.path.insert(0, r"%s")
import stnp
from stnp import Link, LinkMain
from Example.mock_serial import MockSerial
seen=[]
@Link.cmd.HANDSHAKE.func
def handshake(self, payload): seen.append((self.name, payload.token))
stnp.init(transport=MockSerial(), warn_missing=False)
stnp.task.LinkMain.HANDSHAKE(token=7)
stnp.task(LinkMain, Link.cmd.HANDSHAKE, token=8)
time.sleep(0.1)
stnp.shutdown()
assert seen == [("LinkMain", 7), ("LinkMain", 8)], seen
# 0.9 return-code partitioning: LINK is module 0, so its OK sits at 0x0100.
assert int(Link.OK) == 0x0100
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_instance_command_override_wins_over_module_default(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys, time
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront, SensorRear
from Example.mock_serial import MockSerial
seen=[]
@Sensor.cmd.READ.func
def read_default(self): seen.append(("default", self.name))
@SensorFront.cmd.READ.func
def read_front(self): seen.append(("front", self.name))
stnp.init(transport=MockSerial(), warn_missing=False)
stnp.task(SensorFront.task.READ(), SensorRear.task.READ())
time.sleep(0.1)
stnp.shutdown()
assert seen == [("front", "SensorFront"), ("default", "SensorRear")], seen
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_missing_implementation_check_reports_affected_instances(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
missing = stnp.check_implementations()
assert any("LINK.HANDSHAKE" in item and "LinkMain" in item for item in missing)
assert any("SENSOR.READ" in item and "SensorFront" in item and "SensorRear" in item for item in missing)
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def _python_auto_notify_ir():
    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    raw["modules"][0]["auto_notify_enabled"] = True
    return build_project_from_data(raw, load_build_data(BUILD), source_path=EXAMPLE)


def test_python_auto_notify_is_decorator_driven(tmp_path: Path) -> None:
    out = emit_python(_python_auto_notify_ir(), tmp_path, load_build_data(BUILD))
    model = (out / "stnp/core/model.py").read_text(encoding="utf-8")
    runtime = (out / "stnp/core/runtime.py").read_text(encoding="utf-8")
    assert "def _wrap_func" in model
    assert "def _wrap_validate" in model
    assert "command.notify_on_reject" not in runtime

    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import Link, LinkMain
from stnp.core import Transport
from stnp.core.frame import TaskFrame, StreamParser

class T(Transport):
    def __init__(self): self.writes=[]
    def open(self): pass
    def close(self): pass
    def read(self, size=4096): return b""
    def write(self, data): self.writes.append(bytes(data)); return len(data)

t=T(); stnp._runtime.transport=t
seen=[]
@Link.cmd.HANDSHAKE.validate
def validate(self, payload): return Link.OK
@Link.cmd.HANDSHAKE.func
def handler(self, payload): seen.append(payload.token)
stnp._runtime._dispatch_task(TaskFrame(1, LinkMain.id, Link.cmd.HANDSHAKE.code, b"\x07\x00"))
parser=StreamParser(stnp.PROTOCOL)
frames=[]
for raw in t.writes: frames.extend(parser.feed(raw))
assert seen == [7], seen
assert [f.notify_code for f in frames] == [Link.notify.ACCEPTED.code, Link.notify.READY.code]
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_python_auto_reject_is_validate_decorator_driven(tmp_path: Path) -> None:
    out = emit_python(_python_auto_notify_ir(), tmp_path, load_build_data(BUILD))
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import Link, LinkMain
from stnp.core import Transport
from stnp.core.frame import TaskFrame, StreamParser

class T(Transport):
    def __init__(self): self.writes=[]
    def open(self): pass
    def close(self): pass
    def read(self, size=4096): return b""
    def write(self, data): self.writes.append(bytes(data)); return len(data)

t=T(); stnp._runtime.transport=t
seen=[]
@Link.cmd.HANDSHAKE.validate
def validate(self, payload): return Link.REJECTED
@Link.cmd.HANDSHAKE.func
def handler(self, payload): seen.append(payload.token)
stnp._runtime._dispatch_task(TaskFrame(1, LinkMain.id, Link.cmd.HANDSHAKE.code, b"\x07\x00"))
parser=StreamParser(stnp.PROTOCOL)
frames=[]
for raw in t.writes: frames.extend(parser.feed(raw))
assert seen == [], seen
assert len(frames) == 1
assert frames[0].notify_code == Link.notify.REJECTED.code
assert frames[0].result == int(Link.REJECTED)
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_notify_dr_off_silences_typed_and_on_notify(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront
from stnp.core.frame import NotifyFrame

typed = []
raw = []

@Sensor.notify.DATA.func
def on_data(instance, result, payload):
    typed.append((instance.name, int(result), payload.value))

@stnp.on_notify
def on_any(*args):
    raw.append(args)

frame = NotifyFrame(1, SensorFront.id, Sensor.notify.DATA.code, int(Sensor.OK), b"\xef\xbe")

stnp.notify_dispatch_receive_disable()
assert stnp.notify_dispatch_receive_is_enabled() is False
stnp._runtime._dispatch_notify(frame)
assert len(typed) == 0, typed
assert len(raw) == 0, raw

typed.clear()
raw.clear()
stnp.notify_dispatch_receive_enable()
stnp._runtime._dispatch_notify(frame)
assert len(typed) == 1, typed
assert typed[0] == ("SensorFront", int(Sensor.OK), 0xBEEF)
assert len(raw) == 0, raw
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_trace_debug_default_silent_and_import_shape(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    runtime_src = (out / "stnp/core/runtime.py").read_text(encoding="utf-8")
    assert "from .trace import debug as trace_debug, format as trace_format" in runtime_src
    assert "import stnp" not in runtime_src
    assert "trace_format.maybe(" in runtime_src
    assert "trace_debug.bp(" in runtime_src
    init_src = (out / "stnp/__init__.py").read_text(encoding="utf-8")
    assert "trace.load(" in init_src
    assert (out / "config" / "trace.yaml").is_file()
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
hits = []
assert stnp.trace.debug.enabled is False
assert stnp.trace.format.enabled is False
stnp.trace.debug.trap = hits.append
stnp.trace.debug.bp("dispatch")
assert hits == []
stnp.trace.debug.trap = None
stnp.trace.debug.enabled = True
stnp.trace.debug.bp("dispatch")
assert hits == []
stnp.trace.configure(debug_enabled=True, trap=hits.append)
stnp.trace.debug.bp("dispatch")
assert hits == ["dispatch"]
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_trace_debug_legal_task_site_sequence(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys, time
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront
from stnp.core import Transport
from stnp.core.frame import TaskFrame, build_task
from stnp.protocol import PROTOCOL

class T(Transport):
    def __init__(self, chunk):
        self.chunk = chunk
        self.done = False
    def open(self): pass
    def close(self): pass
    def read(self, size=4096):
        if self.done:
            time.sleep(0.02)
            return b""
        self.done = True
        return self.chunk
    def write(self, data):
        return len(data)

seen = []
@Sensor.cmd.READ.func
def on_read(self):
    seen.append(self.name)

raw = build_task(TaskFrame(1, SensorFront.id, Sensor.cmd.READ.code, b""), PROTOCOL)
hits = []
stnp.trace.configure(debug_enabled=True, trap=hits.append)
stnp.init(transport=T(raw), warn_missing=False)
time.sleep(0.2)
stnp.shutdown()
assert seen == ["SensorFront"], seen
assert hits == ["rx_read", "parse_ok", "enqueue", "dispatch", "on_task"], hits
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_trace_enabled_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_trace_debug_parse_resync_per_parse_error(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    runtime_src = (out / "stnp/core/runtime.py").read_text(encoding="utf-8")
    assert "crc_before" not in runtime_src
    assert "proto_before" not in runtime_src
    script = r'''
import sys, time
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront
from stnp.core import Transport
from stnp.core.frame import TaskFrame, build_task
from stnp.protocol import PROTOCOL

class T(Transport):
    def __init__(self, chunks):
        self.chunks = list(chunks)
    def open(self): pass
    def close(self): pass
    def read(self, size=4096):
        if not self.chunks:
            time.sleep(0.02)
            return b""
        return self.chunks.pop(0)
    def write(self, data):
        return len(data)

header = PROTOCOL.task_fixed_size
len_fail = bytes([PROTOCOL.task_sof[0], PROTOCOL.task_sof[1], SensorFront.id, Sensor.cmd.READ.code, 65])
assert len(len_fail) == header
good = build_task(TaskFrame(1, SensorFront.id, Sensor.cmd.READ.code, b""), PROTOCOL)
bad_crc = bytearray(good)
bad_crc[-1] ^= 0xFF
noise = bytes(range(8))

hits = []
stnp.trace.configure(debug_enabled=True, trap=hits.append)
stnp.init(transport=T([len_fail, bytes(bad_crc), noise]), warn_missing=False)
time.sleep(0.3)
stnp.shutdown()
assert hits.count("parse_resync") == 2, hits
assert hits.count("parse_ok") == 0, hits
assert hits.count("on_task") == 0, hits
assert "rx_read" in hits
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_trace_enabled_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_trace_debug_on_notify_exclusive_once(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront
from stnp.core.frame import NotifyFrame

typed = []
raw = []
hits = []

@Sensor.notify.DATA.func
def on_data(instance, result, payload):
    typed.append(payload.value)

@stnp.on_notify
def on_any(*args):
    raw.append(args)

frame = NotifyFrame(1, SensorFront.id, Sensor.notify.DATA.code, int(Sensor.OK), b"\xef\xbe")
stnp.trace.configure(debug_enabled=True, trap=hits.append)

stnp.notify_dispatch_receive_enable()
hits.clear(); typed.clear(); raw.clear()
stnp._runtime._dispatch_notify(frame)
assert typed == [0xBEEF], typed
assert raw == []
assert hits.count("on_notify") == 1, hits
assert hits.count("dispatch") == 1, hits

stnp.notify_dispatch_receive_disable()
hits.clear(); typed.clear(); raw.clear()
stnp._runtime._dispatch_notify(frame)
assert typed == []
assert raw == []
assert hits == []

stnp._runtime._notify_callback = None
hits.clear(); typed.clear(); raw.clear()
stnp._runtime._dispatch_notify(frame)
assert typed == []
assert raw == []
assert hits == []
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_trace_configure_none_keeps_values(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
stnp.trace.configure(debug_enabled=True, commands=["LINK.HANDSHAKE"])
assert stnp.trace.debug.enabled is True
assert stnp.trace.format.commands == {"LINK.HANDSHAKE"}
stnp.trace.configure(debug_enabled=None)
assert stnp.trace.debug.enabled is True
stnp.trace.configure(commands=[])
assert stnp.trace.format.commands == set()
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_trace_init_loads_real_trace_yaml(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    default_yaml = (out / "config" / "trace.yaml").read_text(encoding="utf-8")
    assert "enabled: false" in default_yaml
    (out / "config" / "trace.yaml").write_text(
        "trace:\n"
        "  debug:\n"
        "    enabled: true\n"
        "  format:\n"
        "    enabled: true\n"
        "    commands: [SENSOR.READ]\n"
        "    notifications: [SENSOR.DATA]\n",
        encoding="utf-8",
    )
    script = r'''
import sys
sys.path.insert(0, r"%s")
import yaml
import stnp
from stnp.core import Transport

class T(Transport):
    def open(self): pass
    def close(self): pass
    def read(self, size=4096): return b""
    def write(self, data): return len(data)

assert yaml.__name__ == "yaml"
assert stnp.trace.debug.enabled is False
assert stnp.trace.format.enabled is False
stnp.init(transport=T(), warn_missing=False)
assert stnp.trace.debug.enabled is True
assert stnp.trace.format.enabled is True
assert stnp.trace.format.commands == {"SENSOR.READ"}
assert stnp.trace.format.notifications == {"SENSOR.DATA"}
stnp.shutdown()
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=out,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_trace_yaml_default_file_keeps_trace_off(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp.core import Transport

class T(Transport):
    def open(self): pass
    def close(self): pass
    def read(self, size=4096): return b""
    def write(self, data): return len(data)

stnp.init(transport=T(), warn_missing=False)
assert stnp.trace.debug.enabled is False, stnp.trace.debug.enabled
assert stnp.trace.format.enabled is False, stnp.trace.format.enabled
assert stnp.trace.format.commands == set()
assert stnp.trace.format.notifications == set()
stnp.shutdown()
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=out,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_unknown_frame_01_02_default_and_two_gate(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys, time
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront
from stnp.core import Transport
from stnp.core.frame import TaskFrame, build_task
from stnp.protocol import PROTOCOL

class T(Transport):
    def __init__(self, chunks):
        self.chunks = list(chunks)
    def open(self): pass
    def close(self): pass
    def read(self, size=4096):
        if not self.chunks:
            time.sleep(0.02)
            return b""
        return self.chunks.pop(0)
    def write(self, data):
        return len(data)

hits = []
@stnp.on_unknown_frame
def on_unknown(reason, data):
    hits.append((reason, bytes(data)))

assert stnp.unknown_frame_callback_is_enabled() is False
header = bytes([PROTOCOL.task_sof[0], PROTOCOL.task_sof[1], SensorFront.id, Sensor.cmd.READ.code, 65])
good = build_task(TaskFrame(1, SensorFront.id, Sensor.cmd.READ.code, b""), PROTOCOL)
bad_crc = bytearray(good)
bad_crc[-1] ^= 0xFF
bad_target = build_task(TaskFrame(1, 0x09, Sensor.cmd.READ.code, b""), PROTOCOL)

stnp.init(transport=T([header, bytes(bad_crc), bad_target]), warn_missing=False)
time.sleep(0.3)
stnp.shutdown()
assert hits == [], hits

stnp.unknown_frame_callback_enable()
assert stnp.unknown_frame_callback_is_enabled() is True
stnp._runtime._unknown_callback = None
hits.clear()
stnp.init(transport=T([header]), warn_missing=False)
time.sleep(0.2)
stnp.shutdown()
assert hits == [], hits

stnp._runtime.on_unknown_frame(on_unknown)
stnp.unknown_frame_callback_disable()
assert stnp.unknown_frame_callback_is_enabled() is False
hits.clear()
stnp.init(transport=T([header]), warn_missing=False)
time.sleep(0.2)
stnp.shutdown()
assert hits == [], hits
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_unknown_frame_03_crc_nested(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys, time
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront
from stnp.core import Transport
from stnp.core.frame import ParseError, StreamParser, TaskFrame, build_task
from stnp.protocol import PROTOCOL

class T(Transport):
    def __init__(self, chunk):
        self.chunk = chunk
        self.done = False
    def open(self): pass
    def close(self): pass
    def read(self, size=4096):
        if self.done:
            time.sleep(0.02)
            return b""
        self.done = True
        return self.chunk
    def write(self, data):
        return len(data)

header = PROTOCOL.task_fixed_size
len_fail = bytes([PROTOCOL.task_sof[0], PROTOCOL.task_sof[1], SensorFront.id, Sensor.cmd.READ.code, 65])
parser = StreamParser(PROTOCOL)
items = parser.feed(len_fail)
lens = [i for i in items if isinstance(i, ParseError) and i.reason == "len"]
assert len(lens) == 1
assert lens[0].data == len_fail
assert len(lens[0].data) == header

seen = []
@Sensor.cmd.READ.func
def on_read(self):
    seen.append(self.name)

hits = []
@stnp.on_unknown_frame
def on_unknown(reason, data):
    hits.append(reason)

stnp.unknown_frame_callback_enable()
good = build_task(TaskFrame(1, SensorFront.id, Sensor.cmd.READ.code, b""), PROTOCOL)
bad = bytearray(good)
bad[-1] ^= 0xFF
stnp.init(transport=T(bytes(bad) + good), warn_missing=False)
time.sleep(0.3)
stnp.shutdown()
assert hits == ["crc"], hits
assert seen == ["SensorFront"], seen
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_unknown_frame_04_unroutable_task(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys, time
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront
from stnp.core import Transport
from stnp.core.frame import TaskFrame, build_task
from stnp.protocol import PROTOCOL

class T(Transport):
    def __init__(self, chunk):
        self.chunk = chunk
        self.done = False
    def open(self): pass
    def close(self): pass
    def read(self, size=4096):
        if self.done:
            time.sleep(0.02)
            return b""
        self.done = True
        return self.chunk
    def write(self, data):
        return len(data)

seen = []
@Sensor.cmd.READ.func
def on_read(self):
    seen.append(self.name)

hits = []
@stnp.on_unknown_frame
def on_unknown(reason, data):
    hits.append((reason, bytes(data)))

stnp.unknown_frame_callback_enable()
raw = build_task(TaskFrame(1, 0x09, Sensor.cmd.READ.code, b""), PROTOCOL)
before = stnp.stats.callback_errors
stnp.init(transport=T(raw), warn_missing=False)
time.sleep(0.3)
stnp.shutdown()
assert seen == [], seen
assert [h[0] for h in hits] == ["task"], hits
assert hits[0][1] == raw
assert stnp.stats.callback_errors == before
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_unknown_frame_05_sof_slide(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys, time
sys.path.insert(0, r"%s")
import stnp
from stnp.core import Transport
from stnp.core.frame import ParseError, StreamParser
from stnp.protocol import PROTOCOL

noise = bytes(range(8))
parser = StreamParser(PROTOCOL)
parser.report_sof = False
assert [i for i in parser.feed(noise) if isinstance(i, ParseError)] == []
assert len(parser.buffer) == 1

parser = StreamParser(PROTOCOL)
parser.report_sof = True
items = parser.feed(noise)
sofs = [i for i in items if isinstance(i, ParseError)]
assert all(i.reason == "sof" for i in sofs)
assert len(sofs) == 7
assert [i.data for i in sofs] == [bytes([b]) for b in noise[:-1]]
assert len(parser.buffer) == 1

class T(Transport):
    def __init__(self, chunk):
        self.chunk = chunk
        self.done = False
    def open(self): pass
    def close(self): pass
    def read(self, size=4096):
        if self.done:
            time.sleep(0.02)
            return b""
        self.done = True
        return self.chunk
    def write(self, data):
        return len(data)

hits = []
@stnp.on_unknown_frame
def on_unknown(reason, data):
    hits.append(reason)

stnp.unknown_frame_callback_enable()
stnp._runtime.unknown_report_sof = False
rx_before = stnp.stats.rx_frames
stnp.init(transport=T(noise), warn_missing=False)
time.sleep(0.2)
stnp.shutdown()
assert hits == [], hits
assert stnp.stats.rx_frames == rx_before

hits.clear()
stnp._runtime.unknown_report_sof = True
stnp.unknown_frame_callback_enable()
stnp._runtime.on_unknown_frame(on_unknown)
stnp.init(transport=T(noise), warn_missing=False)
time.sleep(0.2)
stnp.shutdown()
assert hits == ["sof"] * 7, hits
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_unknown_frame_06_python_notify(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront
from stnp.core.frame import NotifyFrame, build_notify
from stnp.protocol import PROTOCOL

hits = []
raw = []
@stnp.on_unknown_frame
def on_unknown(reason, data):
    hits.append((reason, bytes(data)))

stnp.unknown_frame_callback_enable()
wire = build_notify(NotifyFrame(1, SensorFront.id, Sensor.notify.DATA.code, int(Sensor.OK), b"\xef\xbe"), PROTOCOL)
frame = NotifyFrame(1, SensorFront.id, Sensor.notify.DATA.code, int(Sensor.OK), b"\xef\xbe", raw=wire)
stnp._runtime._dispatch_notify(frame)
assert len(hits) == 1, hits
assert hits[0][0] == "notify"
assert hits[0][1] == wire

hits.clear()
@stnp.on_notify
def on_any(*args):
    raw.append(args)
stnp._runtime._dispatch_notify(frame)
assert hits == [], hits
assert len(raw) == 1, raw
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_unknown_frame_08_legal_not_reported(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront
from stnp.core.frame import NotifyFrame, TaskFrame

hits = []
typed_task = []
typed_notify = []
@stnp.on_unknown_frame
def on_unknown(reason, data):
    hits.append(reason)
stnp.unknown_frame_callback_enable()

@Sensor.cmd.READ.func
def on_read(self):
    typed_task.append(self.name)

@Sensor.notify.DATA.func
def on_data(instance, result, payload):
    typed_notify.append(payload.value)

stnp._runtime._dispatch_task(TaskFrame(1, SensorFront.id, Sensor.cmd.READ.code, b""))
stnp._runtime._dispatch_notify(NotifyFrame(1, SensorFront.id, Sensor.notify.DATA.code, int(Sensor.OK), b"\xef\xbe"))
assert typed_task == ["SensorFront"], typed_task
assert typed_notify == [0xBEEF], typed_notify
assert hits == [], hits
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_unknown_frame_09_callback_exception_isolated(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import Sensor, SensorFront
from stnp.core.frame import NotifyFrame

@stnp.on_unknown_frame
def on_unknown(reason, data):
    raise RuntimeError("user unknown boom")

stnp.unknown_frame_callback_enable()
before = stnp.stats.callback_errors
frame = NotifyFrame(1, SensorFront.id, Sensor.notify.DATA.code, int(Sensor.OK), b"\xef\xbe")
stnp._runtime._dispatch_notify(frame)
assert stnp.stats.callback_errors == before
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_trace_format_enabled_allowlist_and_decorator(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import Link, LinkMain, Sensor, SensorFront
from stnp.core.frame import TaskFrame

lines = []
@Link.cmd.HANDSHAKE.validate
def ok_hs(self, payload):
    return Link.OK
@Link.cmd.HANDSHAKE.func
def on_hs(self, payload):
    pass
@Sensor.cmd.READ.func
def on_read(self):
    pass

stnp.trace.configure(format_enabled=True, sink=lines.append)
stnp._runtime._dispatch_task(TaskFrame(1, LinkMain.id, Link.cmd.HANDSHAKE.code, b"\x07\x00"))
stnp._runtime._dispatch_task(TaskFrame(1, SensorFront.id, Sensor.cmd.READ.code, b""))
assert lines == [
    "STNP TASK LinkMain LINK.HANDSHAKE token=7",
    "STNP TASK SensorFront SENSOR.READ",
], lines

lines.clear()
stnp.trace.configure(format_enabled=False, commands=["LINK.HANDSHAKE"], sink=lines.append)
stnp._runtime._dispatch_task(TaskFrame(1, LinkMain.id, Link.cmd.HANDSHAKE.code, b"\x07\x00"))
stnp._runtime._dispatch_task(TaskFrame(1, SensorFront.id, Sensor.cmd.READ.code, b""))
assert lines == ["STNP TASK LinkMain LINK.HANDSHAKE token=7"], lines

lines.clear()
stnp.trace.configure(format_enabled=False, commands=[], sink=lines.append)
@stnp.trace.format("LINK.HANDSHAKE")
def fmt_hs(cmd, payload):
    return f"MOVE {payload.token}"
stnp._runtime._dispatch_task(TaskFrame(1, LinkMain.id, Link.cmd.HANDSHAKE.code, b"\x07\x00"))
assert lines == [], lines
assert "LINK.HANDSHAKE" not in stnp.trace.format.commands

stnp.trace.configure(format_enabled=True, sink=lines.append)
stnp._runtime._dispatch_task(TaskFrame(1, LinkMain.id, Link.cmd.HANDSHAKE.code, b"\x07\x00"))
assert lines == ["MOVE 7"], lines
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_trace_format_validate_and_sink_exception(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import Link, LinkMain
from stnp.core.frame import TaskFrame

ran = []
lines = []
@Link.cmd.HANDSHAKE.validate
def reject(self, payload):
    return Link.REJECTED
@Link.cmd.HANDSHAKE.func
def on_hs(self, payload):
    ran.append(payload.token)

stnp.trace.configure(format_enabled=True, sink=lines.append)
stnp._runtime._dispatch_task(TaskFrame(1, LinkMain.id, Link.cmd.HANDSHAKE.code, b"\x07\x00"))
assert ran == []
assert lines == []

@Link.cmd.HANDSHAKE.validate
def ok_hs(self, payload):
    return Link.OK
def boom(text):
    raise RuntimeError("sink")
stnp.trace.configure(format_enabled=True, sink=boom)
stnp._runtime._dispatch_task(TaskFrame(1, LinkMain.id, Link.cmd.HANDSHAKE.code, b"\x07\x00"))
assert ran == [7]
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_trace_format_notify_claimed_fallback_and_none_payload(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
import stnp
from stnp import Link, LinkMain, Sensor, SensorFront
from stnp.core.frame import NotifyFrame

lines = []
raw = []
typed = []
stnp.trace.configure(format_enabled=True, sink=lines.append)

@Sensor.notify.DATA.func
def on_data(instance, result, payload):
    typed.append(payload.value)
@stnp.on_notify
def on_any(*args):
    raw.append(args)

frame = NotifyFrame(1, SensorFront.id, Sensor.notify.DATA.code, int(Sensor.OK), b"\xef\xbe")
stnp._runtime._dispatch_notify(frame)
assert typed == [0xBEEF]
assert raw == []
assert lines == ["STNP NOTIFY SensorFront SENSOR.DATA result=OK value=48879"], lines

typed.clear(); raw.clear(); lines.clear()
stnp._runtime._notify_callback = on_any
Sensor.notify.DATA._func.module_func = None
Sensor.notify.DATA._func.instance_funcs.clear()
stnp._runtime._dispatch_notify(frame)
assert typed == []
assert len(raw) == 1
assert lines == ["STNP NOTIFY SensorFront SENSOR.DATA result=OK efbe"], lines

lines.clear(); raw.clear()
@Link.notify.READY.func
def on_ready(instance, result):
    typed.append("ready")
ready = NotifyFrame(1, LinkMain.id, Link.notify.READY.code, int(Link.OK), b"")
stnp._runtime._dispatch_notify(ready)
assert typed == ["ready"]
assert lines == ["STNP NOTIFY LinkMain LINK.READY result=OK"], lines
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"


def test_payload_to_display(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)
    script = r'''
import sys
sys.path.insert(0, r"%s")
from stnp.protocol.payloads.link import HandshakePayload
from stnp.protocol.payloads.sensor import DataNotifyPayload, SetRatePayload
assert HandshakePayload(token=7).to_display() == "token=7"
assert DataNotifyPayload(value=1234).to_display() == "value=1234"
assert SetRatePayload(hz=10).to_display() == "hz=10"
print("ok")
''' % str(out)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=_subprocess_env(tmp_path),
    )
    assert result.stdout.strip() == "ok"
