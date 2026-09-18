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


def _subprocess_env(tmp_path: Path) -> dict[str, str]:
    """Run generated code against a minimal ``yaml`` stand-in.

    ``stnp/__init__.py`` imports PyYAML to read ``config/stnp.yaml``; the tests
    below pass explicit transports and never rely on that file, and PyYAML is not a
    test dependency. Shim ``yaml.safe_load`` to an empty mapping instead of skipping.
    """
    stub = tmp_path / "_yaml_stub"
    stub.mkdir(exist_ok=True)
    (stub / "yaml.py").write_text("def safe_load(text):\n    return {}\n", encoding="utf-8")
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(stub) if not existing else str(stub) + os.pathsep + existing
    return env


def test_python_emitter_tree_and_module_instance_split(tmp_path: Path) -> None:
    ir = _load_demo_ir()
    out = _emit_demo_ir(ir, tmp_path)

    assert out.name == "regression_py_STNP_Python"
    for rel in (
        "stnp/core/runtime.py",
        "stnp/sdk/uart/transport.py",
        "stnp/sdk/uart/uart.yaml",
        "stnp/protocol/protocol.yaml",
        "stnp/protocol/modules/link.py",
        "stnp/protocol/modules/sensor.py",
        "stnp/protocol/payloads/link.py",
        "stnp/protocol/instances.py",
        "config/stnp.yaml",
        "Example/mock_serial.py",
        "Example/main.py",
    ):
        assert (out / rel).is_file(), rel

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
