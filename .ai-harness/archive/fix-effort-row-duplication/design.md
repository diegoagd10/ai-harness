# Design — fix-effort-row-duplication

## Context

The set-models wizard renders an agent chooser twice — once on the
**model phase** and once on the **effort phase** — using the same two
prompt functions (`_ask_continue_or_agent` and
`_ask_opencode_continue_or_agent`). Each row shows the agent plus the
current selection so the user can confirm what they just chose before
moving on. On the model phase the call site passes a bare model string
(`"opus"`, `"openai/gpt-5.5"`), so the row reads `agent - model` —
correct. On the effort phase the call site now passes a pre-rendered
`agent: model / <state>` line produced by `format_selection_label`, so
the same assembly renders `agent - agent: model / <state>` — the
user-reported duplication.

The PRD narrows the work to a single seam: the title construction
inside the two prompt functions. The bug is fully described by the
two call sites and the two existing prompt functions; the
`format_selection_label` contract from the previous change
(`improve-set-models-effort-context`) is the source of truth and stays
unchanged. Budget is ~35 LOC.

## Deep modules

### Prompt-adapter title construction (the seam)

- **Seam**: the comprehension that builds the per-agent `Choice.title`
  inside `_ask_continue_or_agent` (Claude) and
  `_ask_opencode_continue_or_agent` (OpenCode), in
  `src/ai_harness/modules/wizard/tui.py` at the existing `choices.extend(...)`
  call (Claude line 545, OpenCode line 838).
- **Interface**: a per-phase title contract on `selections[agent]`:
  - **Model phase** (`phase == "model"`): caller passes a bare model
    string (Claude alias or OpenCode `provider/model` id). The prompt
    function composes `title = f"{agent} - {selections.get(agent, default)}"`.
    Default is `"sonnet"` (Claude) or `"(unset)"` (OpenCode).
  - **Effort phase** (`phase == "effort"`): caller passes a value
    already rendered by `format_selection_label`, which is
    `agent: model / <state>`. The prompt function uses the value
    verbatim — no `agent - ` prefix — because the prefix is already
    present. The default fallback is dead code on the effort phase
    (the call site iterates over the same dict it filled) but stays as
    `"(unset)"` so a future call site that forgets to fill the dict
    still gets a sensible placeholder.
  - The docstring on each prompt function explicitly names this
    per-phase contract so a future caller cannot silently re-introduce
    the duplication by passing the wrong shape of label to the wrong
    phase.
- **Hides**: the per-phase branching logic. The two call sites stay
  unchanged (they already pass the right shape for their phase). The
  `format_selection_label` formatter stays unchanged (it is the source
  of truth for the effort-phase label wording). The model-phase
  `agent - {value}` shape is preserved by branch, not by accident.
- **Depth note**: this is the load-bearing seam of the change. The
  fix is one-line-per-function — a phase branch in the title
  comprehension — but the contract it documents is what stops the
  bug from coming back through a unifying refactor. Deletion test: if
  the phase branch were removed, the duplication returns. Earning its
  keep.

## Internal collaborators

- **`format_selection_label(agent, model, effort, has_effort_support)`**
  in `pure.py` — the formatter that produces the effort-phase label
  (`agent: model / <state>`). Untouched by this change. Tested
  transitively through the new effort-phase tests that assert its
  output is rendered verbatim.
- **The model-phase call sites** (`run_claude_wizard` /
  `run_opencode_wizard`, in the `run_model_phase` closures) — pass a
  bare model string into `selections`; the prompt function prefixes
  it. Untouched. Tested transitively by the existing
  `test_ask_continue_or_agent_uses_dash_label_format` /
  `test_ask_opencode_continue_or_agent_uses_dash_label_format` tests,
  which already assert `agent - model` titles.
- **The effort-phase call sites** (the `run_effort_phase` closures) —
  pre-render `display` via `format_selection_label` and pass it into
  the prompt function. Untouched. Tested transitively by the four
  effort-phase tests that get their assertion strings updated below.

## Seam map

```
run_*_wizard.run_model_phase
        │   selections: {agent: bare_model_string}
        ▼
[prompt] _ask_*_continue_or_agent(phase="model", selections)
        │   branch: model phase → f"{agent} - {selections[agent]}"
        ▼
questionary.Choice(title="agent - model")

run_*_wizard.run_effort_phase
        │   display: {agent: format_selection_label(...) }   # already starts with "agent: "
        ▼
[prompt] _ask_*_continue_or_agent(phase="effort", display)
        │   branch: effort phase → selections[agent] verbatim
        ▼
questionary.Choice(title="agent: model / <state>")
```

One seam, two branches, two call sites. No new module boundaries.

## Rejected alternatives

- **Unify the title assembly behind a helper that always prefixes.**
  Would re-introduce the bug on the effort phase the moment a future
  caller passes a pre-rendered label. The branch is what makes the
  contract explicit; collapsing it into a single shape would mean the
  phase contract lives only in the caller's head.
- **Stop pre-rendering on the effort phase call site and pass the
  raw `model`/`effort` tuple instead.** Would push the
  `format_selection_label` knowledge into the prompt function,
  inverting the seam: the prompt function would now need to know
  about `(NA)` / `(unset)` / reasoning-gating, which it currently
  delegates entirely to the pure layer. The duplication fix is
  cheaper at the title-assembly seam, not at the call-site seam.
- **Add a third phase label type and a tagged value in `selections`.**
  More machinery than the bug warrants and changes the call-site
  signature for both wizards. A boolean phase branch in the prompt
  function is the smallest change that makes the contract load-bearing.
- **Drop the effort-phase pre-render entirely and render the agent
  identity twice in `format_selection_label` so the prompt function
  can stay branchless.** The confirm panel also consumes
  `format_selection_label` and must keep the `agent: model / <state>`
  shape with one agent prefix; double-rendering would propagate the
  duplication to the confirm panel. Out of scope.
