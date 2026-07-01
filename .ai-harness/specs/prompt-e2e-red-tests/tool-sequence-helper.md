# Spec — tool-sequence-helper

## Purpose

Extend `tests-prompts/_extractor.py` (the project's single opencode-schema
authority) with a small, additive helper `tool_sequence` that returns the
ordered list of tool names from the stream. This lets the RED suite
assert "what did NOT happen" deterministically (`["bash", "text"]` vs
`["bash", "task", "text"]`) without baking schema knowledge into the
test files — schema knowledge stays in `_extractor.py`, where the
module's docstring already promises it lives.

## Requirements

### Requirement: `tool_sequence` co-located with existing extractor surface
The helper MUST live in `tests-prompts/_extractor.py` next to the existing
`extract_counts`, and MUST be importable as
`_extractor.tool_sequence(events)`. The helper MUST be ADDITIVE — the
existing `extract_counts(events) -> (int, int, int)` API and its
disjoint-count semantics MUST be unchanged. The module's docstring
promise ("This is the ONLY module in the prompt-test suite that knows
about opencode's JSON event schema") MUST continue to hold.

#### Scenario: existing extractor behavior is unchanged
GIVEN a previously-passing synthetic event list
WHEN `extract_counts(events)` is called
THEN the return triple is identical to its pre-change behaviour AND
calling `tool_sequence(events)` adds a second, additive capability
without altering the first.

### Requirement: Returns ordered list of tool names
The helper MUST return `list[str]` containing, in event order, the
`part.tool` value of every event that satisfies BOTH conditions:
`type == "tool_use"` AND `part.type == "tool"`. Events that do not match
(messages, text events, step boundaries) MUST be skipped. An empty list
MUST be returned when no qualifying events exist.

#### Scenario: ordered tool sequence over a mixed stream
GIVEN an event list with three tool_use events in this order:
`{"part.tool": "bash"}`, `{"part.tool": "text"}`, `{"part.tool": "task"}`
WHEN `tool_sequence(events)` is called
THEN the return value is `["bash", "text", "task"]` (preserves order).

#### Scenario: non-tool events are filtered out
GIVEN a stream that interleaves non-tool events
(`assistant_message`, `step_start`) with tool_use events
WHEN `tool_sequence(events)` is called
THEN only the tool_use events contribute to the returned list AND
non-tool events never appear in the output.

#### Scenario: empty input yields empty list
GIVEN an empty event list
WHEN `tool_sequence(events)` is called
THEN the return value is `[]` (no crash, no `None`).

### Requirement: Operates on `list[dict]`, matching `_e2e_assertions`
The helper MUST take `list[dict]` as input, NOT raw JSON strings. This
keeps parsing in the test (or in `_extractor`'s existing
`extract_counts`-style caller) and classification in the helper,
matching how `_e2e_assertions` consumes events. Both helpers MUST be
parity-compatible at their event-list argument.

#### Scenario: helper accepts the same parsed event shape as `_e2e_assertions`
GIVEN a parsed event list
WHEN `tool_sequence(events)` and `has_task_subagent(events)` are called
on the SAME list
THEN both functions succeed without reparsing AND
`has_task_subagent` returning `True` is consistent with the returned
list containing `"task"` as one of its entries.

### Requirement: Unit test covers the new helper unconditionally
The new helper MUST be covered by
`tests/test_prompt_e2e_assertions_unit.py` (which already runs
unconditionally per `e2e-assertions-helpers`). Coverage MUST include:
(a) ordered sequence over a mixed stream; (b) filtering of non-tool
events; (c) empty input; (d) a parity check that
`"task" in tool_sequence(events)` agrees with
`has_task_subagent(events) is True`.

#### Scenario: helper's parity with `_e2e_assertions` is locked
GIVEN the unconditional unit suite runs in default CI
WHEN `tests/test_prompt_e2e_assertions_unit.py` is collected
THEN at least one test asserts the
`tool_sequence(...) contains "task"` ↔ `has_task_subagent(...)` parity
across the same fixture events.
