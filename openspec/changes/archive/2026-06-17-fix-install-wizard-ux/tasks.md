# Tasks: Fix Install Wizard UX (selection rendering + ESC cancel)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~420-520 |
| 400-line budget risk | Medium |
| Size exception needed | No (fits 800-line project budget) |
| Suggested work units | Unit 1 (canary+bindings), Unit 2 (rendering), Unit 3 (pipe integration) |
| Delivery strategy | single-pr |
| Size exception | No |

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: Medium

Rationale: `wizard.py` is currently 101 lines and gains a new control subclass, style, key-bindings builder, and question builder (~+90-130 lines). `conftest.py` adds a `pipe_input` fixture (~+15-20 lines). `test_wizard.py` and `test_rendering.py` each add 3-5 new test functions with pipe/token assertions (~+150-220 lines combined). `pyproject.toml` is a 1-line version pin. Total estimate sits below the 800-line project budget but above the generic 400-line guideline, so it is flagged Medium risk rather than Low. No maintainer exception is required under the 800-line budget configured for this change.

### Suggested Work Units

| Unit | Goal | Delivery | Notes |
|------|------|----------|-------|
| 1 | Upgrade-canary + ESC key-binding (RED→GREEN) | single PR | Smallest, de-risks questionary coupling first |
| 2 | Marker-only rendering (RED→GREEN) | single PR | Depends on Unit 1's `MarkerOnlyControl` skeleton existing |
| 3 | Pipe-input integration tests + wiring `_build_question`/`_run_checkbox` | single PR | Depends on Units 1-2; proves end-to-end behavior |

## Phase 1: Infrastructure

- [x] 1.1 Pin `questionary==2.1.1` in `pyproject.toml` (was `>=2.1.0`).
- [x] 1.2 Add `pipe_input` fixture to `tests/conftest.py` using `prompt_toolkit.input.create_pipe_input`, yielding the pipe and closing it on teardown.
- [x] 1.3 [RED] Write canary test in `tests/test_wizard.py`: assert `hasattr(InquirerControl, "_get_choice_tokens")`, `create_inquirer_layout` is importable with its current signature, and `INDICATOR_SELECTED == "●"`. Run `uv run pytest` and confirm it fails only if these assumptions are unmet (should pass against pinned 2.1.1 — confirms baseline).

## Phase 2: ESC Key Binding (RED → GREEN)

- [x] 2.1 [RED] In `tests/test_wizard.py`, write `test_checkbox_bindings_includes_escape`: build bindings via `_checkbox_bindings(ic)` (not yet defined) and assert `get_bindings_for_keys((Keys.Escape,))` is non-empty.
- [x] 2.2 [RED] Write `test_checkbox_bindings_preserves_defaults`: assert bindings exist for `Keys.ControlC`, space, `Keys.ControlM`, `Keys.Up`/`Keys.Down`.
- [x] 2.3 Run `uv run pytest tests/test_wizard.py` and confirm both new tests fail (ImportError/AttributeError for `_checkbox_bindings`).
- [x] 2.4 [GREEN] In `src/ai_harness/artifacts/wizard.py`, implement `_checkbox_bindings(ic) -> KeyBindings` cloning questionary checkbox defaults and adding `@kb.add(Keys.Escape, eager=True)` → `event.app.exit(result=None)`.
- [x] 2.5 Run `uv run pytest tests/test_wizard.py` and confirm 2.1-2.2 pass.

## Phase 3: Marker-Only Rendering (RED → GREEN)

- [x] 3.1 [RED] In `tests/test_wizard_rendering.py`, write `test_selected_glyph_uses_dedicated_class`: instantiate `MarkerOnlyControl` (not yet defined) with choices, toggle one into `selected_options`, call `_get_choice_tokens()`, assert the glyph token class is `class:checkbox-selected`. (Deviation: used `tests/test_wizard_rendering.py` instead of `tests/test_rendering.py` — that filename already hosts unrelated `render_dispatcher`/SDD markdown tests; reusing it would conflate two unrelated capabilities in one file.)
- [x] 3.2 [RED] Write `test_selected_title_stays_neutral`: same setup, assert the title token class is `class:text` (NOT `class:selected`).
- [x] 3.3 [RED] Write `test_unselected_and_focused_tokens_unchanged`: assert unselected marker/title classes and the focused `»` pointer token are unaffected by the override.
- [x] 3.4 Run `uv run pytest tests/test_wizard_rendering.py` and confirm 3.1-3.3 fail (ImportError for `MarkerOnlyControl`).
- [x] 3.5 [GREEN] In `wizard.py`, implement `MarkerOnlyControl(InquirerControl)` overriding `_get_choice_tokens` to re-class selected-row glyph as `class:checkbox-selected` and selected-row title as `class:text`, leaving focused/unselected tokens from `super()` untouched.
- [x] 3.6 [GREEN] Add `_WIZARD_STYLE = merge_styles_default([Style([("checkbox-selected", "fg:#00FF00"), ("selected", "")])])` in `wizard.py`.
- [x] 3.7 Run `uv run pytest tests/test_wizard_rendering.py` and confirm 3.1-3.3 pass.

## Phase 4: Prompt Construction Wiring (RED → GREEN)

- [x] 4.1 [RED] In `tests/test_wizard.py`, write `test_build_question_returns_questionary_question`: call `_build_question(title, choices)` (not yet defined) and assert it returns a `questionary.Question` wrapping an `Application` built with `MarkerOnlyControl`, `_checkbox_bindings`, and `_WIZARD_STYLE`.
- [x] 4.2 Run `uv run pytest tests/test_wizard.py` and confirm 4.1 fails (ImportError for `_build_question`).
- [x] 4.3 [GREEN] In `wizard.py`, implement `_build_question(title, choices) -> questionary.Question` using `create_inquirer_layout(ic, header)` + the Phase 2/3 pieces, per design's data-flow diagram.
- [x] 4.4 [GREEN] Update `_run_checkbox` to accept the `Question` from `_build_question` and keep the existing `None → Cancelled()` / `[] → Empty()` / `list → list` translation.
- [x] 4.5 [GREEN] Update `select_install_targets` and `select_uninstall_targets` call sites to use `_build_question` + `_run_checkbox`, keeping their public signatures unchanged.
- [x] 4.6 Run `uv run pytest tests/test_wizard.py` and confirm 4.1 passes; confirm existing `_StubCheckbox` translation tests still pass. (Deviation: `_build_question` no longer calls `questionary.checkbox` — it builds the `Application` directly — so `monkeypatch_questionary`/`_StubCheckbox` in `conftest.py` were evolved to patch `wizard._build_question` instead of `questionary.checkbox`. Same public test contract — `kwargs["choices"]`, `kwargs["instruction"]`, `questionary_return` marker — preserved; only the patch target moved to match the new architectural seam.)

## Phase 5: Pipe-Input Integration Tests (RED → GREEN)

- [x] 5.1 [RED] In `tests/test_wizard.py`, write `test_escape_via_pipe_cancels`: using the `pipe_input` fixture, send `\x1b` (ESC), run `_build_question(...)` through `_run_checkbox` under `DummyOutput`, assert result translates to `Cancelled()`.
- [x] 5.2 [RED] Write `test_space_then_enter_via_pipe_returns_selection`: send `" "` then `\r`, assert the toggled choice is returned as a list.
- [x] 5.3 [RED] Write `test_enter_only_via_pipe_returns_empty`: send `\r` with no prior toggle, assert result translates to `Empty()`.
- [x] 5.4 Run `uv run pytest tests/test_wizard.py` and confirm 5.1-5.3 fail against the current wiring (or pass trivially only after Phase 4 — record actual failure mode before fixing). Actual: all 3 passed trivially on first run — Phase 4's `_build_question`/`_checkbox_bindings` wiring already satisfies ESC/space/enter end-to-end via real `PipeInput`, confirmed manually with a throwaway script before committing the tests.
- [x] 5.5 [GREEN] Adjust `_build_question`/`_run_checkbox` wiring if pipe tests reveal gaps (e.g., eager ESC timing, missing `Application` reset between tests). No gaps found — no adjustment needed.
- [x] 5.6 Run `uv run pytest tests/test_wizard.py` and confirm 5.1-5.3 pass.

## Phase 6: Verification & Cleanup

- [x] 6.1 Run full suite: `uv run pytest` — confirm all tests green, including untouched `install.py`/`uninstall.py` tests. Result: 235 passed (up from 225 baseline).
- [x] 6.2 Run `e2e/docker-test.sh` to confirm the installed CLI's install/uninstall lifecycle still works end-to-end. Result: all e2e categories passed, including Wizard Lifecycle (install --all / uninstall --all state-file assertions).
- [x] 6.3 Manually smoke-test in a real terminal: toggle a choice (marker-only green, no row highlight), press ESC (flow cancels, prints the `Cancelled()` message), confirm `»` pointer still tracks focus. PASSED — user manually confirmed in a real terminal (marker turns green only, ESC cancels, » pointer tracks focus).
- [x] 6.4 Review `wizard.py` for dead code (e.g., any now-unused questionary `checkbox()` kwargs) and remove. No `questionary.checkbox()` call remains (replaced by `_build_question`); no unused kwargs or dead branches found.
- [x] 6.5 Confirm `pyproject.toml` pin and final diff size against the Review Workload Forecast above; note actual changed-line count in the PR description. Actual: 339 changed lines across tracked files (`git diff --shortstat`) + 80 lines in the new `tests/test_wizard_rendering.py` = 419 total, within the 800-line project budget (Medium risk, no exception required, as forecast).
