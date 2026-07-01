# Spec — e2e-assertions-helpers

## Purpose

Provide a single, schema-aware, purely-functional helper module
(`tests-prompts/_e2e_assertions.py`) that exposes the three boolean
routing predicates the RED suite needs. Centralising the predicates in one
importable module lets the `run.sh` second loop, the live pytest RED
driver, the host dispatch driver, and the unconditional unit tests ALL
answer "did the orchestrator grill?" identically — never four different
ways.

## Requirements

### Requirement: Three flat boolean helpers are the module's public API
The module MUST export exactly three functions, each a single-question
classifier over an already-parsed opencode JSON event list
(`list[dict]`):
- `has_bash_ai_harness_change(events: list[dict], subcmd: str) -> bool`
- `has_task_subagent(events: list[dict]) -> bool`
- `final_assistant_text_contains(events: list[dict], needle: str) -> bool`

The module MUST NOT take raw JSON strings; `_extractor.py` is the
boundary that turns bytes into events. The three helpers MUST NOT bundle
a `Routing` dataclass or otherwise couple the questions; the per-fixture
conjunction (e.g. "no `bash change-*` AND final text contains `?`")
belongs with the fixture assertion, not with the helper.

#### Scenario: each helper answers exactly one boolean question
GIVEN a synthetic event list shaped like the opencode JSON stream
WHEN each helper is called with appropriate inputs
THEN each returns a `bool` AND the conjunction "no `bash change-*` AND
final text contains `?`" is expressible at the test site by composing
two of the three calls.

### Requirement: `has_bash_ai_harness_change` matches CLI invocations by subcmd
The helper MUST return `True` iff ANY event in the list is a `tool_use`
whose `part.type == "tool"`, `part.tool == "bash"`, and whose
`part.state.input.command` contains the literal substring
`ai-harness change-<subcmd>` (e.g. `ai-harness change-new`). The
substring check MUST be case-sensitive against the literal
`ai-harness change-` prefix so the helper covers any future subcommand
without code changes.

#### Scenario: matches a bash tool_use that calls change-new
GIVEN an event list containing exactly one
`{"type": "tool_use", "part": {"type": "tool", "tool": "bash",
"state": {"input": {"command": "ai-harness change-new foo"}}}}`
WHEN `has_bash_ai_harness_change(events, "change-new")` is called
THEN the result is `True`.

#### Scenario: ignores a bash tool_use for any non-ai-harness command
GIVEN an event list containing a `bash` tool_use whose `command` is
`ls -la /tmp`
WHEN `has_bash_ai_harness_change(events, "change-new")` is called
THEN the result is `False`.

#### Scenario: matches every ai-harness subcmd without code changes
GIVEN an event list containing a `bash` tool_use whose `command` runs
`ai-harness change-continue prompt-e2e-red-tests`
WHEN `has_bash_ai_harness_change(events, "change-continue")` is called
THEN the result is `True` (proves the substring mechanism is sub-agnostic).

#### Scenario: returns False for an empty event list
GIVEN an empty event list
WHEN any of the three helpers is called
THEN the result is `False` (no crash, no false positive on empty input).

### Requirement: `has_task_subagent` matches subagent delegation
The helper MUST return `True` iff ANY event in the list is a `tool_use`
whose `part.tool == "task"` (delegating to a subagent). The helper MUST
NOT inspect the subagent prompt body; the routing contract is "did a
subagent spawn?", not "was the subagent's task the right thing?".

#### Scenario: matches a task tool_use
GIVEN an event list containing a
`{"type": "tool_use", "part": {"type": "tool", "tool": "task", ...}}`
WHEN `has_task_subagent(events)` is called
THEN the result is `True`.

#### Scenario: ignores bash and other tool_uses
GIVEN an event list containing only `bash` tool_use events
WHEN `has_task_subagent(events)` is called
THEN the result is `False`.

### Requirement: `final_assistant_text_contains` matches the LAST text event
The helper MUST find the LAST `text` event in the stream (an event whose
`type` indicates a text/assistant message) and return `True` iff that
event's text payload contains the `needle` substring. "Last" MUST mean
the final occurrence before stream end, NOT the first and NOT the
longest — the orchestrator may emit multiple text events before settling
on a clarifying question. An empty event list or a list with no text
events MUST return `False`.

#### Scenario: matches the LAST text event, not the first
GIVEN an event list whose first `text` event is "Sure, here is the code…"
and whose LAST `text` event is "Which engine do you want — Unity or
Unreal?"
WHEN `final_assistant_text_contains(events, "?")` is called
THEN the result is `True` (the last event carries the question mark,
the first does not).

#### Scenario: returns False when the final text does NOT contain the needle
GIVEN an event list whose LAST `text` event is "Sure, I'll start a file-backed change."
WHEN `final_assistant_text_contains(events, "?")` is called
THEN the result is `False`.

#### Scenario: no text events yields False
GIVEN an event list containing only `tool_use` events
WHEN `final_assistant_text_contains(events, "?")` is called
THEN the result is `False` (no crash on tool-only streams).

### Requirement: Unconditional unit tests guard the helpers themselves
A NEW `tests/test_prompt_e2e_assertions_unit.py` MUST run UNCONDITIONALLY
in default CI (no env gate). It MUST cover, at minimum: (a) the
positive and negative paths for each of the three helpers; (b) the
empty-event-list path for each; (c) ordering for the "last text event"
semantics in `final_assistant_text_contains`. These tests are the gate
that prevents the assertions from regressing silently.

#### Scenario: unit tests pass on default CI
GIVEN no env var is set
WHEN `pytest tests/test_prompt_e2e_assertions_unit.py` runs
THEN every test executes (NOT skipped) AND the suite passes.
