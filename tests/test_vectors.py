from __future__ import annotations

import json
from pathlib import Path

from stnp_editor.loader import load_project
from stnp_editor.vectors import build_vectors, crc16_modbus, encode_u16

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "C" / "regression_c.stnp"
FIXTURE_BUILD = ROOT / "fixtures" / "C" / "stnp.build.json"

#: ``tests/golden/C/regression_c/vectors.json`` records the historical project
#: name baked into the golden vectors.  Rebuild that raw project name from the
#: shared fixture so this module keeps comparing the fixture payload unchanged.
_VECTOR_PROJECT_NAME = "multi_demo"


def _multi_raw() -> dict:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["project_name"] = _VECTOR_PROJECT_NAME
    return raw


def _base_ir(tmp_path: Path):
    project = tmp_path / "multi_demo.stnp"
    project.write_text(json.dumps(_multi_raw(), ensure_ascii=False, indent=2), encoding="utf-8")
    return load_project(project, FIXTURE_BUILD)


def _frame(hex_str: str) -> list[int]:
    return [int(b, 16) for b in hex_str.split()]


def _payload_sizes(ir) -> dict[tuple[str, str, str], int]:
    """Wire byte length of each vector payload, derived from IR field sizes."""
    sizes: dict[tuple[str, str, str], int] = {}
    for inst in ir.instances:
        for cmd in inst.module.commands:
            sizes[("task", inst.name, cmd.name)] = sum(f.size for f in cmd.fields)
        for ntf in inst.module.notifications:
            sizes[("notify", inst.name, ntf.name)] = sum(f.size for f in ntf.fields)
    return sizes


def _variant_ir(tmp_path: Path, *, seq: bool | None = None, crc: bool | None = None):
    """Build a regression_c IR in a temp dir; the shared fixture stays untouched."""
    raw = _multi_raw()
    features = raw["protocol"].setdefault("features", {})
    if seq is not None:
        features["seq"] = {"enabled": seq}
    if crc is not None:
        features.setdefault("crc", {})["enabled"] = crc
    project = tmp_path / "multi_demo.stnp"
    project.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_project(project, FIXTURE_BUILD)


def _of_kind(payload: dict, kind: str) -> list[dict]:
    return [v for v in payload["vectors"] if v["kind"] == kind]


def test_golden_vectors_match_ir(tmp_path: Path):
    ir = _base_ir(tmp_path)
    got = build_vectors(ir)
    golden = json.loads(
        (ROOT / "tests" / "golden" / "C" / "regression_c" / "vectors.json").read_text(encoding="utf-8")
    )
    assert got == golden


def test_seq_off_task_frames_have_no_seq_slot(tmp_path: Path):
    ir = _base_ir(tmp_path)
    payload = build_vectors(ir)
    assert payload["seq_enabled"] is False
    assert payload["task_fixed_size"] == 5
    sizes = _payload_sizes(ir)
    for v in _of_kind(payload, "task"):
        frame = _frame(v["hex"])
        size = sizes[("task", v["instance"], v["command"])]
        assert len(frame) == 5 + size
        assert frame[0:2] == [0xAA, 0x55]
        # bytes 3-4 are TARGET/CMD directly after SOF, not a SEQ u16
        assert frame[2] == v["target"]
        assert frame[3] == v["code"]
        assert frame[4] == size


def test_seq_on_task_frames_place_seq_after_sof(tmp_path: Path):
    ir = _variant_ir(tmp_path, seq=True)
    payload = build_vectors(ir)
    assert payload["seq_enabled"] is True
    assert payload["task_fixed_size"] == 7
    assert payload["notify_fixed_size"] == 9
    sizes = _payload_sizes(ir)
    for v in _of_kind(payload, "task"):
        frame = _frame(v["hex"])
        size = sizes[("task", v["instance"], v["command"])]
        assert len(frame) == 7 + size
        assert frame[0:2] == [0xAA, 0x55]
        assert frame[2:4] == [0x01, 0x00]  # sampled SEQ = 1, u16 little-endian
        assert frame[4] == v["target"]
        assert frame[5] == v["code"]
        assert frame[6] == size


def test_notify_frames_size_and_seq_placement(tmp_path: Path):
    off_ir = _base_ir(tmp_path)
    off = build_vectors(off_ir)
    assert off["notify_fixed_size"] == 7
    sizes = _payload_sizes(off_ir)
    for v in _of_kind(off, "notify"):
        frame = _frame(v["hex"])
        size = sizes[("notify", v["instance"], v["notify"])]
        assert len(frame) == 7 + size
        assert frame[0:2] == [0xAA, 0x33]
        # no SEQ: SOURCE follows SOF directly
        assert frame[2] == v["source"]
        assert frame[3] == v["notify_code"]

    on_ir = _variant_ir(tmp_path, seq=True)
    on = build_vectors(on_ir)
    assert on["notify_fixed_size"] == 9
    sizes = _payload_sizes(on_ir)
    for v in _of_kind(on, "notify"):
        frame = _frame(v["hex"])
        size = sizes[("notify", v["instance"], v["notify"])]
        assert len(frame) == 9 + size
        assert frame[0:2] == [0xAA, 0x33]
        # SEQ sits after SOF and before SOURCE
        assert frame[2:4] == [0x01, 0x00]
        assert frame[4] == v["source"]
        assert frame[5] == v["notify_code"]
        assert frame[8] == size


def test_crc_on_frames_carry_le_crc_of_body(tmp_path: Path):
    ir = _variant_ir(tmp_path, crc=True)
    payload = build_vectors(ir)
    assert payload["crc_enabled"] is True
    for v in payload["vectors"]:
        frame = _frame(v["hex"])
        body = frame[:-2]
        assert frame[-2:] == encode_u16(crc16_modbus(body))
