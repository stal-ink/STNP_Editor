from __future__ import annotations

import tempfile
from pathlib import Path

from stnp_editor.cli import _diff_trees
from stnp_editor.emit.c import emit_c
from stnp_editor.emit.python import emit_python
from stnp_editor.loader import load_build_data, load_project

ROOT = Path(__file__).resolve().parents[1]


def _assert_matches_golden(project: Path, build_json: Path, golden: Path, emitter) -> None:
    build = load_build_data(build_json)
    ir = load_project(project, build_json)
    with tempfile.TemporaryDirectory(prefix="stnp_golden_") as tmp:
        out = emitter(ir, Path(tmp), build)
        expected = golden / out.name
        diffs = _diff_trees(out, expected)
        assert not diffs, "\n".join(diffs)


def test_c_regression_fixture_matches_c_golden() -> None:
    _assert_matches_golden(
        ROOT / "fixtures" / "C" / "regression_c.stnp",
        ROOT / "fixtures" / "C" / "stnp.build.json",
        ROOT / "tests" / "golden" / "C" / "regression_c",
        emit_c,
    )


def test_python_regression_fixture_matches_python_golden() -> None:
    _assert_matches_golden(
        ROOT / "fixtures" / "python" / "regression_py.stnp",
        ROOT / "fixtures" / "python" / "stnp.build.json",
        ROOT / "tests" / "golden" / "python" / "regression_py",
        emit_python,
    )
