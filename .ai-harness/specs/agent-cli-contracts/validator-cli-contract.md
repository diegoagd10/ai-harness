# Spec — validator-cli-contract

## Purpose

Give the `change-validator` prompt a compact, local `## CLI contracts`
section so the validator carries the exact `task-list` JSON shape locally
instead of probing the CLI at runtime to discover the full task tree.
The section documents `ai-harness task-list -c {change}` and mirrors the
snake_case persistence shape (`id`, `title`, `spec`, `phase`,
`depends_on`, `status`, `subtasks[].{id, title, scenario, status}`). This
spec is a tracer-bullet slice over exactly one prompt file
(`src/ai_harness/resources/change-agent/change-validator.md`).

## Requirements

### Requirement: validator-prompt-carries-cli-contracts-section
`src/ai_harness/resources/change-agent/change-validator.md` MUST
contain a `## CLI contracts` section positioned between its existing
`## Inputs` block and its imperative `## Work` / `## Loop` block.

#### Scenario: section exists in the validator prompt
GIVEN `src/ai_harness/resources/change-agent/change-validator.md`
WHEN the prompt file is read top-to-bottom
THEN a heading-level-2 section titled `## CLI contracts` is present
AND the section sits after the `## Inputs` block
AND the section sits before the imperative `## Work` or `## Loop` block.

#### Scenario: section is scoped strictly to the validator
GIVEN the new `## CLI contracts` section in `change-validator.md`
WHEN each of the four non-executing change-agent prompts
(`change-explorer.md`, `change-propose.md`, `change-design.md`,
`change-specs.md`) is inspected
THEN none of them contains a `## CLI contracts` heading.

### Requirement: validator-contracts-section-documents-task-list
The `## CLI contracts` section in `change-validator.md` MUST contain one
entry for `ai-harness task-list -c {change}` with: a short heading, a
"How it works" block, a single-sentence "Use it to" block, and an
`Expected success response` code block that mirrors the full task-tree
JSON shape.

#### Scenario: task-list example uses the full snake_case shape
GIVEN the new `## CLI contracts` section in `change-validator.md`
WHEN the `task-list` entry's `Expected success response` code block is
parsed
THEN the top-level JSON array contains Task objects whose field names
are exactly `id`, `title`, `spec`, `phase`, `depends_on`, `status`,
`subtasks`
AND each element of every `subtasks` array is an object with the exact
field names `id`, `title`, `scenario`, `status`
AND no camelCase variant (`dependsOn`, `taskProgress`, etc.) appears
in the example.

#### Scenario: task-list example carries more than one task
GIVEN the new `## CLI contracts` section in `change-validator.md`
WHEN the `Expected success response` code block of the `task-list`
entry is read
THEN the JSON array contains at least two Task objects
AND at least one Task object has a non-empty `subtasks` array
AND the example is small enough to read in one screen (not a full
production dump).

#### Scenario: task-list substring remains present in unchanged prose
GIVEN the new `## CLI contracts` section is added to
`change-validator.md`
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`
test runs
THEN the literal substring `task-list` is still present in the file
AND the test passes without any edit to the test suite.

### Requirement: validator-section-preserves-existing-substrings
The new `## CLI contracts` section in `change-validator.md` MUST be
additive only — no existing asserted substring may be deleted or
reflowed out of the file.

#### Scenario: verdict substring keeps passing the renderer gate
GIVEN the new `## CLI contracts` section is added in place
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`
test runs
THEN the substring `verdict` is still present in `change-validator.md`
AND the test passes without any edit to the test suite.

#### Scenario: negative substring checks stay absent
GIVEN the new `## CLI contracts` section is added
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_no_stale_terms`
test runs
THEN neither `change start` nor `change ready` is introduced into
`change-validator.md`
AND the negative assertion keeps passing.
