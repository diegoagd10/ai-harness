# Exploration: Migrate `sdd-status` and `sdd-continue`

## Summary

The active package under `src/ai_harness/` currently exposes only the install/uninstall implementation in `main.py`. The previous Python migration slice under `cli.bak/` already contains a Typer-based implementation of `ai-harness sdd-status` and `ai-harness sdd-continue`, including the SDD state machine, artifact discovery, task parsing, verify-report pass detection, deterministic JSON serialization, and human/dispatcher renderers.

## User Goal

Migrate the backup implementation for:

- `ai-harness sdd-status`
- `ai-harness sdd-continue`

into the active `src/` package, preserving the behavior already proven in `cli.bak/` and adding it to the active test strategy.

## Current Active Implementation

- `src/ai_harness/main.py` owns the active `ai-harness` Typer app and currently includes install/uninstall commands and resource installation logic.
- `pyproject.toml` points the console script to `ai_harness.main:main`.
- The active package does not currently contain the `ai_harness.sdd` package, `compat.py`, or `rendering.py` modules from the backup implementation.
- The active test configuration uses `pytest` with `pythonpath = ["src"]`.

## Backup Implementation Inventory

Relevant backup files:

- `cli.bak/src/ai_harness/cli.py`
  - Defines a Typer app with explicit hyphenated commands `sdd-status` and `sdd-continue`.
  - Uses shared `_dispatch_command()` to resolve status, handle errors, emit JSON, or render human output.
  - `sdd-status` optionally includes phase instructions via `--instructions`.
  - `sdd-continue` always includes instructions and renders dispatcher markdown unless `--json` is requested.
- `cli.bak/src/ai_harness/compat.py`
  - Owns the deterministic Go-compatible JSON contract and exit codes.
  - Emits camelCase fields, ordered payloads, non-null empty lists, and omitted `phaseInstructions` when absent.
- `cli.bak/src/ai_harness/rendering.py`
  - Keeps Rich terminal rendering out of the deterministic JSON path.
  - Provides terminal status rendering and dispatcher markdown rendering.
- `cli.bak/src/ai_harness/sdd/`
  - `models.py`: status dataclasses, constants, dependency states, and base status construction.
  - `workspace.py`: workspace root resolution and active change discovery.
  - `artifacts.py`: artifact discovery and completeness classification.
  - `tasks.py`: markdown task checkbox parsing.
  - `verifyreport.py`: strict pass/fail heuristic for verify reports.
  - `statemachine.py`: dependencies, apply state, next recommendation, and blocker reasons.
  - `instructions.py`: per-phase instructions attached to status.
  - `resolve.py`: top-level status resolution flow.

Relevant backup tests:

- `cli.bak/tests/test_boundary.py`: JSON output remains plain deterministic JSON; Rich is only in rendering.
- `cli.bak/tests/test_json_compat.py`: JSON contract compatibility.
- `cli.bak/tests/test_resolver.py`: status resolution behavior.
- `cli.bak/tests/test_verifyreport.py`: verify-report pass/fail heuristic.
- Additional backup tests cover rendering, CLI, install, picker, and tooling behavior.

## Behavioral Contract to Preserve

### `sdd-status`

- Invocation: `ai-harness sdd-status [change] [--json] [--instructions] [--cwd <path>]`.
- If `--json` is supplied, output deterministic JSON with no Rich/ANSI control sequences.
- If `--instructions` is supplied, attach phase instructions to the status JSON.
- Human output uses Rich and summarizes change name, schema, artifact store, planning home, next recommendation, phase states, task progress, and blockers.

### `sdd-continue`

- Invocation: `ai-harness sdd-continue [change] [--json] [--instructions] [--cwd <path>]`.
- Always attaches phase instructions; `--instructions` is accepted for compatibility but effectively redundant.
- Human output is dispatcher-oriented markdown for LLM/orchestrator consumption.
- Markdown output includes next recommendation, dependency states, blocked reasons, next-phase instructions when applicable, and fenced JSON.

### Workspace and Change Selection

- Root selection uses `--cwd` when provided, otherwise the current working directory.
- Active changes are direct subdirectories under `openspec/changes/`, excluding `archive/`.
- No active changes returns a blocked status recommending `sdd-new`.
- Multiple active changes without explicit name returns a blocked status recommending `select-change`.
- Requested missing change returns a blocked status recommending `sdd-new`.

### State Machine

- Core readiness requires non-empty `proposal.md`, at least one non-empty `spec.md`, non-empty `design.md`, non-empty `tasks.md`, and at least one checkbox task.
- Apply is ready when core artifacts are ready and unchecked tasks remain.
- Verify is ready when core artifacts are ready and either all tasks are complete or apply progress exists.
- Archive is ready only when verify is clearly passing and all tasks are complete.
- Verify report failures/blockers prevent archive readiness.

## Active Testing Capability

OpenSpec config now records both:

- `uv run pytest`
- `e2e/docker-test.sh`

The e2e suite builds a Docker image and exercises `uv tool install`, the installed `ai-harness` binary, reinstall, install behavior, and uninstall behavior. Migration acceptance should include e2e coverage because these commands must work through the installed console script, not only through `uv run`.

## Likely Implementation Shape

- Copy/adapt the backup SDD modules into active `src/ai_harness/`:
  - `compat.py`
  - `rendering.py`
  - `sdd/`
- Integrate the `sdd-status` and `sdd-continue` command definitions into the active Typer app in `src/ai_harness/main.py`, or split the CLI into deeper modules if the design phase chooses to reduce `main.py` complexity.
- Port relevant tests from `cli.bak/tests/` into active `tests/`, preferring behavior-first tests around CLI output, JSON contract, resolver state transitions, verify-report heuristics, and Rich boundary separation.
- Extend e2e coverage so the installed `ai-harness` binary can execute the migrated SDD commands.

## Risks and Open Questions

- `cli.bak/` contains both older Go code and Python code. The migration should treat the Python backup under `cli.bak/src/` as the primary source unless a test reveals mismatch with the intended contract.
- The active `main.py` is already doing install/uninstall work directly. Adding SDD command logic directly would make it shallower and wider; design should decide whether to preserve simplicity or introduce modules to keep boundaries deep.
- Backup implementation references `apply-progress.md`, while current SDD orchestrator artifacts use `apply-report.md`. The spec/design must decide whether to preserve backup compatibility, migrate to the current `apply-report.md` contract, or support both as a compatibility bridge. This is IMPORTANT; otherwise the native dispatcher and orchestrator can disagree.
- E2E tests require Docker availability, so local verification may need to report a blocked/untested e2e step when Docker is unavailable.

## Recommendation

Proceed to proposal. The proposal should explicitly define the authoritative apply artifact name, the command contracts, JSON compatibility expectations, and the required unit/e2e tests before implementation.
