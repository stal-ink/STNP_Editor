from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from stnp_editor.emit.c import emit_c
from stnp_editor.emit.python import emit_python
from stnp_editor.errors import StnpError
from stnp_editor.loader import build_project_from_data, load_project
from stnp_editor.vectors import build_vectors

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "fixtures" / "C" / "regression_c.stnp"
BUILD = ROOT / "fixtures" / "C" / "stnp.build.json"
HANDSHAKE_DEMO = ROOT / "examples" / "handshake_c" / "handshake.stnp"
HANDSHAKE_BUILD = ROOT / "examples" / "handshake_c" / "stnp.build.json"
PY_BUILD = ROOT / "fixtures" / "python" / "stnp.build.json"


def _build_data(**overrides) -> dict:
    """regression_c build config as a plain dict, with optional top-level overrides."""
    data = json.loads(BUILD.read_text(encoding="utf-8"))
    for key, value in overrides.items():
        data[key] = value
    return data


def _write_build(tmp_path: Path, data: dict | None = None, name: str = "case.build.json") -> Path:
    """Write a build file; defaults to the regression_c build config."""
    path = tmp_path / name
    path.write_text(json.dumps(data if data is not None else _build_data()), encoding="utf-8")
    return path


def _companion_build(stnp_path: Path) -> Path:
    """Build file written next to a raw project by ``_write_raw_project``."""
    return stnp_path.with_name(f"{stnp_path.stem}.build.json")


def _write_raw_project(
    tmp_path: Path, raw: dict, name: str = "case.stnp", *, build: dict | None = None
) -> Path:
    """Write a raw .stnp plus its companion build file; return the .stnp path."""
    path = tmp_path / name
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    _write_build(tmp_path, build, f"{path.stem}.build.json")
    return path


def _auto_notify_ir(module_name: str = "CHASSIS"):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    module = next(item for item in raw["modules"] if item["name"] == module_name)
    module["auto_notify_enabled"] = True
    return build_project_from_data(raw, _build_data(), source_path=DEMO)


def _compile(
    out: Path,
    *,
    main: Path | None = None,
    extra_cflags: list[str] | None = None,
    extra_sources: list[str] | None = None,
    exe_name: str = "stnp_test",
) -> Path:
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    exe = out / exe_name
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c", "Implementation/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    if main is None:
        sources.extend(str(p) for p in sorted((out / "Examples").glob("*.c")))
    else:
        sources.append(str(out / "Examples" / "transport_mock.c"))
        sources.append(str(main))
    if extra_sources:
        sources.extend(extra_sources)
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *(extra_cflags or []), *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    return exe


def _write_harness_link_stubs(out: Path, *, raw_callback: bool = True) -> Path:
    """Minimal strong link units for harnesses that deliberately omit Implementation/.

    0.9 generates ``<Mod>_ValidateGenerated`` into ``Implementation/<mod>_impl.c``
    and the generated Module dispatch calls it directly.  A harness that overrides
    the user hooks itself cannot also compile ``<mod>_impl.c`` (duplicate strong
    hooks), so it supplies the generated validators here instead.  When
    ``raw_callback`` is true it also provides a strong ``STNP_Notify_Callback``:
    Core keeps only a weak default, and MinGW/PE does not export weak definitions
    across translation units, so ``stnp_instances.c`` would otherwise reference an
    undefined symbol.
    """
    stub = out / "harness_link_stubs.c"
    lines: list[str] = [
        '#include "Core/stnp.h"',
        '#include "Module/Chassis/chassis.h"',
        '#include "Module/Motor/motor.h"',
        '#include "Module/Sensor/sensor.h"',
        "",
        "Chassis_Result Chassis_ValidateGenerated(",
        "    ChassisHandle *self, STNP_U8 cmd, const void *payload)",
        "{",
        "    STNP_UNUSED(self);",
        "    STNP_UNUSED(cmd);",
        "    STNP_UNUSED(payload);",
        "    return CHASSIS_OK;",
        "}",
        "",
        "Motor_Result Motor_ValidateGenerated(",
        "    MotorHandle *self, STNP_U8 cmd, const void *payload)",
        "{",
        "    STNP_UNUSED(self);",
        "    STNP_UNUSED(cmd);",
        "    STNP_UNUSED(payload);",
        "    return MOTOR_OK;",
        "}",
        "",
        "Sensor_Result Sensor_ValidateGenerated(",
        "    SensorHandle *self, STNP_U8 cmd, const void *payload)",
        "{",
        "    STNP_UNUSED(self);",
        "    STNP_UNUSED(cmd);",
        "    STNP_UNUSED(payload);",
        "    return SENSOR_OK;",
        "}",
    ]
    if raw_callback:
        lines += [
            "",
            "void STNP_Notify_Callback(",
            "    STNP_U8 source, STNP_U8 notify_code, STNP_U16 result,",
            "    const STNP_U8 *payload, STNP_U8 length)",
            "{",
            "    STNP_UNUSED(source);",
            "    STNP_UNUSED(notify_code);",
            "    STNP_UNUSED(result);",
            "    STNP_UNUSED(payload);",
            "    STNP_UNUSED(length);",
            "}",
        ]
    stub.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stub


def _cmake_generator_args() -> list[str]:
    """Pick an explicit CMake generator when none is configured.

    On Windows the default generator is a Visual Studio one, and without VS
    installed CMake falls back to ``NMake Makefiles`` which needs ``nmake``.
    Prefer the MinGW generator when ``mingw32-make`` is available; an existing
    ``CMAKE_GENERATOR`` environment variable is honoured by CMake itself.
    """
    if os.environ.get("CMAKE_GENERATOR"):
        return []
    if os.name == "nt" and shutil.which("mingw32-make") is not None:
        return ["-G", "MinGW Makefiles"]
    return []


def test_load_regression_fixture():
    ir = load_project(DEMO, BUILD)
    assert ir.project_name == "regression_c"
    assert ir.protocol.seq_reserved == (0,)
    assert {m.name for m in ir.modules} == {"CHASSIS", "MOTOR", "SENSOR"}
    assert ir.instances[0].api_prefix == "STNP_ChassisMain"
    chassis = ir.modules[0]
    assert chassis.auto_notify_enabled is False
    assert chassis.commands[0].payload_struct == "Chassis_MovePayload"
    assert chassis.commands[0].user_symbol == "Chassis_Move"
    assert chassis.commands[0].notify_on_done is not None
    sensor = next(m for m in ir.modules if m.name == "SENSOR")
    data = next(n for n in sensor.notifications if n.name == "DATA")
    assert data.payload_struct == "Sensor_DataPayload"


def test_generate_typed_shape(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    chassis_h = (out / "Module" / "Chassis" / "chassis.h").read_text(encoding="utf-8")
    sensor_h = (out / "Module" / "Sensor" / "sensor.h").read_text(encoding="utf-8")
    instance_h = (out / "Instance" / "stnp_instances.h").read_text(encoding="utf-8")
    assert (out / "Embedded" / "docs" / "note.md").is_file()
    assert (out / ".stnp-manifest.json").is_file()
    assert "Chassis_MovePayload" in chassis_h
    assert "Chassis_TaskSend" not in chassis_h
    assert "Chassis_NotifySend" not in chassis_h
    assert "Chassis_MovePack" not in chassis_h
    assert "void Chassis_Move(" in chassis_h
    assert "Sensor_DataPayload" in sensor_h
    assert "Sensor_TaskSend" not in sensor_h
    assert "Sensor_NotifySend" not in sensor_h
    assert "Sensor_DataPack" not in sensor_h
    assert "Sensor_NotifyCallback(" in sensor_h
    assert "Sensor_NotifyCallbackIsEnabled(" in sensor_h
    assert "SetContext" not in chassis_h + instance_h
    assert "STNP_SensorFront_NotifyData" not in instance_h
    assert "STNP_SensorFront_Task" not in instance_h
    assert '#include "../Core/stnp_task.h"' in instance_h
    assert '#include "../Core/stnp_notify.h"' in instance_h
    assert '#include "../Module/Chassis/chassis.h"' in instance_h
    assert '#include "../Module/Motor/motor.h"' in instance_h
    assert '#include "../Module/Sensor/sensor.h"' in instance_h


def test_auto_notify_disabled_is_inert(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    source = (out / "Module" / "Chassis" / "chassis.c").read_text(encoding="utf-8")
    start = source.index("STNP_Result Chassis_OnTask(")
    end = source.index("static STNP_Result Chassis_TaskHandler(", start)
    body = source[start:end]
    assert "AutoNotify" not in source
    assert "CHASSIS_AUTO_NOTIFY" not in source
    assert "TASK_ACCEPTED" not in body
    assert "CHASSIS_NOTIFY_DONE" not in body
    assert "CHASSIS_NOTIFY_TASK_REJECTED" not in body


def test_auto_notify_uses_one_descriptor_table_without_command_wrappers(tmp_path: Path):
    out = emit_c(_auto_notify_ir(), tmp_path, _build_data())
    source = (out / "Module" / "Chassis" / "chassis.c").read_text(encoding="utf-8")
    assert source.count("g_chassis_auto_notify[]") == 1
    assert "Chassis_AutoNotifyFind" in source
    assert "Chassis_AutoNotifySend" in source
    assert "Wrapper" not in source
    assert "CHASSIS_NOTIFY_TASK_ACCEPTED" in source
    assert "CHASSIS_NOTIFY_TASK_REJECTED" in source
    assert "CHASSIS_NOTIFY_DONE" in source
    _compile(out)


def test_auto_notify_c_runtime_orders_accept_handler_done(tmp_path: Path):
    out = emit_c(_auto_notify_ir(), tmp_path, _build_data())
    harness = out / "auto_notify_order_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Core/stnp_frame.h"
#include "Instance/stnp_instances.h"

static STNP_U8 g_tx[3][STNP_FRAME_MAX_SIZE];
static STNP_U16 g_len[3];
static STNP_U8 g_count = 0U;

static STNP_Result CaptureWrite(const STNP_U8 *data, STNP_U16 length)
{
    STNP_U16 i;
    if ((data == STNP_NULL) || (g_count >= 3U) || (length > STNP_FRAME_MAX_SIZE))
    {
        return STNP_ERR_PARAM;
    }
    for (i = 0U; i < length; ++i)
    {
        g_tx[g_count][i] = data[i];
    }
    g_len[g_count] = length;
    ++g_count;
    if (g_count == 1U)
    {
        return STNP_Transport_Receive(data, length);
    }
    return STNP_OK;
}

int main(void)
{
    Chassis_MovePayload req = {1U, 50U};
    STNP_NotifyFrame accept_frame;
    STNP_NotifyFrame done_frame;

    if (STNP_Init(CaptureWrite) != STNP_OK) return 1;
    if (STNP_Instances_Init() != STNP_OK) return 2;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_MOVE, &req) != STNP_OK) return 3;
    if (STNP_Process() != STNP_OK) return 4;
    if (STNP_Dispatch() != STNP_OK) return 5;
    if (g_count != 3U) return 6;
    if (STNP_Frame_ParseNotify(g_tx[1], g_len[1], &accept_frame) != STNP_OK) return 7;
    if (STNP_Frame_ParseNotify(g_tx[2], g_len[2], &done_frame) != STNP_OK) return 8;
    if (accept_frame.notify_code != CHASSIS_NOTIFY_TASK_ACCEPTED) return 9;
    if (accept_frame.result != (STNP_U16)CHASSIS_OK) return 10;
    if (done_frame.notify_code != CHASSIS_NOTIFY_DONE) return 11;
    if (done_frame.result != (STNP_U16)CHASSIS_OK) return 12;
    return 0;
}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)


def test_min_max_is_generated_as_runtime_check_when_validate_hook(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    impl = (out / "Implementation" / "chassis_impl.c").read_text(encoding="utf-8")
    assert "Chassis_ValidateGenerated" in impl
    assert "typed->speed < 1" in impl
    assert "typed->speed > 100" in impl


def _bounds_fixture_raw() -> dict:
    """regression_c with MOVE payload rewritten to hit every min/max edge case."""
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["modules"][0]["commands"][0]["validate_hook"] = True
    raw["modules"][0]["commands"][0]["payload"] = [
        {"name": "a", "type": "u16", "min": 0},          # floor == base floor: dead
        {"name": "b", "type": "u16", "max": 65535},      # ceiling == base ceiling: dead
        {"name": "c", "type": "u8", "min": 0},           # u8 floor: dead
        {"name": "d", "type": "u8", "max": 255},         # u8 ceiling: dead
        {"name": "e", "type": "u16", "min": 1, "max": 100},  # both bounds real
    ]
    return raw


def test_validate_bounds_only_emit_when_range_is_reachable_in_c(tmp_path: Path):
    """gcc-free regression for 0.9 A-fix-1: never emit always-true/false bounds.

    A bound equal to the wire type's own floor/ceiling can never reject a value;
    emitting it is dead code and breaks ``-Werror=type-limits`` compilation.
    """
    project = _write_raw_project(tmp_path, _bounds_fixture_raw(), "bounds.stnp")
    out = emit_c(load_project(project, _companion_build(project)), tmp_path / "c", _build_data())
    impl = (out / "Implementation" / "chassis_impl.c").read_text(encoding="utf-8")

    assert "< 0)" not in impl
    assert "> 65535)" not in impl
    assert "> 255)" not in impl
    # Configured bounds inside the type range must survive.
    assert "< 1)" in impl
    assert "> 100)" in impl


def test_validate_bounds_only_emit_when_range_is_reachable_in_python(tmp_path: Path):
    """Python side must stay aligned with C: no dead comparisons are emitted."""
    py_build = json.loads(PY_BUILD.read_text(encoding="utf-8"))
    ir = build_project_from_data(_bounds_fixture_raw(), py_build, source_path=DEMO)
    out = emit_python(ir, tmp_path / "py", py_build)
    module = (out / "stnp" / "protocol" / "modules" / "chassis.py").read_text(encoding="utf-8")

    for field in ("a", "b", "c", "d"):
        assert f"payload.{field}" not in module
    assert "1 <= payload.e <= 100" in module


def test_validate_hook_false_is_not_generated(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    source = (out / "Module" / "Chassis" / "chassis.c").read_text(encoding="utf-8")
    impl = (out / "Implementation" / "chassis_impl.c").read_text(encoding="utf-8")

    assert "g_validate_move" in source
    assert "g_validate_stop" not in source
    # The generated validator only has a branch for validate_hook commands.
    assert "case CHASSIS_CMD_MOVE:" in impl
    assert "case CHASSIS_CMD_STOP:" not in impl
    setter = source[source.index("void Chassis_SetValidate"):source.index("void Chassis_NotifyCallbackEnable")]
    assert "CHASSIS_CMD_MOVE" in setter
    assert "CHASSIS_CMD_STOP" not in setter


def test_generated_tree_compiles_and_demo_runs(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    exe = _compile(out)
    run = subprocess.run([str(exe)], cwd=out, check=True, capture_output=True, text=True)
    assert "[typed notify]" in run.stdout
    assert "demo ok" in run.stdout


def test_instances_init_is_idempotent(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "reinit_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
int main(void)
{
    if (STNP_Init(TransportMock_Write) != STNP_OK) return 1;
    if (STNP_Instances_Init() != STNP_OK) return 2;
    if (STNP_Instances_Init() != STNP_OK) return 3;
    if (STNP_Instances_Init() != STNP_OK) return 4;
    return 0;
}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)


def test_generated_example_main_is_readably_formatted(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    source = (out / "Examples" / "main.c").read_text(encoding="utf-8")

    assert "; if" not in source
    assert "result=STNP" not in source
    assert "!=STNP" not in source
    assert "\n}\n\nint main(void)\n" in source
    assert "STNP_Result result;" not in source
    assert "(void)STNP_Task_Send(\n" in source
    assert "(void)STNP_Notify_Send(\n" in source
    assert "STNP_Transport_Receive(tx, tx_len) != STNP_OK" not in source
    assert "Pack(" not in source


def test_generated_module_header_is_readably_formatted(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    source = (out / "Module" / "Chassis" / "chassis.h").read_text(encoding="utf-8")

    assert "0x01U,    CHASSIS_CMD" not in source
    assert "0x01U,    CHASSIS_NOTIFY_DONE" not in source
    assert "0x0000U,    CHASSIS_PARAM" not in source
    assert "Chassis_TaskSend" not in source
    assert "Chassis_NotifySend" not in source


def test_user_code_merge(tmp_path: Path):
    ir = load_project(DEMO, BUILD)
    out = emit_c(ir, tmp_path, _build_data())
    impl = out / "Implementation" / "chassis_impl.c"
    text = impl.read_text(encoding="utf-8")
    assert "/* USER CODE BEGIN Includes */" in text
    assert "/* USER CODE BEGIN Private */" in text
    text = text.replace(
        "/* USER CODE BEGIN Includes */",
        "/* USER CODE BEGIN Includes */\n#include <stdio.h>", 1,
    ).replace(
        "/* USER CODE BEGIN Private */",
        "/* USER CODE BEGIN Private */\nstatic int g_custom_state = 1;", 1,
    ).replace(
        "/* USER CODE BEGIN Chassis_Stop */",
        "/* USER CODE BEGIN Chassis_Stop */\n    /* custom-stop */", 1,
    )
    impl.write_text(text, encoding="utf-8")
    emit_c(ir, tmp_path, _build_data())
    regenerated = impl.read_text(encoding="utf-8")
    assert "#include <stdio.h>" in regenerated
    assert "static int g_custom_state = 1;" in regenerated
    assert "/* custom-stop */" in regenerated


def test_notify_callback_has_global_user_regions(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    impl = out / "Implementation" / "stnp_notify_callback.c"
    text = impl.read_text(encoding="utf-8")
    assert '#include "../Instance/stnp_instances.h"' in text
    assert '#include "../Core/stnp.h"' not in text
    assert "/* USER CODE BEGIN Includes */" in text
    assert "/* USER CODE END Includes */" in text
    assert "/* USER CODE BEGIN Private */" in text
    assert "/* USER CODE END Private */" in text
    assert "/* USER CODE BEGIN STNP_Notify_Callback */" in text


def test_raw_notify_callback_can_send_without_extra_stnp_includes(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    impl = out / "Implementation" / "stnp_notify_callback.c"
    source = impl.read_text(encoding="utf-8")
    marker = "    /* USER CODE BEGIN STNP_Notify_Callback */\n"
    source = source.replace(
        marker,
        marker
        + "    (void)STNP_Notify_Send(STNP_INSTANCE_MOTORMAIN_ID, MOTOR_NOTIFY_DONE, MOTOR_OK, STNP_NULL);\n"
        + "    (void)STNP_Task_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_CMD_READ, STNP_NULL);\n",
        1,
    )
    impl.write_text(source, encoding="utf-8")
    _compile(out)


def test_regeneration_upgrades_old_implementation_layout(tmp_path: Path):
    ir = load_project(DEMO, BUILD)
    out = emit_c(ir, tmp_path, _build_data())
    impl = out / "Implementation" / "chassis_impl.c"
    text = impl.read_text(encoding="utf-8")
    text = text.replace(
        "\n/* USER CODE BEGIN Includes */\n\n/* USER CODE END Includes */\n",
        "",
        1,
    ).replace(
        "\n/* USER CODE BEGIN Private */\n\n/* USER CODE END Private */\n",
        "",
        1,
    ).replace(
        "/* USER CODE BEGIN Chassis_Stop */",
        "/* USER CODE BEGIN Chassis_Stop */\n    /* legacy-user-code */",
        1,
    )
    impl.write_text(text, encoding="utf-8")

    emit_c(ir, tmp_path, _build_data())
    regenerated = impl.read_text(encoding="utf-8")
    assert "/* USER CODE BEGIN Includes */" in regenerated
    assert "/* USER CODE BEGIN Private */" in regenerated
    assert "/* legacy-user-code */" in regenerated


def test_manifest_cleanup_and_orphan(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["protocol"]["features"]["crc"]["enabled"] = True
    stnp = tmp_path / "regen.stnp"; stnp.write_text(json.dumps(raw), encoding="utf-8")
    out = emit_c(load_project(stnp, BUILD), tmp_path / "out", _build_data())
    assert (out / "Core" / "stnp_crc.c").is_file()
    raw["protocol"]["features"]["crc"]["enabled"] = False
    raw["modules"] = [m for m in raw["modules"] if m["name"] != "MOTOR"]
    raw["instances"] = [i for i in raw["instances"] if i["module"] != "MOTOR"]
    # Return Code segments follow module position; SENSOR shifts to index 1.
    raw["modules"][1]["return_codes"][0]["value"] = 0x0200
    stnp.write_text(json.dumps(raw), encoding="utf-8")
    emit_c(load_project(stnp, BUILD), tmp_path / "out", _build_data())
    assert not (out / "Core" / "stnp_crc.c").exists()
    assert not (out / "Module" / "Motor").exists()
    assert (out / "Implementation" / "_orphaned" / "motor_impl.c").is_file()


def test_embedded_isolated(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["embedded_files"] = {"Implementation/chassis_impl.c": {"encoding":"text","content":"embedded-not-code\n"}}
    stnp = tmp_path / "embed.stnp"; stnp.write_text(json.dumps(raw), encoding="utf-8")
    out = emit_c(load_project(stnp, BUILD), tmp_path / "out", _build_data())
    assert "Chassis_Move" in (out / "Implementation" / "chassis_impl.c").read_text(encoding="utf-8")
    assert (out / "Embedded" / "Implementation" / "chassis_impl.c").read_text() == "embedded-not-code\n"


def test_payload_over_max_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8")); raw["protocol"]["max_payload"] = 1
    project = _write_raw_project(tmp_path, raw, "small.stnp")
    with pytest.raises(StnpError, match="超过 max_payload"):
        load_project(project, _companion_build(project))


def test_notify_payload_must_be_explicit(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8")); del raw["modules"][0]["notifications"][0]["payload"]
    project = _write_raw_project(tmp_path, raw, "missing.stnp")
    with pytest.raises(StnpError, match="schema 校验失败"):
        load_project(project, _companion_build(project))


def test_seq_range_and_reserved(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8")); raw["protocol"]["task"]["seq"]["start"] = 70000
    project = _write_raw_project(tmp_path, raw, "seq.stnp")
    with pytest.raises(StnpError, match="schema 校验失败"):
        load_project(project, _companion_build(project))
    raw["protocol"]["task"]["seq"]["start"] = 1; raw["protocol"]["task"]["seq"]["reserved"] = [0,1]
    project.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StnpError, match="属于保留集合"):
        load_project(project, _companion_build(project))


def test_distinct_sof_first_bytes(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8")); raw["protocol"]["notify"]["sof"] = [0xBB,0x33]
    project = _write_raw_project(tmp_path, raw, "sof.stnp")
    out = emit_c(load_project(project, _companion_build(project)), tmp_path / "out", _build_data())
    exe = _compile(out)
    run = subprocess.run([str(exe)], cwd=out, check=True, capture_output=True, text=True)
    assert "[typed notify]" in run.stdout


def test_transport_receive_preserves_first_error(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "error_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
int main(void) {
 STNP_U8 b[]={0xAAU,0x55U,1U,0U,0xFEU,1U,0U,0x99U};
 if(STNP_Init(TransportMock_Write)!=STNP_OK) return 2;
 if(STNP_Instances_Init()!=STNP_OK) return 3;
 if(STNP_Transport_Receive(b,(STNP_U16)sizeof(b))!=STNP_OK) return 4;
 /* LEN=0xFE exceeds max_payload, so the length check is the error Process preserves. */
 return STNP_Process()==STNP_ERR_LENGTH?0:5;
}''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)


def test_validator_reject_notify(tmp_path: Path):
    out = emit_c(_auto_notify_ir(), tmp_path, _build_data())
    harness = out / "validator_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Core/stnp_frame.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
static Chassis_Result RejectMove(ChassisHandle *self, STNP_U8 cmd, const void *payload){STNP_UNUSED(self);STNP_UNUSED(cmd);STNP_UNUSED(payload);return CHASSIS_BUSY;}
int main(void){Chassis_MovePayload req={1U,50U};const STNP_U8 *tx;STNP_U16 n;STNP_NotifyFrame f;
 if(STNP_Init(TransportMock_Write)!=STNP_OK||STNP_Instances_Init()!=STNP_OK)return 1;
 Chassis_SetValidate(CHASSIS_CMD_MOVE,RejectMove);
 if(STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID,CHASSIS_CMD_MOVE,&req)!=STNP_OK)return 3;
 if(STNP_Process()!=STNP_OK)return 4;
 if(STNP_Dispatch()!=STNP_OK)return 5;
 tx=TransportMock_GetLast(&n);
 if(STNP_Frame_ParseNotify(tx,n,&f)!=STNP_OK)return 6;
 return (f.notify_code==CHASSIS_NOTIFY_TASK_REJECTED&&f.result==(STNP_U16)CHASSIS_BUSY&&f.length==0U)?0:6;}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)

def test_vectors_roundtrip():
    payload = build_vectors(load_project(DEMO, BUILD))
    done = next(v for v in payload["vectors"] if v["kind"]=="notify" and v["notify"]=="DONE" and v["instance"]=="ChassisMain")
    assert done["hex"] == "AA 33 01 01 00 00 00"


def test_duplicate_instance_id_rejected(tmp_path: Path):
    raw=json.loads(DEMO.read_text(encoding="utf-8"));raw["instances"][1]["id"]=1
    project=_write_raw_project(tmp_path, raw, "d.stnp")
    with pytest.raises(StnpError,match="实例 ID 重复"):load_project(project, _companion_build(project))


def test_notify_on_missing_reference_rejected(tmp_path: Path):
    raw=json.loads(DEMO.read_text(encoding="utf-8"));raw["modules"][0]["commands"][0]["notify_on_done"]={"notify":"MISSING"}
    project=_write_raw_project(tmp_path, raw, "k.stnp")
    with pytest.raises(StnpError,match="引用的通知不存在"):load_project(project, _companion_build(project))


def test_payload_bearing_auto_reject_rejected(tmp_path: Path):
    raw=json.loads(DEMO.read_text(encoding="utf-8"));raw["modules"][0]["auto_notify_enabled"]=True;raw["modules"][0]["notifications"][2]["payload"]=[{"name":"detail","type":"u8"}]
    project=_write_raw_project(tmp_path, raw, "r.stnp")
    with pytest.raises(StnpError,match="零载荷通知"):load_project(project, _companion_build(project))


def test_c_keyword_payload_field_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["modules"][0]["commands"][0]["payload"][0]["name"] = "int"
    project = _write_raw_project(tmp_path, raw, "keyword.stnp")
    with pytest.raises(StnpError, match="非法 C 标识符"):
        load_project(project, _companion_build(project))


def test_builtin_common_type_collision_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["common_types"] = {"types": [{"name": "U8", "kind": "alias", "type": "u8"}]}
    project = _write_raw_project(tmp_path, raw, "ctype.stnp")
    with pytest.raises(StnpError, match="保留 STNP 类型冲突"):
        load_project(project, _companion_build(project))


def test_user_handshake_example_compiles_and_runs(tmp_path: Path):
    out = emit_c(load_project(HANDSHAKE_DEMO, HANDSHAKE_BUILD), tmp_path, _build_data())
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    exe = out / "handshake_user_test"
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.append(str(out / "Examples" / "transport_mock.c"))
    sources.append(str(ROOT / "examples" / "handshake_c" / "handshake_user.c"))
    # The demo links its own Link_ConnectReq/Confirm, so Implementation/link.c is
    # excluded. 0.9 moves the LINK validator into Implementation/, and Core keeps
    # the raw notify callback only as a weak default that MinGW/PE cannot export
    # across translation units; supply both as strong symbols for this harness.
    link_stub = out / "handshake_link_stub.c"
    link_stub.write_text(r'''#include "Core/stnp.h"
#include "Module/Link/link.h"

Link_Result Link_ValidateGenerated(
    LinkHandle *self,
    STNP_U8 cmd,
    const void *payload
)
{
    STNP_UNUSED(self);
    STNP_UNUSED(cmd);
    STNP_UNUSED(payload);
    return LINK_OK;
}

void STNP_Notify_Callback(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length
)
{
    STNP_UNUSED(source);
    STNP_UNUSED(notify_code);
    STNP_UNUSED(result);
    STNP_UNUSED(payload);
    STNP_UNUSED(length);
}
''', encoding="utf-8")
    sources.append(str(link_stub))
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    run = subprocess.run([str(exe)], cwd=out, check=True, capture_output=True, text=True)
    assert "user handshake ok" in run.stdout


def test_identical_task_notify_sof_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["protocol"]["notify"]["sof"] = raw["protocol"]["task"]["sof"][:]
    project = _write_raw_project(tmp_path, raw, "same_sof.stnp")
    with pytest.raises(StnpError, match="SOF 相同"):
        load_project(project, _companion_build(project))


def test_sequence_reserved_values_are_skipped(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["protocol"]["task"]["seq"] = {"type": "u16", "start": 1, "reserved": [0, 2]}
    raw["protocol"].setdefault("features", {})["seq"] = {"enabled": True}
    project = _write_raw_project(tmp_path, raw, "seqskip.stnp")
    out = emit_c(load_project(project, _companion_build(project)), tmp_path / "out", _build_data())
    harness = out / "seq_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Core/stnp_frame.h"
#include "Core/stnp_runtime.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"

/* Core keeps STNP_Runtime_Lock/Unlock only as weak defaults and MinGW/PE does
   not export weak definitions across translation units; enabling SEQ makes
   stnp_frame.c take the shared runtime lock. Single-threaded stubs keep this
   test focused on SequenceReserved reserve/skip semantics. */
STNP_U32 STNP_Runtime_Lock(void) { return 0U; }
void STNP_Runtime_Unlock(STNP_U32 state) { STNP_UNUSED(state); }

int main(void)
{
    const STNP_U8 *tx;
    STNP_U16 n;
    STNP_TaskFrame f;
    Chassis_MovePayload r = {1U, 1U};
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_MOVE, &r) != STNP_OK) return 2;
    tx = TransportMock_GetLast(&n);
    if ((STNP_Frame_ParseTask(tx, n, &f) != STNP_OK) || (f.seq != 1U)) return 3;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_MOVE, &r) != STNP_OK) return 4;
    tx = TransportMock_GetLast(&n);
    if ((STNP_Frame_ParseTask(tx, n, &f) != STNP_OK) || (f.seq != 3U)) return 5;
    return 0;
}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)

def test_command_names_c_normalization_collision_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["modules"][0]["commands"][0]["name"] = "FOO_BAR"
    raw["modules"][0]["commands"][1]["name"] = "FOO__BAR"
    project = _write_raw_project(tmp_path, raw, "cmd_collision.stnp")
    with pytest.raises(StnpError, match="命令名归一化后冲突"):
        load_project(project, _companion_build(project))


def test_notify_names_c_normalization_collision_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["modules"][0]["notifications"][0]["name"] = "FOO_BAR"
    raw["modules"][0]["notifications"][1]["name"] = "FOO__BAR"
    # Remove command metadata references so the test isolates the C-name collision.
    for cmd in raw["modules"][0]["commands"]:
        cmd.pop("notify_on_done", None)
        cmd.pop("notify_on_accept", None)
        cmd.pop("notify_on_reject", None)
    project = _write_raw_project(tmp_path, raw, "notify_collision.stnp")
    with pytest.raises(StnpError, match="通知名归一化后冲突"):
        load_project(project, _companion_build(project))


def test_common_type_core_typedef_collision_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["common_types"]["types"] = [{"name": "Result", "kind": "alias", "type": "u8"}]
    raw["modules"][0]["commands"][0]["payload"][1]["type"] = "u8"
    project = _write_raw_project(tmp_path, raw, "type_collision.stnp")
    with pytest.raises(StnpError, match="保留 STNP 类型冲突"):
        load_project(project, _companion_build(project))


def test_legacy_user_hook_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["modules"][0]["commands"][0]["user_hook"] = {"symbol":"LegacyCustomName","brief":"legacy"}
    project = _write_raw_project(tmp_path, raw, "hook_legacy.stnp")
    with pytest.raises(StnpError, match="schema 校验失败"):
        load_project(project, _companion_build(project))


def test_embedded_parent_escape_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["embedded_files"] = {"../Implementation/chassis_impl.c": {"encoding": "text", "content": "bad"}}
    project = _write_raw_project(tmp_path, raw, "escape.stnp")
    with pytest.raises(StnpError, match="嵌入文件路径不安全"):
        load_project(project, _companion_build(project))

def test_byte_send_uses_array_size_automatically(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "byte_send_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Core/stnp_frame.h"
#include "Examples/transport_mock.h"
int main(void)
{
    STNP_U8 raw[2] = {0x12U, 0x34U};
    const STNP_U8 *tx;
    STNP_U16 n;
    STNP_TaskFrame f;
    if (STNP_Init(TransportMock_Write) != STNP_OK) return 1;
    if (STNP_Task_SendBytes(1U, 0x55U, raw) != STNP_OK) return 2;
    tx = TransportMock_GetLast(&n);
    if (STNP_Frame_ParseTask(tx, n, &f) != STNP_OK) return 3;
    return (f.length == 2U && f.payload[0] == 0x12U && f.payload[1] == 0x34U) ? 0 : 4;
}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)


def test_byte_send_pointer_is_rejected_on_gcc_clang(tmp_path: Path):
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "byte_pointer_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
int main(void)
{
    STNP_U8 raw[2] = {0U, 0U};
    STNP_U8 *p = raw;
    return (int)STNP_Task_SendBytes(1U, 1U, p);
}
''', encoding="utf-8")
    proc = subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", str(harness), "-c", "-o", str(out / "byte_pointer_harness.o")],
        cwd=out, capture_output=True, text=True,
    )
    assert proc.returncode != 0

def test_vtl_algorithm_is_core_and_module_is_metadata_only(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    source = (out / "Module" / "Chassis" / "chassis.c").read_text(encoding="utf-8")
    header = (out / "Module" / "Chassis" / "chassis.h").read_text(encoding="utf-8")
    vtl_h = (out / "Core" / "stnp_vtl.h").read_text(encoding="utf-8")
    vtl_c = (out / "Core" / "stnp_vtl.c").read_text(encoding="utf-8")
    module_h = (out / "Module" / "stnp_module.h").read_text(encoding="utf-8")

    assert "STNP_VTL_Encode(" in vtl_h + vtl_c
    assert "STNP_VTL_Decode(" in vtl_h + vtl_c
    assert "g_chassis_task_vtl" in source
    assert "g_chassis_notify_vtl" in source
    assert "offsetof(Chassis_MovePayload, direction)" in source
    assert "Chassis_MoveDecode" not in source + header
    assert "Chassis_VTL_PackTask" not in source
    assert "Chassis_VTL_PackNotify" not in source
    assert "task_pack" not in module_h
    assert "notify_pack" not in module_h
    assert "Chassis_MovePack" not in source + header
    assert "Chassis_TaskSend" not in source + header
    assert "Chassis_NotifySend" not in source + header
    assert "STNP_Task_SendBytes" not in source



def test_structured_notify_uses_module_vtl(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "typed_notify_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Core/stnp_frame.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
int main(void)
{
    Sensor_DataPayload payload = {0x1234U};
    const STNP_U8 *tx;
    STNP_U16 n;
    STNP_NotifyFrame f;
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    if (STNP_Notify_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_NOTIFY_DATA, SENSOR_OK, &payload) != STNP_OK) return 2;
    tx = TransportMock_GetLast(&n);
    if (STNP_Frame_ParseNotify(tx, n, &f) != STNP_OK) return 3;
    return (f.length == 2U && f.payload[0] == 0x34U && f.payload[1] == 0x12U) ? 0 : 4;
}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)


def test_notify_byte_send_uses_array_size_automatically(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "notify_byte_send_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Core/stnp_frame.h"
#include "Examples/transport_mock.h"
int main(void)
{
    STNP_U8 raw[3] = {0x11U, 0x22U, 0x33U};
    const STNP_U8 *tx;
    STNP_U16 n;
    STNP_NotifyFrame f;
    if (STNP_Init(TransportMock_Write) != STNP_OK) return 1;
    if (STNP_Notify_SendBytes(7U, 0x44U, 0x1234U, raw) != STNP_OK) return 2;
    tx = TransportMock_GetLast(&n);
    if (STNP_Frame_ParseNotify(tx, n, &f) != STNP_OK) return 3;
    return (f.length == 3U && f.payload[0] == 0x11U && f.payload[2] == 0x33U) ? 0 : 4;
}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)



def test_core_vtl_decodes_task_payload_before_user_behavior(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "vtl_decode_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Core/stnp_frame.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
static STNP_U8 g_dir;
static STNP_U8 g_speed;
void Chassis_Move(ChassisHandle *self, const Chassis_MovePayload *payload)
{
    STNP_UNUSED(self);
    g_dir = payload->direction;
    g_speed = payload->speed;
}
int main(void)
{
    STNP_U8 raw[2] = {3U, 77U};
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    if (STNP_Task_SendBytes(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_MOVE, raw) != STNP_OK) return 2;
    if (STNP_Process() != STNP_OK) return 3;
    if ((g_dir != 0U) || (g_speed != 0U)) return 4;
    if (STNP_Dispatch() != STNP_OK) return 5;
    return (g_dir == 3U && g_speed == 77U) ? 0 : 6;
}
''', encoding="utf-8")
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    exe = out / "vtl_decode_test"
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.append(str(out / "Examples" / "transport_mock.c"))
    sources.append(str(harness))
    sources.append(str(_write_harness_link_stubs(out)))
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_common_enum_storage_is_wire_width_stable(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["common_types"]["types"] = [{
        "name": "Mode", "kind": "enum", "type": "u8",
        "values": [{"name": "A", "value": 1}, {"name": "B", "value": 2}],
    }]
    raw["modules"][0]["commands"][0]["payload"][1]["type"] = "Mode"
    project = _write_raw_project(tmp_path, raw, "enum.stnp")
    out = emit_c(load_project(project, _companion_build(project)), tmp_path / "out", _build_data())
    types_h = (out / "Platform" / "stnp_types.h").read_text(encoding="utf-8")
    assert "typedef STNP_U8 STNP_Mode;" in types_h
    assert "#define STNP_Mode_A ((STNP_Mode)1)" in types_h
    _compile(out)


@pytest.mark.parametrize(
    ("case", "symbol"),
    [
        ("return_payload_size", "CHASSIS_MOVE_PAYLOAD_SIZE"),
        ("return_cmd_none", "CHASSIS_CMD_NONE"),
        ("command_typedef", "Chassis_Command"),
        ("command_task_handler", "Chassis_TaskHandler"),
        ("command_validate_callback", "Chassis_ValidateCallback"),
        ("task_notify_payload", "Chassis_MovePayload"),
    ],
)
def test_generated_c_symbol_collisions_are_rejected(tmp_path: Path, case: str, symbol: str):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    chassis = raw["modules"][0]

    if case == "return_payload_size":
        chassis["return_codes"].append({"name": "MOVE_PAYLOAD_SIZE", "value": 0x01F0})
    elif case == "return_cmd_none":
        chassis["commands"] = []
        chassis["return_codes"].append({"name": "CMD_NONE", "value": 0x01F0})
    elif case == "command_typedef":
        chassis["commands"][0]["name"] = "COMMAND"
    elif case == "command_task_handler":
        chassis["commands"][0]["name"] = "TASK_HANDLER"
    elif case == "command_validate_callback":
        chassis["commands"][0]["name"] = "VALIDATE_CALLBACK"
    elif case == "task_notify_payload":
        chassis["notifications"][0]["name"] = "MOVE"
        chassis["notifications"][0]["payload"] = [{"name": "detail", "type": "u8"}]
        for cmd in chassis["commands"]:
            cmd.pop("notify_on_done", None)
            cmd.pop("notify_on_accept", None)
            cmd.pop("notify_on_reject", None)
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(case)

    project = _write_raw_project(tmp_path, raw, f"{case}.stnp")
    with pytest.raises(StnpError, match=rf"生成的 C 符号冲突: {symbol}"):
        load_project(project, _companion_build(project))


def test_common_enable_state_type_collision_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["common_types"]["types"] = [{"name": "EnableState", "kind": "alias", "type": "u8"}]
    raw["modules"][0]["commands"][0]["payload"][1]["type"] = "u8"
    project = _write_raw_project(tmp_path, raw, "enable_state_collision.stnp")
    with pytest.raises(StnpError, match="保留 STNP 类型冲突"):
        load_project(project, _companion_build(project))


def test_output_stem_parent_escape_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    project = _write_raw_project(tmp_path, raw, "output_escape.stnp")
    build = _build_data(output_stem="../escaped")
    build_path = _write_build(tmp_path, build, "escape.build.json")
    with pytest.raises(StnpError, match="unsafe output_stem"):
        load_project(project, build_path)


def test_invalid_base64_embedded_file_rejected(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["embedded_files"] = {"bad.bin": {"encoding": "base64", "content": "!!!!"}}
    project = _write_raw_project(tmp_path, raw, "invalid_base64.stnp")
    with pytest.raises(StnpError, match="Base64 内容无效"):
        load_project(project, _companion_build(project))


def test_base64_embedded_file_allows_whitespace(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["embedded_files"] = {"ok.bin": {"encoding": "base64", "content": "AQID\nBA=="}}
    project = _write_raw_project(tmp_path, raw, "base64_whitespace.stnp")
    out = emit_c(load_project(project, _companion_build(project)), tmp_path / "out", _build_data())
    assert (out / "Embedded" / "ok.bin").read_bytes() == b"\x01\x02\x03\x04"


def test_256_commands_keep_full_vtl_count(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    chassis = raw["modules"][0]
    chassis["commands"] = [
        {"name": f"C{i:03d}", "code": i, "payload": [], "validate_hook": False}
        for i in range(256)
    ]
    project = _write_raw_project(tmp_path, raw, "commands_256.stnp")
    out = emit_c(load_project(project, _companion_build(project)), tmp_path / "out", _build_data())
    module_h = (out / "Module" / "stnp_module.h").read_text(encoding="utf-8")
    module_c = (out / "Module" / "Chassis" / "chassis.c").read_text(encoding="utf-8")
    vtl_h = (out / "Core" / "stnp_vtl.h").read_text(encoding="utf-8")
    assert "STNP_U16 task_vtl_count;" in module_h
    assert "STNP_U16 count," in vtl_h
    assert "(STNP_U16)(sizeof(g_chassis_task_vtl)" in module_c

    harness = out / "vtl_256_commands_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
int main(void)
{
    const STNP_U8 *tx;
    STNP_U16 n;
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_C255, STNP_NULL) != STNP_OK) return 2;
    tx = TransportMock_GetLast(&n);
    return STNP_Transport_Receive(tx, n) == STNP_OK ? 0 : 3;
}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)


def test_256_notifications_keep_full_vtl_count(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    chassis = raw["modules"][0]
    chassis["commands"] = []
    chassis["notifications"] = [
        {"name": f"N{i:03d}", "code": i, "payload": []}
        for i in range(256)
    ]
    project = _write_raw_project(tmp_path, raw, "notifications_256.stnp")
    out = emit_c(load_project(project, _companion_build(project)), tmp_path / "out", _build_data())
    module_h = (out / "Module" / "stnp_module.h").read_text(encoding="utf-8")
    module_c = (out / "Module" / "Chassis" / "chassis.c").read_text(encoding="utf-8")
    assert "STNP_U16 notify_vtl_count;" in module_h
    assert "(STNP_U16)(sizeof(g_chassis_notify_vtl)" in module_c

    harness = out / "vtl_256_notifications_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
int main(void)
{
    const STNP_U8 *tx;
    STNP_U16 n;
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    if (STNP_Notify_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_NOTIFY_N255, CHASSIS_OK, STNP_NULL) != STNP_OK) return 2;
    tx = TransportMock_GetLast(&n);
    return STNP_Transport_Receive(tx, n) == STNP_OK ? 0 : 3;
}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)



def test_emit_c_rejects_mutated_unsafe_output_stem(tmp_path: Path):
    ir = load_project(DEMO, BUILD)
    ir.output_stem = "../escaped"
    with pytest.raises(StnpError, match="unsafe output_stem"):
        emit_c(ir, tmp_path / "chosen", _build_data())


def test_generated_demo_hides_manual_mock_receive(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    main_c = (out / "Examples" / "main.c").read_text(encoding="utf-8")
    mock_c = (out / "Examples" / "transport_mock.c").read_text(encoding="utf-8")
    mock_h = (out / "Examples" / "transport_mock.h").read_text(encoding="utf-8")

    assert "TransportMock_GetLast" not in main_c
    assert "STNP_Transport_Receive" not in main_c
    assert "STNP_Task_Send(" in main_c
    assert "STNP_Notify_Send(" in main_c
    assert "STNP_Transport_Receive(" in mock_c
    assert "TransportMock_Loopback" not in mock_c + mock_h


def test_multi_instance_module_has_no_ambiguous_default_id(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    chassis_h = (out / "Module" / "Chassis" / "chassis.h").read_text(encoding="utf-8")
    sensor_h = (out / "Module" / "Sensor" / "sensor.h").read_text(encoding="utf-8")
    instance_h = (out / "Instance" / "stnp_instances.h").read_text(encoding="utf-8")

    # 0.9 deleted the single-instance convenience ID macro; only the instance
    # registry macros remain.
    assert "#define CHASSIS_ID" not in chassis_h
    assert "#define SENSOR_ID" not in sensor_h
    assert "#define STNP_INSTANCE_CHASSISMAIN_ID 0x01U" in instance_h
    assert "#define STNP_INSTANCE_SENSORFRONT_ID 0x03U" in instance_h


def test_module_name_cannot_collide_with_core_namespace(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["modules"][0]["name"] = "STNP"
    raw["instances"][0]["module"] = "STNP"
    project = _write_raw_project(tmp_path, raw, "module_stnp_collision.stnp")

    with pytest.raises(StnpError, match=r"生成的 C 符号冲突: STNP_(OK|Result)"):
        load_project(project, _companion_build(project))


def test_common_type_cannot_collide_with_platform_macro(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["common_types"]["types"].append(
        {"name": "NULL", "kind": "alias", "type": "u8"}
    )
    project = _write_raw_project(tmp_path, raw, "common_null_collision.stnp")

    with pytest.raises(StnpError, match=r"生成的 C 符号冲突: STNP_NULL"):
        load_project(project, _companion_build(project))


def test_crc_bad_outer_frame_resyncs_to_nested_valid_notify(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["protocol"]["features"]["crc"]["enabled"] = True
    project = _write_raw_project(tmp_path, raw, "crc_nested_resync.stnp")
    out = emit_c(load_project(project, _companion_build(project)), tmp_path / "out", _build_data())

    harness = out / "crc_nested_resync_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"

static STNP_U8 g_tx[STNP_NOTIFY_FIXED_SIZE + STNP_PAYLOAD_MAX + STNP_CRC_SIZE];
static STNP_U16 g_tx_len = 0U;
static STNP_U8 g_notify_count = 0U;

static STNP_Result CaptureWrite(const STNP_U8 *data, STNP_U16 length)
{
    STNP_U16 i;
    if (length > (STNP_U16)sizeof(g_tx)) return STNP_ERR_LENGTH;
    for (i = 0U; i < length; i++) g_tx[i] = data[i];
    g_tx_len = length;
    return STNP_OK;
}

void STNP_Notify_Callback(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    STNP_UNUSED(source);
    STNP_UNUSED(notify_code);
    STNP_UNUSED(result);
    STNP_UNUSED(payload);
    STNP_UNUSED(length);
    g_notify_count++;
}

int main(void)
{
    STNP_U8 nested[64];
    STNP_U16 i;
    STNP_U16 total;
    STNP_U8 outer_payload_len;
    STNP_Result result;

    if ((STNP_Init(CaptureWrite) != STNP_OK) ||
        (STNP_Instances_Init() != STNP_OK)) return 1;

    if (STNP_Notify_Send(
            STNP_INSTANCE_SENSORFRONT_ID,
            SENSOR_NOTIFY_DATA,
            SENSOR_OK,
            STNP_NULL) != STNP_ERR_PARAM)
    {
        /* DATA has a payload; use a zero-payload Chassis notify instead. */
    }

    if (STNP_Notify_Send(
            STNP_INSTANCE_CHASSISMAIN_ID,
            CHASSIS_NOTIFY_DONE,
            CHASSIS_OK,
            STNP_NULL) != STNP_OK) return 2;

    if ((g_tx_len < 2U) || ((STNP_U16)(7U + g_tx_len) > (STNP_U16)sizeof(nested))) return 3;

    /* Fake outer Task: need = 7 + payload + CRC(2) = 7 + valid_notify_len. */
    outer_payload_len = (STNP_U8)(g_tx_len - 2U);
    nested[0] = STNP_TASK_HEADER0;
    nested[1] = STNP_TASK_HEADER1;
    nested[2] = 0U;
    nested[3] = 0U;
    nested[4] = STNP_INSTANCE_CHASSISMAIN_ID;
    nested[5] = CHASSIS_CMD_MOVE;
    nested[6] = outer_payload_len;
    for (i = 0U; i < g_tx_len; i++) nested[7U + i] = g_tx[i];
    total = (STNP_U16)(7U + g_tx_len);

    result = STNP_Transport_Receive(nested, total);
    if (result != STNP_OK) return 4;
    result = STNP_Process();
    if (result == STNP_OK || result == STNP_IDLE) return 5; /* bad outer CRC reported in Process */
    if (STNP_Process() != STNP_OK) return 6; /* nested valid Notify recovered */
    if (g_notify_count != 0U) return 7;
    if (STNP_Dispatch() != STNP_OK) return 8;
    return g_notify_count == 1U ? 0 : 9;
}
''', encoding="utf-8")

    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    exe = out / "crc_nested_resync_test"
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c", "Implementation/*.c"):
        for source in sorted(out.glob(pattern)):
            if source.name != "stnp_notify_callback.c":
                sources.append(str(source))
    sources.append(str(harness))
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_user_business_source_has_global_send_api_without_extra_stnp_includes(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    impl = out / "Implementation" / "chassis_impl.c"
    source = impl.read_text(encoding="utf-8")

    assert '#include "../Instance/stnp_instances.h"' in source
    assert '#include "../Module/Chassis/chassis.h"' not in source

    marker = "/* USER CODE BEGIN Chassis_Stop */\n"
    injection = (
        marker
        + "    STNP_UNUSED(self);\n"
        + "    (void)STNP_Notify_Send(STNP_INSTANCE_MOTORMAIN_ID, MOTOR_NOTIFY_DONE, MOTOR_OK, STNP_NULL);\n"
        + "    (void)STNP_Task_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_CMD_READ, STNP_NULL);\n"
    )
    source = source.replace(marker + "    STNP_UNUSED(self);\n", injection, 1)
    impl.write_text(source, encoding="utf-8")

    _compile(out)


def test_emit_examples_defaults_false_when_omitted(tmp_path: Path):
    build = _build_data(c={"build_system": "mdk_arm"})
    build_path = _write_build(tmp_path, build, "no_examples_default.build.json")

    ir = load_project(DEMO, build_path)
    assert ir.emit_examples is False
    out = emit_c(ir, tmp_path / "out", build)
    assert not (out / "Examples").exists()


def test_keil_c_object_basenames_are_unique(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    sources = [p for p in out.rglob("*.c") if "Embedded" not in p.parts]
    names = [p.name.casefold() for p in sources]
    assert len(names) == len(set(names))
    assert (out / "Module" / "Chassis" / "chassis.c").is_file()
    assert (out / "Implementation" / "chassis_impl.c").is_file()
    assert not (out / "Module" / "Chassis" / "chassis_module.c").exists()


def test_module_impl_naming_avoids_old_keil_collision(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["modules"].append({
        "enabled": True,
        "name": "CHASSIS_MODULE",
        "return_codes": [{"name": "OK", "value": 0x0400}],
        "commands": [{"name": "PING", "code": 10, "validate_hook": False, "payload": []}],
        "notifications": [],
    })
    raw["instances"].append({"name": "chassis_module_1", "module": "CHASSIS_MODULE", "id": 7})
    project = _write_raw_project(tmp_path, raw, "naming.stnp")

    out = emit_c(load_project(project, _companion_build(project)), tmp_path / "out", _build_data())
    assert (out / "Module" / "ChassisModule" / "chassis_module.c").is_file()
    assert (out / "Implementation" / "chassis_module_impl.c").is_file()
    names = [p.name.casefold() for p in out.rglob("*.c") if "Embedded" not in p.parts]
    assert len(names) == len(set(names))


def test_063_renames_062_sources_and_preserves_user_code(tmp_path: Path):
    ir = load_project(DEMO, BUILD)
    out = emit_c(ir, tmp_path, _build_data())

    # Simulate an existing 0.6.2 generated tree.
    new_framework = out / "Module" / "Chassis" / "chassis.c"
    old_framework = out / "Module" / "Chassis" / "chassis_module.c"
    new_framework.replace(old_framework)

    new_impl = out / "Implementation" / "chassis_impl.c"
    text = new_impl.read_text(encoding="utf-8").replace(
        "/* USER CODE BEGIN Private */\n",
        "/* USER CODE BEGIN Private */\nstatic int keep_me = 1;\n",
        1,
    )
    new_impl.write_text(text, encoding="utf-8")
    old_impl = out / "Implementation" / "chassis.c"
    new_impl.replace(old_impl)

    manifest_path = out / ".stnp-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        if entry["path"] == "Module/Chassis/chassis.c":
            entry["path"] = "Module/Chassis/chassis_module.c"
        elif entry["path"] == "Implementation/chassis_impl.c":
            entry["path"] = "Implementation/chassis.c"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    emit_c(ir, tmp_path, _build_data())
    assert not old_framework.exists()
    assert new_framework.is_file()
    assert not old_impl.exists()
    assert new_impl.is_file()
    assert "static int keep_me = 1;" in new_impl.read_text(encoding="utf-8")


def test_sdk_defaults_empty_and_does_not_emit(tmp_path: Path):
    build = _build_data()
    build.pop("sdks", None)
    build_path = _write_build(tmp_path, build, "sdk_default.build.json")

    ir = load_project(DEMO, build_path)
    assert ir.sdks == ()
    out = emit_c(ir, tmp_path / "out", build)
    assert not (out / "SDK").exists()


def test_stm32_hal_uart_sdk_emits_and_manifest_tracks_files(tmp_path: Path):
    build = _build_data(sdks=["stm32_hal_uart"], c={"build_system": "mdk_arm", "emit_examples": False})
    build_path = _write_build(tmp_path, build, "sdk_hal.build.json")

    ir = load_project(DEMO, build_path)
    assert ir.sdks == ("stm32_hal_uart",)
    out = emit_c(ir, tmp_path / "out", build)

    header = out / "SDK" / "STM32_HAL" / "stnp_hal_uart.h"
    source = out / "SDK" / "STM32_HAL" / "stnp_hal_uart.c"
    assert header.is_file()
    assert source.is_file()
    h = header.read_text(encoding="utf-8")
    c = source.read_text(encoding="utf-8")
    assert "STNP_HAL_UART_Init(UART_HandleTypeDef *huart)" in h
    assert '#include "../../Instance/stnp_instances.h"' in h
    assert "HAL_UART_Transmit_IT" in c
    assert "STNP_HAL_UART_TX_QUEUE_DEPTH" in h
    assert "STNP_HAL_UART_TxCpltCallback" in h
    assert "STNP_HAL_UART_ErrorCallback" in h
    assert "HAL_UARTEx_ReceiveToIdle_IT" in c
    assert "STNP_Transport_Receive" in c
    assert "STM32 HAL UART SDK" in (out / "README.md").read_text(encoding="utf-8")

    manifest = json.loads((out / ".stnp-manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["files"]}
    assert "SDK/STM32_HAL/stnp_hal_uart.h" in paths
    assert "SDK/STM32_HAL/stnp_hal_uart.c" in paths


def test_sdk_deselect_cleans_generated_adapter(tmp_path: Path):
    build = _build_data(sdks=["stm32_hal_uart"])
    build_path = _write_build(tmp_path, build, "sdk_toggle.build.json")
    out = emit_c(load_project(DEMO, build_path), tmp_path / "out", build)
    assert (out / "SDK" / "STM32_HAL" / "stnp_hal_uart.c").is_file()

    build["sdks"] = []
    build_path.write_text(json.dumps(build), encoding="utf-8")
    emit_c(load_project(DEMO, build_path), tmp_path / "out", build)
    assert not (out / "SDK" / "STM32_HAL" / "stnp_hal_uart.c").exists()
    assert not (out / "SDK" / "STM32_HAL" / "stnp_hal_uart.h").exists()


def test_stm32_hal_uart_sdk_compiles_with_minimal_hal_stub(tmp_path: Path):
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")

    build = _build_data(sdks=["stm32_hal_uart"], c={"build_system": "mdk_arm", "emit_examples": False})
    build_path = _write_build(tmp_path, build, "sdk_hal_compile.build.json")
    out = emit_c(load_project(DEMO, build_path), tmp_path / "out", build)

    (out / "main.h").write_text(r'''#ifndef TEST_MAIN_H
#define TEST_MAIN_H
#include <stdint.h>
typedef struct __UART_HandleTypeDef { uint32_t marker; } UART_HandleTypeDef;
typedef enum { HAL_OK = 0, HAL_ERROR = 1, HAL_BUSY = 2 } HAL_StatusTypeDef;
static inline uint32_t __get_PRIMASK(void) { return 0U; }
static inline void __disable_irq(void) {}
static inline void __enable_irq(void) {}
HAL_StatusTypeDef HAL_UART_Transmit_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length);
HAL_StatusTypeDef HAL_UARTEx_ReceiveToIdle_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length);
HAL_StatusTypeDef HAL_UART_AbortReceive(UART_HandleTypeDef *huart);
#endif
''', encoding="utf-8")
    harness = out / "hal_stub.c"
    harness.write_text(r'''#include "SDK/STM32_HAL/stnp_hal_uart.h"

static UART_HandleTypeDef g_uart;

HAL_StatusTypeDef HAL_UART_Transmit_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length)
{
    (void)huart; (void)data; (void)length;
    return HAL_OK;
}

HAL_StatusTypeDef HAL_UARTEx_ReceiveToIdle_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length)
{
    (void)huart; (void)data; (void)length;
    return HAL_OK;
}

HAL_StatusTypeDef HAL_UART_AbortReceive(UART_HandleTypeDef *huart)
{
    (void)huart;
    return HAL_OK;
}

int main(void)
{
    return STNP_HAL_UART_Init(&g_uart) == STNP_OK ? 0 : 1;
}
''', encoding="utf-8")
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c", "Implementation/*.c", "SDK/*/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.append(str(harness))
    exe = out / "hal_sdk_test"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True, capture_output=True, text=True)


def test_stm32_hal_uart_sdk_nonblocking_queue_rx_rearm_and_error_recovery(tmp_path: Path):
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")

    build = _build_data(sdks=["stm32_hal_uart"], c={"build_system": "mdk_arm", "emit_examples": False})
    build_path = _write_build(tmp_path, build, "sdk_hal_stress.build.json")
    out = emit_c(load_project(DEMO, build_path), tmp_path / "out", build)

    # Make one generated user handler immediately send a Notify. This reproduces
    # the MCU path that originally wedged RX when TX was blocking inside RX dispatch.
    impl = out / "Implementation" / "chassis_impl.c"
    text = impl.read_text(encoding="utf-8")
    old = """    /* USER CODE BEGIN Chassis_Stop */\n    STNP_UNUSED(self);\n    /* USER CODE END Chassis_Stop */"""
    new = """    /* USER CODE BEGIN Chassis_Stop */\n    STNP_UNUSED(self);\n    (void)STNP_Notify_Send(\n        STNP_INSTANCE_CHASSISMAIN_ID,\n        CHASSIS_NOTIFY_DONE,\n        CHASSIS_OK,\n        STNP_NULL\n    );\n    /* USER CODE END Chassis_Stop */"""
    assert old in text
    impl.write_text(text.replace(old, new), encoding="utf-8")

    (out / "main.h").write_text(r'''#ifndef TEST_MAIN_H
#define TEST_MAIN_H
#include <stdint.h>
typedef struct __UART_HandleTypeDef { uint32_t marker; } UART_HandleTypeDef;
typedef enum { HAL_OK = 0, HAL_ERROR = 1, HAL_BUSY = 2 } HAL_StatusTypeDef;
static inline uint32_t __get_PRIMASK(void) { return 0U; }
static inline void __disable_irq(void) {}
static inline void __enable_irq(void) {}
HAL_StatusTypeDef HAL_UART_Transmit_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length);
HAL_StatusTypeDef HAL_UARTEx_ReceiveToIdle_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length);
HAL_StatusTypeDef HAL_UART_AbortReceive(UART_HandleTypeDef *huart);
#endif
''', encoding="utf-8")

    harness = out / "hal_stress_stub.c"
    harness.write_text(r'''#include "SDK/STM32_HAL/stnp_hal_uart.h"
#include "Core/stnp_frame.h"

#include <string.h>

static UART_HandleTypeDef g_uart;
static uint8_t *g_rx_ptr = 0;
static uint16_t g_rx_capacity = 0U;
static unsigned g_rx_start_count = 0U;
static unsigned g_tx_start_count = 0U;
static unsigned g_abort_count = 0U;
static unsigned g_order_error = 0U;

HAL_StatusTypeDef HAL_UART_Transmit_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length)
{
    (void)data;
    (void)length;
    if (huart != &g_uart)
    {
        return HAL_ERROR;
    }
    /* RX must already be re-armed before a Task handler is allowed to send. */
    if (g_rx_start_count < 2U)
    {
        g_order_error = 1U;
    }
    g_tx_start_count++;
    return HAL_OK;
}

HAL_StatusTypeDef HAL_UARTEx_ReceiveToIdle_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length)
{
    if (huart != &g_uart)
    {
        return HAL_ERROR;
    }
    g_rx_ptr = data;
    g_rx_capacity = length;
    g_rx_start_count++;
    return HAL_OK;
}

HAL_StatusTypeDef HAL_UART_AbortReceive(UART_HandleTypeDef *huart)
{
    if (huart != &g_uart)
    {
        return HAL_ERROR;
    }
    g_abort_count++;
    return HAL_OK;
}

static int feed_stop_task(void)
{
    STNP_TaskFrame frame;
    uint8_t *completed_rx;
    STNP_U8 wire[STNP_TASK_FIXED_SIZE + STNP_PAYLOAD_MAX + STNP_CRC_SIZE];
    STNP_U16 wire_len = 0U;

    memset(&frame, 0, sizeof(frame));
    /* This build has features.seq disabled, so STNP_TaskFrame has no seq slot;
       the HAL non-blocking RX re-arm behavior under test is SEQ-independent. */
    frame.target = STNP_INSTANCE_CHASSISMAIN_ID;
    frame.code = CHASSIS_CMD_STOP;
    frame.length = 0U;

    if (STNP_Frame_BuildTask(&frame, wire, (STNP_U16)sizeof(wire), &wire_len) != STNP_OK)
    {
        return 1;
    }
    if ((g_rx_ptr == 0) || (wire_len > g_rx_capacity))
    {
        return 2;
    }

    completed_rx = g_rx_ptr;
    memcpy(completed_rx, wire, wire_len);
    STNP_HAL_UART_RxEventCallback(&g_uart, wire_len);

    if (g_rx_ptr == completed_rx)
    {
        return 3; /* high-frequency RX must re-arm a different ping-pong buffer */
    }
    if (g_order_error != 0U)
    {
        return 3;
    }
    if (g_rx_start_count < 2U)
    {
        return 4;
    }
    if (g_tx_start_count != 0U)
    {
        return 5;
    }
    if (STNP_Process() != STNP_OK)
    {
        return 6;
    }
    if (g_tx_start_count != 0U)
    {
        return 7;
    }
    if (STNP_Dispatch() != STNP_OK)
    {
        return 8;
    }
    if (g_tx_start_count != 1U)
    {
        return 9;
    }

    STNP_HAL_UART_TxCpltCallback(&g_uart);
    return 0;
}

static int exercise_tx_queue(void)
{
    unsigned i;
    STNP_Result result;
    unsigned before = g_tx_start_count;

    /* Queue depth is 4 by default: one active frame plus three waiting frames. */
    for (i = 0U; i < 4U; i++)
    {
        result = STNP_Notify_Send(
            STNP_INSTANCE_CHASSISMAIN_ID,
            CHASSIS_NOTIFY_DONE,
            CHASSIS_OK,
            STNP_NULL
        );
        if (result != STNP_OK)
        {
            return 10 + (int)i;
        }
    }

    if (g_tx_start_count != (before + 1U))
    {
        return 20;
    }

    result = STNP_Notify_Send(
        STNP_INSTANCE_CHASSISMAIN_ID,
        CHASSIS_NOTIFY_DONE,
        CHASSIS_OK,
        STNP_NULL
    );
    if (result != STNP_ERR_BUFFER)
    {
        return 21;
    }

    for (i = 0U; i < 4U; i++)
    {
        STNP_HAL_UART_TxCpltCallback(&g_uart);
    }
    if (g_tx_start_count != (before + 4U))
    {
        return 22;
    }

    /* Sustained traffic: each completed frame frees the queue immediately. */
    for (i = 0U; i < 3000U; i++)
    {
        result = STNP_Notify_Send(
            STNP_INSTANCE_CHASSISMAIN_ID,
            CHASSIS_NOTIFY_DONE,
            CHASSIS_OK,
            STNP_NULL
        );
        if (result != STNP_OK)
        {
            return 23;
        }
        STNP_HAL_UART_TxCpltCallback(&g_uart);
    }

    return 0;
}

int main(void)
{
    unsigned rx_before_error;
    int rc;

    if (STNP_HAL_UART_Init(&g_uart) != STNP_OK)
    {
        return 100;
    }
    if (g_rx_start_count != 1U)
    {
        return 101;
    }

    rc = feed_stop_task();
    if (rc != 0)
    {
        return rc;
    }

    rc = exercise_tx_queue();
    if (rc != 0)
    {
        return rc;
    }

    rx_before_error = g_rx_start_count;
    STNP_HAL_UART_ErrorCallback(&g_uart);
    if (g_abort_count != 1U)
    {
        return 102;
    }
    if (g_rx_start_count != (rx_before_error + 1U))
    {
        return 103;
    }

    return 0;
}
''', encoding="utf-8")

    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c", "Implementation/*.c", "SDK/*/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.append(str(harness))
    exe = out / "hal_sdk_stress_test"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True, capture_output=True, text=True)


def test_deferred_receive_requires_process_then_dispatch(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "deferred_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
static STNP_U8 g_called = 0U;
void Chassis_Stop(ChassisHandle *self)
{
    STNP_UNUSED(self);
    g_called++;
}
int main(void)
{
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_STOP, STNP_NULL) != STNP_OK) return 2;
    if (g_called != 0U) return 3;
    if (STNP_Process() != STNP_OK) return 4;
    if (g_called != 0U) return 5;
    if (STNP_Dispatch() != STNP_OK) return 6;
    return g_called == 1U ? 0 : 7;
}
''', encoding="utf-8")
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.extend([str(out / "Examples" / "transport_mock.c"), str(harness)])
    sources.append(str(_write_harness_link_stubs(out)))
    exe = out / "deferred_test"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_process_advances_at_most_one_frame_per_call(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "one_frame_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
static STNP_U8 g_called = 0U;
void Chassis_Stop(ChassisHandle *self){STNP_UNUSED(self);g_called++;}
int main(void)
{
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_STOP, STNP_NULL) != STNP_OK) return 2;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_STOP, STNP_NULL) != STNP_OK) return 3;
    if (STNP_Process() != STNP_OK) return 4;
    if (STNP_Dispatch() != STNP_OK || g_called != 1U) return 5;
    if (STNP_Dispatch() != STNP_IDLE) return 6;
    if (STNP_Process() != STNP_OK) return 7;
    if (STNP_Dispatch() != STNP_OK || g_called != 2U) return 8;
    return 0;
}
''', encoding="utf-8")
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.extend([str(out / "Examples" / "transport_mock.c"), str(harness)])
    sources.append(str(_write_harness_link_stubs(out)))
    exe = out / "one_frame_test"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_job_payload_is_snapshot_not_rx_pointer(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "job_snapshot_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
static STNP_U8 g_count = 0U;
static STNP_U8 g_dir[2];
static STNP_U8 g_speed[2];
void Chassis_Move(ChassisHandle *self, const Chassis_MovePayload *payload)
{
    STNP_UNUSED(self);
    if (g_count < 2U) { g_dir[g_count] = payload->direction; g_speed[g_count] = payload->speed; }
    g_count++;
}
int main(void)
{
    Chassis_MovePayload a = {1U, 11U};
    Chassis_MovePayload b = {2U, 22U};
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_MOVE, &a) != STNP_OK) return 2;
    if (STNP_Process() != STNP_OK) return 3;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_MOVE, &b) != STNP_OK) return 4;
    if (STNP_Process() != STNP_OK) return 5;
    if (STNP_Dispatch() != STNP_OK) return 6;
    if (STNP_Dispatch() != STNP_OK) return 7;
    return (g_count == 2U && g_dir[0] == 1U && g_speed[0] == 11U &&
            g_dir[1] == 2U && g_speed[1] == 22U) ? 0 : 8;
}
''', encoding="utf-8")
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.extend([str(out / "Examples" / "transport_mock.c"), str(harness)])
    sources.append(str(_write_harness_link_stubs(out)))
    exe = out / "job_snapshot_test"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_job_queue_full_retains_complete_frame_for_retry(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "job_full_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
int main(void)
{
    STNP_U8 i;
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    for (i = 0U; i < (STNP_U8)(STNP_JOB_QUEUE_DEPTH + 1U); i++)
        if (STNP_Task_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_CMD_READ, STNP_NULL) != STNP_OK) return 2;
    for (i = 0U; i < (STNP_U8)STNP_JOB_QUEUE_DEPTH; i++)
        if (STNP_Process() != STNP_OK) return 3;
    if (STNP_Process() != STNP_ERR_BUFFER) return 4;
    if (STNP_Dispatch() != STNP_OK) return 5;
    if (STNP_Process() != STNP_OK) return 6;
    return 0;
}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)


def test_rx_ring_full_returns_buffer_error_without_reset(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "rx_full_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
static STNP_U8 g_fill[STNP_RX_RING_SIZE];
int main(void)
{
    STNP_U16 i;
    STNP_U8 extra = 0xAAU;
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    for (i = 0U; i < (STNP_U16)sizeof(g_fill); i++) g_fill[i] = 0U;
    if (STNP_Transport_Receive(g_fill, (STNP_U16)sizeof(g_fill)) != STNP_OK) return 2;
    if (STNP_Transport_Receive(&extra, 1U) != STNP_ERR_BUFFER) return 3;
    if (STNP_Process() != STNP_IDLE) return 4; /* drains bounded static ring garbage */
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_STOP, STNP_NULL) != STNP_OK) return 5;
    if (STNP_Process() != STNP_OK) return 6;
    return STNP_Dispatch() == STNP_OK ? 0 : 7;
}
''', encoding="utf-8")
    subprocess.run([str(_compile(out, main=harness))], cwd=out, check=True)


def test_dispatch_concurrent_instances_and_serializes_same_instance(tmp_path: Path):
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "dispatch_concurrency_harness.c"
    harness.write_text(r'''#define _POSIX_C_SOURCE 200809L
#include "Core/stnp.h"
#include "Core/stnp_runtime.h"
#include "Instance/stnp_instances.h"
#include <pthread.h>
#include <time.h>

static pthread_mutex_t g_runtime_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t g_observe_lock = PTHREAD_MUTEX_INITIALIZER;
static int g_active = 0;
static int g_max_active = 0;
static int g_chassis_calls = 0;
static int g_sensor_calls = 0;

STNP_U32 STNP_Runtime_Lock(void){pthread_mutex_lock(&g_runtime_lock);return 0U;}
void STNP_Runtime_Unlock(STNP_U32 s){STNP_UNUSED(s);pthread_mutex_unlock(&g_runtime_lock);}

static void work(int *counter)
{
    struct timespec ts = {0, 50000000L};
    pthread_mutex_lock(&g_observe_lock);
    g_active++;
    if (g_active > g_max_active) g_max_active = g_active;
    pthread_mutex_unlock(&g_observe_lock);
    (void)nanosleep(&ts, 0);
    pthread_mutex_lock(&g_observe_lock);
    (*counter)++;
    g_active--;
    pthread_mutex_unlock(&g_observe_lock);
}
void Chassis_Stop(ChassisHandle *self){STNP_UNUSED(self);work(&g_chassis_calls);}
void Sensor_Read(SensorHandle *self){STNP_UNUSED(self);work(&g_sensor_calls);}
static STNP_Result loopback(const STNP_U8 *d, STNP_U16 n){return STNP_Transport_Receive(d,n);}
static void *run_one(void *arg){STNP_UNUSED(arg);(void)STNP_Dispatch();return 0;}

int main(void)
{
    pthread_t a,b;
    if ((STNP_Init(loopback) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;

    /* Different instance keys must be runnable concurrently. */
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_STOP, STNP_NULL) != STNP_OK) return 2;
    if (STNP_Task_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_CMD_READ, STNP_NULL) != STNP_OK) return 3;
    if (STNP_Process() != STNP_OK || STNP_Process() != STNP_OK) return 4;
    if (pthread_create(&a,0,run_one,0) || pthread_create(&b,0,run_one,0)) return 5;
    pthread_join(a,0); pthread_join(b,0);
    if (g_max_active != 2 || g_chassis_calls != 1 || g_sensor_calls != 1) return 6;

    /* Two Jobs for one instance remain serialized even with two workers. */
    g_max_active = 0;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_STOP, STNP_NULL) != STNP_OK) return 7;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_STOP, STNP_NULL) != STNP_OK) return 8;
    if (STNP_Process() != STNP_OK || STNP_Process() != STNP_OK) return 9;
    if (pthread_create(&a,0,run_one,0) || pthread_create(&b,0,run_one,0)) return 10;
    pthread_join(a,0); pthread_join(b,0);
    if (g_max_active != 1 || g_chassis_calls != 2) return 11;
    if (STNP_Dispatch() != STNP_OK || g_chassis_calls != 3) return 12;
    return 0;
}
''', encoding="utf-8")
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.append(str(harness))
    sources.append(str(_write_harness_link_stubs(out)))
    exe = out / "dispatch_concurrency_test"
    # -static removes the libwinpthread-1.dll runtime dependency, so the exe runs
    # from any cwd without a PATH patch (S1/D6).  The pre-test PATH prepend lived
    # here; conftest.py now owns toolchain PATH bootstrapping (S4/D5).
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-pthread", "-static", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_freertos_sdk_emits_with_hal_zero_scheduler_user_code(tmp_path: Path):
    build = _build_data(
        sdks=["stm32_hal_uart", "freertos"],
        c={"build_system": "mdk_arm", "emit_examples": False},
    )
    build_path = _write_build(tmp_path, build, "rtos_sdk.build.json")
    out = emit_c(load_project(DEMO, build_path), tmp_path / "out", build)

    fr_h = (out / "SDK" / "FreeRTOS" / "stnp_freertos.h").read_text(encoding="utf-8")
    fr_c = (out / "SDK" / "FreeRTOS" / "stnp_freertos.c").read_text(encoding="utf-8")
    hal_c = (out / "SDK" / "STM32_HAL" / "stnp_hal_uart.c").read_text(encoding="utf-8")
    assert "STNP_FREERTOS_WORKER_COUNT 4U" in fr_h
    assert "xTaskCreateStatic" in fr_c
    assert "STNP_Dispatch()" in fr_c
    assert "STNP_FreeRTOS_Start()" in hal_c
    assert "STNP_FreeRTOS_NotifyRxFromISR()" in hal_c
    assert "void Chassis_Stop" not in fr_c


def test_notify_global_and_typed_callbacks_are_deferred_and_enable_semantics_hold(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "notify_deferred_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"

static STNP_U8 g_raw_count = 0U;
static STNP_U8 g_typed_count = 0U;
static STNP_U16 g_value = 0U;

void STNP_Notify_Callback(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    STNP_UNUSED(source); STNP_UNUSED(notify_code); STNP_UNUSED(result);
    STNP_UNUSED(payload); STNP_UNUSED(length);
    g_raw_count++;
}

void Sensor_NotifyCallback(
    SensorHandle *self,
    STNP_U8 notify_code,
    Sensor_Result result,
    const void *payload)
{
    const Sensor_DataPayload *data = (const Sensor_DataPayload *)payload;
    STNP_UNUSED(self); STNP_UNUSED(notify_code); STNP_UNUSED(result);
    g_typed_count++;
    if (data != STNP_NULL) g_value = data->value;
}

int main(void)
{
    Sensor_DataPayload p = {0x1234U};
    if ((STNP_Init(TransportMock_Write) != STNP_OK) ||
        (STNP_Instances_Init() != STNP_OK)) return 1;

    STNP_NotifyDispatchReceive_Disable();
    if (STNP_Notify_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_NOTIFY_DATA, SENSOR_OK, &p) != STNP_OK) return 20;
    if (STNP_Process() != STNP_OK) return 21;
    if (STNP_Dispatch() != STNP_OK) return 22;
    if (g_raw_count != 0U || g_typed_count != 0U) return 23;
    STNP_NotifyDispatchReceive_Enable();

    /* Typed callback is disabled by default; raw callback still must be deferred. */
    if (STNP_Notify_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_NOTIFY_DATA, SENSOR_OK, &p) != STNP_OK) return 2;
    if (g_raw_count != 0U || g_typed_count != 0U) return 3;
    if (STNP_Process() != STNP_OK) return 4;
    if (g_raw_count != 0U || g_typed_count != 0U) return 5;
    if (STNP_Dispatch() != STNP_OK) return 6;
    if (g_raw_count != 1U || g_typed_count != 0U) return 7;

    Sensor_NotifyCallbackEnable(STNP_ENABLE);
    p.value = 0xBEEFU;
    if (STNP_Notify_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_NOTIFY_DATA, SENSOR_OK, &p) != STNP_OK) return 8;
    if (STNP_Process() != STNP_OK) return 9;
    if (g_raw_count != 1U || g_typed_count != 0U) return 10;
    if (STNP_Dispatch() != STNP_OK) return 11;
    return (g_raw_count == 1U && g_typed_count == 1U && g_value == 0xBEEFU) ? 0 : 12;
}
''', encoding="utf-8")
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.extend([str(out / "Examples" / "transport_mock.c"), str(harness)])
    # This harness defines its own raw STNP_Notify_Callback, so only the
    # generated validators need a strong stand-in.
    sources.append(str(_write_harness_link_stubs(out, raw_callback=False)))
    exe = out / "notify_deferred_test"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_rx_ring_wraparound_under_repeated_frames(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "rx_wrap_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
static STNP_U16 g_calls = 0U;
void Chassis_Stop(ChassisHandle *self){STNP_UNUSED(self);g_calls++;}
int main(void)
{
    STNP_U16 i;
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    for (i = 0U; i < 300U; i++)
    {
        if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_STOP, STNP_NULL) != STNP_OK) return 2;
        if (STNP_Process() != STNP_OK) return 3;
        if (STNP_Dispatch() != STNP_OK) return 4;
    }
    return g_calls == 300U ? 0 : 5;
}
''', encoding="utf-8")
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.extend([str(out / "Examples" / "transport_mock.c"), str(harness)])
    sources.append(str(_write_harness_link_stubs(out)))
    exe = out / "rx_wrap_test"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_job_storage_reuses_slots_without_overwrite(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "job_reuse_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"
static STNP_U16 g_calls = 0U;
void Sensor_Read(SensorHandle *self){STNP_UNUSED(self);g_calls++;}
static int fill_and_drain(void)
{
    STNP_U16 i;
    for (i = 0U; i < (STNP_U16)STNP_JOB_QUEUE_DEPTH; i++)
    {
        if (STNP_Task_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_CMD_READ, STNP_NULL) != STNP_OK) return 1;
        if (STNP_Process() != STNP_OK) return 2;
    }
    for (i = 0U; i < (STNP_U16)STNP_JOB_QUEUE_DEPTH; i++)
        if (STNP_Dispatch() != STNP_OK) return 3;
    return 0;
}
int main(void)
{
    int rc;
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    rc = fill_and_drain(); if (rc != 0) return 10 + rc;
    rc = fill_and_drain(); if (rc != 0) return 20 + rc;
    return g_calls == (STNP_U16)(STNP_JOB_QUEUE_DEPTH * 2U) ? 0 : 30;
}
''', encoding="utf-8")
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.extend([str(out / "Examples" / "transport_mock.c"), str(harness)])
    sources.append(str(_write_harness_link_stubs(out)))
    exe = out / "job_reuse_test"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_build_system_defaults_mdk_arm_without_cmake_file(tmp_path: Path):
    build = _build_data(c={"emit_examples": True})
    build_path = _write_build(tmp_path, build, "build_default.build.json")

    ir = load_project(DEMO, build_path)
    assert ir.build_system == "mdk_arm"
    out = emit_c(ir, tmp_path / "out", build)
    assert not (out / "CMakeLists.txt").exists()


def test_cmake_build_system_emits_and_manifest_tracks_file(tmp_path: Path):
    build = _build_data(c={"build_system": "cmake", "emit_examples": True})
    build_path = _write_build(tmp_path, build, "cmake_emit.build.json")

    ir = load_project(DEMO, build_path)
    assert ir.build_system == "cmake"
    out = emit_c(ir, tmp_path / "out", build)
    cmake = out / "CMakeLists.txt"
    assert cmake.is_file()
    text = cmake.read_text(encoding="utf-8")
    assert "add_library(stnp STATIC" in text
    assert '${CMAKE_CURRENT_LIST_DIR}/Core/stnp_core.c' in text
    assert '${CMAKE_CURRENT_LIST_DIR}/Core/stnp_debug.c' in text
    assert '${CMAKE_CURRENT_LIST_DIR}/Core/stnp_unknown.c' in text
    assert "${CMAKE_SOURCE_DIR}" not in text
    assert "target_compile_features" not in text
    assert "C_STANDARD 99" in text
    assert "C_STANDARD_REQUIRED YES" in text
    assert "target_sources(stnp INTERFACE" in text
    assert '${CMAKE_CURRENT_LIST_DIR}/Implementation/chassis_impl.c' in text
    archive_section = text.split("target_sources(stnp INTERFACE", 1)[0]
    assert "Implementation/chassis_impl.c" not in archive_section
    assert "Implementation/stnp_notify_callback.c" not in archive_section

    manifest = json.loads((out / ".stnp-manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["files"]}
    assert "CMakeLists.txt" in paths


def test_switching_cmake_to_mdk_arm_removes_generated_cmake_file(tmp_path: Path):
    build = _build_data(c={"build_system": "cmake", "emit_examples": True})
    build_path = _write_build(tmp_path, build, "build_toggle.build.json")
    out = emit_c(load_project(DEMO, build_path), tmp_path / "out", build)
    assert (out / "CMakeLists.txt").is_file()

    build["c"]["build_system"] = "mdk_arm"
    build_path.write_text(json.dumps(build), encoding="utf-8")
    emit_c(load_project(DEMO, build_path), tmp_path / "out", build)
    assert not (out / "CMakeLists.txt").exists()


def test_generated_cmake_builds_as_subdirectory_with_stm32cubemx_target(tmp_path: Path):
    if shutil.which("cmake") is None:
        pytest.skip("cmake not available")

    build = _build_data(
        sdks=["stm32_hal_uart"],
        c={"build_system": "cmake", "emit_examples": False},
    )
    build_path = _write_build(tmp_path, build, "cmake_hal.build.json")
    stnp_dir = emit_c(load_project(DEMO, build_path), tmp_path / "generated", build)

    parent = tmp_path / "host"
    fake_hal = parent / "fake_hal"
    fake_hal.mkdir(parents=True)
    (fake_hal / "main.h").write_text(r'''#ifndef TEST_MAIN_H
#define TEST_MAIN_H
#include <stdint.h>
typedef struct __UART_HandleTypeDef { uint32_t marker; } UART_HandleTypeDef;
typedef enum { HAL_OK = 0, HAL_ERROR = 1, HAL_BUSY = 2 } HAL_StatusTypeDef;
static inline uint32_t __get_PRIMASK(void) { return 0U; }
static inline void __disable_irq(void) {}
static inline void __enable_irq(void) {}
HAL_StatusTypeDef HAL_UART_Transmit_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length);
HAL_StatusTypeDef HAL_UARTEx_ReceiveToIdle_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length);
HAL_StatusTypeDef HAL_UART_AbortReceive(UART_HandleTypeDef *huart);
#endif
''', encoding="utf-8")
    (parent / "hal_stub.c").write_text(r'''#include "main.h"
HAL_StatusTypeDef HAL_UART_Transmit_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length)
{ (void)huart; (void)data; (void)length; return HAL_OK; }
HAL_StatusTypeDef HAL_UARTEx_ReceiveToIdle_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length)
{ (void)huart; (void)data; (void)length; return HAL_OK; }
HAL_StatusTypeDef HAL_UART_AbortReceive(UART_HandleTypeDef *huart)
{ (void)huart; return HAL_OK; }
''', encoding="utf-8")
    (parent / "main.c").write_text(r'''#include "stnp.h"
int main(void) { UART_HandleTypeDef uart = {0}; return STNP_HAL_UART_Init(&uart) == STNP_OK ? 0 : 1; }
''', encoding="utf-8")
    stnp_path = stnp_dir.as_posix()
    (parent / "CMakeLists.txt").write_text(f'''cmake_minimum_required(VERSION 3.20)\nproject(STNP_CMake_Test C)\nset(CMAKE_C_COMPILE_FEATURES "")\nadd_library(stm32cubemx INTERFACE)\ntarget_include_directories(stm32cubemx INTERFACE "${{CMAKE_CURRENT_SOURCE_DIR}}/fake_hal")\nadd_subdirectory("{stnp_path}" STNP_build)\nadd_executable(STNP_TEST main.c hal_stub.c)\ntarget_link_libraries(STNP_TEST PRIVATE stm32cubemx stnp)\n''', encoding="utf-8")

    build_dir = parent / "build"
    configure = ["cmake", "-S", str(parent), "-B", str(build_dir), *_cmake_generator_args()]
    subprocess.run(configure, check=True, capture_output=True, text=True)
    result = subprocess.run(["cmake", "--build", str(build_dir), "--parallel"], check=True, capture_output=True, text=True)
    archive = build_dir / "STNP_build" / "libstnp.a"
    assert archive.is_file()
    assert "Built target stnp" in (result.stdout + result.stderr)
    if shutil.which("ar") is not None:
        members = subprocess.run(["ar", "t", str(archive)], check=True, capture_output=True, text=True).stdout
        assert "chassis_impl" not in members
        assert "stnp_notify_callback" not in members
    if shutil.which("nm") is not None:
        exe = build_dir / ("STNP_TEST.exe" if os.name == "nt" else "STNP_TEST")
        symbols = subprocess.run(["nm", str(exe)], check=True, capture_output=True, text=True).stdout
        assert any(line.rstrip().endswith(" T Chassis_Move") for line in symbols.splitlines())


def test_invalid_build_system_is_rejected_by_schema(tmp_path: Path):
    build = _build_data(c={"build_system": "makefile"})
    build_path = _write_build(tmp_path, build, "bad_build_system.build.json")
    with pytest.raises(StnpError, match="build 文件 schema 校验失败"):
        load_project(DEMO, build_path)


def test_cmake_lists_selected_freertos_sdk_source(tmp_path: Path):
    build = _build_data(
        sdks=["stm32_hal_uart", "freertos"],
        c={"build_system": "cmake", "emit_examples": False},
    )
    build_path = _write_build(tmp_path, build, "cmake_rtos.build.json")
    out = emit_c(load_project(DEMO, build_path), tmp_path / "out", build)
    text = (out / "CMakeLists.txt").read_text(encoding="utf-8")
    assert '${CMAKE_CURRENT_LIST_DIR}/SDK/STM32_HAL/stnp_hal_uart.c' in text
    assert '${CMAKE_CURRENT_LIST_DIR}/SDK/FreeRTOS/stnp_freertos.c' in text
    assert "target_link_libraries(stnp PUBLIC stm32cubemx)" in text


def test_auto_notify_rejects_payload_bearing_done_mapping():
    with pytest.raises(StnpError, match="零载荷通知"):
        _auto_notify_ir("SENSOR")


def _write_debug_trap_stub(out: Path) -> Path:
    stub = out / "debug_trap_stub.c"
    stub.write_text(
        '#include "Core/stnp.h"\n'
        "void STNP_Debug_Trap(STNP_BpSite site)\n"
        "{\n"
        "    STNP_UNUSED(site);\n"
        "}\n",
        encoding="utf-8",
    )
    return stub


def test_stnp_debug_compiles_off_and_on_without_bkpt(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    assert (out / "Core" / "stnp_debug.h").is_file()
    assert (out / "Core" / "stnp_debug.c").is_file()
    platform_cfg = (out / "Platform" / "stnp_platform_config.h").read_text(encoding="utf-8")
    assert "#define STNP_DEBUG 1" not in platform_cfg
    header = (out / "Core" / "stnp.h").read_text(encoding="utf-8")
    assert '#include "stnp_debug.h"' in header
    for path in out.rglob("*.c"):
        if path.name in {"stnp_debug.c"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "STNP_Debug_Trap" not in text, path
        assert "STNP_LOGE" not in text
        assert "STNP_LOG" not in text
    _compile(out, exe_name="stnp_debug_off")
    stub = _write_debug_trap_stub(out)
    _compile(
        out,
        extra_cflags=["-DSTNP_DEBUG=1"],
        extra_sources=[str(stub)],
        exe_name="stnp_debug_on",
    )


def test_stnp_debug_legal_task_resync_and_sof_sites(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "debug_sites_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"

#define STNP_BP_MAX_HITS 64U
static STNP_BpSite g_hits[STNP_BP_MAX_HITS];
static STNP_U16 g_hit_n = 0U;

void STNP_Debug_Trap(STNP_BpSite site)
{
    if (g_hit_n < STNP_BP_MAX_HITS)
    {
        g_hits[g_hit_n++] = site;
    }
}

static STNP_Result DummyWrite(const STNP_U8 *data, STNP_U16 length)
{
    STNP_UNUSED(data);
    STNP_UNUSED(length);
    return STNP_OK;
}

static void reset_hits(void)
{
    g_hit_n = 0U;
}

static STNP_U16 count_site(STNP_BpSite site)
{
    STNP_U16 i;
    STNP_U16 n = 0U;
    for (i = 0U; i < g_hit_n; i++)
    {
        if (g_hits[i] == site)
        {
            n++;
        }
    }
    return n;
}

int main(void)
{
    STNP_TaskFrame frame;
    STNP_U8 raw[STNP_TASK_FIXED_SIZE + STNP_PAYLOAD_MAX + STNP_CRC_SIZE];
    STNP_U16 raw_len = 0U;
    STNP_U8 oversized[5];
    STNP_U8 noise[4];
    static const STNP_BpSite expect[] = {
        STNP_BP_SITE_RX_COPY,
        STNP_BP_SITE_PROCESS_ENTER,
        STNP_BP_SITE_PARSE_OK,
        STNP_BP_SITE_ENQUEUE,
        STNP_BP_SITE_DISPATCH,
        STNP_BP_SITE_ON_TASK
    };
    STNP_U16 i;

    if ((STNP_Init(DummyWrite) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    frame.target = STNP_INSTANCE_CHASSISMAIN_ID;
    frame.code = CHASSIS_CMD_STOP;
    frame.length = 0U;
    if (STNP_Frame_BuildTask(&frame, raw, (STNP_U16)sizeof(raw), &raw_len) != STNP_OK) return 2;
    reset_hits();
    if (STNP_Transport_Receive(raw, raw_len) != STNP_OK) return 3;
    if (STNP_Process() != STNP_OK) return 4;
    if (STNP_Dispatch() != STNP_OK) return 5;
    if (g_hit_n != (STNP_U16)(sizeof(expect) / sizeof(expect[0]))) return 6;
    for (i = 0U; i < g_hit_n; i++)
    {
        if (g_hits[i] != expect[i]) return 7;
    }

    if (STNP_Init(DummyWrite) != STNP_OK) return 8;
    oversized[0] = STNP_TASK_HEADER0;
    oversized[1] = STNP_TASK_HEADER1;
    oversized[2] = STNP_INSTANCE_CHASSISMAIN_ID;
    oversized[3] = CHASSIS_CMD_STOP;
    oversized[4] = (STNP_U8)(STNP_PAYLOAD_MAX + 1U);
    reset_hits();
    if (STNP_Transport_Receive(oversized, 5U) != STNP_OK) return 9;
    if (STNP_Process() != STNP_ERR_LENGTH) return 10;
    if (count_site(STNP_BP_SITE_PROCESS_ENTER) == 0U) return 11;
    if (count_site(STNP_BP_SITE_PARSE_RESYNC) != 1U) return 12;
    if (count_site(STNP_BP_SITE_PARSE_OK) != 0U) return 13;
    if (count_site(STNP_BP_SITE_ON_TASK) != 0U) return 14;

    if (STNP_Init(DummyWrite) != STNP_OK) return 15;
    noise[0] = 0x00U; noise[1] = 0x01U; noise[2] = 0x02U; noise[3] = 0x03U;
    reset_hits();
    if (STNP_Transport_Receive(noise, 4U) != STNP_OK) return 16;
    if (STNP_Process() != STNP_IDLE) return 17;
    if (count_site(STNP_BP_SITE_PARSE_RESYNC) != 0U) return 18;
    return 0;
}
''', encoding="utf-8")
    exe = _compile(out, main=harness, extra_cflags=["-DSTNP_DEBUG=1"], exe_name="debug_sites_test")
    subprocess.run([str(exe)], cwd=out, check=True)


def test_stnp_debug_on_notify_exclusive_once(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "debug_on_notify_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"

#define STNP_BP_MAX_HITS 64U
static STNP_BpSite g_hits[STNP_BP_MAX_HITS];
static STNP_U16 g_hit_n = 0U;

void STNP_Debug_Trap(STNP_BpSite site)
{
    if (g_hit_n < STNP_BP_MAX_HITS)
    {
        g_hits[g_hit_n++] = site;
    }
}

void STNP_Notify_Callback(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    STNP_UNUSED(source); STNP_UNUSED(notify_code); STNP_UNUSED(result);
    STNP_UNUSED(payload); STNP_UNUSED(length);
}

void Sensor_NotifyCallback(
    SensorHandle *self,
    STNP_U8 notify_code,
    Sensor_Result result,
    const void *payload)
{
    STNP_UNUSED(self); STNP_UNUSED(notify_code); STNP_UNUSED(result);
    STNP_UNUSED(payload);
}

static STNP_U16 count_site(STNP_BpSite site)
{
    STNP_U16 i;
    STNP_U16 n = 0U;
    for (i = 0U; i < g_hit_n; i++)
    {
        if (g_hits[i] == site)
        {
            n++;
        }
    }
    return n;
}

int main(void)
{
    Sensor_DataPayload p = {0xBEEFU};
    STNP_U16 i;

    if ((STNP_Init(TransportMock_Write) != STNP_OK) ||
        (STNP_Instances_Init() != STNP_OK)) return 1;
    Sensor_NotifyCallbackEnable(STNP_ENABLE);
    if (STNP_Notify_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_NOTIFY_DATA, SENSOR_OK, &p) != STNP_OK) return 2;
    if (STNP_Process() != STNP_OK) return 3;
    g_hit_n = 0U;
    if (STNP_Dispatch() != STNP_OK) return 4;
    if (count_site(STNP_BP_SITE_ON_NOTIFY) != 1U) return 5;
    for (i = 0U; i < g_hit_n; i++)
    {
        if (g_hits[i] == STNP_BP_SITE_ON_NOTIFY)
        {
            break;
        }
    }
    return 0;
}
''', encoding="utf-8")
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.extend([str(out / "Examples" / "transport_mock.c"), str(harness)])
    sources.append(str(_write_harness_link_stubs(out, raw_callback=False)))
    exe = out / "debug_on_notify_test"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", "-DSTNP_DEBUG=1", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_unknown_frame_c_01_02_04_05_07_08(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "unknown_frame_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"
#include "Examples/transport_mock.h"

static STNP_UnknownReason g_reasons[32];
static STNP_U16 g_lengths[32];
static STNP_U8 g_n = 0U;
static STNP_U8 g_raw = 0U;
static STNP_U8 g_typed = 0U;
static STNP_U8 g_notify_reason = 0U;

static void OnUnknown(STNP_UnknownReason reason, const STNP_U8 *data, STNP_U16 length)
{
    STNP_UNUSED(data);
    if (reason == STNP_UNKNOWN_NOTIFY)
    {
        g_notify_reason++;
    }
    if (g_n < 32U)
    {
        g_reasons[g_n] = reason;
        g_lengths[g_n] = length;
        g_n++;
    }
}

void STNP_Notify_Callback(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    STNP_UNUSED(source); STNP_UNUSED(notify_code); STNP_UNUSED(result);
    STNP_UNUSED(payload); STNP_UNUSED(length);
    g_raw++;
}

void Sensor_NotifyCallback(
    SensorHandle *self,
    STNP_U8 notify_code,
    Sensor_Result result,
    const void *payload)
{
    STNP_UNUSED(self); STNP_UNUSED(notify_code); STNP_UNUSED(result);
    STNP_UNUSED(payload);
    g_typed++;
}

static STNP_U8 count_reason(STNP_UnknownReason reason)
{
    STNP_U8 i;
    STNP_U8 n = 0U;
    for (i = 0U; i < g_n; i++)
    {
        if (g_reasons[i] == reason)
        {
            n++;
        }
    }
    return n;
}

static STNP_Result DummyWrite(const STNP_U8 *data, STNP_U16 length)
{
    STNP_UNUSED(data);
    STNP_UNUSED(length);
    return STNP_OK;
}

static void fill_len_fail(STNP_U8 *buf)
{
    STNP_U16 i;
    for (i = 0U; i < STNP_TASK_FIXED_SIZE; i++)
    {
        buf[i] = 0U;
    }
    buf[0] = STNP_TASK_HEADER0;
    buf[1] = STNP_TASK_HEADER1;
    buf[STNP_TASK_FIXED_SIZE - 1U] = (STNP_U8)(STNP_PAYLOAD_MAX + 1U);
}

int main(void)
{
    STNP_U8 len_fail[STNP_TASK_FIXED_SIZE];
    STNP_TaskFrame task;
    STNP_U8 raw[STNP_TASK_FIXED_SIZE + STNP_PAYLOAD_MAX + STNP_CRC_SIZE];
    STNP_U16 raw_len = 0U;
    STNP_U8 noise[8];
    STNP_U8 i;

    fill_len_fail(len_fail);

    /* 1: default — callback registered but not enabled */
    if ((STNP_Init(DummyWrite) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    if (STNP_UnknownFrameCallback_IsEnabled() != 0U) return 2;
    g_n = 0U;
    if (STNP_Transport_Receive(len_fail, STNP_TASK_FIXED_SIZE) != STNP_OK) return 3;
    if (STNP_Process() != STNP_ERR_LENGTH) return 4;
    if (STNP_Init(DummyWrite) != STNP_OK) return 5;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    task.target = 0x09U;
    task.code = CHASSIS_CMD_STOP;
    task.length = 0U;
    if (STNP_Frame_BuildTask(&task, raw, (STNP_U16)sizeof(raw), &raw_len) != STNP_OK) return 5;
    if (STNP_Transport_Receive(raw, raw_len) != STNP_OK) return 6;
    if (STNP_Process() != STNP_ERR_TARGET) return 7;
    if (g_n != 0U) return 8;

    /* 2: enable without set */
    if (STNP_Init(DummyWrite) != STNP_OK) return 9;
    STNP_UnknownFrame_SetCallback(STNP_NULL);
    STNP_UnknownFrameCallback_Enable(STNP_ENABLE);
    g_n = 0U;
    if (STNP_Transport_Receive(len_fail, STNP_TASK_FIXED_SIZE) != STNP_OK) return 10;
    if (STNP_Process() != STNP_ERR_LENGTH) return 11;
    if (g_n != 0U) return 12;

    /* 2b: set without enable */
    if (STNP_Init(DummyWrite) != STNP_OK) return 13;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    STNP_UnknownFrameCallback_Enable(STNP_DISABLE);
    g_n = 0U;
    if (STNP_Transport_Receive(len_fail, STNP_TASK_FIXED_SIZE) != STNP_OK) return 14;
    if (STNP_Process() != STNP_ERR_LENGTH) return 15;
    if (g_n != 0U) return 16;

    /* enable + LEN */
    if (STNP_Init(DummyWrite) != STNP_OK) return 17;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    STNP_UnknownFrameCallback_Enable(STNP_ENABLE);
    g_n = 0U;
    if (STNP_Transport_Receive(len_fail, STNP_TASK_FIXED_SIZE) != STNP_OK) return 18;
    if (STNP_Process() != STNP_ERR_LENGTH) return 19;
    if (count_reason(STNP_UNKNOWN_LEN) != 1U) return 20;
    if (g_lengths[0] != STNP_TASK_FIXED_SIZE) return 21;

    /* 4: enable + unknown TARGET; not enqueued */
    if (STNP_Init(DummyWrite) != STNP_OK) return 22;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    STNP_UnknownFrameCallback_Enable(STNP_ENABLE);
    g_n = 0U;
    if (STNP_Transport_Receive(raw, raw_len) != STNP_OK) return 17;
    if (STNP_Process() != STNP_ERR_TARGET) return 18;
    if (count_reason(STNP_UNKNOWN_TASK) != 1U) return 19;
    if (g_lengths[0] != raw_len) return 20;
    if (STNP_Dispatch() != STNP_IDLE) return 21;

    /* 4b: job full — no Report, no shift */
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 22;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    STNP_UnknownFrameCallback_Enable(STNP_ENABLE);
    g_n = 0U;
    for (i = 0U; i < (STNP_U8)(STNP_JOB_QUEUE_DEPTH + 1U); i++)
    {
        if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_STOP, STNP_NULL) != STNP_OK) return 23;
    }
    for (i = 0U; i < (STNP_U8)STNP_JOB_QUEUE_DEPTH; i++)
    {
        if (STNP_Process() != STNP_OK) return 24;
    }
    if (count_reason(STNP_UNKNOWN_TASK) != 0U) return 25;
    if (STNP_Process() != STNP_ERR_BUFFER) return 26;
    if (g_n != 0U) return 27;
    if (STNP_Process() != STNP_ERR_BUFFER) return 28;

    /* 5: SOF default off even with two-gate */
    if (STNP_Init(DummyWrite) != STNP_OK) return 29;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    STNP_UnknownFrameCallback_Enable(STNP_ENABLE);
    g_n = 0U;
    for (i = 0U; i < 8U; i++) noise[i] = (STNP_U8)i;
    if (STNP_Transport_Receive(noise, 8U) != STNP_OK) return 30;
    if (STNP_Process() != STNP_IDLE) return 31;
    if (count_reason(STNP_UNKNOWN_SOF) != 0U) return 32;

    /* 8: legal task/notify do not enter unknown */
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 33;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    STNP_UnknownFrameCallback_Enable(STNP_ENABLE);
    g_n = 0U;
    g_raw = 0U;
    g_typed = 0U;
    if (STNP_Task_Send(STNP_INSTANCE_CHASSISMAIN_ID, CHASSIS_CMD_STOP, STNP_NULL) != STNP_OK) return 34;
    if (STNP_Process() != STNP_OK) return 35;
    if (STNP_Dispatch() != STNP_OK) return 36;
    Sensor_NotifyCallbackEnable(STNP_ENABLE);
    {
        Sensor_DataPayload p = {0xBEEFU};
        if (STNP_Notify_Send(STNP_INSTANCE_SENSORFRONT_ID, SENSOR_NOTIFY_DATA, SENSOR_OK, &p) != STNP_OK) return 37;
    }
    if (STNP_Process() != STNP_OK) return 38;
    if (STNP_Dispatch() != STNP_OK) return 39;
    if (g_n != 0U) return 40;
    if (g_typed != 1U) return 41;

    /* 7: unknown notify_code, module not claimed → global only, unknown 0 */
    if ((STNP_Init(TransportMock_Write) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 42;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    STNP_UnknownFrameCallback_Enable(STNP_ENABLE);
    g_n = 0U;
    g_raw = 0U;
    g_typed = 0U;
    g_notify_reason = 0U;
    if (STNP_Notify_SendBytes(STNP_INSTANCE_SENSORFRONT_ID, 0x7FU, SENSOR_OK, STNP_NULL) != STNP_OK) return 43;
    if (STNP_Process() != STNP_OK) return 44;
    if (STNP_Dispatch() != STNP_OK) return 45;
    if (g_raw != 1U) return 46;
    if (g_typed != 0U) return 47;
    if (g_n != 0U) return 48;
    if (g_notify_reason != 0U) return 49;
    return 0;
}
''', encoding="utf-8")
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.extend([str(out / "Examples" / "transport_mock.c"), str(harness)])
    sources.append(str(_write_harness_link_stubs(out, raw_callback=False)))
    exe = out / "unknown_frame_test"
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_unknown_frame_c_03_crc_nested(tmp_path: Path):
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw["protocol"]["features"]["crc"]["enabled"] = True
    project = _write_raw_project(tmp_path, raw, "unknown_crc.stnp")
    out = emit_c(load_project(project, _companion_build(project)), tmp_path / "out", _build_data())
    harness = out / "unknown_crc_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"

static STNP_U8 g_tx[STNP_NOTIFY_FIXED_SIZE + STNP_PAYLOAD_MAX + STNP_CRC_SIZE];
static STNP_U16 g_tx_len = 0U;
static STNP_U8 g_notify = 0U;
static STNP_U8 g_crc = 0U;

static STNP_Result CaptureWrite(const STNP_U8 *data, STNP_U16 length)
{
    STNP_U16 i;
    if (length > (STNP_U16)sizeof(g_tx)) return STNP_ERR_LENGTH;
    for (i = 0U; i < length; i++) g_tx[i] = data[i];
    g_tx_len = length;
    return STNP_OK;
}

static void OnUnknown(STNP_UnknownReason reason, const STNP_U8 *data, STNP_U16 length)
{
    STNP_UNUSED(data);
    STNP_UNUSED(length);
    if (reason == STNP_UNKNOWN_CRC) g_crc++;
}

void STNP_Notify_Callback(
    STNP_U8 source,
    STNP_U8 notify_code,
    STNP_U16 result,
    const STNP_U8 *payload,
    STNP_U8 length)
{
    STNP_UNUSED(source); STNP_UNUSED(notify_code); STNP_UNUSED(result);
    STNP_UNUSED(payload); STNP_UNUSED(length);
    g_notify++;
}

int main(void)
{
    STNP_TaskFrame task;
    STNP_U8 bad[STNP_TASK_FIXED_SIZE + STNP_PAYLOAD_MAX + STNP_CRC_SIZE];
    STNP_U16 bad_len = 0U;
    STNP_U8 chunk[128];
    STNP_U16 i;
    STNP_U16 total;
    STNP_Result result;

    if ((STNP_Init(CaptureWrite) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    STNP_UnknownFrameCallback_Enable(STNP_ENABLE);
    if (STNP_Notify_Send(
            STNP_INSTANCE_CHASSISMAIN_ID,
            CHASSIS_NOTIFY_DONE,
            CHASSIS_OK,
            STNP_NULL) != STNP_OK) return 2;
    task.target = STNP_INSTANCE_CHASSISMAIN_ID;
    task.code = CHASSIS_CMD_STOP;
    task.length = 0U;
    if (STNP_Frame_BuildTask(&task, bad, (STNP_U16)sizeof(bad), &bad_len) != STNP_OK) return 3;
    if (bad_len == 0U) return 4;
    bad[bad_len - 1U] ^= 0xFFU;
    if ((STNP_U16)(bad_len + g_tx_len) > (STNP_U16)sizeof(chunk)) return 5;
    for (i = 0U; i < bad_len; i++) chunk[i] = bad[i];
    for (i = 0U; i < g_tx_len; i++) chunk[bad_len + i] = g_tx[i];
    total = (STNP_U16)(bad_len + g_tx_len);
    if (STNP_Transport_Receive(chunk, total) != STNP_OK) return 6;
    result = STNP_Process();
    if (result == STNP_OK || result == STNP_IDLE) return 7;
    if (g_crc != 1U) return 8;
    if (STNP_Process() != STNP_OK) return 9;
    if (g_notify != 0U) return 10;
    if (STNP_Dispatch() != STNP_OK) return 11;
    return (g_notify == 1U && g_crc == 1U) ? 0 : 12;
}
''', encoding="utf-8")
    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    exe = out / "unknown_crc_test"
    sources = []
    for pattern in ("Core/*.c", "Module/*.c", "Module/*/*.c", "Instance/*.c"):
        sources.extend(str(p) for p in sorted(out.glob(pattern)))
    sources.append(str(harness))
    sources.append(str(_write_harness_link_stubs(out, raw_callback=False)))
    subprocess.run(
        ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I.", *sources, "-o", str(exe)],
        cwd=out, check=True, capture_output=True, text=True,
    )
    subprocess.run([str(exe)], cwd=out, check=True)


def test_unknown_frame_c_05_sof_second_switch(tmp_path: Path):
    out = emit_c(load_project(DEMO, BUILD), tmp_path, _build_data())
    harness = out / "unknown_sof_harness.c"
    harness.write_text(r'''#include "Core/stnp.h"
#include "Instance/stnp_instances.h"

static STNP_U8 g_sof = 0U;

static void OnUnknown(STNP_UnknownReason reason, const STNP_U8 *data, STNP_U16 length)
{
    if (reason == STNP_UNKNOWN_SOF && length == 1U && data != STNP_NULL)
    {
        g_sof++;
    }
}

static STNP_Result DummyWrite(const STNP_U8 *data, STNP_U16 length)
{
    STNP_UNUSED(data);
    STNP_UNUSED(length);
    return STNP_OK;
}

int main(void)
{
    STNP_U8 noise[8];
    STNP_U8 i;
    if ((STNP_Init(DummyWrite) != STNP_OK) || (STNP_Instances_Init() != STNP_OK)) return 1;
    STNP_UnknownFrame_SetCallback(OnUnknown);
    STNP_UnknownFrameCallback_Enable(STNP_ENABLE);
    for (i = 0U; i < 8U; i++) noise[i] = (STNP_U8)i;
    if (STNP_Transport_Receive(noise, 8U) != STNP_OK) return 2;
    if (STNP_Process() != STNP_IDLE) return 3;
    return (g_sof == 7U) ? 0 : 4;
}
''', encoding="utf-8")
    exe = _compile(
        out,
        main=harness,
        extra_cflags=["-DSTNP_UNKNOWN_REPORT_SOF=1"],
        exe_name="unknown_sof_test",
    )
    subprocess.run([str(exe)], cwd=out, check=True)

