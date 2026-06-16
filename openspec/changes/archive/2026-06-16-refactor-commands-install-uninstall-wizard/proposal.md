# Proposal: Interactive Install/Uninstall Wizard

## Why

`ai-harness install` and `uninstall` act on all three harnesses unconditionally. Users with one or two get artifacts in unused targets; removing a single harness is impossible. This adds user control and a state file tracking what is installed.

## Capabilities

### New Capabilities
- `state-file`: Read/write `~/.ai-harness/state.json` (`{"installed": [...]}`). Missing = empty. Write only if all selected agents succeed.
- `install-wizard`: `questionary` checkbox UI. All three agents shown; pre-selects those not in state. Escape=cancel (exit 1); 0 selected=no-op (exit 0); N>0=execute.
- `uninstall-wizard`: Same UI; shows only installed agents; nothing pre-selected.
- `non-interactive-bypass`: `--all` flag to skip wizard for script/test compatibility.

### Modified Capabilities
- None.

## What Changes

- Add `questionary` to `pyproject.toml`
- New `src/ai_harness/state.py` (~40 LOC): read/write/validate state JSON
- New `src/ai_harness/wizard.py` (~80 LOC): checkbox UI, fixed agent order, terminal-state handling
- Rewrite `install.py` and `uninstall.py`: wizard → run selected → write state (all-or-nothing) + `--all` bypass
- Modify `src/ai_harness/artifacts/installer.py`: surface success/failure (currently returns `None`)
- New tests: `test_state.py`, `test_wizard.py`; rewrite `test_install.py`, `test_uninstall.py`; patch e2e with `--all`

## Impact

| Area | Impact |
|------|--------|
| `src/ai_harness/commands/artifacts/install.py` | Rewritten |
| `src/ai_harness/commands/artifacts/uninstall.py` | Rewritten |
| `src/ai_harness/state.py` | New |
| `src/ai_harness/wizard.py` | New |
| `src/ai_harness/artifacts/installer.py` | Modified (return contract) |
| `pyproject.toml` | Modified (`questionary`) |
| `tests/` + `e2e/` | Rewritten / new |

## Out of Scope

- Per-harness adapter changes
- Legacy migration (files without `state.json` treated as "not installed")
- XDG state directory
- README updates

## Rollback Plan

1. Revert `install.py`/`uninstall.py` to unconditional iteration
2. Delete `state.py`, `wizard.py`
3. Revert `installer.py` return contract
4. Remove `questionary` from `pyproject.toml`; regenerate `uv.lock`
5. Revert tests; delete `~/.ai-harness/state.json`

## Dependencies

- `questionary` (pure Python; depends on `prompt-toolkit`)

## Open Questions

- **Bypass mechanism**: `--all` flag vs. `--targets` CSV vs. TTY detection? `--all` simplest.
- **Failure detection**: Where does the all-or-nothing check live — command, wrapper, or installer? Partial FS state after mid-sequence failure is a real risk.
- **State write timing**: Must occur after wizard confirm AND all installers succeed. Escape = no mutation.
- **Installer contract**: Boolean return, exception, or structured result?

## Success Criteria

- [ ] Install wizard: subset selection installs only chosen agents; state updated
- [ ] Uninstall wizard: only installed agents shown; subset removal mutates state
- [ ] Escape → exit 1; zero selected → exit 0; partial failure → non-zero, state unchanged
- [ ] `--all` bypass preserves existing behavior for scripts and tests
- [ ] All tests pass (existing via bypass, new cover wizard/state/cancellation)
