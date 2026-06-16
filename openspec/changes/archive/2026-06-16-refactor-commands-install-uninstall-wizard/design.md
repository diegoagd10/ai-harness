# Design: Interactive Install/Uninstall Wizard

## 1. Architecture Overview

Two new infrastructure modules (`state.py`, `wizard.py`), a return-contract change on `installer.py`, and rewritten command orchestrators. Each new module owns one decision and hides it behind a narrow public surface.

```
src/ai_harness/
  commands/artifacts/
    install.py        # MODIFIED: Typer cmd, --all flag, orchestrates wizard→install→state
    uninstall.py      # MODIFIED: same shape, mirrored
  artifacts/
    state.py          # NEW: atomic read/write/delete of ~/.ai-harness/state.json
    wizard.py         # NEW: questionary checkbox wrappers (install + uninstall)
    installer.py      # MODIFIED: returns InstallResult/UninstallResult instead of None
    installers/       # MODIFIED: propagate return value from generic installer
```

## 2. Architecture Decision Records

### ADR-1: `questionary.checkbox` for multi-select
**Decision**: Use `questionary.checkbox`.
**Rationale**: Ships the complete interaction model (nav, toggle, confirm, cancel) as one call. Rich lacks checkbox primitives. Hand-rolled `readchar` loop duplicates battle-tested edge cases (resize, SIGWINCH, escape sequences).

### ADR-2: State file at `~/.ai-harness/state.json`
**Decision**: Hard-coded home path with shape `{"installed": ["opencode", ...]}`.
**Rationale**: Discoverable, personal-tool scale. XDG-aware paths add locator complexity. Per-tool manifests would scatter the "what is installed" decision across N files — violation of single-owner principle.

### ADR-3: All-or-nothing state update at the command level
**Decision**: The command collects all `InstallResult` objects and writes state only when every result is `success=True`. The state module knows nothing about install/uninstall semantics.
**Rationale**: "When is state consistent?" is an orchestrator decision, not a file-IO concern. The state module is a pure I/O boundary; the command owns the commit decision.

### ADR-4: Installer returns `InstallResult` dataclass
**Decision**: `InstallResult(success: bool, errors: list[str])` / `UninstallResult(success: bool, errors: list[str])`. The generic installer catches exceptions internally, prints to console, and populates the result. First file-write failure short-circuits with `success=False`.
**Alternatives**: (a) Exceptions — command would need try/except per installer call; (b) bool — loses error detail for user feedback.
**Rationale**: Makes the contract explicit — "I tried to install, here's what happened." Installer owns what constitutes failure; command doesn't need to know which file failed.

### ADR-5: `--all` flag for non-interactive bypass
**Decision**: `--all` CLI flag. Without it, check `sys.stdout.isatty()` and error with "Use --all in non-interactive mode" if no TTY.
**Rationale**: Explicit flag makes intent visible in scripts. Auto-fallback to `--all` would surprise users who accidentally pipe input and unwittingly uninstall everything.

### ADR-6: No-TTY + no `--all` errors rather than auto-fallback
**Decision**: Print descriptive error and exit 1. Never fall back silently.
**Rationale**: Silent fallback creates the worst kind of unknown-unknown — "did my script just install or not?"

### ADR-7: `wizard.py` and `state.py` under `artifacts/`, not `commands/`
**Decision**: Place both as `artifacts/state.py` and `artifacts/wizard.py`.
**Rationale**: Neither is a command — they are reusable infrastructure. `state.py` hides format + path + atomic strategy. `wizard.py` hides questionary internals + ordering + pre-selection rules. Both satisfy the deep-module test: small public surface, substantial hidden complexity.

## 3. Module Designs

### 3.1 `state.py` (NEW)
```python
class StateFileError(Exception): ...

def load_state(home: Path) -> set[str]: ...
def save_state(home: Path, installed: set[str]) -> None: ...
def clear_state(home: Path) -> None: ...
```
**Hidden**: path resolution (`~/.ai-harness/state.json`), directory creation, JSON parse/serialize, atomic write (temp file + rename). Missing file → empty set. Malformed JSON → `StateFileError`.

### 3.2 `wizard.py` (NEW)
```python
class Cancelled: ...
class EmptySelection: ...

def select_install_targets(installed: set[str], console: Console) -> list[str] | Cancelled | EmptySelection: ...
def select_uninstall_targets(installed: set[str], console: Console) -> list[str] | Cancelled | EmptySelection: ...
```
**Hidden**: questionary invocation, agent display names, fixed ordering, pre-selection rules, header/footer text. Shared private `_run_checkbox(choices, defaults, title, console)` helper.

### 3.3 `installer.py` (MODIFIED)
```python
@dataclass
class InstallResult:
    success: bool
    errors: list[str]

def install(manifest, home, console) -> InstallResult: ...
def uninstall(manifest, home, console) -> UninstallResult: ...
```
Each file operation wrapped; first error short-circuits with `success=False` + error text. Per-installer classes propagate the return value unchanged.

### 3.4 `commands/artifacts/install.py` (MODIFIED)
Typer command with `--all: Annotated[bool, typer.Option("--all")] = False`. Flow:
1. `load_state(home)` → installed set.
2. If `--all`: install all 3 unconditionally; `save_state(all_three)` only if all succeed.
3. Else no-TTY check → error + exit 1.
4. Else: `select_install_targets(...)`.
5. Match: `Cancelled` → "Installation cancelled" + exit 1. `EmptySelection` → "No agents were installed" + exit 0. `list[str]` → execute, `save_state` on full success.

### 3.5 `commands/artifacts/uninstall.py` (MODIFIED)
Mirror: `--all`, TTY guard, `select_uninstall_targets(...)`. On success: `save_state(installed - removed)`. If result is empty → `clear_state(home)`.

## 4. Data Flow

### Install (interactive)
```
user → install (no --all, TTY present)
  → load_state(home)                  → {"claude"}
  → select_install_targets({claude})  → ["opencode", "copilot"]
  → [opencode_installer.install(), copilot_installer.install()]
  → all ok? save_state({claude, opencode, copilot}) : state unchanged + error
```

### Uninstall (interactive, partial failure)
```
user → uninstall (state has {opencode, claude})
  → select_uninstall_targets(...)     → ["opencode", "claude"]
  → opencode.uninstall() → OK, claude.uninstall() → FAIL
  → state. save_state(...) NOT called; state unchanged; exit non-zero
```

### Install --all
```
user → install --all
  → all 3 installers called unconditionally
  → all ok? save_state({opencode, claude, copilot}) : state unchanged
```

## 5. Walkthroughs

**Fresh install → pick Claude only**: No state file → `load_state` returns `{}` → wizard pre-selects all 3 → user unchecks opencode + copilot, presses Enter → returns `["claude"]` → `claude_installer.install()` succeeds → `save_state({"claude"})`.

**Partial uninstall failure**: State has `{opencode, claude}` → wizard shows both unselected → user selects both, Enter → `["opencode", "claude"]` → opencode succeeds, claude fails → state file unchanged at `{"installed": ["opencode", "claude"]}`, error printed, exit 1.

**`--all` install on partial state**: State has `{claude}` → `--all` installs all 3 (claude re-installed idempotently) → `save_state({opencode, claude, copilot})`.

**Escape cancellation**: State has `{claude}` → `install` wizard opens → Escape → `Cancelled` sentinel → "Installation cancelled", exit 1, state unchanged.

## 6. Test Strategy

| Layer | What | How |
|-------|------|-----|
| Unit `state.py` | load/save/clear, missing file, malformed JSON, atomic write | `tmp_path` fixture |
| Unit `wizard.py` | pre-selection rules, cancel/empty sentinels | monkeypatch `questionary.checkbox` |
| Unit `installer.py` | return `InstallResult` on success and partial failure | synthetic manifests |
| Integration `test_install.py` | full flow with `--all`, wizard via fake questionary | `CliRunner` + monkeypatch |
| Integration `test_uninstall.py` | mirror of above | `CliRunner` |
| E2E `e2e/` | lifecycle: install --all → uninstall --all | existing Docker harness + `--all` |

Tests to modify: `test_install.py`, `test_uninstall.py` (add `--all` to all existing invocations, add new wizard/state scenarios). Tests to create: `test_state.py`, `test_wizard.py`.

## 7. Risk Register

1. **Partial FS state on mid-sequence failure**: If installer #2 fails, #1's files remain on disk while state file stays unchanged. **Mitigation**: idempotent re-install overwrites leftover files; state file is the single source of truth. Full rollback is out of scope. **Verify**: integration test with forced second-installer failure, assert state unchanged.
2. **Installer return-contract change**: Touches all 3 per-agent classes + 2 commands. **Mitigation**: small contract surface (just propagate a dataclass), all existing tests preserved via `--all`. **Verify**: full test suite passes before any wizard code is merged.
3. **Interactive default breaks non-TTY tests**: **Mitigation**: all existing tests converted to `--all`; new wizard tests use monkeypatched questionary, not real TTY. E2E Docker already has no TTY → exercises the `--all` path naturally. **Verify**: `uv run pytest` and `e2e/docker-test.sh` pass in CI.

## 8. Open Questions

- XDG state directory deferred (out of scope).
- `--only opencode,claude` for targeted bypass deferred (out of scope).
- README update deferred (out of scope; docs to follow after implementation).
