# Exploration: fix-install-wizard-ux

Two TUI defects in the interactive install/uninstall wizard:
1. Selection state is rendered as a full-row highlight instead of marking only the radio/checkbox glyph.
2. Pressing ESC during the flow does not cancel, despite the footer claiming "esc cancel".

## Current State

### TUI stack
- The wizard is built on **questionary 2.1.1**, which is itself built on **prompt_toolkit 3.0.52** (verified via `uv run python -c "import questionary, prompt_toolkit"`).
- Our code (`src/ai_harness/artifacts/wizard.py`) is a thin wrapper: it builds `questionary.Choice` objects and calls `questionary.checkbox(...).ask()`, passing only `title`, `choices`, and `instruction`. It does **not** pass a custom `style`, custom `key_bindings`, or override `pointer`/indicators.
- Rendering and key handling therefore come entirely from questionary's bundled defaults:
  - `.venv/.../questionary/prompts/checkbox.py` — builds the prompt, key bindings, layout.
  - `.venv/.../questionary/prompts/common.py` — `InquirerControl._get_choice_tokens()` produces the per-row tokens (the render logic).
  - `.venv/.../questionary/constants.py` — `DEFAULT_STYLE`, indicator glyphs.
  - `.venv/.../questionary/question.py` — `.ask()` / `.unsafe_ask()` run loop.

### Defect 1 — selection rendering (root cause)
In `common.py:_get_choice_tokens()` (the `append` inner fn, lines ~397-498):
- Marker glyphs are already correct: `INDICATOR_SELECTED = "●"` and `INDICATOR_UNSELECTED = "○"` (`constants.py` lines 22-25).
- The cursor row prefix `»` (`DEFAULT_SELECTED_POINTER`) is a separate token (`class:pointer`).
- The problem: when a choice is selected (`selected = choice.value in self.selected_options`), questionary emits BOTH the indicator AND the entire title text under `class:selected`:
  - line ~450: `tokens.append(("class:selected", "{}".format(indicator)))`
  - lines ~462-464: `tokens.append(("class:selected", "{}{}".format(shortcut, choice.title)))`
- So the whole label row carries `class:selected`. In `DEFAULT_STYLE` (`constants.py` lines 50-51) `selected` is empty (`""`). The "full-width highlight" the user sees is the terminal/style applied to `class:selected` spanning the indicator + title. The cursor row also styles the title under `class:highlighted` (line ~467).
- Conclusion: the row-level emphasis is driven by `class:selected` being applied to the title text. We cannot easily change questionary's token emission without forking, BUT we CAN control how `class:selected` and `class:highlighted` are styled by passing a custom `style=` to `questionary.checkbox`. To make only the marker green, the lever is the indicator vs title styling — and questionary lumps them under the same class, so a pure style override cannot color ONLY the glyph while leaving the title plain unless we restructure tokens.

### Defect 2 — ESC does not cancel (root cause)
In `checkbox.py` the key bindings are (lines ~227-318):
- `ControlC` / `ControlQ` → `event.app.exit(exception=KeyboardInterrupt)` (abort).
- `space` → toggle, `a`/`i` → all/invert, arrows + `j/k` + emacs → move, `ControlM` (Enter) → submit.
- `@bindings.add(Keys.Any)` `other()` → **no-op that swallows every other key, including ESC**.
- There is **no binding for `Keys.Escape`**. ESC is captured by the `Keys.Any` catch-all and does nothing.
- `question.py:.ask()` only converts a `KeyboardInterrupt` into a `None` return (via the `kbi_msg` path). Our `_run_checkbox` maps `None → Cancelled()`. Since ESC never raises and never exits the app, `.ask()` never returns `None`, so `Cancelled()` is unreachable via ESC. The footer text `"esc cancel"` is therefore a lie.
- Note: this is the same root issue regardless of our wrapper — questionary's default checkbox simply does not bind ESC.

### Test coverage
- Unit: `tests/test_wizard.py` monkeypatches `questionary.checkbox` with `_StubCheckbox` (`tests/conftest.py`). It asserts choice construction, pre-selection rules, the instruction footer text (incl. `"esc"` substring at line 98-100), and the `None → Cancelled` / `[] → Empty` translation. It NEVER exercises real key bindings or rendering — the stub bypasses prompt_toolkit entirely. So neither defect is covered by existing tests.
- E2E: `e2e/test_wizard_lifecycle.py` only exercises `--all` (non-interactive bypass) and asserts state-file writes. It does NOT drive the interactive TUI (no pty/key injection).

## Affected Areas
- `src/ai_harness/artifacts/wizard.py` — the only place we can inject a custom `style=` and/or custom `key_bindings`/`pointer` into `questionary.checkbox`. Both fixes land here.
- `src/ai_harness/commands/artifacts/install.py` (lines 40-48) and `uninstall.py` (lines 45-53) — already handle `Cancelled()` correctly; no change needed once ESC actually produces it.
- `tests/test_wizard.py` / `tests/conftest.py` — the stub bypasses key handling, so a regression test for ESC needs either a real prompt_toolkit pipe-input/key-injection harness or a binding-level unit test.
- `tests/test_rendering.py` — existing rendering tests; check whether wizard rendering can be asserted there.

## Approaches

### Defect 2 (ESC) — recommended
1. **Pass custom `key_bindings` that bind `Keys.Escape` to `event.app.exit(result=None)`** — but `questionary.checkbox` does not accept a `key_bindings` kwarg that merges with its own; `**kwargs` only forwards to `Application`. Risk: prompt_toolkit may treat ESC as a prefix (escape sequences) causing latency.
   - Effort: Medium. Need to verify the kwarg plumbing in checkbox.py (it builds its own `KeyBindings` and does not merge an external one).
2. **Build the prompt ourselves** using questionary's lower-level `common.create_inquirer_layout` + our own `KeyBindings` (clone questionary's bindings + add ESC). Full control over both defects in one place.
   - Effort: Medium/High. More code in `wizard.py`, but removes reliance on questionary defaults and fixes BOTH defects cleanly.
3. **Switch to `questionary.checkbox(...)` and post-process** — not viable; ESC must be bound before `.ask()`.

### Defect 1 (marker-only selection) — recommended
1. **Pass a custom `style=`** mapping `class:selected` to a marker-friendly style. PROBLEM: questionary applies `class:selected` to BOTH the glyph and the title in the same token stream, so a style alone cannot isolate the glyph.
2. **Custom render via `InquirerControl` subclass** overriding `_get_choice_tokens` so the green/X marker uses one class and the title stays `class:text`. Combined with approach 2 for ESC (own layout), this is the clean fix.
   - Effort: Medium/High. Requires subclassing questionary internals (semi-private API) — version-pinning risk.
3. **Restyle only**: set `class:selected` to e.g. `fg:#00FF00 noreverse` and `class:highlighted` to a subtle style. This makes the selected ROW green text rather than a reverse-video block, partially satisfying the user (no full-width reverse bar) but still colors the whole label, not just the glyph.
   - Effort: Low. Lowest risk, but does not fully meet "marker only".

## Recommendation
Do BOTH fixes in `src/ai_harness/artifacts/wizard.py` by taking ownership of the prompt construction (Approach 2 for ESC + Approach 2 for rendering): subclass `InquirerControl` to emit the marker under a dedicated `class:checkbox-selected` while keeping titles under `class:text`/`class:highlighted`, and build a `KeyBindings` set that mirrors questionary's defaults plus an explicit `Keys.Escape → app.exit(result=None)` binding. This concentrates both fixes in one module we own and removes brittle dependence on questionary's default styling.

If the team prefers minimal risk for a first pass, ship the LOW-effort variant: custom `style=` to kill the reverse-video bar (Defect 1 partial) and verify whether `questionary.checkbox` will honor an externally supplied ESC binding — but our reading of `checkbox.py` shows it constructs its OWN `KeyBindings` and forwards `**kwargs` only to `Application`, so an external binding is NOT merged. That strongly pushes toward owning the prompt.

Decision needed from the user: full marker-only rendering (subclass internals, version-pin risk) vs. the simpler "green text, no reverse bar" restyle.

## Risks
- questionary `InquirerControl` and `create_inquirer_layout` are semi-private; subclassing/reusing them couples us to questionary 2.1.1 internals. Pin the version and add a test that fails loudly on upgrade.
- ESC in prompt_toolkit is an escape-sequence prefix; binding a bare `Escape` can introduce input latency or swallow arrow-key sequences if `eager`/`filter` are mis-set. Must test with real key injection (prompt_toolkit `PipeInput` / `create_pipe_input`).
- Existing unit tests stub `questionary.checkbox` entirely, so they will NOT catch regressions in our custom bindings/rendering. New tests must drive prompt_toolkit with a pipe input, or assert at the `KeyBindings`/token level.
- `strict_tdd: true` in config — RED tests for both defects must be written first.

## Ready for Proposal
Yes. Root causes are confirmed for both defects and the change is localized to `wizard.py` plus new tests. One open decision (marker-only subclass vs. simpler restyle) should be surfaced to the user during the proposal phase.
