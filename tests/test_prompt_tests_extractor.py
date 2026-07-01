"""Tests for the schema-aware extract_counts helper.

These tests lock down the opencode JSON event contract for the prompt
test suite. If opencode ever renames its tool-name field or its event
type, these tests fail and point straight at the single helper that
needs to change.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load tests-prompts/_extractor.py as a real module (the run.sh script
# invokes it via `python3 /tests-prompts/_extractor.py` per row).
# ---------------------------------------------------------------------------
_HELPERS = Path(__file__).resolve().parent.parent / "tests-prompts" / "_extractor.py"
_spec = importlib.util.spec_from_file_location("_extractor", _HELPERS)
assert _spec and _spec.loader, f"could not load _extractor.py from {_HELPERS}"
_extractor = importlib.util.module_from_spec(_spec)
sys.modules["_extractor"] = _extractor
_spec.loader.exec_module(_extractor)


extract_counts = _extractor.extract_counts


# ---------------------------------------------------------------------------
# Test data — synthetic opencode --format json streams
# ---------------------------------------------------------------------------


def _event(tool: str) -> str:
    """One realistic tool_use event: top-level type=tool_use, part.type=tool."""
    return (
        '{"type":"tool_use","timestamp":0,"sessionID":"s",'
        f'"part":{{"type":"tool","tool":"{tool}","state":{{"status":"completed"}}}}}}'
    )


def _text_event(text: str = "hello") -> str:
    return f'{{"type":"text","timestamp":0,"sessionID":"s","part":{{"type":"text","text":"{text}"}}}}'


def _step_start() -> str:
    return '{"type":"step_start","timestamp":0,"sessionID":"s","part":{"type":"step-start"}}'


def _step_finish() -> str:
    return '{"type":"step_finish","timestamp":0,"sessionID":"s","part":{"type":"step-finish"}}'


# ---------------------------------------------------------------------------
# Scenarios from disjoint-count-assertion spec
# ---------------------------------------------------------------------------


class TestDisjointBuckets:
    def test_skill_call_increments_skills_bucket(self) -> None:
        trace = "\n".join([_step_start(), _event("skill"), _step_finish()]) + "\n"
        tools, skills, sub_agents = extract_counts(trace)
        assert skills == 1
        assert tools == 0
        assert sub_agents == 0

    def test_task_call_increments_sub_agents_bucket(self) -> None:
        trace = "\n".join([_step_start(), _event("task"), _step_finish()]) + "\n"
        tools, skills, sub_agents = extract_counts(trace)
        assert sub_agents == 1
        assert tools == 0
        assert skills == 0

    def test_other_tool_increments_tools_bucket(self) -> None:
        for name in ("read", "bash", "write", "edit", "glob", "grep"):
            trace = "\n".join([_step_start(), _event(name), _step_finish()]) + "\n"
            tools, skills, sub_agents = extract_counts(trace)
            assert tools == 1, f"{name} should land in tools bucket"
            assert skills == 0
            assert sub_agents == 0

    def test_three_buckets_disjoint_and_exhaustive(self) -> None:
        # 2 tools, 3 skills, 4 task calls in any order -> union = 9.
        events = [
            _event("read"),
            _event("skill"),
            _event("bash"),
            _event("task"),
            _event("skill"),
            _event("task"),
            _event("task"),
            _event("skill"),
            _event("task"),
        ]
        trace = _step_start() + "\n" + "\n".join(events) + "\n" + _step_finish() + "\n"
        tools, skills, sub_agents = extract_counts(trace)
        assert (tools, skills, sub_agents) == (2, 3, 4)
        assert tools + skills + sub_agents == 9


class TestNonToolEventsIgnored:
    def test_text_events_dont_move_any_counter(self) -> None:
        trace = "\n".join([_step_start(), _text_event("hello"), _step_finish()]) + "\n"
        tools, skills, sub_agents = extract_counts(trace)
        assert (tools, skills, sub_agents) == (0, 0, 0)

    def test_mixed_text_and_tools_only_tools_count(self) -> None:
        trace = (
            "\n".join(
                [_step_start(), _text_event("thinking..."), _event("read"), _text_event("answer"), _step_finish()]
            )
            + "\n"
        )
        tools, skills, sub_agents = extract_counts(trace)
        assert (tools, skills, sub_agents) == (1, 0, 0)


class TestRobustParsing:
    def test_non_json_lines_skipped_silently(self) -> None:
        # Opencode can sometimes emit warning chatter between events.
        trace = (
            "\n".join(
                [
                    _step_start(),
                    "WARN: connection pool retry",
                    _event("read"),
                    "DEBUG: model returned 200",
                    _step_finish(),
                ]
            )
            + "\n"
        )
        tools, skills, sub_agents = extract_counts(trace)
        assert (tools, skills, sub_agents) == (1, 0, 0)

    def test_empty_input_returns_zeros(self) -> None:
        assert extract_counts("") == (0, 0, 0)

    def test_only_whitespace_returns_zeros(self) -> None:
        assert extract_counts("\n\n   \n") == (0, 0, 0)

    def test_hello_row_trace_has_zero_tool_calls(self) -> None:
        # Mirrors disjoint-count-assertion:smoke-row-hello scenario.
        trace = "\n".join([_step_start(), _text_event("Hey!"), _step_finish()]) + "\n"
        assert extract_counts(trace) == (0, 0, 0)

    def test_hello_prompt_live_with_minimax_m3(self) -> None:
        """End-to-end smoke against real opencode if available + reachable.

        Skips when opencode --version cannot be run (CI without opencode).
        """
        import shutil
        import subprocess

        if not shutil.which("opencode"):
            pytest.skip("opencode not installed in this environment")

        # Use a tmp workdir so change-orchestrator can run with a known dir.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    "opencode",
                    "run",
                    "--agent",
                    "change-orchestrator",
                    "--auto",
                    "--format",
                    "json",
                    "--model",
                    "minimax/MiniMax-M3",
                    "--dir",
                    tmp,
                    "hello",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            trace = result.stdout
            assert extract_counts(trace) == (0, 0, 0), "real change-orchestrator on 'hello' should emit zero tool calls"
