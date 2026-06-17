# Proposal: Fix Install Wizard UX (selection rendering + ESC cancel)

## Intent

Two TUI defects in the interactive install/uninstall wizard erode trust:
- **Selection rendering**: toggling an option highlights the entire row, so users can't quickly scan which items are selected.
- **ESC cancel**: the footer advertises "esc cancel" but ESC does nothing — the flow can't be aborted, making the UI a liar.

Both stem from relying on questionary 2.1.1 defaults that we never override.

## Scope

### In Scope
- Marker-only selection: only the `●`/`○` glyph turns green; title text stays neutral.
- Bind `Keys.Escape` so ESC cancels the flow, returning `None` → `Cancelled()`.
- RED-first tests driving real prompt_toolkit input (pipe) and/or binding/token-level assertions.
- Upgrade-canary test that fails loudly if questionary internals shift.

### Out of Scope
- Changes to `install.py` / `uninstall.py` — they already handle `Cancelled()`.
- Restyling beyond the selection marker (no theme overhaul).
- Upgrading questionary or prompt_toolkit.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `install-wizard`: selection state SHALL be indicated by the marker glyph only (neutral title); ESC SHALL cancel the interactive flow.
- `uninstall-wizard`: selection state SHALL be indicated by the marker glyph only (neutral title); ESC SHALL cancel the interactive flow.

## Approach

Take ownership of prompt construction in `wizard.py` (confirmed by user):
- **Rendering**: subclass questionary's `InquirerControl`, overriding `_get_choice_tokens` so the selected marker emits under a dedicated style class (e.g. `class:checkbox-selected`) while titles stay `class:text`/`class:highlighted`. Supply a matching `style=`.
- **ESC**: build a `KeyBindings` set mirroring questionary's checkbox defaults plus an explicit `Keys.Escape → event.app.exit(result=None)` binding, then drive the prompt via `create_inquirer_layout` / `Application`.

Accept coupling to questionary 2.1.1 internals; pin the version and add an upgrade-canary test as mitigation.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_harness/artifacts/wizard.py` | Modified | Subclass `InquirerControl`, custom `KeyBindings` + ESC, own the prompt build. |
| `tests/test_wizard.py`, `tests/conftest.py` | Modified | `_StubCheckbox` bypasses the TUI; add real prompt_toolkit pipe-input or binding/token-level tests. |
| `tests/test_rendering.py` | Modified | Assert marker-only token styling. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Coupling to questionary 2.1.1 semi-private internals (`InquirerControl`, `create_inquirer_layout`) | High | Pin version; upgrade-canary test fails on API drift. |
| Bare ESC is an escape-sequence prefix → input latency / swallowed arrow keys | Med | Test with real `PipeInput`; tune `eager`/`filter` on the ESC binding. |
| Existing stub tests miss binding/render regressions | High | New RED tests drive prompt_toolkit pipe input or assert at binding/token level. |

## Rollback Plan

Single PR, single module. Revert the `wizard.py` commit (and accompanying test files) to restore the questionary-default behavior. No data, state-file, or migration impact — install/uninstall command paths are untouched.

## Dependencies

- questionary 2.1.1 / prompt_toolkit 3.0.52 (pinned; internals relied upon).

## Success Criteria

- [ ] Selecting an option turns only the marker glyph green; the title stays neutral (no full-row highlight).
- [ ] Pressing ESC during install/uninstall raises `Cancelled()` and aborts cleanly.
- [ ] RED tests written first and passing after fix, exercising real key input (not the stub).
- [ ] Upgrade-canary test guards the questionary internals contract.
