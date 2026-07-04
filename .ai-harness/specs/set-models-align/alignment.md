# Spec — alignment

## Scope

Display-only alignment of the model, effort, and summary rows in the
`ai-harness set-models` wizard. The three visible row blocks (Claude
model chooser, Claude/OpenCode effort chooser, Rich confirmation
panel) currently render per-row f-strings whose separator column drifts
with the longest agent name and whose right edge drifts with the
longest value. After this change, every visible row in those three
blocks shares a fixed separator column and an identical raw line width
— including intentional trailing-space padding on shorter right-column
values — with widths computed dynamically per visible row set.

What stays put: `← Back` / `Continue` / `Separator` navigation choices
and their `Nav.BACK` / `Nav.CONTINUE` / `Nav.ESC_BACK` sentinels;
phase-aware Esc on the first phase; all write paths
(`write_override_store`, `build_override_payload`,
`build_opencode_override_payload`); the selective-write contract and
no-default-pollution invariant; the persisted override-store shape
(`{agent: {model|effort: {claude|opencode: value}}}` with `None`
meaning unset); the per-agent `_ask_*_model` / `_ask_*_effort` pickers
(one agent at a time, no row set to align across); the wizard's
structural phase order and TTY/binary guards.

The file is ordered for the **TDD loop**: helper tests (red) →
helper implementation → `format_selection_label` tests → narrowed
`format_selection_label` implementation → three call sites routing →
seams / invariants (MUST NOT change) → consolidated test coverage
checklist.

---

## Helper tests (red)

These tests are written against `align_label_rows` directly. They
**MUST fail** until the helper lands in
`src/ai_harness/modules/wizard/pure.py` with the signature and
guarantees fixed below.

### Requirement: signature-and-shape

`align_label_rows(pairs: Sequence[tuple[str, str]], *, separator: str
= " - ") -> list[str]` MUST be importable from
`src.ai_harness.modules.wizard.pure`. The helper MUST treat `pairs` as
opaque: it MUST NOT inspect, parse, split, normalise, or reorder the
tuples. Widths are computed only from `len(left)` and `len(right)`.

#### Scenario: default-arguments
GIVEN `align_label_rows` is imported from
`src.ai_harness.modules.wizard.pure`
WHEN it is called with only the positional `pairs` argument
THEN the returned strings use `" - "` as the column separator
AND `separator` is a keyword-only parameter defaulting to `" - "`.

Test: `test_align_label_rows_default_separator_and_signature`.

#### Scenario: pairs-are-opaque
GIVEN pairs `[("a", "b"), ("c", "d/e")]` containing characters that
could be misread as separators
WHEN `align_label_rows` is called
THEN the helper pads based on `len()` alone and does NOT re-split the
right column on `/` or strip an internal `-`.

Test: `test_align_label_rows_pairs_are_opaque`.

### Requirement: equal-raw-len-across-rows

Every returned label MUST have the same raw `len()`. That common
length MUST equal `left_width + len(separator) + right_width`, where
`left_width = max(len(left) for left, _ in pairs)` and `right_width =
max(len(right) for _, right in pairs)`.

#### Scenario: mixed-width-input-equal-len
GIVEN pairs `[("change-implementor", "opus"), ("change-validator",
"openai/gpt-5.5")]`
WHEN `align_label_rows` is called
THEN every returned label has identical `len()`
AND that `len()` equals `len("change-implementor") + len(" - ") +
len("openai/gpt-5.5")`.

Test: `test_align_label_rows_equal_raw_len_across_rows`.

#### Scenario: equal-len-on-equal-width-input
GIVEN pairs `[("a", "x"), ("b", "y")]` (uniform widths)
WHEN `align_label_rows` is called
THEN both labels have the same `len()` and no extra padding is added.

Test: `test_align_label_rows_equal_widths_passthrough`.

### Requirement: separator-at-same-column

The substring `separator` MUST begin at the same column index in every
returned label. That column index MUST equal `left_width`.

#### Scenario: separator-at-fixed-column
GIVEN pairs with mixed left widths
WHEN the helper returns labels
THEN `label.index(separator)` is identical for every label in the
returned list.

Test: `test_align_label_rows_separator_at_same_column`.

### Requirement: trailing-space-right-padding

Shorter right values MUST be right-padded with ASCII space characters
so every label's right edge aligns. The padding MUST be emitted via
`f"{right:<right_width}"` semantics. The helper MUST NOT call
`.strip()` / `.rstrip()` / `.lstrip()` on its output.

#### Scenario: shorter-right-padded-with-trailing-spaces
GIVEN pairs `[("a", "opus"), ("a", "haiku")]`
WHEN `align_label_rows` is called
THEN the `"opus"` label ends with at least one trailing space
AND `repr(label)` shows the trailing spaces as literal spaces
AND both labels have identical `len()`.

Test: `test_align_label_rows_trailing_space_padding_for_shorter_right`.

#### Scenario: padding-survives-string-round-trip
GIVEN a label returned by the helper ending with trailing spaces
WHEN that label is assigned to `questionary.Choice.title` and read
back
THEN the trailing spaces are still present at the end of the title
string. The helper MUST NOT mutate or normalise the returned strings.

Test: `test_align_label_rows_padding_survives_round_trip`.

### Requirement: order-preservation

The helper MUST return labels in input order. The label at output index
N MUST correspond to the input pair at index N. The helper MUST NOT
sort, group, or reorder the pairs.

#### Scenario: shuffled-input-order
GIVEN pairs `[("c", "3"), ("a", "1"), ("b", "2")]` shuffled from a
canonical order
WHEN `align_label_rows` is called
THEN the returned labels are in the same shuffled order
AND the right half of label index N equals the right column of input
pair index N.

Test: `test_align_label_rows_preserves_input_order`.

### Requirement: empty-input

Given an empty input sequence, the helper MUST return `[]`. It MUST
NOT raise `ValueError`, `TypeError`, or any other exception.

#### Scenario: empty-list
GIVEN `align_label_rows([])` is called
WHEN the helper is invoked
THEN the return value is the empty list
AND no exception is raised.

Test: `test_align_label_rows_empty_input_returns_empty_list`.

### Requirement: single-row-uses-self-as-max

Given a single pair, the helper MUST return a one-element list. The
returned label MUST use the pair's own `len(left)` and `len(right)`
as the column widths. No extra padding beyond what the row itself
requires MUST be added.

#### Scenario: single-row
GIVEN `align_label_rows([("change-implementor", "opus")])` is called
WHEN the helper returns
THEN the result has length 1
AND the label's `len()` equals `len("change-implementor") + len(" - ")
+ len("opus")`.

Test: `test_align_label_rows_single_row_uses_self_as_max`.

### Requirement: opencode-long-ids-set-wider-right

Given pairs that mix short Claude aliases and long OpenCode
`provider/model` IDs, the helper MUST compute `right_width` from the
maximum across all rows. The helper MUST NOT apply a hard-coded
maximum length, MUST NOT truncate, and MUST NOT prefer one input
set's widths over another.

#### Scenario: opencode-id-drives-right-width
GIVEN pairs `[("change-implementor", "opus"), ("change-validator",
"openai/gpt-5.5")]`
WHEN `align_label_rows` is called
THEN `right_width` equals `len("openai/gpt-5.5")`
AND the `"opus"` label is right-padded with trailing spaces to that
width.

Test: `test_align_label_rows_opencode_long_ids_set_wider_right`.

### Requirement: placeholders-pass-through-verbatim

The helper MUST NOT inspect, normalise, lowercase, or coalesce the
right column's contents. The literal substrings `(unset)` and `(NA)`
MUST reach the returned label unchanged.

#### Scenario: unset-placeholder-preserved
GIVEN a pair `("change-implementor", "opus / (unset)")`
WHEN `align_label_rows` is called
THEN the right half of the returned label contains `" / (unset)"`
verbatim — case, parentheses, and surrounding spaces unchanged.

Test: `test_align_label_rows_unset_placeholder_verbatim`.

#### Scenario: na-placeholder-preserved
GIVEN a pair `("change-implementor", "opus / (NA)")`
WHEN `align_label_rows` is called
THEN the right half of the returned label contains `" / (NA)"`
verbatim — uppercase `NA`, no lowercasing, no removal.

Test: `test_align_label_rows_na_placeholder_verbatim`.

### Requirement: custom-separator-kwarg

The helper MUST accept a `separator` keyword argument. When the caller
passes `separator=" | "`, every returned label MUST contain `" | "`
between the columns and the equal-`len()` invariant MUST still hold.
The default separator (when the kwarg is omitted) MUST be `" - "`.

#### Scenario: custom-separator
GIVEN `align_label_rows(pairs, separator=" | ")` is called
WHEN the helper returns
THEN every label contains `" | "`
AND every returned label has the same `len()`.

Test: `test_align_label_rows_custom_separator_kwarg`.

#### Scenario: default-separator
GIVEN `align_label_rows(pairs)` is called with no separator argument
WHEN the helper returns
THEN every label contains the substring `" - "`.

Test: `test_align_label_rows_default_separator_is_dash`.

---

## Helper implementation

Once the red tests above pass, the implementation lands in
`src/ai_harness/modules/wizard/pure.py`:

```python
def align_label_rows(
    pairs: Sequence[tuple[str, str]],
    *,
    separator: str = " - ",
) -> list[str]:
    left_width = max((len(left) for left, _ in pairs), default=0)
    right_width = max((len(right) for _, right in pairs), default=0)
    return [
        f"{left:<{left_width}}{separator}{right:<{right_width}}"
        for left, right in pairs
    ]
```

The `default=0` makes `align_label_rows([])` safe (no `ValueError`).

**Guarantees**:

1. The emission shape is exactly
   `f"{left:<{left_width}}{separator}{right:<{right_width}}"` —
   left-aligned space-fill on both columns, separator verbatim.
2. `left_width` and `right_width` are computed over the **visible row
   set passed in** — never memoised, never hard-coded from the agent
   list. Per-call is correct because the visible row set changes
   between model / effort / confirm phases and between Claude /
   OpenCode.
3. Every returned string has `len() == left_width + len(separator) +
   right_width`.
4. Trailing spaces are emitted by `f"{right:<{right_width}}"` and
   NOT removed by any `.strip()` call.
5. Output index N corresponds to input index N (no reordering).

---

## format_selection_label tests

These tests are written against `format_selection_label` after the
narrowing. They **MUST fail** until the function's output shape is
reduced from `"{agent}: {model} / {state}"` to just the right column
(`"{model} / {state}"`).

### Requirement: three-branch-decision-preserved

`format_selection_label(agent, model, effort, has_effort_support)`
MUST preserve the three-branch semantic decision:

- `has_effort_support is False` MUST return `"{model} / (NA)"`. The
  `effort` value MUST be discarded.
- `has_effort_support is True and effort is None` MUST return
  `"{model} / (unset)"`.
- `has_effort_support is True and effort is a non-None string` MUST
  return `"{model} / {effort}"`.

#### Scenario: supported-model-with-effort
GIVEN `format_selection_label("change-implementor", "opus", "high",
has_effort_support=True)`
WHEN the function returns
THEN the result equals `"opus / high"`.

Test: `test_format_selection_label_supported_model_with_effort`.

#### Scenario: supported-model-no-effort-emits-unset
GIVEN `format_selection_label("change-implementor", "opus", None,
has_effort_support=True)`
WHEN the function returns
THEN the result equals `"opus / (unset)"`.

Test:
`test_format_selection_label_supported_model_no_effort_emits_unset`.

#### Scenario: unsupported-model-no-effort-emits-na
GIVEN `format_selection_label("change-implementor", "opus", None,
has_effort_support=False)`
WHEN the function returns
THEN the result equals `"opus / (NA)"` (NOT `"opus / (unset)"`). The
`has_effort_support` flag dominates.

Test:
`test_format_selection_label_unsupported_model_no_effort_emits_na`.

#### Scenario: unsupported-model-ignores-effort-value
GIVEN `format_selection_label("change-implementor", "opus", "high",
has_effort_support=False)`
WHEN the function returns
THEN the result equals `"opus / (NA)"`
AND the literal string `"high"` does NOT appear in the result.

Test:
`test_format_selection_label_unsupported_model_ignores_effort_value`.

#### Scenario: defensive-empty-model-does-not-raise
GIVEN `format_selection_label("change-implementor", "", None,
has_effort_support=True)`
WHEN the function returns
THEN no exception is raised (no `IndexError` / `ValueError` /
`AttributeError`).

Test: `test_format_selection_label_empty_model_does_not_raise`.

### Requirement: no-agent-prefix-in-output

`format_selection_label` MUST NOT include the agent name in its
returned string. The agent prefix is added later by
`align_label_rows`. The `agent` parameter is still in the signature
but the value MUST be unused in the returned string.

#### Scenario: agent-name-absent-from-output
GIVEN `format_selection_label("change-implementor", "opus", "high",
has_effort_support=True)`
WHEN the function returns
THEN `"change-implementor"` does NOT appear in the result
AND the result has no leading agent prefix.

Test: `test_format_selection_label_no_agent_prefix_in_output`.

#### Scenario: agent-name-absent-for-na
GIVEN `format_selection_label("change-validator", "openai/gpt-5.5",
"low", has_effort_support=False)`
WHEN the function returns
THEN the result is exactly `"openai/gpt-5.5 / (NA)"` and the substring
`"change-validator"` does NOT appear.

Test: `test_format_selection_label_no_agent_prefix_on_na_branch`.

### Requirement: effort-phase-and-confirm-panel-right-column-parity

For a given `(agent, model, effort, has_effort_support)` tuple, the
right column returned by `format_selection_label` MUST be identical
whether the caller is the effort phase or the confirmation panel.
The right-column parity is the underlying invariant that the
alignment helper relies on.

#### Scenario: parity-on-none-effort
GIVEN `format_selection_label("change-implementor", "opus", None,
True)` is called from the effort phase
AND the same call is made from `build_confirmation_rows`
WHEN both calls return
THEN the two return values are byte-identical.

Test:
`test_format_selection_label_effort_phase_and_confirm_panel_match_for_none_effort`.

#### Scenario: parity-on-set-effort
GIVEN `format_selection_label("change-implementor", "opus", "high",
True)` is called from both the effort phase and `build_confirmation_rows`
WHEN both return
THEN the two return values are byte-identical.

Test:
`test_format_selection_label_effort_phase_and_confirm_panel_match_for_set_effort`.

### Requirement: placeholders-not-normalised

The substrings `(unset)` and `(NA)` MUST appear in the output exactly
as written — case-sensitive, no lowercasing, no whitespace stripping,
no removal of parentheses, no translation to alternative glyphs.

#### Scenario: placeholder-case-preserved
GIVEN `format_selection_label("a", "opus", None, True)`
WHEN the function returns
THEN `"(unset)"` appears verbatim.

Test: `test_format_selection_label_unset_case_preserved`.

#### Scenario: na-case-preserved
GIVEN `format_selection_label("a", "opus", "high", False)`
WHEN the function returns
THEN `"(NA)"` appears verbatim — uppercase `NA`, not `"(na)"`, not
`"(Not Available)"`.

Test: `test_format_selection_label_na_case_preserved`.

---

## format_selection_label implementation

Once the narrowed-output tests above pass, the function's
implementation narrows. The agent prefix is removed; the three-branch
decision stays.

**Before** (one of three full strings):

```python
f"{agent}: {model} / {effort}"   # or
f"{agent}: {model} / (unset)"    # or
f"{agent}: {model} / (NA)"
```

**After** (right column only):

```python
f"{model} / {effort}"    # effort set, supported
f"{model} / (unset)"     # effort None, supported
f"{model} / (NA)"        # not supported
```

The function still owns the three-branch decision (which placeholder,
whether to drop the effort value). The agent name is no longer its
concern; `align_label_rows` wraps the agent name around whatever this
returns.

**Why the narrowing matters**: without it, `align_label_rows`'s input
would not be homogeneous — every call site would have to strip a
prefix the helper itself added. The narrowing keeps call sites uniform
and keeps the alignment helper's contract simple (opaque strings).

The three-branch decision is per-row state, not per-call state.
Keeping it separate from the multi-row helper is what lets every
call site pass the full pairs list without re-implementing the
placeholder logic at each call site.

---

## Three call sites routing

Three call sites in `src/ai_harness/modules/wizard/tui.py` route
through `align_label_rows`. Each builds the visible row set as
`(left, right)` pairs, calls the helper once on the full set, and
assigns the formatted labels back to the choice/row object the
questionary / Rich layer consumes. Row order is **always preserved**.

### Requirement: claude-model-and-effort-chooser-routing

`_ask_continue_or_agent(phase, selections)` MUST route both phases
(`"model"` and `"effort"`) through `align_label_rows`. The function
MUST build the visible row set as `[(agent, selections.get(agent,
default_right)) for agent in claude_wizard_agents()]`, call
`align_label_rows` once on that list, then assign each returned label
to `questionary.Choice(title=aligned_label, value=agent)`.

#### Scenario: claude-model-phase-routing
GIVEN `_ask_continue_or_agent(phase="model", selections=...)` is called
with `selections` keyed by agent (each value is a bare model alias
such as `"opus"` or `"sonnet"`)
WHEN the function builds `questionary.Choice` objects
THEN each agent row's `Choice.title` is one of the strings returned
by `align_label_rows` over the visible row set
AND every agent-row `Choice.title` has the same `len()`
AND `Choice.value` is the bare agent name.

#### Scenario: claude-effort-phase-routing
GIVEN `run_claude_wizard.run_effort_phase` has built `display[agent]
= format_selection_label(agent, model, efforts[agent],
has_effort_support=True)` for every agent
WHEN `_ask_continue_or_agent(phase="effort", selections=display, ...)`
builds the choices
THEN each agent row's `Choice.title` is one of the strings returned
by `align_label_rows([(agent, display.get(agent, "(unset)")) for
agent in agent_list])`
AND every agent-row `Choice.title` has the same `len()`
AND no title contains the forbidden substring
`f"{agent} - {agent} -"` (which would happen if the caller still
passed the old `"{agent}: ..."` shape).

### Requirement: opencode-model-and-effort-chooser-routing

`_ask_opencode_continue_or_agent(phase, selections, agents)` MUST
follow the same routing shape. For the effort phase,
`selections[agent]` is the right-column-only output of
`format_selection_label(...)` with
`has_effort_support=opencode_model_is_reasoning(model)` per agent.

#### Scenario: opencode-model-phase-routing
GIVEN `_ask_opencode_continue_or_agent(phase="model", selections=...,
agents=...)` is called
WHEN the function builds the choices
THEN each agent row's `Choice.title` is one of the strings returned
by `align_label_rows` over the visible row set
AND the right column width is driven by the longest OpenCode
`provider/model` ID (not a hard-coded constant)
AND `Choice.value` is the bare agent name.

#### Scenario: opencode-effort-phase-routing
GIVEN the OpenCode effort phase has built `display[agent]` using
`has_effort_support=opencode_model_is_reasoning(model)`
WHEN `_ask_opencode_continue_or_agent(phase="effort", ...)` builds
the choices
THEN each agent row's `Choice.title` is one of the strings returned
by `align_label_rows`
AND no title contains `f"{agent} - {agent} -"`
AND the right column for each agent is the format-selection-label
output verbatim.

### Requirement: confirmation-panel-routing-through-build-confirmation-rows

`_ask_confirm(title, selections)` consumes `PickerRow.label` as a
raw string — body construction is
`"\n".join(f"  • {row.label}" for row in rows)` (no strip). The
alignment happens **inside** `build_confirmation_rows(selections)`,
which composes `format_selection_label(..., has_effort_support=True)`
and `align_label_rows` once over the full visible row set.

#### Scenario: confirmation-rows-aligned-internally
GIVEN `selections = {agent: ModelSelection(model, effort)}` in
insertion order
WHEN `build_confirmation_rows(selections)` returns
THEN the function walks `selections.items()` in insertion order
AND for each pair computes `right =
format_selection_label(agent, model, effort,
has_effort_support=True)`
AND calls `align_label_rows([(agent, right) for ...])` once on the
full set
AND returns `PickerRow(value=agent, label=aligned_label)` per row, in
insertion order
AND every returned `row.label` has the same `len()`.

#### Scenario: ask-confirm-consumes-raw-labels-unchanged
GIVEN `build_confirmation_rows(selections)` has returned rows whose
labels end with trailing-space right padding
WHEN `_ask_confirm(title, selections)` builds the Rich `Panel` body
THEN each body line is `f"  • {row.label}"` (no `.strip()`,
`.rstrip()`, or re-formatting)
AND the trailing spaces survive into the body string
AND `rich.panel.Panel(body, title=...)` is constructed with the body
unchanged.

### Requirement: per-agent-pickers-not-routed

`_ask_claude_model`, `_ask_claude_effort`, `_ask_opencode_model`,
`_ask_opencode_effort` MUST NOT be routed through `align_label_rows`.
They display a single agent and have no row set to align across.

#### Scenario: per-agent-picker-stays-outside-helper
GIVEN any per-agent picker function builds its choice list
WHEN the choice list is inspected
THEN `align_label_rows` is NOT called
AND the per-agent picker's titles, values, separators, and ordering
are byte-identical to the pre-change behaviour.

---

## Seams / invariants (MUST NOT change)

These invariants are **load-bearing for any implementation of this
design**. A change that relaxes any of these is out of scope for this
PRD and MUST be flagged separately.

### Requirement: back-continue-esc-semantics-unchanged

The wizard's navigation choices (`← Back`, `Separator`, `Continue`),
the `Nav.BACK` / `Nav.CONTINUE` / `Nav.ESC_BACK` sentinels, and the
phase-aware Esc behaviour MUST be preserved verbatim.

#### Scenario: nav-sentinels-unchanged
GIVEN the wizard runs the model → effort → confirm phases
WHEN each phase completes
THEN the return values still include `Nav.BACK`, `Nav.CONTINUE`, and
`Nav.ESC_BACK` exactly as before
AND `← Back` and `Continue` still appear in the choice lists with
their original sentinel values
AND the `questionary.Separator` row appears exactly once with its
original title.

#### Scenario: phase-aware-esc-on-first-phase
GIVEN the wizard is in the `phase="model"` phase (first phase, no
predecessor)
WHEN the user presses Esc
THEN the wizard returns `Nav.ESC_BACK` (or equivalent phase-zero Esc
behaviour) exactly as before.

### Requirement: write-paths-and-payload-builders-unchanged

`write_override_store`, `build_override_payload`,
`build_opencode_override_payload`, and the selective-write contract
(only fields the user changed are persisted) MUST be unchanged. The
alignment refactor MUST NOT introduce new write logic, new keys, or
new validation in the writer path. The no-default-pollution invariant
MUST be preserved.

#### Scenario: selective-write-contract-preserved
GIVEN the user changes only `change-implementor`'s Claude model
WHEN the wizard exits and writes the override store
THEN the persisted file contains only the changed agent and only the
changed field
AND no default values for unmodified agents are written.

#### Scenario: writer-functions-untouched
GIVEN the alignment refactor is applied
WHEN `src/ai_harness/modules/wizard/pure.py` and `tui.py` are
inspected
THEN `write_override_store`, `build_override_payload`, and
`build_opencode_override_payload` have not gained or lost lines
relating to write behaviour
AND the override-store shape they emit is byte-identical to the
pre-change shape for any given input.

### Requirement: persisted-config-shape-unchanged

The override store's persisted shape — `{agent: {model|effort:
{claude|opencode: value}}}` — MUST be preserved. The semantic that
`effort = None` means "(unset)" MUST be preserved. No `(unset)`
placeholder text MUST leak into the persisted file.

#### Scenario: persisted-shape-byte-identical
GIVEN a representative `selections` dict
WHEN the wizard writes the override store
THEN the on-disk JSON shape is byte-identical to what the pre-change
code would have produced for the same `selections`.

#### Scenario: none-means-unset
GIVEN an agent with effort `None`
WHEN the override store is written
THEN that agent's effort value is encoded as `None` / omitted exactly
as before
AND no `(unset)` placeholder text leaks into the persisted file.

### Requirement: format-selection-label-is-single-source-of-truth

No call site is allowed to re-implement the `(unset)` / `(NA)` /
bare-value decision locally. Every consumer of the right column MUST
obtain it from `format_selection_label`. The helper does NOT
normalise, lowercase, or coalesce the right column — the placeholders
reach the screen verbatim.

#### Scenario: no-local-three-branch
GIVEN any call site that needs to render `model / effort` text
WHEN that call site is inspected
THEN it calls `format_selection_label(...)` to obtain the right
column
AND it does NOT compute the placeholder via local `if effort is None:
"..."` branching.

#### Scenario: effort-phase-right-column-reaches-screen-verbatim
GIVEN `format_selection_label` returns `"opus / (unset)"` for an
agent
WHEN that string is passed to `align_label_rows` and assigned to a
`questionary.Choice.title`
THEN the title contains the substring `"/ (unset)"` verbatim.

### Requirement: confirm-panel-na-suppression-constant

`build_confirmation_rows` MUST continue to pass
`has_effort_support=True` as a constant to
`format_selection_label`. The confirm panel never renders `(NA)` —
already locked by
`test_build_confirmation_rows_never_renders_na_on_confirm_panel`.
The alignment refactor MUST NOT relax this constant.

#### Scenario: confirm-never-renders-na
GIVEN `selections` contains agents whose underlying models would
otherwise be flagged as non-reasoning
WHEN `build_confirmation_rows(selections)` is called
THEN no label contains the substring `"(NA)"`
AND the `has_effort_support=True` constant is the only value passed
internally (regardless of any per-agent reasoning flag the user
supplied in `selections`).

### Requirement: row-order-preservation-end-to-end

The agent rows in the model chooser, the effort chooser, and the
confirmation panel MUST appear in the same order as the caller-
supplied agent list (`claude_wizard_agents()` for Claude,
`opencode_change_agents()` for OpenCode, `selections.items()`
insertion order for the confirm panel). `align_label_rows` MUST NOT
reorder. The user's mental model of "first row in = first row shown"
MUST survive end-to-end.

#### Scenario: claude-order
GIVEN `claude_wizard_agents()` returns `[A1, A2, A3]` in that order
WHEN `_ask_continue_or_agent(phase=..., ...)` builds the choices
THEN the choice list's agent rows appear in order `[A1, A2, A3]`
AND `align_label_rows` was called with pairs in the same order.

#### Scenario: confirm-panel-insertion-order
GIVEN `selections` is built in the order `[A1, A2, A3]`
WHEN `build_confirmation_rows(selections)` returns
THEN the returned `PickerRow` list is `[row_A1, row_A2, row_A3]` in
that order.

### Requirement: rich-panel-and-questionary-consume-raw-labels

Rich `Panel` and questionary MUST consume the raw padded labels
returned by the helper without reformatting. Trailing spaces from
`align_label_rows` MUST survive the round-trip into the panel body
and the choice titles. Whether the **terminal** visually preserves
them is out of scope (Rich preserves; some terminals collapse — the
contract is on raw labels, not rendered output).

#### Scenario: no-strip-in-panel-body-construction
GIVEN `build_confirmation_rows(selections)` returns rows whose labels
end with trailing-space right padding
WHEN `_ask_confirm(title, selections)` builds the panel body
THEN no `.strip()`, `.rstrip()`, or `.lstrip()` is called on
`row.label` between the helper output and the panel body
AND the trailing spaces are still present in the body string.

#### Scenario: questionary-choice-title-stays-padded
GIVEN `align_label_rows` returns a title ending with trailing spaces
WHEN that title is assigned to `questionary.Choice(title=...)`
THEN `Choice.title` still ends with the trailing spaces
AND `Choice.value` is the bare agent name (unpadded).

### Requirement: wizard-structural-flow-unchanged

The `_drive_phases` loop, `_print_header`, keybinding helpers,
`run_wizard_or_bail` TTY/binary guards, and the phase order (model →
effort → confirm) MUST be unchanged. The alignment refactor MUST NOT
alter which phases run, in which order, or under which guards.

#### Scenario: phase-order-preserved
GIVEN the wizard runs end-to-end
WHEN the phases execute
THEN the order is `model` → `effort` → confirm
AND each phase's structural behaviour (calls, returns, prompts) is
unchanged.

#### Scenario: tty-binary-guards-preserved
GIVEN the wizard runs in a non-TTY or pipe context
WHEN `run_wizard_or_bail` is invoked
THEN the bail behaviour is identical to the pre-change behaviour.

### Requirement: navigation-choices-not-padded-by-helper

The `← Back`, `Separator`, and `Continue` choices MUST be appended
around the aligned agent rows but MUST NOT themselves be passed
through `align_label_rows`. They keep their own titles and values.
Their presence in the choice list MUST NOT change the equal-`len()`
invariant on agent rows — only the agent rows are aligned.

#### Scenario: navigation-rows-have-distinct-titles
GIVEN any phase's choice list is built
WHEN the list is inspected
THEN the agent rows have aligned titles with equal `len()`
AND the `← Back`, `Separator`, and `Continue` rows retain their
original titles and are not padded to match the agent rows.

---

## Test coverage checklist

This is the consolidated TDD checklist for the implementor. Every
test below MUST land in `tests/test_set_models.py`. Tests are grouped
into **NEW** (helper-direct tests against `align_label_rows`) and
**MODIFIED** (existing tests whose expected strings change to lock the
new aligned shape). One-line lock target per test.

### NEW — direct `align_label_rows` tests

- `test_align_label_rows_default_separator_and_signature` — locks the signature (`Sequence[tuple[str, str]]`, keyword-only `separator`, default `" - "`).
- `test_align_label_rows_pairs_are_opaque` — locks that the helper does not re-split or normalise inputs containing `/`, `-`, `:`.
- `test_align_label_rows_equal_raw_len_across_rows` — locks the equal-raw-`len()` invariant for mixed-width input.
- `test_align_label_rows_equal_widths_passthrough` — locks that uniform-width input gets no extra padding.
- `test_align_label_rows_separator_at_same_column` — locks the separator column index = `left_width` for every label.
- `test_align_label_rows_trailing_space_padding_for_shorter_right` — locks that shorter right values are right-padded (verified via `repr`).
- `test_align_label_rows_padding_survives_round_trip` — locks that padding survives assignment to `questionary.Choice.title` and back.
- `test_align_label_rows_preserves_input_order` — locks output index N = input index N for shuffled input.
- `test_align_label_rows_empty_input_returns_empty_list` — locks `[]` → `[]` without exception.
- `test_align_label_rows_single_row_uses_self_as_max` — locks that one pair returns one label with `len(left) + len(" - ") + len(right)`.
- `test_align_label_rows_opencode_long_ids_set_wider_right` — locks that mixing short Claude aliases and long OpenCode IDs drives `right_width` to the long ID.
- `test_align_label_rows_unset_placeholder_verbatim` — locks that `(unset)` reaches the output unchanged.
- `test_align_label_rows_na_placeholder_verbatim` — locks that `(NA)` reaches the output unchanged.
- `test_align_label_rows_custom_separator_kwarg` — locks `separator=" | "` produces `" | "`-separated labels with equal `len()`.
- `test_align_label_rows_default_separator_is_dash` — locks that the default separator (kwarg omitted) is `" - "`.

### NEW — narrowed `format_selection_label` tests

- `test_format_selection_label_supported_model_with_effort` — locks `"opus / high"` for supported + set.
- `test_format_selection_label_supported_model_no_effort_emits_unset` — locks `"opus / (unset)"` for supported + `None`.
- `test_format_selection_label_unsupported_model_no_effort_emits_na` — locks `"opus / (NA)"` for unsupported + `None` (not `(unset)`).
- `test_format_selection_label_unsupported_model_ignores_effort_value` — locks that `"high"` does NOT appear in the `(NA)` output.
- `test_format_selection_label_empty_model_does_not_raise` — locks that `model=""` does not raise.
- `test_format_selection_label_no_agent_prefix_in_output` — locks that the agent name does NOT appear in the returned string.
- `test_format_selection_label_no_agent_prefix_on_na_branch` — locks no agent prefix on the `(NA)` branch with a long OpenCode ID.
- `test_format_selection_label_effort_phase_and_confirm_panel_match_for_none_effort` — locks right-column byte-identity between effort phase and confirm panel for `effort=None`.
- `test_format_selection_label_effort_phase_and_confirm_panel_match_for_set_effort` — locks right-column byte-identity between effort phase and confirm panel for `effort="high"`.
- `test_format_selection_label_unset_case_preserved` — locks that `(unset)` is lowercase verbatim.
- `test_format_selection_label_na_case_preserved` — locks that `(NA)` is uppercase verbatim.

### MODIFIED — Claude call-site tests

- `test_ask_continue_or_agent_uses_dash_label_format` (~1433): assert each agent-row title is one of the strings from `align_label_rows`, all titles have equal `len()`, the `"(current: ")` negative assertion still holds.
- `test_ask_continue_or_agent_effort_phase_no_agent_dash_agent_substring` (~4090): lock against the new forbidden substring `f"{agent} - {agent} -"`. Verbatim-consumption assertion updates to the new shape.

### MODIFIED — OpenCode call-site tests

- `test_ask_opencode_continue_or_agent_uses_dash_label_format` (~1458): same updates as the Claude test, plus assert the right column width is driven by the longest OpenCode `provider/model` ID.
- `test_ask_opencode_continue_or_agent_effort_phase_no_agent_dash_agent_substring` (~4139): same forbidden-substring update as the Claude test.

### MODIFIED — confirmation-panel tests

- `test_build_confirmation_rows_unset_effort_renders_unset_placeholder` (~1754): expected label is the new aligned form, right column ends with `"/ (unset)"`.
- `test_build_confirmation_rows_set_effort_renders_effort_value` (~1771): expected label ends with `"/ high"`.
- `test_build_confirmation_rows_never_renders_na_on_confirm_panel` (~1791): unchanged in shape; the negative `(NA)` assertion stays and the `has_effort_support=True` constant stays.
- Add **equal-`len()`** assertion across multi-row `build_confirmation_rows` outputs.

### MODIFIED — effort-phase context parity tests

- Effort-phase context parity tests at ~3829, ~3872, ~3912, ~3960, ~4008: update literal title assertions from `"change-implementor: sonnet / (unset)"` to the new aligned form `"change-implementor - sonnet / (unset)"`. The mixed-agent test gains an equal-`len()` assertion across its titles.
- `test_run_claude_wizard_effort_phase_never_shows_na` (~3872): negative `(NA)` assertion stays; format context updates to ` - ` from `:`.

### UNCHANGED — write-path / structural tests

These tests assert on persisted override-store content and wizard structural behaviour, NOT on label text. They MUST continue to pass unmodified:

- `test_run_opencode_wizard_no_changes_does_not_create_override_file`
- `test_run_opencode_wizard_non_reasoning_model_skips_effort_prompt`
- All `write_override_store`, `build_override_payload`, `build_opencode_override_payload` direct tests
- All `Nav.BACK` / `Nav.CONTINUE` / `Nav.ESC_BACK` sentinel tests
- `_drive_phases` loop, `_print_header`, `run_wizard_or_bail` TTY/binary guard tests

### Test-surface rules (binding for both NEW and MODIFIED)

- Tests that assert on label text MUST NOT rely on `.strip()`, `.rstrip()`, or any whitespace-collapsing normalisation between the helper output and the equality check. Trailing-space assertions MUST use `len(label)` directly or `repr(label)`.
- Tests MUST NOT capture `Console.print` output and assert on its visible character sequence. The contract is on raw labels (`PickerRow.label`, `Choice.title`), not on rendered output.

## Result

```result
status:    done
artifacts: .ai-harness/changes/set-models-align/specs/alignment.md
skills:    none
```