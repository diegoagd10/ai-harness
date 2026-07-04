# PRD — set-models-align

## Intent

Make the `ai-harness set-models` wizard output easy to read at a glance by aligning the model, effort, and summary rows as a two-column table in monospace rendering.

Today, the wizard prints rows where the separator moves with agent-name length and each line ends at a different column. The user-visible effect is visually broken: agents, separators, and selected values do not scan cleanly across rows.

The desired outcome is that every visible row in the models, effort, and summary sections shares:

- a fixed separator column, and
- an identical raw line width, including intentional trailing-space padding on shorter right-column values.

Widths must be computed dynamically from the rows being rendered, not hard-coded from the current agent list or model aliases.

## Scope

### In

- Add a reusable pure alignment helper in `src/ai_harness/modules/wizard/pure.py` for two-column label rendering.
- Route Claude and OpenCode model chooser labels through the shared alignment helper.
- Route Claude and OpenCode effort chooser labels through the shared alignment helper while preserving model/effort meaning.
- Route summary/confirm rows through the shared alignment helper.
- Update `tests/test_set_models.py` to lock the new aligned output, including intentional trailing spaces.
- Preserve existing row order, navigation choices, write behavior, and wizard flow.

### Out

- No change to configuration write paths or persisted model/effort values.
- No change to Back, Continue, selection, or navigation semantics.
- No terminal-width-based truncation, wrapping, or responsive layout behavior.
- No new CLI flags or user configuration for formatting.
- No broad rewrite of the wizard or questionary/Rich rendering stack.

## Capabilities

- Pure alignment helper: `pure.py` exposes a deterministic helper that takes a list of `(left, right)` pairs and returns aligned label strings shaped as `{left:<left_width} - {right:<right_width}`, including trailing-space right padding so all returned labels have equal raw `len()`.
- Model section alignment: Claude and OpenCode model chooser rows use the helper so agent names align to one separator column and selected model values align to one shared right edge.
- Effort section alignment: Claude and OpenCode effort rows use the helper with the right column containing the existing semantic value text, such as `model / effort`, `model / (unset)`, or `model / (NA)`. The displayed separator should change to `-` for visual consistency with the model section and the user-provided target format; the underlying meaning remains `agent -> model plus effort`.
- Summary/confirm alignment: Confirmation rows are built with the same helper so the final review panel presents the same separator column and line width as the chooser sections.
- Navigation preservation: Back, Continue, separators, prompt messages, and selected row behavior remain unchanged; only the human-readable label strings change.
- Test coverage update: `tests/test_set_models.py` asserts fixed separator positions, equal raw line lengths, trailing-space padding for shorter values, OpenCode long ID behavior, effort placeholders, and summary row output.

## Approach

Introduce one multi-row formatter in `pure.py` rather than continuing to format each row independently. The helper should compute `left_width = max(len(left))` and `right_width = max(len(right))` over the provided visible row set, then emit labels using a consistent separator.

The model chooser paths in `tui.py` should build all visible `(agent, selected_model)` pairs first, format them together, and then assign the formatted labels to `questionary.Choice.title` without changing the choice values.

The effort phases should continue to derive the right-side value from the existing model/effort state, preserving `(unset)` and `(NA)` placeholders. They should pass `(agent, "model / effort")` pairs to the alignment helper instead of embedding the agent prefix in a pre-rendered single-row string.

The confirm path should format all confirmation rows as one visible set and preserve the current dict-driven row order. Rich panel printing should consume the padded raw labels returned by the helper.

The separator should be standardized to ` - ` across models, effort, and summary. This slightly changes existing effort/summary labels from `agent: model / effort` to `agent - model / effort`, but it makes the three wizard sections visually consistent and matches the user's target example. Tests should make that separator decision explicit so it cannot drift silently.

## Affected Areas

- `src/ai_harness/modules/wizard/pure.py` — add the shared formatter and update summary row construction or supporting helpers.
- `src/ai_harness/modules/wizard/tui.py` — route Claude/OpenCode model and effort chooser display labels through the formatter.
- `tests/test_set_models.py` — update old exact-string expectations and add focused alignment assertions.

## Risks

- Trailing spaces are intentional but fragile: assertions that call `.strip()` or failure output that hides spaces can miss regressions.
- OpenCode `provider/model` IDs can be much longer than Claude aliases, so widths must be dynamic per visible row set.
- `(unset)` and `(NA)` placeholders must remain semantically distinct and must not be dropped or normalized.
- `build_confirmation_rows()` currently follows dict iteration order; alignment must not reorder rows while computing widths.
- Rich `Panel` and questionary may differ in how visibly they preserve trailing spaces even when raw labels are correct.
- Changing effort/summary separators from `:` to `-` may affect downstream users who parse displayed labels instead of persisted config, even though the CLI does not expose these labels as a formal API.

## Rollback Plan

Revert the helper usage and restore the previous per-row formatting strings in the model, effort, and summary call sites. Since this change is display-only and does not alter write paths, rollback should not require migration or config repair.

## Dependencies

- Existing wizard helpers in `src/ai_harness/modules/wizard/pure.py` and `tui.py`.
- Existing test coverage in `tests/test_set_models.py` for model chooser labels, effort-phase context, and confirmation rows.
- Current Rich/questionary rendering behavior for preserving raw label text.

## Success Criteria

- In the models section, all agent rows render with the dash at the same column and all raw labels have the same length, including examples where `opus` and `haiku` are right-padded.
- In the effort section, Claude and OpenCode rows render with the same aligned dash format while preserving model/effort values and `(unset)` / `(NA)` placeholders.
- In the summary section, confirmation rows use the same aligned layout and retain the existing row order.
- No Back, Continue, navigation, prompt, or write behavior changes.
- Tests in `tests/test_set_models.py` fail if separator columns drift, right-edge padding disappears, row order changes, or placeholders are lost.
