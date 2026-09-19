"""Root pytest configuration: toolchain bootstrap + one fixed design-skip notice.

Bootstrap (S4/D5): before any test is collected, ``tests/_toolchain.py`` resolves
``gcc`` and ``cmake`` through the shared three-level order (environment variable ->
PATH -> loud failure), prepends the directories it actually found to ``PATH`` and
sets ``CMAKE_GENERATOR=MinGW Makefiles`` on Windows.
Nothing is fabricated: an unresolved tool prints the resolver's one-line guidance
and the toolchain-gated tests keep skipping, which ``scripts/test.ps1 -FailOnSkip``
then reports as UNEXPECTED (D7).  The chosen tools are printed with their source
(D11) and the fixed D12 disclaimer is part of the same header.

Design-skip notice: after the run, if any test was skipped for a design reason -- a
skip reason mentioning ``STNP_TEST_EXE`` or ``stnpe`` (case-insensitive) -- print one
fixed notice block explaining how to enable those tests, listing only the note lines
whose keyword actually matched.  If neither kind of skip occurred, print nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import _toolchain  # imported after the tests directory joins sys.path

_BOOTSTRAPPED, _BOOTSTRAP_FAILURES = _toolchain.bootstrap()

_DESIGN_SKIP_NOTES = (
    ("STNP_TEST_EXE", "  - packaging tests: set STNP_TEST_EXE=1 to run"),
    ("stnpe", "  - cli e2e: run pip install -e . to enable"),
)

_HEADER = "-" * 27 + " skipped " + "-" * 27
_LEAD_IN = "Some tests were skipped by design:"
_FOOTER = "-" * 65


def _write_boot_lines(write_line) -> None:
    """Print the D11 tool lines and the D12 disclaimer, then any loud failure."""
    for tool in _BOOTSTRAPPED:
        write_line(tool.describe())
    for failure in _BOOTSTRAP_FAILURES:
        write_line("WARNING: " + failure)
    write_line(_toolchain.DISCLAIMER)


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    """Surface the resolved toolchain on every run, quiet mode included."""
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        _write_boot_lines(reporter.write_line)
    else:  # pragma: no cover - only when the terminal plugin is disabled
        _write_boot_lines(print)


def _skip_reason(report: pytest.TestReport) -> str:
    """Return a skipped report's reason text regardless of pytest's encoding."""
    longrepr = report.longrepr
    if isinstance(longrepr, tuple) and len(longrepr) >= 3:
        return str(longrepr[2])
    return str(longrepr)


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """Print the design-skip notice once, listing only applicable notes."""
    reasons = [
        _skip_reason(report).casefold()
        for report in terminalreporter.stats.get("skipped", [])
    ]
    notes = [
        note
        for keyword, note in _DESIGN_SKIP_NOTES
        if any(keyword.casefold() in reason for reason in reasons)
    ]
    if not notes:
        return
    terminalreporter.write_line(_HEADER)
    terminalreporter.write_line(_LEAD_IN)
    for note in notes:
        terminalreporter.write_line(note)
    terminalreporter.write_line(_FOOTER)
