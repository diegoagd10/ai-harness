# Spec — implementor-cli-contract

## Purpose

Give the `change-implementor` prompt a compact, local `## CLI contracts`
section so the implementor stops probing `ai-harness --help` to rediscover
the two task commands it runs to advance a change through implementation.
The section documents `ai-harness task-next -c {change}` (next pending
Task JSON, or `null`) and `ai-harness task-done -c {change} -i
'{"id": "<id>"}'` (containing Task JSON, with the parent auto-marked
done when its last subtask completes). This spec is a tracer-bullet slice
over exactly one prompt file
(`src/ai_harness/resources/change-agent/change-implementor.md`).

## Requirements

### Requirement: implementor-prompt-carries-cli-contracts-section
`src/ai_harness/resources/change-agent/change-implementor.md` MUST
contain a `## CLI contracts` section positioned between its existing
`## Inputs` block and its imperative `## Work` / `## Loop` block.

#### Scenario: section exists in the implementor prompt
GIVEN `src/ai_harness/resources/change-agent/change-implementor.md`
WHEN the prompt file is read top-to-bottom
THEN a heading-level-2 section titled `## CLI contracts` is present
AND the section sits after the `## Inputs` block
AND the section sits before the imperative `## Work` or `## Loop` block.

#### Scenario: section is scoped strictly to the implementor
GIVEN the new `## CLI contracts` section in `change-implementor.md`
WHEN each of the four non-executing change-agent prompts
(`change-explorer.md`, `change-propose.md`, `change-design.md`,
`change-specs.md`) is inspected
THEN none of them contains a `## CLI contracts` heading.

### Requirement: implementor-contracts-section-documents-task-next
The `## CLI contracts` section in `change-implementor.md` MUST contain
one entry for `ai-harness task-next -c {change}` with: a short heading,
a "How it works" block, a single-sentence "Use it to" block, and an
`Expected success response` code block that documents both the
pending-Task-JSON outcome and the `null` outcome.

#### Scenario: task-next entry shows the pending-task JSON shape
GIVEN the new `## CLI contracts` section in `change-implementor.md`
WHEN the `task-next` entry is read
THEN the `Expected success response` code block shows a Task JSON
object with the exact field names `id`, `title`, `spec`, `phase`,
`depends_on`, `status`, `subtasks`
AND only pending entries remain in `subtasks` (the filtered-out
completed subtasks are absent from the example).

#### Scenario: task-next entry also shows the null outcome
GIVEN the new `## CLI contracts` section in `change-implementor.md`
WHEN the `task-next` entry's success-response code block is parsed
THEN one of the documented examples (either inline within the block or
in an adjacent code block in the same entry) is the bare JSON literal
`null`, not an empty object or empty array.

#### Scenario: task-next substring remains present in unchanged prose
GIVEN the new `## CLI contracts` section is added to
`change-implementor.md`
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`
test runs
THEN the literal substring `task-next` is still present in the file
AND the test passes without any edit to the test suite.

### Requirement: implementor-contracts-section-documents-task-done
The `## CLI contracts` section in `change-implementor.md` MUST contain
one entry for `ai-harness task-done -c {change} -i '{"id": "<id>"}'`
with: a short heading, a "How it works" block, a single-sentence
"Use it to" block, and an `Expected success response` code block that
shows the containing Task JSON (parent auto-marked `done` when the last
subtask completes; accept both a subtask id and a parent id).

#### Scenario: task-done entry shows the containing Task JSON
GIVEN the new `## CLI contracts` section in `change-implementor.md`
WHEN the `task-done` entry's `Expected success response` code block is
parsed
THEN the JSON object uses the exact field names `id`, `title`, `spec`,
`phase`, `depends_on`, `status`, `subtasks`
AND the example shows the parent task with its final subtask's
`status` flipped to `done`
AND the example makes the boundary between a parent id and a subtask
id obvious (either by using a subtask id like `"1.1"` in the prose or
by using a parent id in the prose and pointing to the subtask list in
the response).

### Requirement: implementor-section-preserves-existing-substrings
The new `## CLI contracts` section in `change-implementor.md` MUST be
additive only — no existing asserted substring may be deleted or
reflowed out of the file.

#### Scenario: existing renderer substring gate keeps passing
GIVEN the new `## CLI contracts` section is added in place
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`
test runs
THEN every asserted substring that already lives in
`change-implementor.md` is still present in the file
AND the test passes without any edit to the test suite.

#### Scenario: negative substring checks stay absent
GIVEN the new `## CLI contracts` section is added
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_no_stale_terms`
test runs
THEN neither `change start` nor `change ready` is introduced into
`change-implementor.md`
AND the negative assertion keeps passing.
