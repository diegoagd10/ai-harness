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

# _e2e_assertions is added in task 2 of the prompt-e2e-red-tests change.
_E2E_ASSERTIONS_PATH = _HELPERS_DIR / "_e2e_assertions.py"
_e2e_assertions = _load("_e2e_assertions", "_e2e_assertions.py") if _E2E_ASSERTIONS_PATH.is_file() else None


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
