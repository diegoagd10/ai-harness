# Spec — tasks-cli-contract

## Purpose

Give the `change-tasks` prompt a compact, local `## CLI contracts`
section so the agent carries the exact `task-create` input shape and
Task JSON response shape locally instead of rediscovering it at runtime.
The section documents `ai-harness task-create -c {change} -i '{json}'`,
uses `depends_on` (snake_case) in the input example, and the same change
fixes the pre-existing `dependsOn` field-name reference in
`change-tasks.md` so every example in the file matches what the CLI
parser actually accepts. This spec is a tracer-bullet slice over exactly
one prompt file (`src/ai_harness/resources/change-agent/change-tasks.md`).

## Requirements

### Requirement: tasks-prompt-carries-cli-contracts-section
`src/ai_harness/resources/change-agent/change-tasks.md` MUST contain a
`## CLI contracts` section positioned between its existing `## Inputs`
block and its imperative `## Work` / `## Loop` block.

#### Scenario: section exists in the tasks prompt
GIVEN `src/ai_harness/resources/change-agent/change-tasks.md`
WHEN the prompt file is read top-to-bottom
THEN a heading-level-2 section titled `## CLI contracts` is present
AND the section sits after the `## Inputs` block
AND the section sits before the imperative `## Work` or `## Loop` block.

#### Scenario: section is scoped strictly to the tasks agent
GIVEN the new `## CLI contracts` section in `change-tasks.md`
WHEN each of the four non-executing change-agent prompts
(`change-explorer.md`, `change-propose.md`, `change-design.md`,
`change-specs.md`) is inspected
THEN none of them contains a `## CLI contracts` heading.

### Requirement: tasks-contracts-section-documents-task-create
The `## CLI contracts` section in `change-tasks.md` MUST contain one
entry for `ai-harness task-create -c {change} -i '{json}'` with: a short
heading, a "How it works" block, a single-sentence "Use it to" block,
and an `Expected success response` code block with the persisted Task
JSON shape.

#### Scenario: task-create input example uses snake_case depends_on
GIVEN the new `## CLI contracts` section in `change-tasks.md`
WHEN the `task-create` entry is read
THEN the input example (or its prose reference) names the required
keys `title`, `spec`, `phase`, `depends_on`, and `subtasks`
AND the literal field name used is `depends_on` (snake_case), never
`dependsOn`.

#### Scenario: task-create expected-success response mirrors persisted shape
GIVEN the new `## CLI contracts` section in `change-tasks.md`
WHEN the `Expected success response` code block of the `task-create`
entry is parsed
THEN the JSON object uses these exact field names:
`id`, `title`, `spec`, `phase`, `depends_on`, `status`, `subtasks`
AND each element of `subtasks` is an object with the exact field
names `id`, `title`, `scenario`, `status`
AND no camelCase variant of `depends_on` appears in the response
example.

#### Scenario: task-create substring remains present in unchanged prose
GIVEN the new `## CLI contracts` section is added to `change-tasks.md`
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`
test runs
THEN the literal substring `task-create` is still present in the file
AND the test passes without any edit to the test suite.

### Requirement: tasks-prompt-fixes-pre-existing-dependsOn-to-depends_on
The pre-existing Task JSON shape example in `change-tasks.md` MUST use
the field name `depends_on` (snake_case) instead of `dependsOn`. The
fix is in place — it is not extracted into its own section — so every
JSON example the file carries accepts the CLI parser's required input
on the first call.

#### Scenario: no dependsOn camelCase survives anywhere in change-tasks.md
GIVEN the corrected `change-tasks.md`
WHEN the file is searched for the token `dependsOn`
THEN zero matches remain in any JSON example or schema documentation
in the file.

#### Scenario: a task-create payload built from the file no longer triggers the parser error
GIVEN an agent reads the example JSON from `change-tasks.md` verbatim
WHEN the agent runs `ai-harness task-create -c {change} -i '{json}'`
with that payload
THEN the CLI parser accepts the input (does not raise
`Missing TaskInput field: depends_on`)
AND the response is the persisted Task JSON.

#### Scenario: pre-existing snake_case parser tests keep passing
GIVEN the `dependsOn` → `depends_on` fix in `change-tasks.md`
WHEN `tests/test_tasks.py` is run (including
`test_cli_task_create_parses_input_and_outputs_json`)
THEN all tests pass without any edit to the test suite.
