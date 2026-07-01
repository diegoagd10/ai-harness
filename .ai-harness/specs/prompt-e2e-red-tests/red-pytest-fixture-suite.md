# Spec — red-pytest-fixture-suite

## Purpose

Provide the live RED pytest surface as
`tests/test_prompt_e2e_red.py`. The file holds the RED contract in code:
a top-of-file markdown table maps each fixture to its expected routing
behaviour, then one test per fixture spawns a fresh
`opencode run --agent change-orchestrator …` subprocess against a
per-test `tmp_path` and asserts the routing contract. This is the
contract the rest of this change defends.

## Requirements

### Requirement: Top-of-file contract table is the living spec
The file MUST begin with a markdown table whose rows are the three
fixtures (small/concrete `fibonacci-ES`, ambiguous/large
`mario-kart-3d-vague`, complete/large `mario-kart-3d-complete`) and
whose columns cover, at minimum: fixture id, prompt category
(small/ambiguous/complete), expected `bash change-*` presence, expected
`task` subagent presence, and expected final-text characteristics. The
table MUST be the canonical reader-facing mapping so future contributors
do not need to read three files to understand the contract.

#### Scenario: the table is the first thing a reader sees
GIVEN a contributor opens `tests/test_prompt_e2e_red.py` in a fresh
clone
WHEN they scroll past the docstring / imports
THEN the contract table appears before any `def test_…` block.

### Requirement: One test per fixture, asserting the per-fixture contract
The file MUST define exactly three test functions (one per fixture row
in `cases_e2e.csv`). Each test MUST spawn a fresh `opencode run`
subprocess with the args mandated by the design and MUST parse the
stdout JSON event list through the helpers exported by
`_e2e_assertions`. The assertions MUST enforce the per-fixture contract
table:
- `fibonacci-ES`: `has_bash_ai_harness_change(events, "change-new") is
  False` AND `has_bash_ai_harness_change(events, "change-continue") is
  False` AND `has_task_subagent(events) is False`.
- `mario-kart-3d-vague`: `has_bash_ai_harness_change(events, "change-new") is
  False` AND `has_task_subagent(events) is False` AND
  `final_assistant_text_contains(events, "?") is True` AND the final
  text does NOT contain the substring `change-new`.
- `mario-kart-3d-complete`:
  `has_bash_ai_harness_change(events, "change-new") is True` OR
  `has_task_subagent(events) is True` (either pattern fenced together).

#### Scenario: vague fixture conjunctive assertion holds
GIVEN a captured event list with no `bash` tool_use and a final text
ending in `?`
WHEN `test_mario_kart_3d_vague` runs
THEN the assertion passes AND its failure path dumps the full trace for
debugging.

#### Scenario: complete fixture OR-fence holds
GIVEN a captured event list with a `bash` tool_use whose command
contains `ai-harness change-new`
WHEN `test_mario_kart_3d_complete` runs
THEN the assertion passes via the first OR branch.

### Requirement: Env gate and PATH skip apply at module level
The file MUST be decorated (at module or per-test level) with
`pytest.mark.skipif` such that ALL of its tests are skipped unless BOTH
conditions hold: (a) the env var `PROMPT_E2E_RED == "1"` is set; (b)
`opencode` is resolvable on `PATH` via `shutil.which`. The skip reason
MUST explain both conditions. The skip MUST NOT raise; it MUST just
mark every test as skipped in the pytest report.

#### Scenario: gate off -> all tests skip cleanly
GIVEN `PROMPT_E2E_RED` is unset
WHEN `pytest tests/test_prompt_e2e_red.py` runs
THEN every test is reported as `SKIPPED` AND the suite exits `0` (or
`5`, the conventional pytest "no tests ran" exit) with no `opencode`
subprocess spawned.

#### Scenario: opencode missing -> all tests skip cleanly
GIVEN `PROMPT_E2E_RED=1` but `opencode` is not on PATH
WHEN `pytest tests/test_prompt_e2e_red.py` runs
THEN every test is reported as `SKIPPED` AND the skip reason mentions
the missing binary.

### Requirement: Live run uses pinned model and per-test tmp_path
Each test MUST invoke:
`opencode run --agent change-orchestrator --auto --format json --model
minimax/MiniMax-M3 --dir <tmp_path> <prompt>`
where `<tmp_path>` is the pytest `tmp_path` fixture passed per-test, so
any stray `.ai-harness/changes/<name>/` the orchestrator might create
dies with the test's temp directory and never touches the host worktree.
The model pin MUST match `run.sh:98` and
`tests/test_prompt_tests_extractor.py:175`.

#### Scenario: model pin matches existing seams
GIVEN the new test file is reviewed
WHEN `grep minimax/MiniMax-M3` runs across the test
THEN exactly the literal `--model minimax/MiniMax-M3` is present AND no
other model identifiers appear.

### Requirement: Failure path dumps the full trace for debugging
When an assertion fails, the test MUST print the captured JSON event
list to the pytest failure report, mirroring the existing
`dump_failure_trace` shape in `run.sh:222-235`. The dump MUST be
truncated only when the captured stdout exceeds an upper bound
configurable for legibility (default cap acceptable); the cap MUST NOT
silently elide events that contain a `?` or contain `ai-harness`.

#### Scenario: vague fixture regression dumps the offending trace
GIVEN the captured trace has a `bash` tool_use calling
`ai-harness change-new` (vague fixture regression)
WHEN `test_mario_kart_3d_vague` asserts
THEN the pytest failure output includes the offending `bash` event AND
the assertion message names which clause (`has_bash_ai_harness_change`,
`final_assistant_text_contains`, etc.) tripped first.
