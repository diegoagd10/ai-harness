# Spec — host-dispatch-driver

## Purpose

Provide a worktree-friendly pytest driver
`tests/test_prompt_e2e_red_dispatch.py` that invokes
`opencode run --agent change-orchestrator …` directly as a host
subprocess (no Docker, no `docker-test.sh`). This mirrors the
established pattern at
`tests/test_prompt_tests_extractor.py::test_hello_prompt_live_with_minimax_m3`,
which already drives the live extractor via a host subprocess. The
dispatch driver exists so RED can run on a worktree where Docker is
unavailable, while keeping the same per-fixture contract as the
container-side RED test.

## Requirements

### Requirement: One test per fixture, reusing the contract table
The file MUST define one test per fixture (matching the three fixtures
in `tests/test_prompt_e2e_red.py`) and MUST assert the same
per-fixture contract as `red-pytest-fixture-suite`. The tests MUST NOT
hard-code a different routing decision; if the contract changes, BOTH
this file and `tests/test_prompt_e2e_red.py` change together. The
shared semantics are enforced by both files calling the same
`_e2e_assertions` helpers.

#### Scenario: contract parity with the Docker-side RED suite
GIVEN the per-fixture contract lives in `tests/test_prompt_e2e_red.py`
WHEN `tests/test_prompt_e2e_red_dispatch.py` is reviewed
THEN every assertion in this file maps 1:1 to one of the three
assertions in the Docker-side file AND no fourth routing rule appears.

### Requirement: Subprocess invocation pattern mirrors the existing extractor live test
Each test MUST invoke `opencode run` via `subprocess.run` (or
equivalent), passing the same args the Docker-side test passes
(`--agent change-orchestrator --auto --format json --model
minimax/MiniMax-M3 --dir <tmp_path> <prompt>`), parse the stdout through
`json.loads`, and pass the event list through the `_e2e_assertions`
helpers. The pattern MUST be the same as `test_hello_prompt_live_with_minimax_m3`,
so the worktree driver inherits that test's lessons (env detection,
model pin, stderr capture strategy).

#### Scenario: subprocess invocation matches the extractor live test's shape
GIVEN `tests/test_prompt_tests_extractor.py` is the host-side exemplar
WHEN the dispatch driver's `subprocess.run` call is read
THEN the command-line argument list (same flags, same order, same
model pin) matches `test_hello_prompt_live_with_minimax_m3`'s shape.

### Requirement: Per-test `tmp_path` keeps host clean
Each test MUST invoke the orchestrator with `--dir <tmp_path>` so any
`.ai-harness/changes/<name>/` created by the complete-fixture run dies
with the test's tmpdir, mirroring `red-pytest-fixture-suite`. The
driver MUST NOT mutate the worktree.

#### Scenario: complete fixture leaves no host footprint
GIVEN `test_mario_kart_3d_complete_dispatch` runs to completion
WHEN `ls -la .ai-harness/changes/` is inspected
THEN no new change folder exists outside pytest's tmpdir AND
pytest's tmpdir teardown removes the new folder with it.

### Requirement: Env gate and PATH skip apply at module level
The file MUST apply the same `pytest.mark.skipif` policy as
`red-pytest-fixture-suite`: skip unless BOTH `PROMPT_E2E_RED == "1"`
AND `shutil.which("opencode")` is non-None. The skip MUST be consistent
with the Docker-side file so neither suite runs in default CI.

#### Scenario: defaults match `red-pytest-fixture-suite`
GIVEN `PROMPT_E2E_RED` is unset
WHEN `pytest tests/test_prompt_e2e_red_dispatch.py` runs
THEN every test is reported `SKIPPED` AND the skip reason is consistent
with `tests/test_prompt_e2e_red.py`'s skip reason.

### Requirement: No Docker dependency in the import graph
The dispatch driver MUST NOT import or depend on `docker`, the
`tests-prompts/Dockerfile`, or the in-container `run.sh`. The host
subprocess path is the entire test surface.

#### Scenario: import graph is Docker-free
GIVEN the dispatch driver file is parsed for imports
WHEN `grep -E "docker|Dockerfile|run.sh"` runs over its imports
THEN no Docker-coupled names appear AND the only subprocess target is
the `opencode` binary.
