"""Unconditional unit tests for the prompt-E2E RED helpers.

Covers:
  - `tests-prompts/_extractor.tool_sequence(events)` — ordered tool-name list.
  - `tests-prompts/_e2e_assertions.has_bash_ai_harness_change`,
    `has_task_subagent`, `final_assistant_text_contains` — routing predicates.

These tests guard the helpers themselves so they cannot regress silently.
They run in default CI without env gates; the live RED pytest files
(`tests/test_prompt_e2e_red.py`, `tests/test_prompt_e2e_red_dispatch.py`)
are env-gated and live separately.

The tests load both helper modules from `tests-prompts/` via
`importlib.util.spec_from_file_location` (the same pattern used by
`tests/test_prompt_tests_extractor.py`) so the test file does not
require the helper modules to live on `sys.path`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Loader: tests-prompts/_extractor.py is a real file, not on sys.path,
# loaded by importlib to mirror run.sh's `python3 /tests-prompts/_extractor.py`
# invocation. _e2e_assertions is loaded when present (task 2 onwards).
# ---------------------------------------------------------------------------
_HELPERS_DIR = Path(__file__).resolve().parent.parent / "tests-prompts"


def _load(module_name: str, file_name: str):
    path = _HELPERS_DIR / file_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader, f"could not load {file_name} from {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_extractor = _load("_extractor", "_extractor.py")

# _e2e_assertions is required for the unit suite — the file must exist.
# Loaded unconditionally so the suite fails loud if the module is missing
# rather than silently skipping.
_e2e_assertions = _load("_e2e_assertions", "_e2e_assertions.py")


# ---------------------------------------------------------------------------
# Synthetic event builders — operate on already-parsed dicts (the helpers
# consume list[dict], not raw JSON strings).
# ---------------------------------------------------------------------------


def _tool_event(tool: str, command: str | None = None) -> dict:
    """One realistic `tool_use` event with optional `bash` command payload."""
    part: dict = {"type": "tool", "tool": tool}
    if command is not None:
        part["state"] = {"status": "completed", "input": {"command": command}}
    else:
        part["state"] = {"status": "completed"}
    return {"type": "tool_use", "timestamp": 0, "sessionID": "s", "part": part}


def _text_event(text: str = "hello") -> dict:
    return {
        "type": "text",
        "timestamp": 0,
        "sessionID": "s",
        "part": {"type": "text", "text": text},
    }


def _assistant_message_event(text: str) -> dict:
    return {
        "type": "assistant_message",
        "timestamp": 0,
        "sessionID": "s",
        "part": {"type": "text", "text": text},
    }


def _step_start_event() -> dict:
    return {
        "type": "step_start",
        "timestamp": 0,
        "sessionID": "s",
        "part": {"type": "step-start"},
    }


# ---------------------------------------------------------------------------
# tool_sequence — coverage for task 1 subtasks 1.1 / 1.2 / 1.3
# ---------------------------------------------------------------------------


class TestToolSequence:
    """`_extractor.tool_sequence(events) -> list[str]` is the ordered
    tool-name list extracted from `part.tool` of every `tool_use` event
    whose `part.type == "tool"`. Non-tool events are filtered out; an
    empty event list yields `[]`.
    """

    def test_returns_ordered_sequence_over_mixed_stream(self) -> None:
        # Scenario 1.1 — preserves event order over a mixed tool stream.
        events = [
            _tool_event("bash"),
            _tool_event("read"),
            _tool_event("task"),
        ]
        assert _extractor.tool_sequence(events) == ["bash", "read", "task"]

    def test_filters_non_tool_events_out(self) -> None:
        # Scenario 1.2 — text / assistant_message / step_start events
        # never appear in the returned list.
        events = [
            _step_start_event(),
            _tool_event("bash"),
            _text_event("thinking..."),
            _tool_event("read"),
            _assistant_message_event("answer"),
            _tool_event("task"),
        ]
        assert _extractor.tool_sequence(events) == ["bash", "read", "task"]

    def test_empty_input_returns_empty_list(self) -> None:
        # Scenario 1.3 — empty event list must NOT crash; returns [].
        assert _extractor.tool_sequence([]) == []

    def test_tool_only_events_yield_exact_sequence(self) -> None:
        # Adjacent tool events with no interleaved non-tool events.
        events = [_tool_event("bash"), _tool_event("bash"), _tool_event("read")]
        assert _extractor.tool_sequence(events) == ["bash", "bash", "read"]

    def test_no_tool_events_yields_empty_list(self) -> None:
        # No qualifying events at all → empty list (not None, not a crash).
        events = [
            _step_start_event(),
            _text_event("hello"),
            _assistant_message_event("world"),
        ]
        assert _extractor.tool_sequence(events) == []


# ---------------------------------------------------------------------------
# _e2e_assertions helpers — coverage for task 2 subtasks 2.1 / 2.2 / 2.3 / 2.4
# ---------------------------------------------------------------------------

# The helpers live in tests-prompts/_e2e_assertions.py. The test file
# loads them via importlib only when the module exists (task 2+).


@pytest.fixture(scope="module")
def e2e():
    """Return the already-loaded _e2e_assertions module.

    The module is loaded unconditionally at module import time so this
    fixture is a thin alias that keeps the test signatures readable.
    """
    return _e2e_assertions


def _text_event_with_payload(text: str, event_type: str = "text") -> dict:
    """Text event with a configurable top-level type (text / assistant_message)."""
    return {
        "type": event_type,
        "timestamp": 0,
        "sessionID": "s",
        "part": {"type": "text", "text": text},
    }


class TestHasBashAiHarnessChange:
    """`has_bash_ai_harness_change(events, subcmd)` matches a bash
    `tool_use` whose `part.state.input.command` contains the literal
    substring `ai-harness change-<subcmd>`. Case-sensitive against the
    literal `ai-harness change-` prefix.
    """

    def test_matches_change_new_bash_invocation(self, e2e) -> None:
        # Scenario 2.1 — positive path for change-new.
        events = [
            _tool_event("bash", command="ai-harness change-new mario-kart-3d"),
        ]
        assert e2e.has_bash_ai_harness_change(events, "change-new") is True

    def test_ignores_non_ai_harness_bash_invocation(self, e2e) -> None:
        # Negative path — `ls -la` is bash but does NOT call ai-harness.
        events = [
            _tool_event("bash", command="ls -la /tmp"),
        ]
        assert e2e.has_bash_ai_harness_change(events, "change-new") is False

    def test_matches_change_continue_without_code_change(self, e2e) -> None:
        # Sub-agnostic substring mechanism: change-continue matches without
        # a per-subcmd branch.
        events = [
            _tool_event("bash", command="ai-harness change-continue prompt-e2e-red-tests"),
        ]
        assert e2e.has_bash_ai_harness_change(events, "change-continue") is True

    def test_matches_when_substring_appears_alongside_other_args(self, e2e) -> None:
        # Whitespace + flags + quotes around the cli invocation — the
        # substring match must still fire.
        events = [
            _tool_event("bash", command="cd /work && ai-harness change-new mario"),
        ]
        assert e2e.has_bash_ai_harness_change(events, "change-new") is True

    def test_ignores_bash_tool_use_without_command_field(self, e2e) -> None:
        # A bash event with no command payload must not crash; treat as no-match.
        events = [_tool_event("bash")]
        assert e2e.has_bash_ai_harness_change(events, "change-new") is False

    def test_ignores_non_bash_tool_calls(self, e2e) -> None:
        # A read / write / edit event cannot satisfy the helper.
        events = [
            _tool_event("read"),
            _tool_event("write"),
            _tool_event("edit"),
        ]
        assert e2e.has_bash_ai_harness_change(events, "change-new") is False


class TestHasTaskSubagent:
    """`has_task_subagent(events)` matches any tool_use with `part.tool == "task"`."""

    def test_matches_task_tool_use(self, e2e) -> None:
        # Scenario 2.2 — positive path.
        events = [_tool_event("task")]
        assert e2e.has_task_subagent(events) is True

    def test_ignores_bash_and_other_tool_uses(self, e2e) -> None:
        # Negative path — only bash/read/write present, no task.
        events = [
            _tool_event("bash", command="ls"),
            _tool_event("read"),
            _tool_event("write"),
        ]
        assert e2e.has_task_subagent(events) is False

    def test_matches_task_even_when_mixed_with_other_tools(self, e2e) -> None:
        # First bash, then task — the helper must find the task.
        events = [
            _tool_event("bash", command="ls"),
            _tool_event("task"),
            _tool_event("read"),
        ]
        assert e2e.has_task_subagent(events) is True


class TestFinalAssistantTextContains:
    """`final_assistant_text_contains(events, needle)` matches the LAST
    text event's payload (not the first, not the longest).
    """

    def test_matches_last_text_event_not_first(self, e2e) -> None:
        # Scenario 2.3 — first text has no `?`, last text does.
        events = [
            _text_event_with_payload("Sure, here is the code..."),
            _text_event_with_payload("Which engine do you want — Unity or Unreal?"),
        ]
        assert e2e.final_assistant_text_contains(events, "?") is True

    def test_returns_false_when_final_text_lacks_needle(self, e2e) -> None:
        # Final text is "I'll start a file-backed change." with no `?`.
        events = [
            _text_event_with_payload("Which engine?", event_type="text"),
            _text_event_with_payload("Sure, I'll start a file-backed change."),
        ]
        assert e2e.final_assistant_text_contains(events, "?") is False

    def test_no_text_events_yields_false(self, e2e) -> None:
        # Tool-only stream — no text events at all → False (no crash).
        events = [_tool_event("bash"), _tool_event("read")]
        assert e2e.final_assistant_text_contains(events, "?") is False

    def test_matches_assistant_message_type_too(self, e2e) -> None:
        # Both `text` and `assistant_message` event types are text payloads.
        events = [
            _text_event_with_payload("thinking...", event_type="assistant_message"),
            _text_event_with_payload("Do you mean 2D or 3D?"),
        ]
        assert e2e.final_assistant_text_contains(events, "?") is True


class TestEmptyEventListContract:
    """Scenario 2.4 — every helper returns False on an empty event list."""

    def test_has_bash_ai_harness_change_empty_returns_false(self, e2e) -> None:
        assert e2e.has_bash_ai_harness_change([], "change-new") is False

    def test_has_task_subagent_empty_returns_false(self, e2e) -> None:
        assert e2e.has_task_subagent([]) is False

    def test_final_assistant_text_contains_empty_returns_false(self, e2e) -> None:
        assert e2e.final_assistant_text_contains([], "?") is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
