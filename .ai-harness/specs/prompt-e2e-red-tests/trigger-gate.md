# Spec — trigger-gate

## Purpose

Provide the single env gate that wires the live RED tests to the future
change that edits `src/ai_harness/resources/change-agent/change-orchestrator.md`.
The gate MUST be off in default CI (so CI cost is unchanged), and MUST
be flippable by a future change at `apply` time so the RED surface
moves with the prompt. The unconditional helper tests and the static
`cases_e2e_csv.test.py` parse test MUST NOT read this gate — only the
live RED pytest drivers do.

## Requirements

### Requirement: Single env var, single default — off
The gate MUST be implemented as a single env var
(`PROMPT_E2E_RED`) consulted by exactly two pytest modules:
`tests/test_prompt_e2e_red.py` and
`tests/test_prompt_e2e_red_dispatch.py`. Default MUST be "off" — i.e.
when `PROMPT_E2E_RED` is unset, every live RED test is skipped. The
unconditional helper tests and
`tests-prompts/tests/cases_e2e_csv.test.py` MUST NOT consult the gate.

#### Scenario: default CI does not run live RED
GIVEN no `PROMPT_E2E_RED` env var is set
WHEN `pytest` runs in default CI
THEN every test in
`tests/test_prompt_e2e_red.py` and
`tests/test_prompt_e2e_red_dispatch.py` is reported `SKIPPED` AND the
unconditional suites
(`tests/test_prompt_e2e_assertions_unit.py`,
`tests-prompts/tests/cases_e2e_csv.test.py`,
`tests/test_prompt_tests_*.py`) execute normally.

### Requirement: Skipping is silent and side-effect free
When the gate is off, the skip MUST mark tests as skipped, MUST NOT
spawn `opencode` subprocesses, MUST NOT touch `tmp_path`, and MUST NOT
emit extra stderr noise beyond the standard pytest skip reason. A
`shutil.which("opencode")` probe in the skipif decorator is allowed
because it is read-only.

#### Scenario: skip without subprocess spawn
GIVEN the gate is off
WHEN pytest collects the RED suite
THEN `ps` shows no `opencode` process spawned by the suite AND
the only output mentioning `opencode` is the skip reason string.

### Requirement: Gate is the one switch a follow-up change flips
The follow-up PRD that edits
`src/ai_harness/resources/change-agent/change-orchestrator.md` is the
single entity responsible for setting `PROMPT_E2E_RED=1` at `apply`
time (or equivalent CI configuration). This slice does NOT flip the
gate; doing so would run the live RED tests against a prompt we have
not yet intentionally edited.

#### Scenario: this slice does not flip the gate
GIVEN the artifacts of this slice are applied
WHEN `grep -R "PROMPT_E2E_RED" tests/` and `grep -R "PROMPT_E2E_RED"
tests-prompts/` are run
THEN no test default-enables the gate AND no fixture marks the gate
on by default.

### Requirement: Skipping documents the gate contract in the source
Each env-gated test file MUST carry a module docstring that names the
gate, names both conditions (`PROMPT_E2E_RED == "1"` AND `opencode` on
PATH), and explains why the gate exists (live RED cost; only run when
the prompt it's testing is being edited). This keeps the contract
readable without grepping the gate variable.

#### Scenario: gate rationale is documented at the top of the file
GIVEN a contributor opens `tests/test_prompt_e2e_red.py` or
`tests/test_prompt_e2e_red_dispatch.py` for the first time
WHEN they read the module docstring
THEN `PROMPT_E2E_RED=1` and `opencode` on PATH are named as the
unlock conditions AND the docstring explains that the gate exists to
keep CI cost flat until the orchestrator-prompt change runs.
