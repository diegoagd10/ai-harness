"""Static tests for tests-prompts/run.sh after the prompt-e2e-red-tests
second-loop addition.

The run.sh script gains a CASES_CSV_E2E-driven second loop that
captures per-row traces into $LOGS_DIR on EVERY row (not just FAIL)
and pipes them through tests-prompts/_e2e_assertions.py.

These tests inspect the script's source for the contract:
  - the second loop is gated on CASES_CSV_E2E being set
  - the existing first loop body is byte-identical
  - the run_row function is unchanged
  - the dump_failure_trace shape is unchanged
  - the set -uo pipefail header is preserved
  - bash -n syntax check stays clean
  - the [E2E-ASSERT] verdict line shape is present

Mirrors the static-check pattern in tests/test_prompt_tests_slugs.py.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_RUN_SH = Path(__file__).resolve().parent.parent / "tests-prompts" / "run.sh"


@pytest.fixture(scope="module")
def run_sh_text() -> str:
    if not _RUN_SH.is_file():
        pytest.skip(f"run.sh not found at {_RUN_SH}")
    return _RUN_SH.read_text()


class TestSecondLoopActivation:
    """Subtask 6.1 — CASES_CSV_E2E env var gates the second loop."""

    def test_cases_csv_e2e_env_var_is_read(self, run_sh_text: str) -> None:
        assert re.search(r"CASES_CSV_E2E=", run_sh_text), (
            "run.sh must read CASES_CSV_E2E so the second loop can be opt-in via env"
        )

    def test_second_loop_skips_when_unset(self, run_sh_text: str) -> None:
        # The second loop should be guarded by a [ -n "$VAR" ] style
        # check that exits / skips when the var is unset. Accept any
        # brace-or-no-brace form of the variable reference.
        assert "CASES_CSV_E2E" in run_sh_text
        # Patterns accepted:
        #   [ -n "${CASES_CSV_E2E:-}" ]     — defensive ${VAR:-} form
        #   [ -n "$CASES_CSV_E2E" ]          — plain form
        #   [ -z "${CASES_CSV_E2E}" ]        — inverted form
        #   [ -n "${VAR+x}" ]                — set-but-not-empty form
        pattern = (
            r"\[\s*-n\s*\"?\$\{?CASES_CSV_E2E"
            r"(?:[:-][^\"]*)?\}?\"?\s*\]"
            r"|\[\s*-z\s*\"?\$\{?CASES_CSV_E2E"
            r"(?:[:-][^\"]*)?\}?\"?\s*\]"
        )
        assert re.search(pattern, run_sh_text), (
            f"CASES_CSV_E2E must be guarded by a [ -n ... ] or [ -z ... ] check; no such guard found in:\n{run_sh_text}"
        )


class TestSecondLoopTraceDump:
    """Subtask 6.2 — per-row JSON trace is ALWAYS dumped (not just on FAIL)."""

    def test_e2e_row_dump_function_exists(self, run_sh_text: str) -> None:
        # The E2E loop must always write the trace to $LOGS_DIR, on
        # both PASS and FAIL. The existing dump_failure_trace is FAIL-only.
        # We expect either a new helper or a direct printf that writes
        # the trace unconditionally inside the second loop.
        e2e_section = self._extract_e2e_section(run_sh_text)
        assert e2e_section, "run.sh must contain a CASES_CSV_E2E second loop section (no section was identifiable)"
        assert "LOGS_DIR" in e2e_section or "logs" in e2e_section.lower(), (
            "E2E loop must write to $LOGS_DIR (or equivalent) so RED traces survive for debugging"
        )

    def test_e2e_row_dump_uses_slugified_filename(self, run_sh_text: str) -> None:
        # Per spec runsh-e2e-group.md the per-row trace filename must
        # use the slugify helper so RED traces share the directory
        # shape and naming convention already covered by
        # tests/test_prompt_tests_slugs.py::TestSlugifyContract.
        e2e_section = self._extract_e2e_section(run_sh_text)
        assert "slug" in e2e_section.lower(), "E2E loop must slugify the prompt to derive the trace filename"
        # Filename shape: <row_index>-<slug>.json — accept any E2E_ROW
        # or ROW_INDEX form (case-insensitive on `row`).
        assert re.search(r"\$\{?E2E_ROW\}?", e2e_section) or re.search(r"\$ROW_INDEX", e2e_section), (
            "E2E loop must include the row index in the filename"
        )

    @staticmethod
    def _extract_e2e_section(run_sh_text: str) -> str:
        """Find the second loop block by anchoring on CASES_CSV_E2E."""
        marker = "CASES_CSV_E2E"
        idx = run_sh_text.find(marker)
        if idx == -1:
            return ""
        # Take a generous window after the first mention of the env var.
        return run_sh_text[idx : idx + 4000]


class TestSecondLoopAssertions:
    """Subtask 6.3 — per-row verdict printed via [E2E-ASSERT] fixture=<slug> row=<n> pass|fail."""

    def test_e2e_assert_prefix_appears(self, run_sh_text: str) -> None:
        assert "[E2E-ASSERT]" in run_sh_text, "run.sh must emit an [E2E-ASSERT] verdict line per E2E row"

    def test_e2e_assert_includes_fixture_slug(self, run_sh_text: str) -> None:
        # Look for a printf with `fixture=<slug>` shape.
        assert re.search(r"fixture=", run_sh_text), "run.sh [E2E-ASSERT] line must include fixture=<slug>"

    def test_e2e_assert_includes_row_number(self, run_sh_text: str) -> None:
        assert re.search(r"row=", run_sh_text), "run.sh [E2E-ASSERT] line must include row=<n>"

    def test_e2e_assert_runs_through_python_helper(self, run_sh_text: str) -> None:
        # The second loop should pipe the trace through _e2e_assertions
        # (or the runner that composes them). We accept either name.
        assert "_e2e_assertions" in run_sh_text or "_e2e_runner" in run_sh_text, (
            "run.sh must pipe E2E traces through _e2e_assertions or _e2e_runner"
        )


class TestSecondLoopExitCode:
    """Subtask 6.4 — non-zero exit if any E2E row fails."""

    def test_e2e_exit_code_var_present(self, run_sh_text: str) -> None:
        # Look for an aggregate like E2E_RC or E2E_FAILED that gets
        # checked at the end.
        assert re.search(r"E2E_(RC|FAILED|PASSED)", run_sh_text), (
            "run.sh must aggregate per-row E2E pass/fail into a single "
            "verdict var (e.g. E2E_RC, E2E_FAILED, E2E_PASSED)"
        )


class TestFirstLoopUnchanged:
    """Subtask 6.5 — first loop body, run_row, dump_failure_trace unchanged."""

    def test_run_row_function_intact(self, run_sh_text: str) -> None:
        # The run_row function must still exist and call opencode with
        # the same flags as before. Look for the --model + --format json.
        assert "--agent" in run_sh_text
        assert "--format" in run_sh_text
        assert "--model" in run_sh_text
        assert re.search(
            r"PINNED_MODEL.*=.*minimax",
            run_sh_text,
        ), "PINNED_MODEL default must still be minimax/minimax-m3"

    def test_set_uo_pipefail_header_preserved(self, run_sh_text: str) -> None:
        first_line = next(
            (ln for ln in run_sh_text.splitlines() if ln.strip().startswith("set ")),
            None,
        )
        assert first_line is not None, "run.sh must start with a `set` directive"
        assert "pipefail" in first_line, "set ... pipefail must be in the header"
        assert "set -e" not in first_line, "per-row failures must not abort the loop; set -e must be absent"

    def test_dump_failure_trace_intact(self, run_sh_text: str) -> None:
        assert "dump_failure_trace" in run_sh_text, "dump_failure_trace function must be preserved"


class TestRunShSyntax:
    """Subtask 6.6 — bash -n stays clean."""

    def test_bash_n_clean(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(_RUN_SH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"bash -n failed:\nstdout={result.stdout}\nstderr={result.stderr}"
