# Design — set-models-align

## Context

The `ai-harness set-models` wizard prints three visible row blocks — the
model chooser, the effort chooser, and the confirmation panel — each of
which today renders the per-agent row with an ad-hoc f-string. The
separator column (`-` for the model chooser, `:` for the effort and
confirm panels) drifts with the longest agent name on each row, and the
right edge drifts with the longest value on each row. The user sees
staggered columns and ragged right edges, which makes the wizard hard
to scan. The change must fix that *visually only*: write paths,
navigation, prompt semantics, and persisted config are not in scope.

The deep-module question is **where the alignment lives**. It is a
rendering concern (it depends on the visible row set), so it must cross
the pure / TUI seam exactly once and be consumed by all three blocks
through one helper. The semantic decisions underneath the alignment
— which agent, which model, whether the effort is `(unset)`,
`(NA)`, or a set value — must keep their single source of truth
(`format_selection_label`) and not be re-derived at the call sites.

## Deep modules

### `wizard.pure` (modified)

The pure data-prep layer gains **one new public seam** and changes the
shape of two existing seams so the alignment helper can wrap them.

#### `align_label_rows` (new seam — load-bearing)

- **Seam**: `src/ai_harness/modules/wizard/pure.py`, sibling of
  `format_selection_label` and `build_confirmation_rows`.
- **Interface**:

  ```python
  def align_label_rows(
      pairs: Sequence[tuple[str, str]],
      *,
      separator: str = " - ",
  ) -> list[str]:
  ```

  Input: an ordered sequence of `(left, right)` pairs representing the
  visible row set. The pairs are **opaque strings** to the helper — it
  never inspects, normalises, or re-splits them.

  Output: a list of label strings, one per input pair, in the same
  order. Every returned string has the form
  ``f"{left:<left_width}{separator}{right:<right_width}"`` where:

  - ``left_width  = max(len(left)  for left, _ in pairs)``
  - ``right_width = max(len(right) for _, right in pairs)``

  Invariants the helper **MUST** guarantee:

  1. **Determinism**: same input → same output, byte-for-byte.
  2. **Equal raw `len()`**: every returned label has the same raw
     `len()` — that length is ``left_width + len(separator) + right_width``.
  3. **Separator column consistency**: the separator starts at column
     ``left_width`` in every label.
  4. **Trailing-space right padding**: shorter right values are
     right-padded with spaces (`f"{right:<right_width}"`) so the row's
     right edge aligns. Trailing spaces are **intentional** and must
     survive round-trip.
  5. **Order preservation**: output list index N corresponds to input
     list index N. The helper does not reorder.
  6. **Empty input**: returns `[]`. No crash.
  7. **Single-row input**: still applies padding (the row is its own
     max). Useful for the confirm panel where the visible row set is
     the full `selections` dict.

- **Hides**:
  - The width-max reduction over the visible row set.
  - The f-string composition and Python `<{width}` padding semantics.
  - The decision that widths are computed per-call (not memoised, not
    cached, not keyed on a global). Per-call is correct because the
    visible row set changes between model / effort / confirm phases
    (and between Claude / OpenCode).
  - The decision that trailing spaces are kept verbatim — no strip on
    output.
- **Depth note**: the helper's interface is small (one function, one
  input list, one output list) and the implementation is dense — it
  eliminates an entire class of "did we forget to pad the shorter
  rows?" bugs that currently scatter across `tui.py` and `pure.py`.
  Deleting it would re-spread that bug surface across three call sites.
  This is the load-bearing seam: `to-issues` slices *inside* it
  (test surface) but cannot slice *across* it without breaking the
  "all three blocks share one formatter" invariant.

#### `format_selection_label` (modified seam — semantic meaning preserved, output shape narrows)

- **Seam**: `src/ai_harness/modules/wizard/pure.py` (existing).
- **Interface (shape change)**:

  ```python
  def format_selection_label(
      agent: str,
      model: str,
      effort: str | None,
      has_effort_support: bool,
  ) -> str:
  ```

  Today it returns one of three full strings —
  `"{agent}: {model} / {effort}"`,
  `"{agent}: {model} / (unset)"`,
  `"{agent}: {model} / (NA)"`.

  After this change it returns one of three **right-column-only**
  strings:

  - `"{model} / {effort}"`   (effort set, supported)
  - `"{model} / (unset)"`    (effort `None`, supported)
  - `"{model} / (NA)"`       (not supported)

  The function still owns the three-branch decision (which placeholder,
  whether to drop the effort value). The agent name is no longer its
  concern; the alignment helper wraps the agent name around whatever
  this returns.

- **Hides**:
  - The mapping from `(effort, has_effort_support)` to placeholder
    text — that mapping is the function's semantic job and stays
    internal.
- **Depth note**: narrowing the output from "agent-prefixed label" to
  "right column content" is what makes the alignment helper's input
  homogeneous. Every call site (effort phase, confirm panel) passes the
  same shape — a single right-column string — and the alignment helper
  wraps it. Without this narrowing, the alignment helper would need to
  know how to strip the agent prefix it once added, which inverts the
  data flow and forces the alignment helper to leak semantic
  knowledge. Deleting the narrowing would force one of the call sites
  to re-implement the three-branch decision; that is the god-object
  smell the deletion test catches.

#### `build_confirmation_rows` (modified seam — internal delegation)

- **Seam**: `src/ai_harness/modules/wizard/pure.py` (existing).
- **Interface**: signature unchanged — `(selections: dict[str, ModelSelection]) -> list[PickerRow]`.
- **What changes internally**: instead of returning
  `PickerRow(value=agent, label=format_selection_label(...))` per
  row, it now:

  1. Builds the right column for every agent via
     `format_selection_label(..., has_effort_support=True)`.
  2. Calls `align_label_rows([(agent, right) for agent, right in ...])`
     on the **full visible row set** (one call, dynamic widths).
  3. Returns `PickerRow(value=agent, label=aligned_label)` per row.

  This keeps the caller's contract (one row per agent with a label and
  a value) while letting the alignment helper compute widths once over
  the full set.

- **Hides**:
  - The order it walks `selections.items()` — Python 3.7+ insertion
    order, preserved verbatim.
  - The internal `has_effort_support=True` constant (load-bearing for
    suppressing `(NA)` on the confirm panel — already locked by
    `test_build_confirmation_rows_never_renders_na_on_confirm_panel`).
- **Depth note**: this is an **internal collaborator**, not a public
  test seam — it composes `format_selection_label` and
  `align_label_rows` and is covered transitively through the alignment
  and confirm tests. Removing this indirection (inlining the logic
  into `_ask_confirm`) would re-spread the format + align combination
  into the TUI, which is what the layering is meant to prevent.

#### Unchanged pure helpers

`build_model_picker_rows`, `build_effort_picker_rows`,
`build_opencode_*`, `parse_agent_mode`, `AgentMode`, `ModelSelection`,
`AgentCli`-shaped enums — all keep their current signatures and
semantics. The alignment helper is **not** used inside the per-agent
picker rows (the model picker and effort picker show one agent at a
time, so there is no row set to align across).

### `wizard.tui` (modified)

The TUI is the alignment helper's only consumer. Three call sites
change; everything else stays put.

#### `_ask_continue_or_agent` (Claude) — model + effort chooser

- **Seam**: `src/ai_harness/modules/wizard/tui.py` (existing).
- **What changes**: instead of building `title` per row with an f-string,
  it builds `(agent, right_text)` pairs for every agent, calls
  `align_label_rows` once, then assigns the padded titles to
  `Choice(title=aligned_title, value=agent)`.
- **Contract change** at the seam with `run_effort_phase`:
  - For `phase == "model"`: caller still passes bare model aliases
    (e.g. `"opus"`). No change.
  - For `phase == "effort"`: caller now passes the **right column
    only** (e.g. `"opus / (unset)"`), not the full
    `"agent: model / state"` line. The duplication-bug test
    (`test_ask_continue_or_agent_effort_phase_no_agent_dash_agent_substring`)
    is re-locked against the new format — no title may contain
    `"{agent} - {agent} -"` (the new duplicated-prefix shape).
- **What stays**:
  - `← Back`, `Continue`, `questionary.Separator` choices — appended
    around the aligned agent rows, not aligned.
  - `_filterable_select` kwargs (search filter, j/k, esc-back).
  - Phase-driven `_filterable_select` message.
  - Esc → BACK / ESC_BACK mapping.

#### `_ask_opencode_continue_or_agent` — model + effort chooser

- **Seam**: same module, existing function.
- **What changes**: same shape as Claude — pairs + `align_label_rows`,
  contract change for `phase == "effort"` (right column only).
- **What stays**: same invariants as Claude variant, plus the
  `(NA)` branch from the per-agent reasoning lookup.

#### `_ask_confirm` — confirmation panel

- **Seam**: same module, existing function.
- **What changes**: **almost nothing**. It already calls
  `build_confirmation_rows(selections)` and prints
  `f"  • {row.label}"`. Since `build_confirmation_rows` now returns
  aligned labels internally, the panel body automatically inherits the
  alignment. The change at the TUI layer here is a docstring update
  noting that the row labels are already padded.
- **What stays**:
  - `Rich Panel` border style, bold title prefix, blank line after
    `_print_header`.
  - The `Esc → BACK` binding on the `questionary.confirm` prompt.
  - The `True / False` → `CONFIRM / CANCEL` translation.

#### Unchanged TUI surface

All write paths (`write_override_store`, payload builders), all
`_ask_*_model` and `_ask_*_effort` per-agent pickers (single agent,
no alignment needed), `_print_header`, keybinding helpers,
`run_wizard_or_bail` TTY / binary guards, the `_drive_phases` loop —
none change. The change is purely a presentation refactor.

### `tests/test_set_models.py` (modified)

Test surface changes are listed under **Test seams** below. No new
test file; the alignment helper lives in `pure.py` and its coverage
goes alongside the existing pure-helper tests.

## Internal collaborators

The alignment is not split into multiple internal collaborators —
`align_label_rows` is the leaf. The two helpers it composes with
(`format_selection_label` for effort / confirm rows, the call site's
own right-column expression for model rows) are **not** internal
collaborators of the alignment helper; they are upstream inputs.

One internal composition is worth naming:

- **`build_confirmation_rows` ↔ `align_label_rows` + `format_selection_label`**: this composition is **internal** to `pure.py`, never mocked. It is covered transitively through the confirm-panel tests that
  assert on `PickerRow.label` and through the dedicated
  `align_label_rows` tests that lock the helper's invariants directly.

## Seam map

```
wizard.pure
├── align_label_rows(pairs) -> list[str]   [NEW — load-bearing seam]
│       consumes:  Sequence[tuple[str, str]] (opaque)
│       produces:  list[str] (equal len, separator column, order-preserving)
│
├── format_selection_label(agent, model, effort, has_effort_support) -> str   [MODIFIED]
│       consumes:  agent (str), model (str), effort (str|None), flag (bool)
│       produces:  right-column string only ("opus / (unset)", etc.)
│       NO LONGER pre-pends "{agent}: ".
│
├── build_confirmation_rows(selections) -> list[PickerRow]   [MODIFIED — internal composition]
│       builds right column via format_selection_label,
│       aligns via align_label_rows,
│       returns PickerRow(value=agent, label=aligned_label)
│
└── (all other pure helpers unchanged)

wizard.tui
├── _ask_continue_or_agent(phase, selections) -> str|None   [MODIFIED — Claude chooser]
│       for phase="model":  pairs = [(agent, selections[agent])] -> align_label_rows
│       for phase="effort": pairs = [(agent, selections[agent])] -> align_label_rows
│       Contract: selections[agent] is the RIGHT COLUMN for effort phase.
│       Appends ← Back / Separator / Continue around the aligned agent rows.
│
├── _ask_opencode_continue_or_agent(phase, selections, agents) -> str|None   [MODIFIED]
│       Same shape as Claude. selections[agent] is the RIGHT COLUMN for effort phase.
│
└── _ask_confirm(title, selections) -> str   [BODY UNCHANGED]
        Still calls build_confirmation_rows and prints row labels in a Rich Panel.
        The alignment is invisible at this layer — it already happens inside pure.

tests/test_set_models.py
    All existing exact-string assertions that lock the old ":" separator
    are updated to lock the new " - " separator AND the alignment invariants.
    New tests target align_label_rows directly.
```

The number of cross-module seams is unchanged (pure exposes to tui, tui
calls pure). The number of seams inside pure grew by exactly one
(`align_label_rows`); the alignment itself crosses the pure / tui
boundary as `Sequence[tuple[str, str]]` — opaque to the consumer, which
is what keeps the test surface narrow.

## Seam contract — what MUST NOT change

The following are load-bearing invariants for any implementation of this
design. They are the audit surface `to-issues` slices within and the
validator audits against:

1. **Back / Continue / Separator / Esc semantics**: navigation choices,
   `Nav.BACK` / `Nav.CONTINUE` / `Nav.ESC_BACK` sentinels, phase-aware
   Esc behaviour on the first phase ("model" has no predecessor; Esc is
   a no-op there). Unchanged.
2. **Write paths**: `write_override_store`, `build_override_payload`,
   `build_opencode_override_payload`, the selective-write contract
   (only fields the user changed), the no-default-pollution invariant.
   Unchanged.
3. **Persisted config**: the override store's shape
   (`{agent: {model|effort: {claude|opencode: value}}}`), the
   `None`-means-unset semantic for effort. Unchanged.
4. **`format_selection_label` semantic meaning**: the three-branch
   decision — `(unset)` for supported + `None`, `(NA)` for
   not-supported (with effort value dropped), bare value for supported
   + set. The function's *contract* (what `(unset)` / `(NA)` mean) is
   preserved; only its *output shape* narrows (no more agent prefix).
5. **Per-agent picker rows**: `_ask_claude_model`, `_ask_claude_effort`,
   `_ask_opencode_model`, `_ask_opencode_effort` — these show one agent
   at a time, no alignment. Unchanged.
6. **Order of confirmation rows**: `build_confirmation_rows` walks
   `selections.items()` in insertion order; the alignment helper does
   not reorder. The user's mental model of "first row in = first row
   shown" survives.
7. **Effort-phase row semantics**: `format_selection_label`'s three
   branches reach the screen verbatim through the alignment helper;
   the helper does not normalise, lowercase, or coalesce placeholders.
8. **Confirm panel `(NA)` suppression**: `build_confirmation_rows`
   passes `has_effort_support=True` as a constant — already locked by
   `test_build_confirmation_rows_never_renders_na_on_confirm_panel`.
   Unchanged.
9. **Rich Panel rendering**: `_ask_confirm` consumes `row.label` as a
   raw string; trailing spaces survive the round-trip into the panel
   body. Whether the *terminal* visually preserves them is out of
   scope (Rich preserves; some terminals collapse — the test surface
   targets raw labels, not rendered output).

## Data flow

Three call sites converge on `align_label_rows`. Row order is preserved
in every case.

### 1. Model chooser (Claude + OpenCode)

```
claude_wizard_agents() / opencode_change_agents()  --->  agent_list
                                                        (insertion order)

run_model_phase closure:
  selections  --->  [(agent, selections.get(agent, "sonnet"))
                     for agent in agent_list]   --->  align_label_rows
                                                        |
                                                        v
                                          questionary.Choice(title=aligned,
                                                              value=agent)
                                          [+ ← Back / Separator / Continue]
```

Row order: agent_list order → pairs list order → aligned titles order →
Choice list order. `_filterable_select` receives a list whose first
agent row matches the first agent in `claude_wizard_agents()` (or
`opencode_change_agents()`).

### 2. Effort chooser (Claude + OpenCode)

```
run_effort_phase closure:
  efforts  --->  for each agent:
                  right = format_selection_label(
                      agent,
                      models[agent],
                      efforts[agent],
                      has_effort_support=...
                                  True                    (Claude)
                                  opencode_model_is_reasoning(...)  (OpenCode)
                  )
                display = {agent: right for ...}

  display  --->  [(agent, display.get(agent, "(unset)"))
                   for agent in agent_list]   --->  align_label_rows
                                                     |
                                                     v
                                          questionary.Choice(title=aligned,
                                                              value=agent)
```

Row order: `agent_list` order. The right column for each agent is the
output of `format_selection_label` — the **only** place the three-branch
semantic decision lives. The alignment helper never inspects the
right column.

### 3. Confirmation panel (Claude + OpenCode)

```
selections (dict[agent, ModelSelection(model, effort)])  --->  build_confirmation_rows
                                                                     |
                                                                     v
                                                              for each agent:
                                                                right = format_selection_label(
                                                                    agent, model, effort,
                                                                    has_effort_support=True
                                                                )
                                                              pairs = [(agent, right) for ...]
                                                              aligned = align_label_rows(pairs)
                                                              return [PickerRow(value=agent,
                                                                                label=aligned_title)
                                                                      for ...]

rows  --->  _ask_confirm:
              body = "\n".join(f"  • {row.label}" for row in rows)
              Rich Panel(body)  --->  Console.print
```

Row order: `selections.items()` insertion order — Python 3.7+ stable,
preserved verbatim by both `build_confirmation_rows` and
`align_label_rows`.

## Rejected alternatives

### A. Hard-code widths from the current agent set

The agent names are stable today (the nine `change-*` agents), so one
could `left_width = max(len(a) for a in claude_wizard_agents())` and
hard-code `left_width = 19`. Rejected because:

- Future agent renames or additions would silently misalign until a
  developer remembers to update the constant.
- The Claude and OpenCode agent sets diverge
  (`change-orchestrator` ordering, future sub-agents) — a single
  constant would either over-pad one set or under-pad the other.
- The deletion test fails: hard-coding moves complexity (knowing which
  agent set is in scope) rather than hiding it.

Per-call dynamic widths from the visible row set is the deep answer.

### B. Single helper that decides both the semantic state and the alignment

A combined `format_aligned_row(agent, model, effort, has_effort_support, all_pairs) -> str`
that embeds the `(unset)` / `(NA)` decision inside the alignment
function. Rejected because:

- The semantic decision does not depend on the row set — it is per-row
  state, not per-call state. Coupling it to the multi-row helper would
  force every call site to pass the full pairs list even when only one
  row is being formatted.
- The single source of truth for `(unset)` / `(NA)` would no longer be
  a single function — it would be the *combination* of `format_selection_label`
  semantics + the alignment helper's padding. A future test that
  asserts "confirm panel never renders `(NA)`" would have to
  instantiate the combined helper, not call `format_selection_label`
  directly.
- The deletion test catches the god-object smell: the combined helper
  owns both "decide the placeholder" and "compute column widths" — two
  unrelated jobs.

Two helpers, two responsibilities — `format_selection_label` decides
the placeholder, `align_label_rows` decides the geometry.

### C. Pass the right column as a callable into the alignment helper

```python
align_label_rows(agents, lambda agent: format_selection_label(agent, ...))
```

Rejected because:

- Adds indirection without solving a real problem — the call sites
  already build the right column with one line each.
- Makes the alignment helper's input shape heterogeneous per call site
  (one site passes model aliases, another passes the
  `format_selection_label` output). The opaque-`Sequence[tuple[str, str]]`
  interface is uniform.
- Makes testing harder — the alignment helper tests would need to mock
  the callable, which leaks the helper's design into the test surface.

The opaque-pairs interface keeps the alignment helper's contract
simple and its test surface flat.

## Test seams

The alignment is locked by tests at three levels. The existing test
file is the only place these assertions live; no new file is added.

### Level 1 — direct `align_label_rows` tests (new)

Focused tests that lock the helper's invariants without going through
the wizard. Each is a single, narrow assertion against the helper's
output:

- **`test_align_label_rows_equal_raw_len_across_rows`**: given a
  mixed-width input (long agent, short agent; long value, short value),
  assert every returned label has the same `len()`.
- **`test_align_label_rows_separator_at_same_column`**: for the same
  input, find the index of the separator substring in every label and
  assert they are identical.
- **`test_align_label_rows_trailing_space_padding_for_shorter_right`**:
  pass `("a", "opus")` and `("a", "haiku")`; assert the first label
  ends with the spaces needed to match the second label's `len()`,
  using `repr(label)` to make trailing spaces visible.
- **`test_align_label_rows_preserves_input_order`**: shuffle input
  pairs and assert output order matches input order exactly.
- **`test_align_label_rows_empty_input_returns_empty_list`**: `[]` →
  `[]`.
- **`test_align_label_rows_single_row_uses_self_as_max`**: one pair →
  one label, no extra padding beyond the row's own width.
- **`test_align_label_rows_opencode_long_ids_set_wider_right`**: pass
  pairs mixing `("change-implementor", "opus")` and
  `("change-validator", "openai/gpt-5.5")`; assert the right column
  width is `len("openai/gpt-5.5")`, not a hard-coded constant.
- **`test_align_label_rows_placeholders_pass_through_verbatim`**:
  `(agent, "opus / (unset)")` → the right column in the output ends
  with `"/ (unset)"`; `(agent, "opus / (NA)")` → ends with `"/ (NA)"`.
- **`test_align_label_rows_custom_separator_kwarg`**: passing
  `separator=" | "` produces labels with ` | ` between columns;
  default is ` - `.

### Level 2 — call-site tests (existing, modified)

These tests already lock the model / effort / confirm shapes. They are
updated — not loosened — to lock the new aligned shape plus the
alignment invariants.

- **`test_ask_continue_or_agent_uses_dash_label_format`** (line ~1433):
  update to assert (a) the title contains the new aligned form with
  trailing-space padding, and (b) all returned titles have equal
  `len()`. The `"(current: "` negative assertion stays.
- **`test_ask_opencode_continue_or_agent_uses_dash_label_format`**
  (line ~1458): same update for the OpenCode side, including the
  long-id width case.
- **`test_build_confirmation_rows_unset_effort_renders_unset_placeholder`**,
  **`..._set_effort_renders_effort_value`**,
  **`..._never_renders_na_on_confirm_panel`** (lines ~1754–1791):
  update the literal-string assertions to the new aligned form
  (`"change-implementor - opus / (unset)"` with the right width
  computed against the visible row set). Add equal-`len()` assertions
  on the multi-row `build_confirmation_rows` outputs.
- **`test_format_selection_label_supported_model_with_effort`** and
  the other three branch tests (lines ~1801–1840): update the
  expected strings to the **right-column-only** shape
  (`"opus / high"`, `"opus / (unset)"`, `"opus / (NA)"`). The
  semantic invariants (`(NA)` ignores effort value, `None` → `(unset)`,
  supported + set → bare value) stay — they are what these tests were
  really about.
- **`test_format_selection_label_effort_phase_and_confirm_panel_match_for_none_effort`**
  and **`..._for_set_effort`** (lines ~4192–4212): update to assert
  that the effort-phase right column equals the confirm-panel right
  column (both `format_selection_label` outputs); the alignment helper
  is what unifies the *full* label on both sides, but the right-column
  parity is the underlying invariant.
- **`test_ask_continue_or_agent_effort_phase_no_agent_dash_agent_substring`**
  and **`test_ask_opencode_continue_or_agent_effort_phase_no_agent_dash_agent_substring`**
  (lines ~4090, 4139): the existing duplicate-prefix guard tests stay
  in shape — they pin against the new format
  (`"{agent} - {agent} -"` is the new forbidden substring, since the
  old `"{agent} - {agent}:"` no longer appears in any label). The
  verbatim-consumption assertion updates to the new shape: the
  caller-supplied right column appears verbatim inside the aligned
  title.
- **Effort-phase context parity tests** at lines ~3829, ~3872, ~3912,
  ~3960, ~4008: update the literal title assertions from
  `"change-implementor: sonnet / (unset)"` to the new aligned form
  `"change-implementor - sonnet / (unset)"` with the appropriate
  left-column padding. The mixed-agent test (`..._mixed_agent_set`)
  also gets an equal-`len()` assertion across its titles.
- **`test_run_claude_wizard_effort_phase_never_shows_na`** (line ~3872):
  update the negative assertion — `(NA)` still must not appear, but
  the format is now ` - ` not `:`. The branch-suppression invariant is
  what this test was really about; the format change is incidental.

### Level 3 — full-wizard tests (existing, lightly modified)

The scripted end-to-end tests (e.g. `test_run_opencode_wizard_no_changes_does_not_create_override_file`,
`test_run_opencode_wizard_non_reasoning_model_skips_effort_prompt`)
do **not** assert on label text — they assert on the override-store
content and on the wizard's structural behaviour. They are unchanged;
the alignment change does not touch write paths or navigation.

The one exception is any scripted-wizard test that inspects
`questionary.Choice.title` (e.g. the captures-based effort-phase
tests) — those are in level 2 above.

### What the test surface explicitly does NOT lock

- **Terminal rendering of trailing spaces**. Rich `Panel` and the
  user's terminal may visually collapse trailing whitespace; tests
  target raw labels (`PickerRow.label`, `Choice.title`), not rendered
  output. The acceptance criterion is "raw labels are aligned"; the
  visual scan is a downstream property.
- **Column widths across phases**. The helper computes widths per
  call; tests assert that the width is *correct for the visible row
  set*, not that it equals a specific constant. The Claude model's
  agent names are stable today, but locking a constant would regress
  if the agent set evolves.
- **Color or rich markup**. The wizard does not pass any `[...]`
  markup through the alignment helper; the helper treats its inputs
  as opaque strings. Future rich markup, if added, would be a
  separate concern.

## Affected files

- `src/ai_harness/modules/wizard/pure.py` — gain `align_label_rows`;
  narrow `format_selection_label` output; rewire
  `build_confirmation_rows` through `align_label_rows`.
- `src/ai_harness/modules/wizard/tui.py` — rewire
  `_ask_continue_or_agent` and `_ask_opencode_continue_or_agent`
  through `align_label_rows`; update the docstring of both functions
  to document the new `selections[agent]` shape for the effort phase.
- `tests/test_set_models.py` — update literal-string assertions; add
  `align_label_rows`-direct tests.

No other files change. The CLI adapter, the harness renderers, the
override-store writer, and the catalog loader are out of scope by the
PRD's "display-only" framing, and the design above respects that
boundary by routing every alignment decision through one pure seam.