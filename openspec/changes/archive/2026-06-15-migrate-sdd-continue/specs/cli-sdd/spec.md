# Spec Delta: cli-sdd

## Purpose

This delta adds the `sdd-continue` subcommand, dispatcher markdown rendering, `--instructions` flag on `sdd-status`, `include_instructions` kwarg on `resolve()`, `PhaseInstructions` re-export, and the `phaseInstructions` JSON key to the `cli-sdd` domain. Together these close the capability gap deferred by the first migration slice (`migrate-sdd-status-continue`), bringing the Python CLI to parity with Go's `sdd-continue` path (`cli.bak/cmd/ai-harness/run.go:56-97`) and its dispatcher markdown contract (`cli.bak/internal/sdd/render.go:35-148`).

## ADDED Requirements

### Requirement: `sdd-continue` subcommand

The system MUST register a Typer subcommand `sdd-continue` accepting an optional positional `[CHANGE]` argument and two optional flags: `--json` (boolean) and `--cwd PATH` (string, default process cwd). The subcommand MUST call `resolve()` with `include_instructions=True` (`cli.bak/cmd/ai-harness/run.go:59-60`).

Output behavior:
- Default (no `--json`): emits dispatcher markdown to stdout via `render_dispatcher()`.
- `--json`: emits deterministic camelCase JSON to stdout matching the `ai-harness.sdd-status@1` schema.

Exit codes MUST mirror Go (`run.go:87-95`):
- 0 on successful resolution (including blocked/unresolved changes reported as valid output).
- 1 on `SddError` or serialization failure.
- 2 on usage/argument parse error (Typer-handled).

#### Scenario: Dispatcher markdown on active change

- GIVEN one active change "fix-auth" in `openspec/changes/`
- WHEN `sdd-continue` runs
- THEN dispatcher markdown is printed to stdout containing: a `## Native SDD Dispatcher: fix-auth` header, a `next_recommended` line, a `### Dependency States` section, a task progress line, and a trailing `### JSON` fenced block
- AND exit code is 0

#### Scenario: JSON output always includes phase instructions

- GIVEN one active change in `openspec/changes/`
- WHEN `sdd-continue --json` runs
- THEN camelCase JSON is emitted with the `phaseInstructions` key present, containing `apply`, `verify`, and `archive` sub-keys with instruction lists
- AND exit code is 0

#### Scenario: No active change emits unresolved dispatcher

- GIVEN cwd with zero active changes under `openspec/changes/`
- WHEN `sdd-continue` runs
- THEN dispatcher markdown header reads `## Native SDD Dispatcher: unresolved`
- AND `next_recommended: sdd-new` appears with a `### Blocked Reasons` section containing the reason for no active changes
- AND `### Next Phase Instructions` section is absent
- AND exit code is 0

#### Scenario: Unknown change name reports blocked status

- GIVEN no active change named "ghost"
- WHEN `sdd-continue ghost` runs
- THEN dispatcher markdown shows header `## Native SDD Dispatcher: ghost` with `next_recommended: sdd-new` and blocked reason naming the missing change
- AND exit code is 0

### Requirement: `resolve()` `include_instructions` keyword argument

The `resolve(cwd, workspace_root, change_name)` function MUST accept a new keyword-only argument `include_instructions: bool` defaulting to `False`. Existing positional calls (three arguments) MUST continue to work unchanged; no caller migration is required.

When `include_instructions=True` and the resolved or blocked `Status` has a concrete next phase (`apply`, `verify`, or `archive`), the returned `Status.phase_instructions` MUST be a populated `PhaseInstructions` instance with non-empty instruction lists for that phase (built by `build_phase_instructions`, mirroring `cli.bak/internal/sdd/render.go:124-148`).

When `include_instructions=False`, `Status.phase_instructions` MUST be `None`. When the next phase is a sentinel (`sdd-new`, `select-change`, `resolve-blockers`), `phase_instructions` MUST be `None` regardless of the flag — there is no concrete phase to instruct.

#### Scenario: Default preserves existing callers

- GIVEN an active change
- WHEN `resolve(cwd, "", name)` is called with three positional arguments and no `include_instructions`
- THEN `status.phase_instructions` is `None`
- AND all other `Status` fields are populated as before

#### Scenario: include_instructions=True populates apply instructions

- GIVEN an active change with core artifacts done and unchecked tasks
- WHEN `resolve(cwd, "", name, include_instructions=True)` is called
- THEN `status.next_recommended` is `"apply"`
- AND `status.phase_instructions` is not `None`
- AND `status.phase_instructions.apply` is a list of four non-empty strings

#### Scenario: include_instructions=True with blocked status omits instructions

- GIVEN cwd with zero active changes
- WHEN `resolve("/root", "", "", include_instructions=True)` is called
- THEN `status.next_recommended` is `"sdd-new"`
- AND `status.phase_instructions` is `None`

### Requirement: `PhaseInstructions` public re-export

The module `ai_harness.sdd` MUST re-export `PhaseInstructions` from `ai_harness.sdd.models` so that `from ai_harness.sdd import PhaseInstructions` succeeds. The re-exported name MUST be identical to `ai_harness.sdd.models.PhaseInstructions` (same class object, not a copy). This preserves the deep-module boundary: consumers import from `ai_harness.sdd`, not from internal submodules.

#### Scenario: Public import succeeds

- GIVEN the package is installed
- WHEN `from ai_harness.sdd import PhaseInstructions` is executed
- THEN no `ImportError` is raised

#### Scenario: Identity with source module

- GIVEN the package is installed
- WHEN `PhaseInstructions` is imported from `ai_harness.sdd`
- THEN `PhaseInstructions is ai_harness.sdd.models.PhaseInstructions` evaluates to `True`

### Requirement: `phaseInstructions` key in JSON output

The serialized JSON emitted by `--json` for both `sdd-status` and `sdd-continue` MUST follow the `ai-harness.sdd-status@1` schema.

When `include_instructions=True` (always for `sdd-continue`; opt-in for `sdd-status --instructions`), and when the resolved `Status` has a non-`None` `phase_instructions`, the serialized JSON MUST include a `phaseInstructions` key with the stable shape:

```json
"phaseInstructions": {
  "apply": ["Change: <name>", "State: <dep_state>", "<hint>", "<hint>"],
  "verify": ["Change: <name>", "State: <dep_state>", "<hint>", "<hint>"],
  "archive": ["Change: <name>", "State: <dep_state>", "<hint>"]
}
```

The `phaseInstructions` key MUST appear in the JSON object immediately before `nextRecommended` (mirrors Go struct field order; see `compat.py:80-83`).

When `Status.phase_instructions` is `None` (because `include_instructions=False` or the next phase is not concrete), the `phaseInstructions` key MUST be absent from the serialized output — consistent with Go's `omitempty` behavior.

#### Scenario: sdd-continue --json always includes phaseInstructions

- GIVEN one active change
- WHEN `sdd-continue --json` runs
- THEN the emitted JSON object contains `"phaseInstructions"` with `"apply"`, `"verify"`, and `"archive"` keys

#### Scenario: sdd-status --json omits phaseInstructions by default

- GIVEN one active change
- WHEN `sdd-status --json` runs (no `--instructions` flag)
- THEN the emitted JSON object does NOT contain a `"phaseInstructions"` key

#### Scenario: sdd-status --instructions --json includes phaseInstructions

- GIVEN one active change
- WHEN `sdd-status --json --instructions` runs
- THEN the emitted JSON object contains `"phaseInstructions"`

#### Scenario: blocked status omits phaseInstructions regardless of flag

- GIVEN cwd with no active changes
- WHEN `sdd-continue --json` runs
- THEN `status.phase_instructions` is `None` and the emitted JSON does NOT contain a `"phaseInstructions"` key

### Requirement: Dispatcher markdown renderer

The system MUST provide `render_dispatcher(status: Status) -> str` that produces a plain markdown string with zero ANSI escape codes and no Rich dependency. The output MUST match Go's `RenderDispatcherMarkdown` (`cli.bak/internal/sdd/render.go:35-63`), containing these sections in order:

1. **Header**: `## Native SDD Dispatcher: <name>` where `<name>` is `status.change_name` or `"unresolved"` when `None` (line 37).
2. **Advisory line**: the static string `"Native status is authoritative. Route by next_recommended and dependency state, not by prompt inference."` followed by a blank line (line 39).
3. **Next recommendation**: `next_recommended: <status.next_recommended>` (line 41).
4. **Dependency States**: `### Dependency States` section listing `proposal`, `specs`, `design`, `tasks`, `apply`, `verify`, `archive` dependency values, plus `task_progress: <completed>/<total> complete` (lines 43-51).
5. **Blocked Reasons** (conditional): `### Blocked Reasons` section, present only when `status.blocked_reasons` is non-empty; each reason on a `- ` line (lines 53, 72-81).
6. **Next Phase Instructions** (conditional): `### Next Phase Instructions: <phase>` section, present only when `next_recommended` is a concrete phase (`apply`, `verify`, or `archive`); each instruction on a `- ` line (lines 55-59, 93-99).
7. **JSON**: `### JSON` section followed by a fenced ```json block containing the full `status_to_json(status)` output (lines 62, 83-89).

The per-phase instruction lines MUST exactly match Go's `buildPhaseInstructions` (`render.go:124-148`):

- **apply** (4 lines):
  1. `Change: <status.change_name or "unresolved">`
  2. `State: <status.dependencies.apply>`
  3. `Read proposal, specs, design, and tasks before editing.`
  4. `Implement only unchecked tasks and update tasks.md checkboxes as work completes.`

- **verify** (4 lines):
  1. `Change: <change_name>`
  2. `State: <status.dependencies.verify>`
  3. `Verify implementation against proposal, specs, design, and task completion.`
  4. `Incomplete tasks remain archive blockers even when apply-progress.md exists.`

- **archive** (3 lines):
  1. `Change: <change_name>`
  2. `State: <status.dependencies.archive>`
  3. `Archive only when verify-report.md exists and every task checkbox is complete.`

**Note**: The verify hints retain the Go string `apply-progress.md` (line 140) — this is intentional Go parity; the Python resolve layer uses `apply-report.md` internally, but the instruction text preserves the original wording.

#### Scenario: Render apply next produces four apply hints

- GIVEN a `Status` with `next_recommended="apply"`, `change_name="fix-auth"`, `dependencies.apply="ready"`
- WHEN `render_dispatcher(status)` is called
- THEN the output contains `### Next Phase Instructions: apply`
- AND four hint lines follow, beginning with `Change: fix-auth` and `State: ready`
- AND the `### JSON` fenced block appears after the instructions

#### Scenario: Render verify next produces four verify hints

- GIVEN a `Status` with `next_recommended="verify"`, `change_name="feat-x"`, `dependencies.verify="ready"`
- WHEN `render_dispatcher(status)` is called
- THEN the output contains `### Next Phase Instructions: verify`
- AND the fourth hint line reads `Incomplete tasks remain archive blockers even when apply-progress.md exists.`

#### Scenario: Render archive next produces three archive hints

- GIVEN a `Status` with `next_recommended="archive"`, `dependencies.archive="ready"`
- WHEN `render_dispatcher(status)` is called
- THEN the output contains `### Next Phase Instructions: archive`
- AND exactly three hint lines follow

#### Scenario: sdd-new next omits the instructions section

- GIVEN a `Status` with `next_recommended="sdd-new"`
- WHEN `render_dispatcher(status)` is called
- THEN the output does NOT contain the string `### Next Phase Instructions`

#### Scenario: resolve-blockers next renders blocked reasons without instructions

- GIVEN a `Status` with `next_recommended="resolve-blockers"` and `blocked_reasons=["Missing proposal.md", "Missing specs/"]`
- WHEN `render_dispatcher(status)` is called
- THEN the output contains `### Blocked Reasons` listing both reasons
- AND the output does NOT contain `### Next Phase Instructions`

#### Scenario: select-change next renders as unresolved

- GIVEN a `Status` with `next_recommended="select-change"`, `change_name=None`, and `blocked_reasons=["Change selection is ambiguous: a, b."]`
- WHEN `render_dispatcher(status)` is called
- THEN the header reads `## Native SDD Dispatcher: unresolved`
- AND `### Blocked Reasons` appears
- AND `### Next Phase Instructions` is absent

#### Scenario: all-tasks-complete transition shows verify instructions

- GIVEN a `Status` with `next_recommended="verify"`, all task checkboxes checked, and `apply_report` present
- WHEN `render_dispatcher(status)` is called
- THEN the instructions section is `### Next Phase Instructions: verify`
- AND the `State:` line reflects `dependencies.verify`, not `dependencies.apply`

### Requirement: `--instructions` flag on `sdd-status`

The `sdd-status` subcommand MUST accept an optional `--instructions` boolean flag (Typer `Option`, default `False`). When `--instructions` is passed, `sdd-status` MUST call `resolve()` with `include_instructions=True`, populating `phase_instructions` on the resolved `Status`. When `--instructions` is omitted, `resolve()` MUST be called without `include_instructions`, preserving the existing behavior where `phase_instructions` is `None`. This flag SHALL have no effect when `sdd-status` is called without `--json` (sdd-status does not render markdown in this slice; it always emits JSON).

#### Scenario: sdd-status --json --instructions includes phaseInstructions

- GIVEN one active change
- WHEN `sdd-status --json --instructions` runs
- THEN the emitted JSON contains a `"phaseInstructions"` key
- AND exit code is 0

#### Scenario: sdd-status --json without --instructions omits phaseInstructions

- GIVEN one active change
- WHEN `sdd-status --json` runs (no `--instructions` flag)
- THEN the emitted JSON does NOT contain a `"phaseInstructions"` key
- AND exit code is 0

#### Scenario: sdd-status --instructions on no-active-change emits blocked reasons

- GIVEN cwd with zero active changes
- WHEN `sdd-status --json --instructions` runs
- THEN the emitted JSON contains `"nextRecommended": "sdd-new"` with populated `"blockedReasons"`
- AND the `"phaseInstructions"` key is absent (next is not a concrete phase)
- AND exit code is 0

## MODIFIED Requirements

### R1: sdd-status CLI

Registers Typer `sdd-status` with optional `[CHANGE]` positional argument and flags `--json`, `--cwd`, and `--instructions`. The `--instructions` flag (boolean, default `False`) causes `resolve()` to be called with `include_instructions=True`, making the `phaseInstructions` key appear in JSON output when the next phase is concrete. When `--instructions` is omitted, behavior is identical to the first slice. JSON output MUST contain zero ANSI escapes.

(Previously: `--instructions` was listed as "deferred" and not accepted by the CLI.)

#### Scenario: JSON status on active change

- GIVEN one active change in `openspec/changes/`
- WHEN `sdd-status --json` runs
- THEN deterministic camelCase JSON is printed to stdout and exit code is 0

#### Scenario: Explicit change name

- GIVEN change "fix-auth" exists in `openspec/changes/`
- WHEN `sdd-status fix-auth --json` runs
- THEN JSON resolves only "fix-auth"

#### Scenario: Missing workspace root

- GIVEN cwd with no `openspec/` ancestor
- WHEN `sdd-status --json` runs
- THEN exit code is 1 and stderr reports "workspace root not found"

#### Scenario: --instructions flag accepted and wired

- GIVEN one active change with concrete next phase
- WHEN `sdd-status --json --instructions` runs
- THEN exit code is 0 and the `phaseInstructions` key is present in the emitted JSON

### R7: Deterministic JSON Contract

camelCase in Go field order, 2-space indent, HTML-escaped (`&→\u0026`, `<→\u003c`, `>→\u003e`, plus U+2028/U+2029), sorted artifact map keys, non-null empty lists, `null` for unresolved change fields.

When `Status.phase_instructions` is not `None`, the serialized JSON MUST include a `phaseInstructions` key inserted before `nextRecommended` in the output object, with the stable shape `{ "apply": [<strings>], "verify": [<strings>], "archive": [<strings>] }` (mirrors `compat.py:80-83`). When `Status.phase_instructions` is `None`, the `phaseInstructions` key MUST be absent from the output.

JSON MUST be produced by `compat.status_to_json()` which SHALL NOT import Rich.

(Previously: the JSON schema had no `phaseInstructions` key. The `phase_instructions` field existed on `Status` but was never populated; it is now conditionally populated via `include_instructions`.)

#### Scenario: applyReport in JSON

- WHEN `status_to_json` serializes
- THEN `artifactPaths` contains `applyReport` and `artifacts` contains `applyReport` sorted lexically; `applyProgress` is absent from both

#### Scenario: phaseInstructions present when populated

- GIVEN a `Status` with `phase_instructions` not `None`
- WHEN `status_to_json(status)` is called
- THEN the output JSON string contains `"phaseInstructions"` before `"nextRecommended"`
- AND `"phaseInstructions"` is an object with `"apply"`, `"verify"`, `"archive"` keys

#### Scenario: phaseInstructions absent when None

- GIVEN a `Status` with `phase_instructions` is `None`
- WHEN `status_to_json(status)` is called
- THEN the output JSON string does NOT contain `"phaseInstructions"`

## REMOVED Requirements

None.
