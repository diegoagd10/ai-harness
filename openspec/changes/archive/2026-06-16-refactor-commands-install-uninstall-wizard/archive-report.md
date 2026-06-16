# Archive Report: refactor-commands-install-uninstall

**Date archived**: 2026-06-16
**Verify verdict**: PASS
**Preflight delivery**: B2 (size exception — maintainer-approved, estimated ~600–700 LOC)
**Archive path**: `openspec/changes/archive/2026-06-16-refactor-commands-install-uninstall-wizard/`

> **Note on naming**: A prior archive with the same change name exists at
> `openspec/changes/archive/2026-06-16-refactor-commands-install-uninstall/`
> (from the earlier CLI-command modularization cycle, 14 tasks, 135 tests). This archive
> covers the **interactive wizard + state file** cycle (30 tasks, 186 tests) and uses the
> `-wizard` suffix to distinguish them in the audit trail.

## Summary

This change added interactive install/uninstall wizards (`questionary`-based) and a persistent
state file (`~/.ai-harness/state.json`) to `ai-harness`. Users can now select which agents to
install or uninstall instead of the unconditional all-three operation. A `--all` flag preserves
backward compatibility for scripts and CI. State file writes are all-or-nothing, and the
uninstall wizard shows only installed agents with nothing pre-selected. A polish pass closed
all 5 WARNINGs and 3 NITs from the initial verify, extracted a shared agent registry, and
removed the unused `console` parameter from the wizard API.

## Stats

- **Tasks**: 30/30 complete (all `[x]`)
- **Unit tests**: 186 passing, 0 failing
- **Coverage**: 94% total; changed files: state.py 100%, wizard.py 100%, registry.py 83%,
  install.py 98%, uninstall.py 98%
- **E2E categories**: 8/8 passing (Tool Lifecycle, Harness Lifecycle x2, Copilot CLI Lifecycle,
  Wizard Lifecycle, SDD Lifecycle x3)
- **Spec scenarios**: 26/28 fully compliant, 2 partially compliant (pre-existing indirect
  coverage — no regressions)

### Production files

| File | Action |
|------|--------|
| `pyproject.toml` | Modified — added `questionary>=2.1.0` |
| `uv.lock` | Regenerated |
| `src/ai_harness/artifacts/state.py` | **Created** — load/save/clear state file, atomic write, validation |
| `src/ai_harness/artifacts/wizard.py` | **Created** — questionary checkbox wrappers for install/uninstall |
| `src/ai_harness/artifacts/registry.py` | **Created** (polish pass) — shared agent catalog, deduplicates `_AGENTS` + `installer_classes` |
| `src/ai_harness/artifacts/installer.py` | Modified — added `InstallResult`/`UninstallResult` dataclasses |
| `src/ai_harness/artifacts/installers/opencode.py` | Modified — propagate `InstallResult`/`UninstallResult` |
| `src/ai_harness/artifacts/installers/claude.py` | Modified — same return-type propagation |
| `src/ai_harness/artifacts/installers/copilot.py` | Modified — same return-type propagation |
| `src/ai_harness/commands/artifacts/install.py` | Rewritten — `--all` flag, TTY guard, wizard branch, all-or-nothing state |
| `src/ai_harness/commands/artifacts/uninstall.py` | Rewritten — mirror of install with `clear_state` on last removal |

### Test files

| File | Action |
|------|--------|
| `tests/test_state.py` | **Created** — 9 tests: load/save/clear/validation |
| `tests/test_wizard.py` | **Created** — 9 tests: install + uninstall presets, cancellation, footer hints |
| `tests/conftest.py` | Modified — added `monkeypatch_questionary` fixture |
| `tests/test_installer.py` | Modified — added return-contract tests |
| `tests/test_install.py` | Modified — 16 tests: all-bypass, wizard, terminal states, all-or-nothing |
| `tests/test_uninstall.py` | Modified — 20 tests: empty-state, all-bypass, wizard, TTY guard, all-or-nothing |

### E2E files

| File | Action |
|------|--------|
| `e2e/test_wizard_lifecycle.py` | **Created** — state file assertions (written after install, deleted after uninstall) |
| `e2e/test_harness_lifecycle.py` | Modified — added `--all` to all install/uninstall invocations |
| `e2e/test_copilot_cli_lifecycle.py` | Modified — added `--all` to all invocations (needed for full suite) |
| `e2e/tasks.py` | Modified — wired `wizard_lifecycle` into test task |

## Spec Convention

Per the project's established convention (documented in the prior archive's `archive-report.md`
and confirmed by user decision on 2026-06-16), the canonical location for specs is the archive
folder of the change that introduced them — NOT `openspec/specs/`. The four capability specs
remain in this archive's `specs/` directory:

| Domain | Path | Requirements | Scenarios |
|--------|------|-------------|-----------|
| `state-file` | `specs/state-file/spec.md` | 3 (Read, Write, Delete) | 6 |
| `install-wizard` | `specs/install-wizard/spec.md` | 3 (Display, Navigation, Terminal states) + Visual | 8 |
| `uninstall-wizard` | `specs/uninstall-wizard/spec.md` | 4 (Display, Navigation, Terminal states, All-or-nothing, File removal) | 8 |
| `non-interactive-bypass` | `specs/non-interactive-bypass/spec.md` | 3 (`--all` install, `--all` uninstall, Default behavior) | 6 |

No canonical tree (`openspec/specs/`) was created or modified, per the project convention.

## Deviations from Design

1. **`console` parameter removed from wizard** (polish pass NIT 2): The design specified
   `console: Console` parameter on `select_install_targets` and `select_uninstall_targets`,
   but the parameter was never used (questionary handles TTY I/O). Removed for simpler API.
2. **`_Empty`/`_Cancelled` → `Empty`/`Cancelled`** (polish pass NIT 3): Private sentinel names
   renamed per coding-guidelines (public API symbols should not have underscore prefixes).
3. **`registry.py` created** (polish pass NIT 1): Not in the original design. Agent-ID-to-class
   mapping was extracted from `wizard.py` + both commands into a shared deep module, eliminating
   cross-command duplication.
4. **`e2e/test_copilot_cli_lifecycle.py` updated**: Not listed in task 6.1, but required for
   full e2e suite pass because the no-TTY guard broke its `install`/`uninstall` invocations too.

All other design decisions (ADR-1 through ADR-7) match the implementation exactly.

## Follow-ups (non-blocking)

These minor coverage gaps from the verify report are deferred for future work:

1. **`save_state` overwrite test**: The spec scenario "Write replaces existing state file" lacks
   a dedicated unit test. Exercised indirectly via command-level tests only.
2. **`install --all` partial-state overwrite test**: No test seeds partial state and runs
   `install --all` to assert overwrite. Pre-existing gap, not a regression.
3. **`registry.py` defensive branch uncovered**: The `ValueError` in `get_installer()` for
   unknown agent IDs is uncovered (defensive guard; a single unit test would bring coverage
   to 100%).

## ADR Compliance

| ADR | Decision | Status |
|-----|----------|--------|
| ADR-1 | `questionary.checkbox` for multi-select | [PASS] |
| ADR-2 | State file at `~/.ai-harness/state.json` | [PASS] |
| ADR-3 | All-or-nothing state update at command level | [PASS] |
| ADR-4 | Installer returns `InstallResult` dataclass | [PASS] |
| ADR-5 | `--all` flag for non-interactive bypass | [PASS] |
| ADR-6 | No-TTY + no `--all` errors rather than auto-fallback | [PASS] |
| ADR-7 | `wizard.py` and `state.py` under `artifacts/` | [PASS] |

## Next Steps for the User

1. Review the changes (`git status`, `git diff --stat`).
2. Commit and push (or open a PR).
3. Address the 3 follow-ups in a future SDD change if desired.
4. The README update was deferred per the proposal — consider adding wizard usage docs.

## Integrity

- No commits or PRs were created by this archive step.
- All artifacts moved intact: `proposal.md`, `exploration.md`, `design.md`, `tasks.md`,
  `apply-report.md`, `verify-report.md`, `specs/` (4 domains).
- The active `openspec/changes/` no longer contains this change.
