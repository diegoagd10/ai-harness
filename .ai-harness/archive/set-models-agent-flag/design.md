# Design — set-models-agent-flag

## Context

Today `set-models -o opencode` configures a single fixed agent set: the four loop agents (`loop-orchestrator`, `explorer`, `implementor`, `validator`). A second fixed set already lives on disk — eight change agents (`change-orchestrator`, `change-explorer`, `change-implementor`, `change-validator`, `propose`, `design`, `specs`, `tasks`) — and the renderer already knows about them (`_discover_loop_agents()` walks both `loop-agent/` and `change-agent/` resource dirs). The wizard is the only thing that hasn't caught up. This slice closes that gap: a new `-a` / `--agent` flag lets the user pick which set to configure, the opencode wizard body is parameterised on the agent tuple, and the claude wizard ignores the flag entirely. No `renderers.py` or `operations.py` change — the renderer's seam already covers the new branch.

## Deep modules

### `AgentMode` — the flag's vocabulary type

- **Seam**: a module-level symbol exported from `modules/wizard/pure.py` (re-exported from `tui.py` alongside the existing `Nav` style) that the CLI adapter parses raw strings into before they cross the wizard boundary.
- **Interface**:
  ```python
  class AgentMode(StrEnum):
      LOOP = "loop"
      CHANGE = "change"
  ```
  Plus a tiny helper for the CLI adapter: `parse_agent_mode(raw: str) -> AgentMode` that raises `ValueError("...")` naming the valid set on any other input.
- **Hides**: the string-vs-enum decision (callers only ever see `AgentMode`); the strict-lowercase contract (the parser is the one place that knows about case sensitivity); the future-proofing for adding a third mode (one tuple append + one enum member + one parser branch).
- **Depth note**: `StrEnum` matches the existing `AgentCli` (in `harness/models.py`) and `Nav` (in `wizard/tui.py`) convention. The values compare equal to raw strings (`AgentMode.LOOP == "loop"` is `True`), so `questionary.Choice(value=...)` and any downstream string comparison keep working unchanged. Choosing `StrEnum` over `Literal["loop", "change"]` because (a) it matches the existing house style for enums, (b) it lets the CLI adapter raise a typed exception that the typer layer translates to `typer.BadParameter` without leaking the literal type to call sites, and (c) `tuple[str, ...]` agent lists handed off across module boundaries don't have to widen to `tuple[Literal["loop","change"], ...]` and back.

### `run_wizard_or_bail` — the seam between CLI adapter and wizard

- **Seam**: the function that the CLI adapter (`commands/set_models.py`) calls and that the wizard enters through.
- **Interface** (after):
  ```python
  def run_wizard_or_bail(
      cli: AgentCli,
      *,
      home: Path,
      agent_mode: AgentMode = AgentMode.LOOP,
  ) -> bool
  ```
- **Hides**: which CLI consumes the flag and which ignores it (the dispatcher body); the OpenCode binary pre-flight; the TTY pre-flight. The CLI adapter only knows "give me a cli + an agent mode + a home, get back a bool".
- **Depth note**: default `AgentMode.LOOP` preserves today's byte-for-byte behavior — every existing caller (unit tests, e2e sandbox, future commands) keeps working without changes. The `agent_mode` parameter is accepted for every `cli` so the CLI adapter's call site is uniform: it always passes the parsed value through, and the wizard's per-CLI branch decides whether to consume it. This keeps the seam's surface uniform even though only one branch reads it — a uniform surface beats a polymorphic one for a parameter this small.

### `run_wizard` — the CLI dispatcher inside the wizard

- **Seam**: internal to the wizard; not exported.
- **Interface** (after):
  ```python
  def run_wizard(
      cli: AgentCli,
      *,
      home: Path,
      agent_mode: AgentMode = AgentMode.LOOP,
  ) -> bool
  ```
- **Hides**: nothing on top of what it hides today — it still dispatches on `cli`. What changes: it forwards `agent_mode` to `run_opencode_wizard` only; the Claude path swallows it.
- **Depth note**: forwarding rather than dispatching here keeps the per-CLI wizard signatures parallel. Future CLIs that need to know the agent set (none today) read it from this layer without re-plumbing the CLI adapter.

### `run_opencode_wizard` — the deep module

- **Seam**: the opencode wizard's external surface; receives the parsed `agent_mode`.
- **Interface** (after):
  ```python
  def run_opencode_wizard(
      *,
      home: Path,
      agent_mode: AgentMode = AgentMode.LOOP,
  ) -> bool
  ```
- **Hides** (all hidden behind this one signature):
  - the agent-tuple selection (`opencode_wizard_agents()` for `LOOP`, `opencode_change_agents()` for `CHANGE`);
  - the per-agent baseline/selections dicts;
  - the model catalog join (`join_opencode_catalog`);
  - the reasoning-effort gate (`opencode_model_is_reasoning`);
  - the selective-write payload shape (`build_opencode_override_payload`);
  - the override-store write (`write_override_store`);
  - the re-render call (`re_render_for_agent_clis([AgentCli.OPENCODE])`).
- **Depth note**: the body is unchanged from today except for the agent tuple coming from `agent_mode`. The phase functions (`run_model_phase`, `run_effort_phase`, `run_confirm_phase`) read `agents` from the enclosing closure, so the change is one tuple selection at the top of the body — no per-phase branching, no duplicated phase functions, no header string duplication. The wizard's depth (one signature → one full TUI flow → consistent override store + re-render) is preserved.

### `OPENCODE_CHANGE_AGENTS` — the change-set vocabulary

- **Seam**: a frozen tuple + accessor exported from `modules/wizard/pure.py`, mirroring today's `OPENCODE_WIZARD_AGENTS` / `opencode_wizard_agents()` shape.
- **Interface**:
  ```python
  OPENCODE_CHANGE_AGENTS: tuple[str, ...] = (
      "change-orchestrator",
      "change-explorer",
      "change-implementor",
      "change-validator",
      "propose",
      "design",
      "specs",
      "tasks",
  )

  def opencode_change_agents() -> tuple[str, ...]: ...
  ```
- **Hides**: the orchestrator-first ordering (the change-orchestrator leads, like the loop-orchestrator does); the rule that names are stable strings (no aliasing); the rule that the wizard's only knowledge of the change set is the tuple.
- **Depth note**: the pure layer is the single source of truth. The renderer reads from the filesystem (`_discover_loop_agents`), the wizard reads from the tuple — they don't need to share a discoverer because the renderer is a write-path (filesystem) and the wizard is a read-path (pure data) by design. This is intentional asymmetry, not duplication.

## Internal collaborators

| Module | Role in this change | Touched? |
| --- | --- | --- |
| `commands/set_models.py` | Parses `-a` into `AgentMode` via `parse_agent_mode`, threads through to `run_wizard_or_bail`. Validates with `typer.BadParameter` naming the valid set. | Yes (~12 LOC) |
| `modules/wizard/tui.py` | Adds `AgentMode` re-export; threads `agent_mode` through `run_wizard_or_bail` → `run_wizard` → `run_opencode_wizard`. Branches the opencode agent-tuple selection; claude branch swallows the parameter. | Yes (~25 LOC) |
| `modules/wizard/pure.py` | Adds `AgentMode`, `parse_agent_mode`, `OPENCODE_CHANGE_AGENTS`, `opencode_change_agents()`. | Yes (~8 LOC) |
| `modules/harness/renderers.py` | Already walks both `loop-agent/` and `change-agent/` via `_discover_loop_agents()` — re-render scope is correct out of the box. | **No** |
| `modules/harness/operations.py` | `re_render_for_agent_clis([AgentCli.OPENCODE])` already calls `render_agents(AgentCli.OPENCODE)` which re-emits all 12 files. | **No** |
| `modules/harness/models.py` | `AgentCli` is fine as-is. | **No** |
| `tests/test_set_models.py` | New tests for pure vocab, CLI validation, claude silent-ignore, opencode `-a change` happy path, help-text pin. | Yes (~100 LOC) |
| `e2e/set_models_lifecycle.py` | One new arg-validation case for unknown `-a` value. | Yes (~5 LOC) |

## Seam map

```
┌────────────────────────────────────────────────────────────────┐
│  commands/set_models.py                                        │
│                                                                │
│  set_models(to: list[str], agent: str = "loop") ──► typer      │
│      │                                                        │
│      │ parse_agent_mode(raw)                                  │
│      ▼                                                        │
│  AgentMode.LOOP | AgentMode.CHANGE                             │
│      │                                                        │
│      ▼                                                        │
│  run_wizard_or_bail(cli, *, home, agent_mode)                  │
└──────────────────────────┬─────────────────────────────────────┘
                           │  SEAM — agent_mode consumed iff cli == OPENCODE
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  modules/wizard/tui.py                                         │
│                                                                │
│  run_wizard_or_bail ─► run_wizard ─► run_opencode_wizard       │
│                              │                                │
│                              │  (claude branch ignores        │
│                              │   agent_mode — signature-only) │
│                              ▼                                │
│  run_opencode_wizard(*, home, agent_mode)                      │
│      │                                                        │
│      │  agent_mode == LOOP   ► opencode_wizard_agents()        │
│      │  agent_mode == CHANGE ► opencode_change_agents()        │
│      ▼                                                        │
│  agents: tuple[str, ...]   (everything below is parameterized │
│                             on agents — no per-mode branches)  │
│      │                                                        │
│      ▼                                                        │
│  baseline_models/efforts ─► model phase ─► effort phase        │
│      │                                                        │
│      ▼                                                        │
│  build_opencode_override_payload ─► write_override_store       │
│      │                                                        │
│      ▼                                                        │
│  re_render_for_agent_clis([AgentCli.OPENCODE])                │
│      │                                                        │
│      │  → render_agents(AgentCli.OPENCODE)                     │
│      │    → _discover_loop_agents()                            │
│      │      → walks BOTH loop-agent/ AND change-agent/         │
│      │      → returns all 12 names                             │
│      │    → re-emits all 12 .config/opencode/agent/*.md files  │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  modules/wizard/pure.py                                        │
│                                                                │
│  AgentMode (StrEnum: LOOP, CHANGE)                             │
│  parse_agent_mode(raw) -> AgentMode                            │
│  OPENCODE_WIZARD_AGENTS / opencode_wizard_agents()   (today)   │
│  OPENCODE_CHANGE_AGENTS / opencode_change_agents()    (NEW)    │
│  OPENCODE_REASONING_EFFORTS                          (unchanged)│
│  join_opencode_catalog / opencode_model_is_reasoning (unchanged)│
│  build_opencode_override_payload                     (unchanged)│
└────────────────────────────────────────────────────────────────┘
```

Two seams, both small:

1. **CLI → wizard**: `run_wizard_or_bail(cli, *, home, agent_mode)`. The CLI adapter owns parsing and validation; the wizard owns dispatch and per-CLI behavior.
2. **Wizard → renderer**: `re_render_for_agent_clis([AgentCli.OPENCODE])`. The wizard owns the override-store write; the renderer owns the disk write of every agent prompt — and already walks both resource dirs.

## Rejected alternatives

1. **`Literal["loop", "change"]` instead of `StrEnum`.** Python 3.12 supports string literals natively and they're lighter than `StrEnum`. Rejected because (a) it breaks the existing house style — `AgentCli` and `Nav` are both `StrEnum`; (b) it forces every `tuple[str, ...]` parameter that flows across the seam to widen to a `Literal` or stay a `str`, splitting the type story; (c) the parser's exception type becomes `ValueError` from a one-line helper, which is no better than a `StrEnum`-based parser raising `ValueError` — `Literal` saves no lines and loses the `AgentCli`-style affordances (e.g. `AgentMode.LOOP.value` for log messages).
2. **Differentiating the header string (`"set-models · opencode · change — model"` vs `"set-models · opencode · loop — model"`).** Visibly communicates which agent set the user is configuring. Rejected because the agent chooser prompt immediately below the header lists the agents by name (`change-orchestrator`, `propose`, etc.), so the user already has visible feedback in the first line of the prompt body. Differentiating the header would touch three header strings for no real information gain — and would risk future drift between the header text and the actual agent set if someone renames a mode without updating the strings. Locking the header unchanged keeps the diff small and the contract mechanical.
3. **Narrowing `re_render_for_agent_clis([AgentCli.OPENCODE])` to only the change-agent files when `-a change`.** Smaller write surface, fewer files touched. Rejected — the existing `_discover_loop_agents()` walk is the renderer's contract, and the PRD pins that this slice must not narrow it. Every on-disk prompt must reflect the fresh override state; a per-mode subset would silently leave loop-agent files stale when the user only ran `-a change` and the override store just gained new change-agent keys.
4. **A `discover_change_agents()` parallel to `_discover_loop_agents()`.** Mirrors the tuple seam. Rejected — the wizard reads from pure data (`OPENCODE_CHANGE_AGENTS`), the renderer reads from the filesystem. They don't share a discoverer by design, and a parallel discoverer would invite the assumption that the wizard is also filesystem-driven (it isn't, and shouldn't be).
5. **Per-agent override-store cleanup when a `-a change` run follows a `-a loop` run.** Removes the other set's keys from the store. Rejected — the keys are distinct (no collisions), the deep-merge handles side-by-side layout, and a cleanup pass is a behavior change that's out of scope for an additive flag.
6. **Case-insensitive `-a LOOP` / `-a Change` matching.** Friendlier UX. Rejected — strict-lowercase matches the existing vocabulary (`CLAUDE_MODELS`, `OPENCODE_REASONING_EFFORTS`, the AgentCli enum members) and avoids the "did the user type `Loop` and mean `loop`?" ambiguity that case-insensitive matching would invite. Pinned by PRD success-criteria scenario #7.
7. **Notice when `-a change` is paired with `-o claude` ("`-a change` ignored for claude").** Honest feedback. Rejected — PRD locks "silently ignored". A future `--verbose` flag may add the notice; out of scope here.