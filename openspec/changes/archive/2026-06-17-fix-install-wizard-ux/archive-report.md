# Archive Report: Fix Install Wizard UX

**Date**: 2026-06-17  
**Change**: fix-install-wizard-ux  
**Status**: ARCHIVED  
**Verdict**: PASS WITH WARNINGS (manual TTY smoke test 6.3 completed by user)

## Task Completion Gate

All 30 implementation tasks marked complete in `tasks.md`:
- Phases 1-5 (infrastructure, ESC binding, rendering, prompt construction, pipe integration): 29/29 tasks checked
- Phase 6 (verification & cleanup): 6/6 tasks complete, including task 6.3 (manual TTY smoke test) confirmed PASSED by user in a real terminal

**Gate Status**: ✅ PASS — All tasks complete, no unchecked implementation tasks remain. Task 6.3 reconciled (was deferred, user confirmed green in real terminal: marker-only green, ESC cancels, » pointer tracks focus).

## Specs Merged

### Domain: install-wizard

**Action**: Created `openspec/specs/install-wizard/spec.md`

**Merge Summary**:
- Base from archive (2026-06-16-refactor-commands-install-uninstall-wizard): 4 requirements (Wizard displays, Keyboard navigation, Terminal states, Visual presentation)
- Delta (fix-install-wizard-ux): MODIFIED "Visual presentation" + MODIFIED "Terminal states"

**Changes**:
1. **Visual presentation** — expanded from {Header, Footer} to {Header, Footer, Selected option marks only glyph, Unselected keeps neutral, Cursor indicator independent}
   - Added: Scenario "Selected option marks only the glyph" (marker turns green, title neutral)
   - Added: Scenario "Unselected option keeps neutral marker and title"
   - Added: Scenario "Cursor indicator is independent of selection" (» pointer independent)

2. **Terminal states** — expanded from {Confirm w/ selection, Confirm w/ empty, Cancel via Escape} to {..., plus explicit "aborts the prompt" outcome, plus "Escape propagates to clean command-level cancel"}
   - Replaced: "Cancel via Escape" scenario (was generic "prints... exits 1") with "Cancel via Escape aborts the prompt" (explicit no-confirmation outcome)
   - Added: Scenario "Escape propagates to a clean command-level cancel" (Cancelled() path, filesystem untouched)

**Requirements added**: 0 new top-level requirements; 5 new scenarios under existing requirements.  
**Requirements modified**: 2 (Visual presentation, Terminal states).  
**Requirements removed**: 0.

---

### Domain: uninstall-wizard

**Action**: Created `openspec/specs/uninstall-wizard/spec.md`

**Merge Summary**:
- Base from archive (2026-06-16-refactor-commands-install-uninstall-wizard): 5 requirements (Wizard shows installed, Keyboard navigation, Terminal states, All-or-nothing state file, State file removal)
- Delta (fix-install-wizard-ux): MODIFIED "Terminal states" + ADDED "Visual presentation"

**Changes**:
1. **Terminal states** — expanded to clarify Escape cancellation and match install wizard
   - Modified: Requirement text now explicitly mandates "cancelled via Escape" and " propagate to uninstall command as a clean cancel via existing Cancelled() path"
   - Added: Scenario "Cancel via Escape aborts the prompt" (explicit no-confirmation outcome)
   - Added: Scenario "Escape propagates to a clean command-level cancel" (Cancelled() path, state file untouched)

2. **Visual presentation** (ADDED) — new requirement matching install wizard
   - Requirement text: "indicate selected options by the marker glyph only: when an option is selected, only its ●/○ marker SHALL change appearance (turns green), title MUST remain neutral"
   - Scenarios: "Selected option marks only the glyph", "Cursor indicator is independent of selection"

**Requirements added**: 1 (Visual presentation).  
**Requirements modified**: 1 (Terminal states — clarified Escape semantics).  
**Requirements removed**: 0.

---

## Implementation Verification

**Apply Phase Report**: apply-report.md  
- 339 changed lines + 80 lines in new test file = 419 total (within 800-line project budget)
- All 30 tasks mapped to RED-first tests and GREEN implementations

**Verify Phase Report**: verify-report.md  
- Verdict: **PASS WITH WARNINGS**
- Tests: 235 passed / 0 failed (225 baseline + 10 new = 235)
- Coverage: 92% average on changed files; wizard.py at 80% (acceptable floor; covers new fixes, cloned questionary defaults presence-tested)
- Spec compliance: 14/14 in-scope scenarios compliant (both install and uninstall)
- TDD evidence: 6/6 checks passed
- Critical issues: None
- Warnings: Task 6.3 (manual TTY smoke test) was deferred; now completed by user confirmation
- Acceptable deviations: test file name (`test_wizard_rendering.py` vs `test_rendering.py` to avoid conflating unrelated tests) and conftest patch target (`wizard._build_question` vs `questionary.checkbox` — reflects actual seam where Application is now built)

**E2E Test**: docker-test.sh passed (all categories including Wizard Lifecycle)

---

## Compliance Evidence

### Two Load-Bearing Fixes (Both Complete)

| Fix | Requirement | Test Evidence | Status |
|-----|-------------|---|--------|
| Marker-only rendering | "selected marker glyph only, title neutral" | `test_wizard_rendering.py`: 3 render token assertions; `MarkerOnlyControl._get_choice_tokens()` proven; shared by both wizards via `_build_question` | ✅ COVERED |
| ESC → Cancelled() | "ESC cancels, Cancelled() path" | `test_wizard.py`: real `PipeInput` feeds `\x1b` → `None`→`Cancelled()`; command-level exit tests in `test_install.py` + `test_uninstall.py` assert exit 1 + message | ✅ COVERED |

### Design Decisions Followed

| Decision | Implemented | Evidence |
|----------|---|---|
| Subclass `InquirerControl`, override `_get_choice_tokens` | ✅ Yes | `MarkerOnlyControl` class in wizard.py, asserted in render tests |
| Own `Application`/`KeyBindings`, add eager ESC | ✅ Yes | `_checkbox_bindings` + `_build_question` in wizard.py; binding tests pass |
| Reuse `create_inquirer_layout` + `Question` wrapper | ✅ Yes | Preserves `.ask()` + None/[]/list translation; public signatures unchanged |
| Pin questionary, add canary | ✅ Yes | `pyproject.toml` pins `==2.1.1`; `test_questionary_internals_contract_holds` in test_wizard.py |

### Test Coverage Breakdown

- **Unit (token/binding)**: 5 tests (canary, binding presence ×2, render ×3)
- **Integration (real PipeInput)**: 3 tests (ESC→Cancelled, space+enter, enter-only)
- **Command-level (exit codes)**: 2 tests (install ESC, uninstall ESC)
- **E2E (Docker)**: Passed (wizard lifecycle verified)
- **Total**: 235 passed

---

## Archive Contents Checklist

- [x] proposal.md — present and complete (3.8 KB)
- [x] design.md — present and complete (6.6 KB)
- [x] specs/ — present with both delta specs (install-wizard, uninstall-wizard)
- [x] tasks.md — present with all 30 tasks complete (task 6.3 reconciled)
- [x] apply-report.md — present (12.1 KB)
- [x] verify-report.md — present (15.7 KB)
- [x] exploration.md — present (9.3 KB)
- [x] archive-report.md — this file

---

## Source of Truth Updated

The following canonical specs now reflect the merged changes:

| Spec | Location | Status |
|------|----------|--------|
| install-wizard | `openspec/specs/install-wizard/spec.md` | ✅ Created (merged from base + delta) |
| uninstall-wizard | `openspec/specs/uninstall-wizard/spec.md` | ✅ Created (merged from base + delta) |

Both specs are now the authoritative source for the install and uninstall wizard behavior, including the two load-bearing UX fixes (marker-only rendering + ESC cancel).

---

## Exceptional Reconciliation Note

**Task 6.3 Completion** (manual TTY smoke test):
- Original state: Deferred (no interactive TTY in apply/verify sandbox)
- Verify verdict: PASS WITH WARNINGS (all automatable observables covered; manual TTY test flagged as required pre-merge human step)
- Archive action: User confirmed 6.3 PASSED in a real terminal — visually observed marker-only green selection, ESC cancellation working, and » pointer tracking focus correctly
- Checkbox reconciliation: Archive-time update of `tasks.md` to mark 6.3 complete, backed by user confirmation that the smoke test observables match the spec
- Justification: The verify-report proves all automatable aspects (rendering token classes, ESC→Cancelled via real PipeInput, command-level exit codes); the manual TTY test adds no new coverage — it was a visual confirmation of what the tests already prove. User confirmation makes the checkbox current.

---

## Delivery Summary

**SDD Cycle**: Complete  
**Outcome**: fix-install-wizard-ux successfully archived with all specs merged into canonical source.  
**Next Phase**: Ready for deployment. The unified specs are now authoritative for both install and uninstall wizard behavior.

---

*Archived on 2026-06-17 by sdd-archive phase*
