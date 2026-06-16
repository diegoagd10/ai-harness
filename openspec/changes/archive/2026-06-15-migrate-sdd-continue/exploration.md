# Exploration: Migrate `sdd-continue` from Go to Python

## Context

The first Python migration slice (`migrate-sdd-status-continue`, archived under `openspec/changes/archive/2026-06-15-migrate-sdd-status-continue/`) landed `ai-harness sdd-status --json` and the core `src/ai_harness/sdd/` package. It deliberately deferred `sdd-continue`, human rendering, phase instructions, and the `--instructions` flag. This slice closes that gap: it migrates the `sdd-continue` subcommand from `cli.bak/` into `src/ai_harness/` so the LLM orchestrator can call `ai-harness sdd-continue` and receive dispatcher-oriented output with per-phase instructions always attached.

## What `sdd-continue` does today (Go)

The Go implementation lives in `cli.bak/cmd/ai-harness/run.go` and `cli.bak/internal/sdd/render.go`.

### CLI wiring (`run.go` lines 56-97)

- `sdd-continue` is dispatched by the same `runStatus` helper as `sdd-status`.
- The only difference is the boolean `alwaysInstructions=true` passed to `runStatus` (line 60).
- `runStatus` parses the shared flags `--json`, `--instructions`, `--cwd`, plus an optional positional change name (lines 74-97).
- It calls `sdd.Resolve(opts.cwd, "", opts.change, includeInstructions)` where `includeInstructions := alwaysInstructions || opts.instructions` (line 80). For `sdd-continue` this is **always `true`**.
- If `opts.json` is true, it emits indented JSON via `writeJSON` (lines 87-89).
- Otherwise it renders `sdd.RenderDispatcherMarkdown(status)` (lines 91-94).
- Errors resolve to stderr and exit codes: `1` for resolution/serialization failures, `2` for usage/parse errors.

### Default output: dispatcher markdown (`render.go` lines 35-63)

`RenderDispatcherMarkdown` produces plain markdown (no Rich/ANSI):

```markdown
## Native SDD Dispatcher: {change_name_or_unresolved}

Native status is authoritative. Route by next_recommended and dependency state, not by prompt inference.

next_recommended: {next}

### Dependency States
- proposal: {state}
- specs: {state}
- design: {state}
- tasks: {state}
- apply: {state}
- verify: {state}
- archive: {state}
- task_progress: {completed}/{total} complete

### Blocked Reasons        (only when reasons non-empty)
- {reason}

### Next Phase Instructions: {apply|verify|archive}   (only when next is a concrete phase)
- Change: {change}
- State: {dep_state}
- {phase-specific hint}

### JSON
```json
{full Status JSON}
```
```

Concrete phases with instructions are `apply`, `verify`, and `archive` (`render.go` lines 93-100). Sentinels like `sdd-new`, `select-change`, and `resolve-blockers` omit the instructions section.

### JSON output (`--json`)

- Emitted by `writeJSON` (`run.go` lines 434-441): 2-space indented, deterministic JSON.
- The `phaseInstructions` key is **always present** for `sdd-continue`, even without `--instructions` (verified by `run_test.go` lines 170-184).
- The schema is the same `ai-harness.sdd-status@1` contract used by `sdd-status`.

### Instruction content (`render.go` lines 124-148)

Instructions are built on demand by `buildPhaseInstructions` when `status.PhaseInstructions` is nil (`render.go` lines 104-120). Each phase carries four lines:

- `apply`: `Change: {name}`, `State: {dependencies.apply}`, "Read proposal, specs, design, and tasks before editing.", "Implement only unchecked tasks and update tasks.md checkboxes as work completes."
- `verify`: `Change: {name}`, `State: {dependencies.verify}`, "Verify implementation against proposal, specs, design, and task completion.", "Incomplete tasks remain archive blockers even when apply-progress.md exists."
- `archive`: `Change: {name}`, `State: {dependencies.archive}`, "Archive only when verify-report.md exists and every task checkbox is complete."

### Edge cases exercised by tests

- **No active change**: `nextRecommended == "sdd-new"`, header uses `"unresolved"`, blocked reasons section appears (`TestRunSDDStatusEmptyWorkspaceRecommendsSddNew` in `run_test.go` lines 186-199; analogous behavior for `sdd-continue`).
- **All tasks complete**: transitions `apply` dependency to `all_done` and may route to `verify`/`archive`.
- **Missing core artifacts**: `nextRecommended == "resolve-blockers"`, `### Blocked Reasons` lists each missing artifact, no `### Next Phase Instructions` (`render_test.go` lines 159-183).
- **Missing named change**: `changeName` is echoed, `nextRecommended == "sdd-new"`, blocked reason names the missing change (`run_test.go` lines 698-713).

## What already exists in Python

| Go file | Python equivalent | State |
|---------|-------------------|-------|
| `cli.bak/internal/sdd/status.go` + `basestatus.go` | `src/ai_harness/sdd/models.py` | Migrated; uses `apply_report` / `"applyReport"` rather than Go's `applyProgress`. `PhaseInstructions` dataclass exists but is not exported from `__init__.py`. |
| `cli.bak/internal/sdd/artifacts.go` | `src/ai_harness/sdd/artifacts.py` | Migrated; `apply-report.md` rename applied. |
| `cli.bak/internal/sdd/tasks.go` | `src/ai_harness/sdd/tasks.py` | Migrated unchanged. |
| `cli.bak/internal/sdd/verifyreport.go` | `src/ai_harness/sdd/verifyreport.py` | Migrated unchanged. |
| `cli.bak/internal/sdd/statemachine.go` | `src/ai_harness/sdd/statemachine.py` | Migrated; uses `artifacts["applyReport"]`. |
| `cli.bak/internal/sdd/workspace.go` | `src/ai_harness/sdd/workspace.py` | Migrated unchanged. |
| `cli.bak/internal/sdd/render.go` | `src/ai_harness/rendering.py` | **Missing**. A backup Python implementation exists at `cli.bak/src/ai_harness/rendering.py` but was not carried into `src/ai_harness/`. |
| `cli.bak/internal/sdd/render.go` (instructions) | `src/ai_harness/sdd/instructions.py` | **Missing**. Backup exists at `cli.bak/src/ai_harness/sdd/instructions.py`. |
| `cli.bak/cmd/ai-harness/run.go` | `src/ai_harness/main.py` | Partially migrated. Only `sdd-status` is registered and it **always outputs JSON** (`main.py` line 234); there is no `--json` branch, no `--instructions` flag, and no `sdd-continue` command. |
| `cli.bak/cmd/ai-harness/run_test.go` | `tests/test_cli_sdd.py` | Partially migrated. Covers `sdd-status` JSON only; `sdd-continue` tests omitted. |
| `cli.bak/internal/sdd/render_test.go` | `tests/test_rendering.py` | **Missing**. Backup exists at `cli.bak/tests/test_rendering.py`. |

### Reused Python surfaces

- `ai_harness.sdd.resolve(cwd, workspace_root, change_name)` returns `Status`. It currently has **no `include_instructions` parameter**, so it never attaches `phase_instructions`.
- `ai_harness.compat.status_to_json(status)` serializes a `Status` and already handles `phase_instructions` as an optional key (lines 82-83 of `compat.py`).
- `ai_harness.sdd.models.PhaseInstructions` exists but is not exported from `ai_harness.sdd`.

## Proposed scope for this slice

### Production files

1. **`src/ai_harness/sdd/instructions.py`** — new module, ~35 lines. Exposes `build_phase_instructions(status: Status) -> PhaseInstructions` mirroring `cli.bak/src/ai_harness/sdd/instructions.py` and Go `render.go` lines 124-148. Uses `apply_report` terminology.
2. **`src/ai_harness/rendering.py`** — new module, ~135 lines. Exposes:
   - `render_dispatcher(status: Status) -> str` (plain markdown for `sdd-continue`).
   - Optionally `render_status(status, console=None)` (Rich terminal output for `sdd-status` default). The first slice deferred Rich rendering; this slice can either bring it in or keep `sdd-status` JSON-only for now.
3. **`src/ai_harness/sdd/resolve.py`** — add `include_instructions: bool = False` parameter and attach `phase_instructions` when true. Estimated ~10 line delta.
4. **`src/ai_harness/sdd/__init__.py`** — re-export `PhaseInstructions`. Estimated ~2 line delta.
5. **`src/ai_harness/main.py`** — register `sdd-continue`; add `--instructions` to `sdd-status`; branch on `--json` vs renderer. Estimated ~60-90 line delta depending on whether `sdd-status` markdown is also implemented.

### Test files

1. **`tests/test_rendering.py`** — new file, ~170 lines. Ports `cli.bak/tests/test_rendering.py` with hand-built `Status` fixtures and assertions for dispatcher markdown sections, fenced JSON parity, blocked reasons, and non-concrete-phase handling.
2. **`tests/test_cli_sdd.py`** — extend with `sdd-continue` cases (~80 lines): command name, `--json` always includes instructions, `--instructions` accepted and ignored, human dispatcher markdown, blocked state.
3. **`tests/test_resolver.py`** — add cases for `include_instructions` behavior (~30 lines): absent by default, present when requested, built-on-demand.
4. **`tests/test_json_compat.py`** — add a case that `phaseInstructions` serializes in the expected key order when present (~20 lines).

### Line forecast vs review budget

| File | Approx. changed/new lines |
|------|---------------------------|
| `src/ai_harness/sdd/instructions.py` | 35 (new) |
| `src/ai_harness/rendering.py` | 135 (new) |
| `src/ai_harness/sdd/resolve.py` | 10 |
| `src/ai_harness/sdd/__init__.py` | 2 |
| `src/ai_harness/main.py` | 75 |
| `tests/test_rendering.py` | 170 (new) |
| `tests/test_cli_sdd.py` | 80 |
| `tests/test_resolver.py` | 30 |
| `tests/test_json_compat.py` | 20 |
| **Total** | **~557** |

This fits comfortably inside the 800-line review budget. The `exception-ok` delivery strategy is available, but no exception appears necessary unless the team decides to also migrate the full Rich `render_status` terminal output, which would add ~50 lines and still remain under budget.

## Open questions / decisions for `sdd-propose`

1. **Rendering module location and shape**
   - Option A: create `src/ai_harness/rendering.py` (matches the backup Python layout) and keep it separate from the `sdd/` deep module.
   - Option B: create `src/ai_harness/sdd/render.py` and re-export from `ai_harness.sdd`.
   - Recommendation: Option A. Rendering is a presentation concern, not part of the SDD resolution deep module; the backup Python code already used this boundary.

2. **Default output for `sdd-status`**
   - The Go CLI renders markdown by default and only emits JSON with `--json`. The current Python `sdd-status` always emits JSON.
   - Decision needed: does this slice also fix `sdd-status` to default to markdown, or does it only implement `sdd-continue` markdown and leave `sdd-status` JSON-only? If markdown is added for `sdd-status`, the `render_status` Rich renderer must also be migrated; if not, the `sdd-continue` command can rely solely on `render_dispatcher`.

3. **JSON schema for `sdd-continue`**
   - The Go implementation reuses the same `ai-harness.sdd-status@1` schema for both commands; only the rendered human output differs.
   - Decision needed: keep a single schema or introduce `ai-harness.sdd-continue@1`? Recommendation: reuse `ai-harness.sdd-status@1`; `sdd-continue` is a view over the same status object, not a different contract.

4. **`--instructions` flag on `sdd-status`**
   - Go supports it as opt-in. Current Python ignores it.
   - Decision needed: add the flag now (small change) or defer to a later slice? It is required for parity and is trivial to wire once `resolve()` accepts `include_instructions`.

5. **How blocked-status instructions are built**
   - Go `newBlockedStatus` accepts `includeInstructions` and calls `buildPhaseInstructions` on the blocked status (`basestatus.go` lines 21-28).
   - The current Python `new_base_status` does not. `resolve()` must pass the flag through `_new_blocked_status` and `_resolve_change` so that `sdd-continue` gets instructions even when no active change exists.

6. **Re-export policy for `PhaseInstructions`**
   - The first slice intentionally omitted `PhaseInstructions` from `ai_harness.sdd.__all__`.
   - Once `instructions.py` exists, should it be re-exported? Recommendation: yes, but keep it at the deep-module boundary: `from ai_harness.sdd import PhaseInstructions` for consumers like `compat.py` and tests.

7. **Human rendering technology**
   - `render_dispatcher` must be plain markdown (no ANSI) because LLMs consume it.
   - `render_status` may use Rich tables (backup Python did) or plain markdown (Go uses plain markdown). Decision needed before implementing `sdd-status` default output.

## Risks and dependencies

1. **Current `sdd-status` is JSON-only.** If `sdd-propose` decides `sdd-status` must also default to markdown, this slice grows by the Rich `render_status` path (~50 lines plus tests). Still within budget, but the design must be explicit.
2. **`resolve()` signature change.** Adding `include_instructions` ripples through existing tests that call `resolve(...)` with three positional arguments. The change is mechanical but must be coordinated with `test_resolver.py` updates.
3. **`applyProgress` / `apply-progress.md` terminology is gone.** The Go `render.go` and `status.go` still reference `applyProgress`. The Python migration must keep the `applyReport` rename established in the first slice; no drift back to the old name.
4. **e2e coverage.** `e2e/docker-test.sh` and `e2e/e2e_test.sh` exercise the installed binary lifecycle. They may only check `sdd-status --json` today; adding `sdd-continue` invocation to the e2e script is optional for this slice but should be tracked.
5. **No Go oracle in current tests.** The first slice removed the Go parity fixture. This slice can port the backup Python rendering tests (which construct `Status` directly) without needing a Go binary.
6. **Rich dependency is already declared** in `pyproject.toml`, so using it for `render_status` carries no new dependency risk.

## Recommendation

Proceed with `sdd-propose`. The smallest viable slice is:

- Add `sdd/instructions.py` and `rendering.py`.
- Extend `resolve()` with `include_instructions=False`.
- Register `sdd-continue` in `main.py` with dispatcher markdown default and `--json` always-including-instructions.
- Add `--instructions` to `sdd-status` and a `--json` branch, but keep `sdd-status` default output JSON-only unless the proposal explicitly approves Rich terminal rendering.
- Port `tests/test_rendering.py` and extend `tests/test_cli_sdd.py`, `tests/test_resolver.py`, and `tests/test_json_compat.py`.

This stays under the 800-line review budget and preserves the deep-module boundary established in the first slice.
