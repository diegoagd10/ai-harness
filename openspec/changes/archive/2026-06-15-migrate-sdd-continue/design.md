# Design: Migrate `sdd-continue` (Second Slice)

## Technical Approach

A presentation-layer module (`rendering.py`) and a deep-module extension (`sdd/instructions.py`) are added alongside a backward-compatible `include_instructions` keyword argument on `resolve()` and a new Typer `sdd-continue` command that mirrors Go's dispatcher markdown contract. The `sdd-status` command gains an opt-in `--instructions` flag. The architecture respects the boundary established in the first slice: resolution lives in `ai_harness.sdd`; presentation lives in `ai_harness.rendering`; JSON serialization remains the single responsibility of `ai_harness.compat`.

## Architecture Overview

```mermaid
sequenceDiagram
    participant CLI as main.py sdd-continue
    participant Resolve as sdd/resolve.py
    participant Instr as sdd/instructions.py
    participant Render as rendering.py
    participant Compat as compat.py

    CLI->>Resolve: resolve(cwd, "", change, include_instructions=True)
    Resolve->>Resolve: workspace.discover(...), select change, compute state machine
    alt next is concrete (apply/verify/archive)
        Resolve->>Instr: build_phase_instructions(status)
        Instr-->>Resolve: PhaseInstructions
        Resolve->>Resolve: status.phase_instructions = ...
    end
    Resolve-->>CLI: Status
    alt --json
        CLI->>Compat: status_to_json(status)
        Compat-->>CLI: JSON string (phaseInstructions before nextRecommended)
    else default (markdown)
        CLI->>Render: render_dispatcher(status)
        Render-->>CLI: dispatcher markdown string
    end
    CLI-->>stdout: output; exit 0
```

## Module Boundaries (Deep Module Application)

### `src/ai_harness/sdd/instructions.py` — NEW

**Purpose**: Build `PhaseInstructions` for the three concrete SDD phases on demand. Public surface is a single function: `build_phase_instructions(status: Status) -> PhaseInstructions`. Hidden knowledge: the four-line string tables per phase (`apply`, `verify`, `archive`), the `"unresolved"` fallback for missing `change_name`, and the dependency-state key lookup.

**Deep-module justification**: One function (~35 lines) hides the phase-keyed message table that would otherwise be duplicated across every consumer. The caller expresses intent ("build me the instructions"), not mechanics ("for apply, format change name, then format apply dependency state, then append this static line..."). If instruction text changes, only this module is touched — neither `resolve.py`, `rendering.py`, `main.py`, nor `compat.py` carries the strings.

### `src/ai_harness/rendering.py` — NEW

**Purpose**: Present a resolved `Status` as dispatcher-structured markdown for LLM consumption. Public surface: `render_dispatcher(status: Status) -> str`. Hidden: section ordering (header → advisory → recommendation → dependencies → blocked reasons → instructions → JSON fenced block), the concrete-phase detection logic (`apply`/`verify`/`archive` vs. sentinels), the `"unresolved"` fallback for the header, and the fenced JSON formatting.

**Deep-module justification**: Callers depend on one function name and one argument type. They do not know (or repeat) the section order, the five-line header pattern, the conditional blocked-reasons block, the concrete-phase guard, or the trailing fenced JSON embed. Changing the markdown structure (e.g., moving the advisory line, adding a new section) affects only this module — never `main.py` or any consumer. This is a presentation-layer deep module: narrow interface (1 function), non-trivial implementation (~135 lines), and the complexity of markdown structure is hidden behind a simple call.

**Note on Rich**: The backup Python implementation (`cli.bak/src/ai_harness/rendering.py`) includes a Rich `render_status` function. This slice does NOT migrate it — `sdd-status` remains JSON-only per proposal decision Q2=A. The Rich import in `main.py` (line 5) is used only by `install`/`uninstall` and is unaffected.

### `src/ai_harness/sdd/resolve.py` — MODIFIED

**Purpose**: Extended with one keyword argument `include_instructions: bool = False`. When `True` and the resolved or blocked status has a concrete next phase (`apply`, `verify`, `archive`), calls `build_phase_instructions(status)` and attaches the result to `status.phase_instructions`.

**Deep-module justification**: The kwarg default-off preserves all three existing callers (`main.py:226`, `test_resolver.py`, `test_json_compat.py`) without any migration. The decision to build instructions lives inside `resolve()`, not in every command that calls it — the module absorbs the conditional logic (is the next phase concrete? should instructions be built?) so callers simply say `include_instructions=True`.

### `src/ai_harness/sdd/__init__.py` — MODIFIED

Re-exports `PhaseInstructions` from `ai_harness.sdd.models` so consumers use `from ai_harness.sdd import PhaseInstructions` without reaching into internal submodules. Two-line delta: one import, one `__all__` entry. Preserves the existing deep-module boundary.

### `src/ai_harness/main.py` — MODIFIED

Two new Typer declarations and a shared private helper. The `sdd-continue` command mirrors `sdd-status` in structure: resolve → branch on `--json` → emit. A private `_run_sdd_resolve` helper is extracted to DRY the error-handling and Typer exit logic shared by both commands. The `sdd-status` command gains an `--instructions` flag passed through to `resolve()`.

## Function Signatures

```python
# src/ai_harness/sdd/instructions.py
def build_phase_instructions(status: Status) -> PhaseInstructions:
    """Build PhaseInstructions with all three phases populated from status.
    
    The change name defaults to "unresolved" when status.change_name is None.
    Returns a PhaseInstructions whose lists are never empty — each phase
    carries 3–4 instruction lines matching Go's buildPhaseInstructions
    (cli.bak/internal/sdd/render.go:124-148).
    """

# src/ai_harness/rendering.py
def render_dispatcher(status: Status) -> str:
    """Render the routing-oriented dispatcher markdown for sdd-continue.
    
    Produces plain markdown (no Rich, no ANSI) targeting LLM consumption,
    matching Go's RenderDispatcherMarkdown (render.go:35-63). The output
    contains seven sections in fixed order: header, advisory line, next
    recommendation, dependency states, blocked reasons (conditional),
    next-phase instructions (conditional), and a fenced JSON block.
    """

# src/ai_harness/sdd/resolve.py
def resolve(
    cwd: str,
    workspace_root: str,
    change_name: str,
    include_instructions: bool = False,
) -> Status:
    """Compute Status for one change, optionally attaching phase instructions.
    
    include_instructions=True populates status.phase_instructions via
    build_phase_instructions() when next_recommended is a concrete phase
    (apply, verify, archive). When False or the next phase is a sentinel,
    phase_instructions remains None.
    
    Raises SddError on broken workspace root or unreadable artifacts.
    """

# src/ai_harness/main.py
def sdd_continue(
    change: str | None = typer.Argument(
        None, help="Active OpenSpec change name; inferred when omitted."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit deterministic JSON instead of dispatcher markdown."
    ),
    cwd: str = typer.Option("", "--cwd", help="Workspace directory to read openspec/ from."),
) -> None:
    """Show the next SDD action and per-phase instructions (dispatcher markdown by default)."""

def sdd_status(
    change: str | None = typer.Argument(
        None, help="Active OpenSpec change name; inferred when omitted."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit deterministic JSON instead of a rendered summary."
    ),
    instructions: bool = typer.Option(
        False, "--instructions", help="Include phase instructions in JSON output."
    ),
    cwd: str = typer.Option("", "--cwd", help="Workspace directory to read openspec/ from."),
) -> None:
    """Report the SDD phase state for a change."""

# Private helper (in main.py)
def _run_sdd_resolve(
    cwd: str,
    workspace_root: str,
    change_name: str,
    include_instructions: bool,
    json_output: bool,
) -> None:
    """Resolve status, then emit JSON (when json_output) or dispatcher markdown.
    
    Resolution errors and OSError are caught, reported to stderr, and exit 1.
    """
```

**Exit-code policy** (all commands):
- `0` — resolution succeeded; output emitted to stdout (markdown or JSON).
- `1` — `SddError` during workspace traversal or `OSError` during artifact reads / JSON serialization; message on stderr.
- `2` — usage/argument parse error (handled by Typer, echoes usage text).

## Data Flow

### Path: `sdd-continue --json` on an active "fix-auth" change in `apply` phase

1. Typer parses argv, invokes `sdd_continue(json_output=True, change=None, cwd=".")`.
2. `sdd_continue` calls `_run_sdd_resolve(cwd, "", "", include_instructions=True, json_output=True)`.
3. `_run_sdd_resolve` calls `resolve(cwd, "", "", include_instructions=True)`.
4. `resolve` discovers workspace, finds active change "fix-auth", reads artifacts, computes dependency states, transitions `apply` from `ready` to `all_done` if all tasks checked.
5. `resolve` sees `next_recommended` is `"apply"` (concrete) and `include_instructions=True`, so it calls `build_phase_instructions(status)`. The returned `PhaseInstructions` carries populated lists for all three phases.
6. `resolve` attaches `PhaseInstructions` to `status.phase_instructions` and returns the `Status`.
7. `_run_sdd_resolve` sees `json_output=True`, calls `compat.status_to_json(status)`. The `status_to_dict` function inserts `phaseInstructions` key before `nextRecommended` (pre-existing logic in `compat.py:82-83`).
8. JSON string goes to stdout. Exit 0.

### Path: `sdd-continue` (no `--json`) on the same workspace

Steps 1–6 identical. At step 7, `_run_sdd_resolve` sees `json_output=False`, calls `render_dispatcher(status)`. The renderer builds markdown sections (header with "fix-auth", advisory line, `next_recommended: apply`, all seven dependency states, no blocked reasons, `### Next Phase Instructions: apply` with four hint lines, `### JSON` fenced block with status JSON). The string goes to stdout. Exit 0.

### Path: `sdd-continue` on empty workspace

1. `resolve(cwd, "", "", include_instructions=True)` discovers zero active changes.
2. `_select_change` returns a `_ChangeBlock` with `next=NEXT_SDD_NEW` and one reason.
3. `_new_blocked_status` builds the blocked status. `next_recommended` is `"sdd-new"` (sentinel, not concrete).
4. `resolve` skips `build_phase_instructions` because the next phase is not concrete. `phase_instructions` stays `None`.
5. `render_dispatcher(status)` produces header with `"unresolved"`, `next_recommended: sdd-new`, dependency states all `blocked`, `### Blocked Reasons` with the reason line. No `### Next Phase Instructions` section. Fenced JSON block contains no `phaseInstructions` key.

### Path: `sdd-status --json --instructions` on active change

1. `sdd_status` calls `_run_sdd_resolve(cwd, "", change_name, include_instructions=True, json_output=True)`.
2. Same `resolve()` path as `sdd-continue` — `phase_instructions` populated when next is concrete.
3. JSON output includes `phaseInstructions` key.

### Path: `sdd-status --json` (no `--instructions`) on active change

1. `sdd_status` calls `_run_sdd_resolve(cwd, "", change_name, include_instructions=False, json_output=True)`.
2. `resolve()` returns status with `phase_instructions=None`.
3. `compat.status_to_dict()` skips the `phaseInstructions` key (pre-existing logic at line 82: `if status.phase_instructions is not None`).
4. JSON output identical to first-slice `sdd-status --json` — no `phaseInstructions` key.

## Decision Log (NEW decisions raised by design)

### Decision: Extract shared `_run_sdd_resolve` helper in `main.py`

| Option | Tradeoff | Decision |
|--------|----------|----------|
| A: Inline resolve+render in each command (~15 lines duplication each) | Simple but duplicates error-handling and branching logic across `sdd-status` and `sdd-continue` | Rejected — change amplification: a new flag or error-code change touches two places |
| B: Extract `_run_sdd_resolve` private helper that all SDD commands call | DRY, single error-handling path; matches Go `runStatus` pattern | **Chosen** |

**Rationale**: The `sdd-status` and `sdd-continue` commands share identical resolve→branch-on-json logic with different defaults (`include_instructions`, output format). A private `_run_sdd_resolve(cwd, workspace_root, change_name, include_instructions, json_output)` absorbs the error handling and Typer exit logic. Satisfies spec scenarios for both commands.

### Decision: `render_dispatcher` is a single function — no internal private helpers split out

| Option | Tradeoff | Decision |
|--------|----------|----------|
| A: Split into `_render_header`, `_render_dependencies`, `_render_blocked_reasons`, `_render_instructions`, `_render_fenced_json` | Each private function adds an interface cost (name, signature) while hiding only 3–5 lines of string building — classitis | Rejected |
| B: Single function with section comments, tested via full-string assertions | No unnecessary interfaces; the function is testable end-to-end with hand-built Status fixtures | **Chosen** |

**Rationale**: Splitting markdown section builders into separate functions would create five shallow modules (interface cost ≈ implementation). The Go code already demonstrates this as a single coherent function. Tests assert on the full output string, not on internal intermediates, so private helpers add no testability benefit.

### Decision: `build_phase_instructions` always populates all three phases unconditionally

| Option | Tradeoff | Decision |
|--------|----------|----------|
| A: Only populate the current next phase's instructions | Saves ~2 list allocations but creates a conditional interface — callers must handle `PhaseInstructions` with partially-empty lists | Rejected |
| B: Populate apply, verify, and archive simultaneously | Identical to Go; `PhaseInstructions` is always fully-formed; renderer picks the relevant sub-list | **Chosen** |

**Rationale**: Go's `buildPhaseInstructions` populates all three phases unconditionally. This keeps the interface simple (no partial `PhaseInstructions`) and matches the JSON contract where the `phaseInstructions` key always has all three sub-keys when present. Satisfies spec scenario "sdd-continue --json always includes phaseInstructions" with all three keys.

### Decision: `_select_change` blocked path never builds instructions (simplification vs Go)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| A: Pass `include_instructions` through `_new_blocked_status` so `build_phase_instructions` is called even on blocked statuses | Mirrors Go `newBlockedStatus` accepting the flag, but blocked statuses always have sentinel next phases — the call is a no-op | Rejected — unnecessary complexity |
| B: Only call `build_phase_instructions` in `resolve()` when next is concrete | Simpler; blocked statuses never have concrete phases, so no useful work is skipped | **Chosen** |

**Rationale**: Blocked statuses (no active change, ambiguous selection, missing named change) always produce sentinel `next_recommended` values (`sdd-new`, `select-change`, `resolve-blockers`). Go's `newBlockedStatus` calls `buildPhaseInstructions` but the renderer discards it because `recommendedPhase` returns false for sentinels. Skipping the call in Python eliminates dead work without changing observable behavior. Satisfies spec scenarios: "No active change emits unresolved dispatcher", "Unknown change name reports blocked status", "blocked status omits phaseInstructions".

## TDD / Test Architecture

Strict TDD order — red tests written and verified failing BEFORE green implementation:

1. **RED: `tests/test_instructions.py`** (new)
   - Assert `build_phase_instructions(status)` returns `PhaseInstructions` with 4 apply lines, 4 verify lines, 3 archive lines; change name reflected; dependency state reflects the correct phase; `"unresolved"` fallback when `change_name` is `None`.
   - Fixtures: `Status` objects hand-built in conftest with `dependencies.apply/verify/archive` set to `"ready"`.

2. **RED: `tests/test_rendering.py`** (new)
   - Assert `render_dispatcher(status)` produces sections in order: header with name, advisory line, `next_recommended`, dependency states block with all 7 deps + task_progress, blocked reasons condition, instructions condition (present for apply/verify/archive, absent for sdd-new/resolve-blockers/select-change), fenced JSON block.
   - Port Go contract tests from `cli.bak/tests/test_rendering.py`: resolved change with apply next, verify next, archive next, blocked (resolve-blockers), unresolved (sdd-new with blocked reasons).
   - Fixtures: `Status` objects built via `new_base_status` + manual field assignment.

3. **RED: extend `tests/test_resolver.py`** with `include_instructions` scenarios
   - `test_include_instructions_default_false`: three positional args → `phase_instructions is None`.
   - `test_include_instructions_true_populates_apply`: active change with core done, tasks unchecked → `phase_instructions` is `not None`, `phase_instructions.apply` has 4 strings.
   - `test_include_instructions_true_blocked_status_omits`: empty workspace → `phase_instructions is None` because next is `"sdd-new"`.

4. **RED: extend `tests/test_json_compat.py`** with `phaseInstructions` serialization
   - `test_phase_instructions_present_when_populated`: `status.phase_instructions = PhaseInstructions(...)` → `status_to_json(status)` contains `"phaseInstructions"` before `"nextRecommended"` with all three sub-keys.
   - `test_phase_instructions_absent_when_none`: `status.phase_instructions = None` → `status_to_json(status)` does NOT contain `"phaseInstructions"`.

5. **RED: extend `tests/test_cli_sdd.py`** with `sdd-continue` CLI cases
   - `test_sdd_continue_dispatcher_markdown`: `sdd-continue` on active change → stdout contains header, dependencies, no Rich markup.
   - `test_sdd_continue_json_includes_instructions`: `sdd-continue --json` → `phaseInstructions` key present.
   - `test_sdd_continue_empty_workspace`: `sdd-continue` on empty workspace → header is `"unresolved"`, blocked reasons present, no instructions section.
   - `test_sdd_status_instructions_flag`: `sdd-status --json --instructions` → `phaseInstructions` present.
   - `test_sdd_status_no_instructions_flag`: `sdd-status --json` → `phaseInstructions` absent.
   - `test_sdd_continue_missing_change`: `sdd-continue ghost` → blocked reasons mention `"ghost"`, exit 0.

6. **GREEN: implement production code**
   - `src/ai_harness/sdd/instructions.py` — `build_phase_instructions()` (~35 lines).
   - `src/ai_harness/rendering.py` — `render_dispatcher()` (~135 lines).
   - `src/ai_harness/sdd/resolve.py` — add `include_instructions` kwarg, conditional instruction build (~10 line delta).
   - `src/ai_harness/sdd/__init__.py` — re-export `PhaseInstructions` (2 line delta).
   - `src/ai_harness/main.py` — `_run_sdd_resolve` helper, `sdd-continue` command, `--instructions` flag on `sdd-status` (~75 line delta).

7. **REFACTOR: verify no duplication, check imports**
   - Confirm `compat.py` no longer imports `PhaseInstructions` from `ai_harness.sdd.models` directly — switch to `from ai_harness.sdd import PhaseInstructions`.
   - Confirm no `applyProgress` string appears in any new code path.
   - Confirm `uv run pytest` passes all five test files.

## Migration Safety

- **`resolve()` signature**: Adding `include_instructions: bool = False` as the fourth parameter is backward-compatible. All three existing callsites use positional arguments only:
  - `src/ai_harness/main.py:226`: `resolve(cwd, "", change or "")` — 3 positional args, default `False` applies.
  - `tests/test_resolver.py` (19 calls): all are `resolve(str(tmp_path), "", ...)` — 3 positional args.
  - `tests/test_json_compat.py` (2 calls): both are `resolve(str(tmp_path), "", ...)` — 3 positional args.
  - Zero callsites pass four arguments; no migration needed.

- **`PhaseInstructions` re-export**: `src/ai_harness/sdd/__init__.py` adds one import and one `__all__` entry. No existing import is removed or renamed. `compat.py` line 20 (`from ai_harness.sdd.models import PhaseInstructions`) continues to work and can later be updated to the public import without breaking anything.

- **`sdd-status` JSON unchanged without `--instructions`**: When `--instructions` is omitted, `include_instructions=False` is passed to `resolve()`, `phase_instructions` stays `None`, and `compat.status_to_dict()` skips the key (existing logic, line 82). JSON output is byte-identical to the first slice.

- **No DB or file-state migration**: This slice adds code, not data. No migration required.

## Open Questions

None.
