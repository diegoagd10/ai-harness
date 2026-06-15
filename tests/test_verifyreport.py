"""Verify-report heuristic: pass/fail/blocked heuristics per spec R5.

Ported from cli.bak/tests/test_verifyreport.py. Tests pure-function logic
on report_is_clearly_passing — must be importable and pass on valid content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.sdd.verifyreport import report_is_clearly_passing

CASES = [
    ("blank report", "   \n\t\n", False),
    ("bare PASS line", "PASS\n", True),
    ("status field pass", "# Verify\nStatus: PASS\n", True),
    ("all checks passed phrase", "# Verify\nAll checks passed.\n", True),
    ("ready for archive phrase", "Ready for archive\n", True),
    ("pass with warnings verdict", "Verdict: PASS WITH WARNINGS\n", True),
    ("no pass signal at all", "# Verify\nSome prose only.\n", False),
    ("pass but failed count nonzero", "PASS\nfailed: 2\n", False),
    ("pass but zero failed is benign", "PASS\nfailed: 0\n", True),
    ("N failed reversed order", "PASS\n3 failed\n", False),
    ("critical none is benign", "PASS\n**CRITICAL**: None\n", True),
    ("critical with content blocks", "PASS\ncritical: data loss\n", False),
    ("blockers no blockers benign", "PASS\nBlockers: no blockers\n", True),
    ("verdict fail blocks", "Verdict: FAIL\n", False),
    ("glyph fail status blocks", "PASS\n\u274c FAILING\n", False),
    ("pass colon no blocks", "PASS: no\n", False),
    ("not complete blocks", "PASS\nWork is not complete\n", False),
    ("todo blocks", "PASS\nTODO: run e2e\n", False),
    ("pending blocks", "PASS\nPENDING review\n", False),
    ("bullet field pass", "- **Verdict**: PASS\n", True),
    ("todo adjacent to non-ascii blocks", "PASS\nTODO\u00e9 marker\n", False),
    ("failed count adjacent to non-ascii blocks", "PASS\n3 failed\u00e9\n", False),
]


def test_empty_path_is_not_passing():
    assert report_is_clearly_passing("") is False


@pytest.mark.parametrize("name, content, want", CASES, ids=[c[0] for c in CASES])
def test_report_is_clearly_passing(tmp_path: Path, name: str, content: str, want: bool):
    report = tmp_path / "verify-report.md"
    report.write_text(content, encoding="utf-8")
    assert report_is_clearly_passing(str(report)) is want
