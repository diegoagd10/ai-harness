# Spec — C-1 Loop Resource Purge

## Purpose

Delete every loop-agent prompt file and remove all loop-agent registry entries from the renderer
so that no loop artifact exists at the filesystem, metadata, or discovery layers after the change.

---

## Requirements

### Requirement: Loop resource directory deleted

The system MUST delete `src/ai_harness/resources/loop-agent/` and all 5 files it contains
(`explorer.md`, `implementor.md`, `loop-orchestrator.md`, `validator.md`, `_result-contract.md`).
No loop-agent file MUST remain anywhere under `src/ai_harness/resources/`.

#### Scenario: Directory absent after change

GIVEN the `deprecate-loop` branch is applied
WHEN `find src/ai_harness/resources/loop-agent` is executed
THEN the command exits non-zero (directory not found) and produces no output

#### Scenario: No stray loop files under resources

GIVEN the `deprecate-loop` branch is applied
WHEN `find src/ai_harness/resources -name "*.md" | xargs grep -l "loop-orchestrator"` is executed
THEN the command returns no matches

---

### Requirement: `_AGENT_RESOURCE_DIRS` contains no loop entry

The system MUST update `_AGENT_RESOURCE_DIRS` in `renderers.py` to `("change-agent",)` only.
`"loop-agent"` MUST NOT appear in this tuple.

#### Scenario: Grep for loop-agent in renderer constant

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "loop-agent" src/ai_harness/modules/harness/renderers.py` is executed
THEN the command returns no matches

---

### Requirement: `_AGENT_META` contains no loop entries

The system MUST remove the four loop keys (`"loop-orchestrator"`, `"explorer"`, `"implementor"`,
`"validator"`) from `_AGENT_META` in `renderers.py`. The dict MUST retain all 9 change-agent
entries unchanged.

#### Scenario: Loop agent meta lookup raises at runtime

GIVEN `_AGENT_META` has no `"explorer"` key
WHEN `get_agent_meta("explorer")` is called
THEN a `ValueError` is raised with the message `"Unknown agent template: 'explorer'"`

#### Scenario: Change agent meta lookup succeeds

GIVEN `_AGENT_META` retains all 9 change entries
WHEN `get_agent_meta("change-implementor")` is called
THEN the function returns the expected metadata dict without raising

---

### Requirement: Discovery function renamed to `_discover_agents`

The system MUST rename the internal function `_discover_loop_agents` to `_discover_agents` in
`renderers.py`. All internal call sites within `renderers.py` and the named import in
`tests/test_renderers.py` (line 22) MUST be updated atomically in the same task.

#### Scenario: Old name absent from source and tests

GIVEN the `deprecate-loop` branch is applied
WHEN `grep -r "_discover_loop_agents" src/ tests/` is executed
THEN the command returns no matches

#### Scenario: New name discoverable and callable

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "_discover_agents" src/ai_harness/modules/harness/renderers.py` is executed
THEN at least one match is found (definition site)

#### Scenario: Test module imports the renamed function

GIVEN `tests/test_renderers.py` imports `_discover_agents`
WHEN `uv run pytest tests/test_renderers.py --collect-only` is executed
THEN the collection succeeds (no `ImportError`)

---

### Requirement: Loop docstrings and comments removed from renderers

The system SHOULD update every docstring and inline comment in `renderers.py` that references
"loop agents" or "loop agent templates" so that it reads "change agents" instead.

#### Scenario: No loop-agents wording in renderer docstrings

GIVEN the `deprecate-loop` branch is applied
WHEN `grep -n "loop agent" src/ai_harness/modules/harness/renderers.py` is executed
THEN the command returns no matches

---

### Requirement: Loop-specific tests removed from test_renderers.py

The system MUST remove all test functions in `tests/test_renderers.py` whose sole subject is a
loop-agent artefact (e.g., `test_loop_orchestrator_description_mentions_loop_labeled_sub_issues`,
loop-orchestrator frontmatter, copilot loop path assertions, loop-orchestrator override tests).
Existing change-agent tests MUST remain unmodified.

#### Scenario: No loop-orchestrator test functions remain

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "def test_.*loop" tests/test_renderers.py` is executed
THEN the command returns no matches

#### Scenario: Change-agent tests still pass

GIVEN all loop-agent tests are removed
WHEN `uv run pytest tests/test_renderers.py` is executed
THEN the suite passes (exit code 0)

---

### Requirement: ADRs 0003, 0007, 0008 carry deprecation headers

The system MUST prepend the following block at the very top of each of
`docs/adr/0003-loop-pr-prd-linking.md`, `docs/adr/0007-loop-worktree-isolation.md`, and
`docs/adr/0008-copilot-loop-agents-native-model.md` — above the `# NNNN.` heading:

```
> **Superseded** — the loop agent set was removed in the `deprecate-loop` change.
> This ADR is retained as a historical decision record.
```

The ADR bodies MUST remain otherwise unchanged (present tense preserved for historical accuracy).
The files MUST NOT be deleted.

#### Scenario: Deprecation header present in ADR 0003

GIVEN the `deprecate-loop` branch is applied
WHEN the first two lines of `docs/adr/0003-loop-pr-prd-linking.md` are read
THEN the content matches `> **Superseded** — the loop agent set was removed in the \`deprecate-loop\` change.`

#### Scenario: Deprecation header present in ADR 0007

GIVEN the `deprecate-loop` branch is applied
WHEN the first two lines of `docs/adr/0007-loop-worktree-isolation.md` are read
THEN the content matches the same two-line superseded block

#### Scenario: Deprecation header present in ADR 0008

GIVEN the `deprecate-loop` branch is applied
WHEN the first two lines of `docs/adr/0008-copilot-loop-agents-native-model.md` are read
THEN the content matches the same two-line superseded block

#### Scenario: ADR bodies not deleted

GIVEN the `deprecate-loop` branch is applied
WHEN `wc -l docs/adr/0003-loop-pr-prd-linking.md` is executed
THEN the line count is greater than 5 (header added; body retained)

---

### Requirement: Docs remove loop-workflow prose

The system MUST remove all loop-workflow prose from `README.md`, `CONTEXT.md`, and the project
`CLAUDE.md`, including:
- The "Running the loop in a worktree" section and any loop agent install descriptions.
- The loop-label triage instruction (`loop` (= `LOOP_LABEL`) means queued for loop implementation).
- The note that sub-issues receive the `loop` label.
- The "Loop agents" vocabulary entry and loop session description in `CONTEXT.md`.

The system MUST NOT remove unrelated content from these files.

#### Scenario: Loop prose absent from CLAUDE.md

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "LOOP_LABEL\|loop-label\|loop implementation" CLAUDE.md` is executed from the project root
THEN the command returns no matches

#### Scenario: Loop vocabulary absent from CONTEXT.md

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "loop-orchestrator\|loop session\|Loop agents" CONTEXT.md` is executed from the project root
THEN the command returns no matches

---

### Requirement: All quality gates pass after purge

The system MUST pass all quality gates after completing the resource purge.
The e2e gate MUST be run because install/uninstall behavior changes.

#### Scenario: Quality gates green

GIVEN all loop resource and registry changes are applied
WHEN `uv run ruff format --check . && uv run ruff check . && uv run pytest` are executed sequentially
THEN each command exits with code 0
