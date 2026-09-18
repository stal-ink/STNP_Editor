"""Root pytest configuration: one fixed design-skip notice.

After the run, if any test was skipped for a design reason -- a skip reason
mentioning ``STNP_TEST_EXE`` or ``stnpe`` (case-insensitive) -- print one fixed
notice block explaining how to enable those tests, listing only the note lines
whose keyword actually matched.  If neither kind of skip occurred, print
nothing at all.
"""

from __future__ import annotations

import pytest

_DESIGN_SKIP_NOTES = (
    ("STNP_TEST_EXE", "  - packaging tests: set STNP_TEST_EXE=1 to run"),
    ("stnpe", "  - cli e2e: run pip install -e . to enable"),
)

_HEADER = "-" * 27 + " skipped " + "-" * 27
_LEAD_IN = "Some tests were skipped by design:"
_FOOTER = "-" * 65


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
