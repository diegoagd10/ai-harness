"""_e2e_assertions.py — schema-aware routing predicates for the prompt-E2E RED suite.

This module answers the three boolean routing questions every per-fixture
assertion in `tests/test_prompt_e2e_red.py` and
`tests/test_prompt_e2e_red_dispatch.py` needs:

    has_bash_ai_harness_change(events, subcmd) -> bool
    has_task_subagent(events) -> bool
    final_assistant_text_contains(events, needle) -> bool

Schema awareness stays narrow: this module knows ONLY the routing-relevant
fields (`part.tool`, `part.state.input.command`, text payloads). General
schema parsing (event-type filtering, tool-name extraction) lives in
`_extractor.py`, which is the project's single opencode-schema module.

Inputs are always `list[dict]`. Raw JSON strings are out of scope; the
test parses once and passes the resulting event list to each helper.

The per-fixture conjunction logic (e.g. "no `bash change-*` AND final text
contains `?` AND no `change-new` substring") is composed at the test
site, NOT in this module. One helper = one boolean question.
"""

from __future__ import annotations

# Top-level event type constants — kept here so this module is self-contained.
# Mirrors `_extractor._TOOL_USE_TOP_TYPE` / `_TOOL_PART_TYPE` for the
# subset of fields this module reads.
_TOOL_USE_TOP_TYPE = "tool_use"
_TOOL_PART_TYPE = "tool"
_BASH_TOOL_NAME = "bash"
_TASK_TOOL_NAME = "task"
_TEXT_TOP_TYPES = frozenset({"text", "assistant_message"})
_TEXT_PART_TYPE = "text"


def has_bash_ai_harness_change(events: list[dict], subcmd: str) -> bool:
    """Return True iff ANY event is a bash `tool_use` whose command contains
    the literal substring `ai-harness <subcmd>` (e.g. `ai-harness change-new`).

    The substring check is case-sensitive against the literal
    `ai-harness ` prefix so the helper covers any future subcommand
    without code changes. Callers pass the full subcommand token
    (e.g. `"change-new"`, `"change-continue"`).
    """
    needle = f"ai-harness {subcmd}"
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") != _TOOL_USE_TOP_TYPE:
            continue
        part = event.get("part") or {}
        if not isinstance(part, dict):
            continue
        if part.get("type") != _TOOL_PART_TYPE:
            continue
        if part.get("tool") != _BASH_TOOL_NAME:
            continue
        state = part.get("state") or {}
        if not isinstance(state, dict):
            continue
        inputs = state.get("input") or {}
        if not isinstance(inputs, dict):
            continue
        command = inputs.get("command")
        if isinstance(command, str) and needle in command:
            return True
    return False


def has_task_subagent(events: list[dict]) -> bool:
    """Return True iff ANY event is a `tool_use` whose `part.tool == "task"`.

    The helper does NOT inspect the subagent prompt body; the routing
    contract is "did a subagent spawn?", not "was the subagent's task
    the right thing?".
    """
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") != _TOOL_USE_TOP_TYPE:
            continue
        part = event.get("part") or {}
        if not isinstance(part, dict):
            continue
        if part.get("type") != _TOOL_PART_TYPE:
            continue
        if part.get("tool") == _TASK_TOOL_NAME:
            return True
    return False


def final_assistant_text_contains(events: list[dict], needle: str) -> bool:
    """Return True iff the LAST text event's payload contains `needle`.

    "Last" means the final occurrence before stream end — NOT the first
    and NOT the longest. The orchestrator may emit multiple text events
    before settling on a clarifying question.

    An event is a "text event" when its top-level `type` is in
    `{text, assistant_message}` AND `part.type == "text"`. Other event
    types (tool_use, step_start, step_finish) are ignored.

    Returns False on empty event list or when no text events exist.
    """
    last_text: str | None = None
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") not in _TEXT_TOP_TYPES:
            continue
        part = event.get("part") or {}
        if not isinstance(part, dict):
            continue
        if part.get("type") != _TEXT_PART_TYPE:
            continue
        text = part.get("text")
        if isinstance(text, str):
            last_text = text
    if last_text is None:
        return False
    return needle in last_text
