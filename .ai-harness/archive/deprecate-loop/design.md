# Design — deprecate-loop

## Context

The loop agent set (loop-orchestrator, explorer, implementor, validator) has been superseded by the
change-orchestrator workflow. The harness currently maintains two parallel agent sets — loop and
change — across resources, metadata, wizard vocabulary, CLI options, and tests. This change removes
the loop set entirely so operators and tests interact exclusively with the change agent set.

The removal is ~1000 LOC dominated by deletions, but it crosses four distinct module seams. Getting
the seam contracts wrong here means misleading names survive (a function called
`_discover_loop_agents` that discovers change agents), a single-member enum gets deleted and
validation disappears, or file-count baselines drift silently in tests. Deep-module discipline
demands each seam be explicit about what it hides and why the surviving interface is the minimum
the caller needs.

---

## Deep modules

### Wizard Vocabulary (`src/ai_harness/modules/wizard/pure.py`)

- **Seam:** `pure.py` is the single source of truth for wizard vocabulary: valid agent modes, the
  fixed agent sets, and picker-row builders. No other file may define what `-a/--agent` accepts or
  which agents the wizards manage. The TUI and command layer consume; they never re-derive vocabulary.

- **Interface (after change):**
  - `AgentMode` — single-member `StrEnum`: `CHANGE = "change"`. `LOOP` member deleted.
  - `parse_agent_mode(raw: str) -> AgentMode` — strict-lowercase parse; raises `ValueError` with
    `"valid values: change."` when `raw` is not `"change"`. Callers surface the error as
    `typer.BadParameter`. The valid-set string is derived from `AgentMode` members so the error
    stays accurate automatically.
  - `CLAUDE_WIZARD_AGENTS: tuple[str, ...]` — expands from 3 (loop subagents) to 9: the 8 change
    subagents plus `change-orchestrator`. Covers all agents the Claude install manages. The
    orchestrator is included even though its model override is not rendered (the skill renderer
    ignores overrides by design); the wizard presents all 9 for a uniform UX.
  - `claude_wizard_agents() -> tuple[str, ...]` — accessor; unchanged shape.
  - `OPENCODE_CHANGE_AGENTS` / `opencode_change_agents()` — unchanged; already carries all 9
    change agents with the orchestrator first.
  - **Deleted:** `OPENCODE_WIZARD_AGENTS` constant and `opencode_wizard_agents()` function (the
    4-item loop agent tuple and its accessor).

- **Hides:** The string set that constitutes valid `-a` values; the 9 change agent names; the
  ordering of agents in each wizard; the distinction between "the wizard manages this agent" and
  "the renderer can configure this agent's model" (the latter is a renderer concern, not a
  vocabulary concern).

- **Depth note:** Deleting `AgentMode` entirely would force `set_models.py` and `tui.py` to do
  inline string comparison and duplicate error message wording. The single-member enum costs
  nothing but preserves the validated parse seam; callers see a typed `AgentMode.CHANGE` not a
  raw string. The deletion test passes: removing this module forces callers to re-implement
  validation and the agent-name registry — genuine complexity concentration.

---

### Agent Renderer (`src/ai_harness/modules/harness/renderers.py`)

- **Seam:** The renderer owns all knowledge of which resource directories exist, which agents are
  available, and how to render a template into a CLI-native file. Nothing outside this module
  enumerates agent names from the filesystem.

- **Interface (after change):**
  - `_AGENT_RESOURCE_DIRS: tuple[str, ...]` — shrinks from `("loop-agent", "change-agent")` to
    `("change-agent",)` only.
  - `_AGENT_META: dict[str, dict]` — loses 4 loop entries: `"explorer"`, `"implementor"`,
    `"validator"`, `"loop-orchestrator"`. Retains all 9 change agent entries unchanged. Any call to
    `get_agent_meta("explorer")` now raises `ValueError("Unknown agent template: 'explorer'")`.
  - `_discover_agents() -> list[str]` — **renamed** from `_discover_loop_agents`. The new name
    reflects what the function actually does: discover all agents in the configured resource
    directories. No functional change; semantics are identical, only the name changes. All internal
    call sites in this file and the one named import in `tests/test_renderers.py` (line 22) must
    be updated atomically.
  - `render_agents` public docstring — "loop agents" replaced by "change agents". Public signature
    unchanged.
  - All private render-function docstrings that say "loop agent" — updated to "change agent".

- **Hides:** The filesystem layout of resource directories; YAML frontmatter construction; the
  skill-vs-subagent mode dispatch; the override store resolution path; deep-merge semantics.

- **Depth note:** The rename from `_discover_loop_agents` to `_discover_agents` is mandatory.
  Leaving a function named `_discover_loop_agents` that discovers change agents violates the
  no-misleading-names rule in CODING_STANDARDS.md and leaves a ticking grep hazard. The function
  is private (only callers are internal and one test import), so the rename is a contained edit
  with no interface surface change beyond updating those two import sites.

---

### set-models Command (`src/ai_harness/commands/set_models.py`)

- **Seam:** The command is the Typer edge. It owns argument parsing and dispatch only; no business
  logic beyond parsing and `BadParameter` wrapping.

- **Interface (after change):**
  - `-a/--agent` default changes from `"loop"` to `"change"`.
  - Help text: removes `"'loop' for the four loop agents,"` phrasing; new text names only `change`
    as the valid value for OpenCode.
  - `parse_agent_mode(agent)` is called before dispatch; a `"loop"` input raises `ValueError`
    which the command wraps in `typer.BadParameter`. No additional catch block needed — the existing
    error-surfacing path handles any `ValueError` from `parse_agent_mode`.
  - Docstring: removes `"loop for the four loop agents"` sentence; retains the `change` description.

- **Hides:** Nothing new; this is a thin adapter throughout. The change is vocabulary-only.

- **Depth note:** Keeping `-a/--agent` as an explicit CLI option (rather than removing it since
  there is now only one valid value) preserves forward compatibility for a future third agent set.
  The cost is one optional flag with a clear error. The `typer.BadParameter` path on `"loop"` makes
  the migration self-documenting: users who muscle-memory `set-models -a loop` get an immediate
  error with guidance.

---

### Wizard TUI (`src/ai_harness/modules/wizard/tui.py`)

- **Seam:** The TUI is the interactive shell that orchestrates wizard sessions. It is intentionally
  untested (questionary requires a real TTY); correctness is validated transitively through the pure
  helpers it calls.

- **Interface (after change):**
  - Remove `opencode_wizard_agents` from imports (function deleted from `pure.py`).
  - `run_wizard(cli, agent_mode, home)` default for `agent_mode`: `AgentMode.LOOP` → `AgentMode.CHANGE`.
  - `run_claude_wizard(home, agent_mode)` default: same change.
  - `run_wizard_or_bail(cli, agent_mode, home)` default: same change.
  - The `if agent_mode == AgentMode.LOOP` branch inside `run_wizard` is deleted. The dispatch
    collapses to an unconditional call to `opencode_change_agents()`. The single remaining
    `if agent_mode == AgentMode.CHANGE` block can be kept or flattened to unconditional — either
    is correct since `AgentMode` has exactly one member.
  - Docstrings and inline comments that say "loop agents" updated to "change agents".
  - Comment claiming "Claude wizard ignores agent_mode" remains accurate but the rationale
    simplifies: with one mode, the note becomes "the Claude wizard always presents all change
    agents regardless of the agent_mode parameter."

- **Hides:** Questionary I/O calls; re-render triggers; Ctrl+C → no-op translation.

- **Depth note:** The TUI is a shallow adapter by design. The dispatch simplification (removing the
  loop branch) reduces complexity — after this change, `run_wizard` has no conditional logic on
  `agent_mode` at all (or a trivially true condition). Flattening to unconditional is preferred
  if it removes dead code; retaining the condition with a single `AgentMode.CHANGE` branch is also
  acceptable if `to-issues` slices this file as one task.

---

### ADR Deprecation Headers

- **Seam:** Each of `docs/adr/0003-loop-pr-prd-linking.md`, `0007-loop-worktree-isolation.md`, and
  `0008-copilot-loop-agents-native-model.md` receives a one-line superseded notice at the very top
  of the file (above the `# NNNN.` heading), not as a frontmatter field.

- **Interface:** The header format is:
  ```
  > **Superseded** — the loop agent set was removed in the `deprecate-loop` change.
  > This ADR is retained as a historical decision record.
  ```
  No other content changes. The ADR bodies remain in present tense to preserve historical accuracy.

- **Hides:** Nothing — this is a documentation-only change. No code reads these files at runtime.

- **Depth note:** Deletion would destroy the decision record for why loop PRD linking, worktree
  isolation, and copilot native-model choices were made. A deprecation header is the minimum signal
  that these decisions are no longer operative without erasing the rationale.

---

## Internal collaborators

The following modules are **not test seams** — they are covered transitively through the public
seams above and must never be mocked directly in tests:

- `_agent_resource_dirs()` — internal helper called by `_discover_agents()`. It reads
  `_AGENT_RESOURCE_DIRS` and filters to existing directories. After the change, it returns one
  entry (the `change-agent` dir). Tested transitively through `render_agents` and `_discover_agents`.
- `_agent_template_files(root)` — returns sorted visible `.md` files from a resource root. No
  change needed; covered transitively through `_discover_agents`.
- `_deep_merge(base, override)` — pure dict merge. Unchanged. Tested transitively through
  `get_agent_meta` and `write_override_store`.
- `_load_override_store(home)` — reads `~/.ai-harness/overrides.json`. Unchanged. Covered
  transitively through `render_agents` and `get_agent_meta` in `test_renderers.py`.

---

## Seam map

```
set_models.py (Typer edge)
    │ parse_agent_mode(raw) → AgentMode        ← pure.py
    │ run_wizard_or_bail(cli, agent_mode, home) ← tui.py
    ↓
tui.py (interactive shell)
    │ claude_wizard_agents() → tuple[str,...]  ← pure.py
    │ opencode_change_agents() → tuple[str,..] ← pure.py
    │ re_render_for_agent_clis(...)            ← operations.py
    │ write_override_store(home, payload)      ← renderers.py
    ↓
renderers.py (render engine)
    │ _discover_agents() → list[str]           ← internal (private)
    │ _AGENT_META                              ← internal (constant, 9 change entries only)
    │ _AGENT_RESOURCE_DIRS = ("change-agent",) ← internal (constant)
    ↓
resources/change-agent/*.md  (template files — filesystem)
```

Cross-cutting: `pure.py` is consumed by both `set_models.py` (parse seam) and `tui.py` (agent
list seam) but has no dependency on anything in this map — it is a pure data module.

---

## Rejected alternatives

### Alternative 1: Delete `AgentMode` entirely (bare string in the command)

Removing the enum and inlining `if agent == "change"` in `set_models.py` eliminates one file's
worth of enum machinery. Rejected because it scatters the valid-value definition: `set_models.py`
would own the string `"change"`, `tui.py` would compare against it, and the error message wording
would duplicate across callers. A single-member `StrEnum` costs two lines and buys a typed,
self-describing parse seam. The deletion test: deleting `AgentMode` forces each caller to re-derive
validation — the complexity concentrates in the enum.

### Alternative 2: Keep `opencode_wizard_agents()` as an alias for `opencode_change_agents()`

Preserving the old function name as a shim would avoid updating `~12-15` call sites in
`test_set_models.py`. Rejected because it leaves a misleading name (`opencode_wizard_agents`
suggesting loop agents) in the vocabulary module — exactly the kind of shallow alias the
CODING_STANDARDS forbids. The call-site updates in the test file are mechanical and caught by
`grep opencode_wizard_agents` during validation.

### Alternative 3: Exclude `change-orchestrator` from `CLAUDE_WIZARD_AGENTS` (8 agents)

The existing rationale for excluding the orchestrator from `CLAUDE_WIZARD_AGENTS` ("it renders as a
skill; model/effort overrides are ignored") would keep the constant at 8. Rejected because the PRD
explicitly specifies 9 agents and `C-3` requires the wizard to present all 9. The orchestrator's
model override being ignored by `_render_claude_skill` is a renderer concern, not a vocabulary
concern. The wizard's UX is more consistent when it manages the same 9-agent set regardless of
which install surface the user targets. Any stored override for `change-orchestrator` on Claude is
a benign no-op.

### Alternative 4: Rename `_discover_loop_agents` without updating the test import first

A sequential implementation that renames in `renderers.py` before fixing `tests/test_renderers.py`
line 22 would cause the entire test module to fail at collection time (import error). Rejected as
an implementation order risk, not a design alternative. The design mandates that the rename and
the test import fix are part of the same atomic task.
