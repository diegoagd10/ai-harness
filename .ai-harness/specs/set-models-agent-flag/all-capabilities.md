---
change: set-models-agent-flag
artifact: specs
---

# Specs — set-models-agent-flag

Ratification layer over `prd.md` (8 acceptance scenarios) and `design.md` (deep-module seams). This spec does not replace the PRD scenarios — it pins each one in RFC 2119 form, maps them to the six PRD capabilities, and slices the work into independently-grabbable, demoable, working-at-each-pause units.

The locked decisions (no re-debate) are: `-a`/`--agent` optional, default `"loop"`, valid `{"loop", "change"}`, strict lowercase; honored for `-o opencode`, silently ignored for `-o claude`; `StrEnum AgentMode` lives in `src/ai_harness/modules/wizard/pure.py`; `_discover_loop_agents()` re-render scope stays at 12 files (no narrowing, no parallel `discover_change_agents`).

## 1. Capability traceability matrix

| PRD capability | Specs requirements | GIVEN/WHEN/THEN coverage | Direct unit / e2e tests |
| --- | --- | --- | --- |
| `vocab-opencode-change-agents` | `req:vocab-opencode-change-agents-001`, `req:vocab-opencode-change-agents-002` | (pure data — covered by requirements + unit test; no end-user-visible scenario) | unit: `test_opencode_change_agents_returns_eight_change_agents` |
| `cli-flag-agent` | `req:cli-flag-agent-001`, `req:cli-flag-agent-002`, `req:cli-flag-agent-003` | Scenarios 2, 5, 6, 7 | unit: `test_cli_set_models_unknown_agent_flag_errors`, `test_cli_set_models_default_agent_flag_is_loop`, `test_cli_set_models_uppercase_agent_flag_errors`; e2e: `_test_set_models_unknown_agent_flag_errors` |
| `wizard-opencode-agent-set` | `req:wizard-opencode-agent-set-001`, `req:wizard-opencode-agent-set-002`, `req:wizard-opencode-agent-set-003`, `req:re-render-scope-001` | Scenarios 1, 2, 5, 8 | unit: `test_run_opencode_wizard_change_agent_set_writes_eight_overrides`, `test_run_opencode_wizard_change_agent_set_re_renders_change_agent_files` |
| `wizard-claude-agent-flag-ignored` | `req:wizard-claude-agent-flag-ignored-001`, `req:wizard-claude-agent-flag-ignored-002` | Scenarios 3, 4 | unit: `test_cli_set_models_agent_flag_with_claude_is_silently_ignored` |
| `help-text-honest` | `req:help-text-honest-001` | (covered by requirement + unit test pinning text; not a behavioral scenario) | unit: `test_cli_set_models_help_mentions_agent_flag_and_valid_values` |
| `tests-and-e2e-coverage` | (cross-cutting — composed from the tests above; no new requirements of its own) | (cross-cutting — composed from Scenarios 1–8) | All listed unit tests + the e2e sandbox case |

Every PRD capability has at least one specs requirement; every user-visible behavior path has at least one of the eight PRD scenarios. Pure-data (`vocab-opencode-change-agents`) and help-text (`help-text-honest`) capabilities have no dedicated GIVEN/WHEN/THEN scenario because their behavior is either internal data or text-pinned rather than user-action-driven — both are pinned by requirements and unit tests so a refactor cannot silently weaken them. `tests-and-e2e-coverage` is the cross-cutting test surface; it is satisfied by the union of the tests above.

## 2. Tracer-bullet slice ordering

Each slice leaves the harness in a working state. After every slice, `ruff`, `mypy --strict`, `pytest tests/test_set_models.py tests/test_renderers.py`, and `e2e/set_models_lifecycle.py` pass (gates per the PRD).

### Slice 1 — Pure change-agent vocabulary (`src/ai_harness/modules/wizard/pure.py`)

Add `OPENCODE_CHANGE_AGENTS` tuple and `opencode_change_agents()` accessor (and `AgentMode` StrEnum + `parse_agent_mode` helper as the parsing/validation seam used by slice 2). No callers yet.

**Red-phase failing test:** `tests/test_set_models.py::test_opencode_change_agents_returns_eight_change_agents` — fails on `ImportError` (cannot import `opencode_change_agents` from `modules.wizard.pure`) until the symbol is exported. Once slice 1 lands, the test passes and `pure.py` is self-consistent with no callers depending on it.

### Slice 2 — CLI flag plumbing (`src/ai_harness/commands/set_models.py`)

Add the `-a`/`--agent` `typer.Option`, route the raw string through `parse_agent_mode`, and thread the parsed `AgentMode` into `run_wizard_or_bail`. The wizard ignores the new parameter for now (it has a default).

**Red-phase failing test:** `tests/test_set_models.py::test_cli_set_models_unknown_agent_flag_errors` — fails because typer rejects the entire invocation with "no such option: -a" before any validation logic runs. After slice 2, the test fails differently — typer reaches the validation, sees `bogus`, and emits a `typer.BadParameter` naming `loop`/`change` with exit code 2.

### Slice 3 — Wizard dispatch (`src/ai_harness/modules/wizard/tui.py`)

`run_wizard_or_bail`, `run_wizard`, and `run_opencode_wizard` are wired together: `run_wizard_or_bail` selects the agent tuple at the seam and threads it down as `agents: tuple[str, ...]`; `run_opencode_wizard` accepts the tuple and does not call `opencode_wizard_agents()` / `opencode_change_agents()` internally. The Claude branch accepts `agent_mode` for signature symmetry and ignores it.

**Red-phase failing test:** `tests/test_set_models.py::test_run_opencode_wizard_change_agent_set_writes_eight_overrides` — fails with `TypeError` (unexpected keyword argument `agent_mode` or `agents`) until the parameter is added. Once slice 3 lands, the `-a change` happy path is reachable end-to-end.

### Slice 4 — Claude silent-ignore

Confirm `run_claude_wizard` (or the claude dispatch branch) accepts the parameter for signature symmetry, ignores its value, runs the Claude loop wizard unchanged, and never writes any change-agent key to `~/.ai-harness/overrides.json`.

**Red-phase failing test:** `tests/test_set_models.py::test_cli_set_models_agent_flag_with_claude_is_silently_ignored` — fails because either the claude wizard crashes on the unused parameter or the override store gains `change-orchestrator` / `propose` / etc. keys. After slice 4, the override store contents are byte-equal to a run without `-a`.

### Slice 5 — Help-text honest

The typer `--help` output for `set-models` documents `-a`/`--agent`, names both valid values, and states that the flag is silently ignored when `-o claude` is passed.

**Red-phase failing test:** `tests/test_set_models.py::test_cli_set_models_help_mentions_agent_flag_and_valid_values` — fails because the current `--help` output does not mention `-a`, the valid values, or the claude-ignored note. After slice 5, the wording matches `req:help-text-honest-001`.

### Slice 6 — Tests + e2e

Add the e2e sandbox case for the rejection path and the scripted full-flow test for the `-a change` re-render scope. The earlier slices covered the underlying logic; this slice wires the sandbox-level coverage and runs the full test + e2e matrix as a final gate.

**Red-phase failing test:** `e2e/set_models_lifecycle.py::_test_set_models_unknown_agent_flag_errors` — fails until slices 2 + 3 + 5 are in place (the CLI rejects, the wizard doesn't crash, and the help-text is informative). After slice 6, the e2e sandbox lifecycle runs green end-to-end.

## 3. RFC 2119 requirements

Requirements are grouped by capability. Each requirement MUST be satisfied for the slice carrying that capability to be considered done; unit tests pin each requirement's observable behavior so a future refactor cannot silently weaken it.

### Capability: `vocab-opencode-change-agents`

#### Requirement: `req:vocab-opencode-change-agents-001`
`src/ai_harness/modules/wizard/pure.py` MUST export `OPENCODE_CHANGE_AGENTS` as a `tuple[str, ...]` containing exactly the eight change-agent names, in this order: `change-orchestrator`, `change-explorer`, `change-implementor`, `change-validator`, `propose`, `design`, `specs`, `tasks`. The tuple MUST be immutable at the type level (annotated `tuple[str, ...]`, not `list[str]`).

#### Requirement: `req:vocab-opencode-change-agents-002`
`src/ai_harness/modules/wizard/pure.py` MUST expose `opencode_change_agents() -> tuple[str, ...]` returning `OPENCODE_CHANGE_AGENTS`. This function MUST be the only public accessor for the change-agent set; consumers MUST NOT import the `OPENCODE_CHANGE_AGENTS` tuple directly. The accessor MUST return the same tuple object on every call (identity-stable, so `opencode_change_agents() is opencode_change_agents()` is `True`).

### Capability: `cli-flag-agent`

#### Requirement: `req:cli-flag-agent-001`
The `set-models` typer command MUST accept an optional `-a` / `--agent` `typer.Option` whose raw value type is `str` and whose default is the string `"loop"`. When the user supplies a non-`None` value, the CLI MUST validate that the value is in `{"loop", "change"}` (strict lowercase, no normalization, no case folding). The parsed value MUST be threaded into `run_wizard_or_bail` as an `AgentMode`.

#### Requirement: `req:cli-flag-agent-002`
When validation fails (raw value not in `{"loop", "change"}`), the CLI MUST raise `typer.BadParameter` whose message names the valid set explicitly (both `loop` and `change`). typer MUST map this to exit code 2.

#### Requirement: `req:cli-flag-agent-003`
When `-a` is omitted, the CLI MUST default to `"loop"`. Today's byte-for-byte behavior for both `-o opencode` (4-agent loop set) and `-o claude` (Claude loop wizard) MUST be preserved — no observable difference between a run with `-a loop` and a run with no `-a`.

### Capability: `wizard-opencode-agent-set`

#### Requirement: `req:wizard-opencode-agent-set-001`
`run_wizard_or_bail` MUST accept a new keyword-only argument `agent_mode: AgentMode = AgentMode.LOOP`. The default MUST preserve today's byte-for-byte behavior. The `AgentMode` type MUST be exported from `src/ai_harness/modules/wizard/pure.py` (matching the design's house style alongside `AgentCli` and `Nav`).

#### Requirement: `req:wizard-opencode-agent-set-002`
When `cli == AgentCli.OPENCODE`, the wizard dispatch layer (`run_wizard` per the design) MUST select `opencode_wizard_agents()` when `agent_mode == AgentMode.LOOP` and `opencode_change_agents()` when `agent_mode == AgentMode.CHANGE`, and MUST pass the chosen tuple into `run_opencode_wizard` as the `agents` parameter. The selection MUST be made once and threaded as a single `agents: tuple[str, ...]` value — there MUST NOT be per-mode duplication of the wizard body.

#### Requirement: `req:wizard-opencode-agent-set-003`
`run_opencode_wizard` MUST accept a keyword-only argument `agents: tuple[str, ...]` representing the selected agent set. The body of `run_opencode_wizard` MUST NOT call `opencode_wizard_agents()` or `opencode_change_agents()` directly; the `agents` parameter is the single source of truth for the agent set inside the wizard body. (Per the design's deep-module interface, `run_opencode_wizard(*, home, agent_mode=AgentMode.LOOP)` MAY keep `agent_mode` on the signature for symmetry, but the tuple MUST be resolved at the dispatch layer and passed in, not derived inside the body.)

### Capability: `wizard-claude-agent-flag-ignored`

#### Requirement: `req:wizard-claude-agent-flag-ignored-001`
When `cli == AgentCli.CLAUDE`, the value of `agent_mode` MUST be ignored entirely. The Claude loop wizard MUST run exactly as today. There MUST be no warning, no error, no informational notice, no `print`, and no difference in log output between a run with `agent_mode == AgentMode.LOOP` and a run with `agent_mode == AgentMode.CHANGE`.

#### Requirement: `req:wizard-claude-agent-flag-ignored-002`
When `cli == AgentCli.CLAUDE` regardless of `agent_mode` value, the override store MUST NOT gain any key whose name starts with `change-`, `propose`, `design`, `specs`, or `tasks`. A user-visible inspection of `~/.ai-harness/overrides.json` after `set-models -o claude -a change` (or `-a loop` or no `-a`) MUST NOT show any of these keys.

### Capability: `help-text-honest`

#### Requirement: `req:help-text-honest-001`
The typer `--help` output for `set-models` MUST document the `-a` / `--agent` option, MUST name both valid values (`loop` and `change`), and MUST state that the flag is silently ignored when `-o claude` is passed. The wording MUST remain honest under future refactors; a unit test pins the text (exact match or regex covering the key phrases) so a refactor cannot silently drop the claude-ignored note or omit a valid value.

### Capability: `re-render-scope` (cross-cuts `wizard-opencode-agent-set`)

#### Requirement: `req:re-render-scope-001`
After a successful `-a change` wizard confirm, the on-disk state under `.config/opencode/agent/` MUST contain fresh frontmatter in all twelve agent files: `loop-orchestrator.md`, `explorer.md`, `implementor.md`, `validator.md` (loop set) plus `change-orchestrator.md`, `change-explorer.md`, `change-implementor.md`, `change-validator.md`, `propose.md`, `design.md`, `specs.md`, `tasks.md` (change set). `_discover_loop_agents()` MUST NOT be replaced, MUST NOT be narrowed to a subset, and MUST continue to walk both `loop-agent/` and `change-agent/` resource directories. No parallel `discover_change_agents()` helper MAY be introduced.

## 4. GIVEN/WHEN/THEN scenarios

The eight scenarios below restate the PRD's acceptance criteria in original numbering. SHOULD-clauses capture non-obvious behavior that the implementation must respect but that does not change the pass/fail outcome of the scenario.

### Scenario 1 — Opencode `-a change` targets the 8 change agents

GIVEN a fresh `~/.ai-harness/overrides.json` (or any prior state)
AND the `opencode` binary on PATH
AND the opencode model catalog present
WHEN the user runs `ai-harness set-models -o opencode -a change` and walks through the wizard
THEN the agent chooser lists exactly `change-orchestrator`, `change-explorer`, `change-implementor`, `change-validator`, `propose`, `design`, `specs`, `tasks` (orchestrator first)
AND the override store, after confirm, contains those 8 agent keys (plus any pre-existing loop-agent keys, untouched)
AND `re_render_for_agent_clis([AgentCli.OPENCODE])` re-emits all 12 `.config/opencode/agent/*.md` files (4 loop + 8 change) with fresh frontmatter.
SHOULD the picker header text remain unchanged between `-a loop` and `-a change` runs, because visible feedback for the agent set is provided by the agent chooser label immediately below the header (header differentiation is out of scope per design rejected alternative #2).

### Scenario 2 — Opencode `-a loop` preserves today's behavior byte-for-byte

GIVEN any prior state
WHEN the user runs `ai-harness set-models -o opencode -a loop`
THEN the wizard runs identically to the pre-`-a` `set-models -o opencode` flow — 4-agent agent chooser, same model source, same effort source, same re-render.
SHOULD the re-render continue to cover all 12 agent files even though only the 4 loop-agent keys are written in this run, so the override store and the on-disk state stay synchronized regardless of which agent set was last configured.

### Scenario 3 — Claude with `-a change` runs the Claude loop wizard silently

GIVEN the Claude wizard prerequisites (Claude installed, TTY present)
WHEN the user runs `ai-harness set-models -o claude -a change`
THEN the Claude loop wizard runs unchanged
AND no notice about the ignored flag is printed
AND the override store, after confirm, contains only Claude wizard keys (no change-agent keys, no `change-orchestrator` / `propose` / etc. pollution).
SHOULD the bytes on stdout and stderr be identical to a run without `-a`, so the silent-ignore contract is testable by diffing captured output.

### Scenario 4 — Claude with no `-a` runs the Claude loop wizard (today's behavior)

GIVEN the Claude wizard prerequisites
WHEN the user runs `ai-harness set-models -o claude` (no `-a`)
THEN the Claude loop wizard runs unchanged
AND the override store, after confirm, contains only Claude wizard keys.
SHOULD the override store contents after this run be byte-equal to a run with `-a loop` or `-a change`, so the claude branch is provably independent of the flag.

### Scenario 5 — `-a` omitted with `-o opencode` defaults to `loop`

GIVEN any prior state
WHEN the user runs `ai-harness set-models -o opencode` (no `-a`)
THEN the wizard routes through the loop-agent branch (4-agent chooser, today's behavior).
SHOULD the override store after this run be byte-equal to a run with `-a loop`, since the omitted flag defaults to `"loop"` per `req:cli-flag-agent-003`.

### Scenario 6 — `-a bogus` is rejected with a typer error naming valid values

GIVEN any state
WHEN the user runs `ai-harness set-models -o opencode -a bogus`
THEN typer exits non-zero
AND the error message names the valid values (`loop`, `change`).
SHOULD the exit code be exactly 2, mapping `typer.BadParameter` per `req:cli-flag-agent-002` and the existing typer convention in this codebase.

### Scenario 7 — `-a LOOP` (uppercase) is rejected — strict lowercase

GIVEN any state
WHEN the user runs `ai-harness set-models -o opencode -a LOOP`
THEN typer exits non-zero with the same valid-values hint as scenario 6.
SHOULD any mixed-case variant (`Loop`, `cHaNgE`, etc.) be rejected identically, since strict-lowercase matches the existing vocabulary (`CLAUDE_MODELS`, `OPENCODE_REASONING_EFFORTS`, `AgentCli` enum members) and case-insensitive matching is explicitly out of scope per the design.

### Scenario 8 — Ctrl+C at any prompt writes nothing

GIVEN any state
WHEN the user runs `ai-harness set-models -o opencode -a change` and presses Ctrl+C during any prompt
THEN `~/.ai-harness/overrides.json` is unchanged
AND no re-render runs
AND the CLI exits non-zero with the existing cancel banner.
SHOULD this contract hold identically for `-a loop` and for the claude branch, since the cancel path is upstream of any agent-set branching.

## 5. Out of scope

The implementor MUST NOT introduce the following without an explicit, separate change PRD. Each item restates a row from the PRD's "Out" list and is a barrier against scope expansion.

- **Claude-side notice for the ignored flag.** `-a change` paired with `-o claude` is fully silent — no warning, no error, no informational print, no log difference. A future `--verbose` notice may be added in a separate slice.
- **Re-render narrowing.** `re_render_for_agent_clis([AgentCli.OPENCODE])` already re-emits all 12 files via `_discover_loop_agents()`. The implementation MUST NOT narrow the re-render to a per-mode subset, MUST NOT introduce a parallel `discover_change_agents()`, and MUST NOT introduce a per-CLI render subset.
- **`minimax/MiniMax-M3` template-default fix.** The change-agent template defaults in `_AGENT_META["model"]["opencode"]` are `minimax/MiniMax-M3`. On a fresh machine running `-a change` and confirming without edits, the rendered change-agent frontmatter still contains the template-default model id (the override store stays empty → renderer falls back to template). Picker pre-selection stays at "unknown" for ids not in the catalog (`cost_input=None`, `reasoning=False`). Pre-existing behavior, not fixed in this slice.
- **Help-text e2e coverage.** The e2e covers the rejection path only. A unit test asserts the help text mentions `-a`, the valid values, and the claude-ignored note.
- **Case-insensitive matching.** Strict lowercase only. `-a LOOP`, `-a Loop`, `-a CHANGE`, `-a cHaNgE` are all rejected with the same valid-values hint.
- **Multi-occurrence rejection for `-a`.** typer already keeps the last occurrence. No explicit multi-occurrence validation is added.
- **Per-agent override-store cleanup.** Loop-agent and change-agent overrides live side-by-side in `~/.ai-harness/overrides.json`, keyed by distinct names with no collisions, no shared prefixes, no shared slugs. No migration, no cleanup pass.
- **Changes to `renderers.py`, `operations.py`, `models.py`.** The existing seams cover the `-a change` branch unchanged. The implementor MUST NOT touch these files in this slice.

## 6. Open questions ratifying the design's deferred items

The following items were debated during design and locked; this spec ratifies each so the implementor finds the decision here without re-reading `design.md`. None is open for re-debate inside this slice.

- **`StrEnum AgentMode` over `Literal["loop", "change"]`** — locked. Matches the existing house style of `AgentCli` (in `harness/models.py`) and `Nav` (in `wizard/tui.py`). Lets the parser raise a typed `ValueError` that the typer layer translates to `typer.BadParameter` without leaking the literal type to call sites, and keeps `tuple[str, ...]` agent lists from having to widen to `tuple[Literal["loop","change"], ...]` at the seam.
- **Header text unchanged between `-a loop` and `-a change`** — locked as NO differentiation. The agent chooser label immediately below the header lists the agents by name, so visible feedback for the agent set is already there. Differentiating would touch three header strings for no real information gain and would risk future drift between the header text and the actual agent set if someone renames a mode without updating the strings. Captured in Scenario 1 SHOULD.
- **No narrowing of `re_render_for_agent_clis([AgentCli.OPENCODE])`** — locked. The re-render continues to cover all 12 files via `_discover_loop_agents()` walking both `loop-agent/` and `change-agent/`. Captured in `req:re-render-scope-001`.
- **No parallel `discover_change_agents()`** — locked. The wizard reads from pure data (`OPENCODE_CHANGE_AGENTS`); the renderer reads from the filesystem. Asymmetric by design, not duplication.
- **No per-agent override-store cleanup** — locked as out of scope. The 8 change-agent names are distinct from the 4 loop-agent names; `write_override_store`'s deep-merge handles side-by-side layout without migration.
- **Strict-lowercase matching** — locked. Matches the existing vocabulary in `CLAUDE_MODELS`, `OPENCODE_REASONING_EFFORTS`, and the `AgentCli` enum members. Pinned by Scenario 7 and `req:cli-flag-agent-001`.
- **No Claude-side notice for the ignored flag** — locked as fully silent. A future `--verbose` flag may add a notice in a separate slice. Pinned by Scenario 3 SHOULD and `req:wizard-claude-agent-flag-ignored-001`.