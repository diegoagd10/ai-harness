# Exploration — set-models-align

## Budget
70

## Affected Files
- `src/ai_harness/modules/wizard/tui.py` — current model-phase agent chooser assembles unaligned `f"{agent} - {model}"` labels for both Claude and OpenCode; effort phases pass pre-rendered labels through unchanged; confirm panel prints `build_confirmation_rows()` labels inside a Rich `Panel`.
- `src/ai_harness/modules/wizard/pure.py` — owns the reusable display helpers (`format_selection_label()`, `build_confirmation_rows()`) and is the best place for a pure column-alignment helper so model, effort, and confirm surfaces cannot drift.
- `tests/test_set_models.py` — contains exact string assertions for current unaligned labels (`change-implementor - opus`, `change-implementor: opus / high`, effort-phase context parity, confirm rows) and should gain direct tests for padding/trailing spaces.

## Current Printing Logic
- `set-models` is registered in `src/ai_harness/main.py` and implemented by `src/ai_harness/commands/set_models.py`; it only validates CLI args and dispatches to `run_wizard_or_bail()`.
- The interactive output lives in `src/ai_harness/modules/wizard/tui.py`.
- Model sections: `_ask_continue_or_agent()` and `_ask_opencode_continue_or_agent()` build `questionary.Choice.title` as `f"{agent} - {selected_model}"`, so the separator column moves with agent-name length and the right edge varies with model length.
- Effort sections: `run_claude_wizard.run_effort_phase()` and `run_opencode_wizard.run_effort_phase()` build a `display` dict with `format_selection_label()` and pass the strings through unchanged to the chooser. The helper currently formats `agent: model / effort`, `agent: model / (unset)`, or `agent: model / (NA)`.
- Summary/confirm section: `_ask_confirm()` calls `build_confirmation_rows()`, then prints each `row.label` as `  • {row.label}` in a Rich `Panel`; `build_confirmation_rows()` currently delegates to `format_selection_label()`.
- No existing column-alignment helper was found for this wizard. `build_agent_list_rows()` exists but is not used by the active chooser paths.

## Plan
- Add a small pure formatting helper in `pure.py` that computes max left-column and right-column widths across rows and returns labels like `{agent:<left_width} - {value:<right_width}`; keep trailing right padding intentional.
- Use that helper for Claude and OpenCode model-phase chooser rows in `_ask_continue_or_agent()` / `_ask_opencode_continue_or_agent()` instead of per-row f-strings.
- Rework effort-phase and confirm labels through the same helper, likely treating the right column as the existing value text (`model / effort`, `model / (unset)`, or `model / (NA)`) so both the dash column and final line length align without changing the underlying model/effort semantics.
- Keep Back, Continue, separators, prompt messages, write paths, and navigation behavior unchanged.
- Update tests that assert exact labels and add direct formatter tests that verify separator column consistency and trailing-space right padding for shorter model names (`opus`, `haiku`).

## Edge Cases
- Trailing spaces are meaningful for alignment and must be asserted without accidental `.strip()`/normalization.
- OpenCode model IDs can be much longer than Claude aliases (`provider/model`); padding should be computed from the current row set and should not assume fixed terminal width.
- Effort rows include placeholders `(unset)` and `(NA)`; alignment must preserve those states and must not reintroduce duplicate agent prefixes.
- Confirm rows are printed inside a Rich `Panel`; Rich/questionary may preserve or visually collapse trailing spaces differently depending on render path, so tests should target the raw labels as well as the TUI call boundary where practical.
- Dict iteration order in `build_confirmation_rows()` currently drives row order; width calculation should be done across the rows passed in without reordering.

## Test Surface
- `tests/test_set_models.py::test_ask_continue_or_agent_uses_dash_label_format` and OpenCode equivalent: update to aligned/padded expected strings.
- `tests/test_set_models.py` confirmation row tests around `build_confirmation_rows()` and `format_selection_label()` need updated expected labels or an added lower-level helper test if `format_selection_label()` remains unaligned for single rows.
- Effort-phase context parity tests around lines ~3829 should assert the aligned display still contains exactly one agent prefix and keeps `(unset)`/`(NA)` behavior.
- Add focused pure tests for a multi-row sample matching the user example: fixed dash column and equal raw `len()` for every returned label, including trailing spaces.

## Risks
- Existing tests intentionally lock the old unaligned exact strings; implementation must update those expectations carefully, not just loosen them.
- Padding with trailing spaces may be invisible in failure output and easy to regress unless tests compare `repr()`/length or explicit suffixes.
- Rich markup/panel rendering and questionary display may treat trailing spaces differently from plain strings; raw `Choice.title` and `PickerRow.label` tests reduce but do not fully eliminate visual-terminal risk.
- Changing `format_selection_label()` directly would affect both effort and confirm call sites; safer design may require a new multi-row alignment helper so single-row semantic formatting remains simple.
- Alignment should be per visible row set; hard-coding widths from the current nine change agents would be brittle if agent sets change.

## semantic_facts
```yaml
budget: 70
affected_files:
  - src/ai_harness/modules/wizard/tui.py
  - src/ai_harness/modules/wizard/pure.py
  - tests/test_set_models.py
risks:
  - Exact tests currently lock old unaligned strings.
  - Trailing spaces are intentional but visually fragile in assertions and terminal rendering.
  - Rich/questionary may preserve padding differently across render paths.
  - OpenCode model IDs and effort placeholders require dynamic widths rather than fixed constants.
follow_up: Design the helper boundary so model, effort, and confirm sections share alignment without breaking existing model/effort semantics or navigation behavior.
```
