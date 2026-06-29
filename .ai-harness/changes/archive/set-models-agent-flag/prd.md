---
change: set-models-agent-flag
artifact: prd
---

# PRD — set-models-agent-flag

## Intent

When the user runs `ai-harness set-models -o opencode`, they can pick which agent set to configure: today's four loop agents (`loop-orchestrator`, `explorer`, `implementor`, `validator`) via `-a loop` (the default, today's behavior preserved byte-for-byte), or eight change agents (`change-orchestrator`, `change-explorer`, `change-implementor`, `change-validator`, `propose`, `design`, `specs`, `tasks`) via `-a change`. Both branches share the same model source (`opencode models` joined via `join_opencode_catalog` with `~/.cache/opencode/models.json`) and the same reasoning-effort gate (`OPENCODE_REASONING_EFFORTS = ("low", "medium", "high")`, gated per-model on the catalog's `reasoning` boolean). For `-o claude` the flag is **silently ignored**: the existing Claude loop wizard runs unchanged, the override store is not polluted with change-agent keys, no notice is printed.

## Scope

### In

- New optional CLI flag `-a` / `--agent` on the `set-models` command. Default `loop`. Valid values: `loop`, `change`. Reject any other value with a `typer.BadParameter` naming the valid set. Case-sensitive lowercase only (matches the existing `CLAUDE_MODELS` / `OPENCODE_REASONING_EFFORTS` vocabulary).
- New `OPENCODE_CHANGE_AGENTS` vocabulary tuple + accessor in `pure.py` so the change-agent set is the wizard's single source of truth, mirroring today's `OPENCODE_WIZARD_AGENTS` shape.
- Thread `agent_mode` through `run_wizard_or_bail` → `run_wizard` → `run_opencode_wizard`. The opencode wizard is parameterised by the agent tuple; the only real branching is which tuple to pass in (`loop-orchestrator`/`explorer`/`implementor`/`validator` vs `change-orchestrator`/`change-explorer`/`change-implementor`/`change-validator`/`propose`/`design`/`specs`/`tasks`).
- Honest `--help` text that names both valid values and states claude-ignored behavior.
- Unit tests (pure vocab + CLI validation + scripted full-flow) and one new e2e sandbox case for the arg-validation rejection path.

### Out

- **Claude-side notice.** `-a change` paired with `-o claude` is fully silent — no warning, no error, no override-store pollution. A future slice may add a `--verbose` notice; out of scope here.
- **Re-render narrowing.** `re_render_for_agent_clis([AgentCli.OPENCODE])` already re-emits all 12 files (4 loop + 8 change) via the existing `_discover_loop_agents()` walk over both `loop-agent/` and `change-agent/` resource dirs. The design must NOT introduce a parallel `discover_change_agents`, a per-CLI subset, or any narrowing of the render. This is the right behavior — all on-disk prompts reflect fresh overrides — and embracing it avoids scope-creep.
- **`minimax/MiniMax-M3` template-default limitation.** The change-agent template defaults in `_AGENT_META["model"]["opencode"]` are `minimax/MiniMax-M3`, which is unlikely to be in a typical user's opencode catalog. On a fresh machine running `-a change` and confirming without edits, the rendered change-agent frontmatter will still contain the template-default model id (the override store stays empty → renderer falls back to template). Pre-existing behavior, not fixed in this slice. The picker pre-selects nothing on a fresh machine (`join_opencode_catalog` returns `cost_input=None`, `reasoning=False` for unknown ids — the same "unknown" rendering today's wizard already uses). A future slice may add a CLI catalog fetch fallback; out of scope here.
- **Help-text e2e.** The e2e covers the rejection path only; a unit test asserts the help text mentions `-a` and the valid values.
- **Case-insensitive matching.** Strict lowercase only. `-a LOOP`, `-a Loop`, `-a CHANGE` are all rejected.
- **Multiple `-a` flags.** typer already keeps the last occurrence; we do not add explicit multi-occurrence rejection (the existing `-o` pattern is for repeated `-o` only).
- **Per-agent override-store cleanup.** Loop-agent and change-agent overrides live side-by-side in `~/.ai-harness/overrides.json` keyed by distinct names — no collisions, no migration, no cleanup pass.
- **Changes to `renderers.py`, `operations.py`, `models.py`.** The existing seams already cover the `-a change` branch.

## Capabilities

- **vocab-opencode-change-agents**: pure layer gains `OPENCODE_CHANGE_AGENTS = ("change-orchestrator", "change-explorer", "change-implementor", "change-validator", "propose", "design", "specs", "tasks")` plus an `opencode_change_agents()` accessor, exactly mirroring today's `OPENCODE_WIZARD_AGENTS` / `opencode_wizard_agents()` shape. Independently specifiable as a tracer-bullet slice — one tuple + one accessor + one unit test.
- **cli-flag-agent**: `set_models` gains an optional `-a` / `--agent` `typer.Option` defaulting to `"loop"`. Validation: reject any value not in `{"loop", "change"}` with `typer.BadParameter` naming the valid set. Thread the parsed string into `run_wizard_or_bail`. Independently specifiable — touches only `commands/set_models.py` and one unit test on the typer CLI.
- **wizard-opencode-agent-set**: `run_wizard_or_bail` and `run_wizard` accept an `agent_mode` parameter and pass it through; `run_opencode_wizard` branches on `agent_mode` to pick the agent tuple (`opencode_wizard_agents()` vs `opencode_change_agents()`). Same model source, same effort source, same re-render call. The body is one wizard parameterised by a tuple — no per-mode duplication. Independently specifiable — touches `tui.py` and the scripted full-flow unit test.
- **wizard-claude-agent-flag-ignored**: `run_claude_wizard` is reachable from the new flag path but is a no-op for `agent_mode` — it accepts the parameter for signature symmetry, ignores its value, and runs the existing Claude loop wizard unchanged. No override-store pollution with change-agent keys, no notice, no error. Independently specifiable — a unit test on `set-models -o claude -a change` confirms the override store does not gain change-agent keys.
- **help-text-honest**: the `-a` option's `help=` text is honest about the flag's scope and the claude-ignored behavior, names both valid values, and matches the rest of the typer surface's voice. Asserted by a unit test on the typer `--help` output.
- **tests-and-e2e-coverage**: unit tests cover pure vocab, CLI validation (`-a bogus` rejection, `-a` default-is-loop, `-a change` happy path), scripted full-flow for `-a change` (override store + re-rendered files), and claude silent-ignore (no change-agent key pollution). E2E sandbox covers the arg-validation rejection path only.

## Approach

The slice is additive and mostly orthogonal to the existing wizard. Three layers change, each with a single, narrow surface:

1. **Pure data layer** (`modules/wizard/pure.py`, ~8 LOC) — add the change-agent vocabulary tuple + accessor. No logic changes; the wizard already parameterises on `agents` in two places (`_ask_opencode_continue_or_agent` and the per-agent baseline/effort dicts in `run_opencode_wizard`) — the new accessor just feeds the alternative tuple through.

2. **CLI adapter** (`commands/set_models.py`, ~12 LOC) — add the `-a` `typer.Option`, validate `value ∈ {"loop", "change"}`, default `loop`, thread into `run_wizard_or_bail`. Mirrors the existing `-o` validation shape (single value, typer rejection, valid-set naming in the error).

3. **TUI dispatcher** (`modules/wizard/tui.py`, ~25 LOC) — `run_wizard_or_bail(cli, *, home, agent_mode)` accepts the flag; for `cli == OPENCODE` it picks `opencode_wizard_agents()` when `agent_mode == "loop"` and `opencode_change_agents()` when `agent_mode == "change"`, then passes the tuple into a wizard body that is already parameterised by `agents`. For `cli == CLAUDE` the flag is ignored (the parameter exists for signature symmetry but is unused).

**Re-render is unchanged.** `re_render_for_agent_clis([AgentCli.OPENCODE])` already calls `render_agents(AgentCli.OPENCODE)` which defaults `names=None` → `_discover_loop_agents()` → walks both `loop-agent/` and `change-agent/` resource dirs → returns all 12 names → all 12 `.config/opencode/agent/*.md` files are re-emitted. The wizard does not need a parallel `discover_change_agents`. `renderers.py` and `operations.py` stay untouched.

**Override-store keys are unique by construction.** Each of the 8 change-agent names (`change-orchestrator`, `change-explorer`, `change-implementor`, `change-validator`, `propose`, `design`, `specs`, `tasks`) is a distinct key in `~/.ai-harness/overrides.json` — no collisions with the 4 loop-agent names. A loop run and a change run can interleave; each writes its own slice of the store.

## Affected Areas

| Path | Change |
| --- | --- |
| `src/ai_harness/modules/wizard/pure.py` | Add `OPENCODE_CHANGE_AGENTS` tuple + `opencode_change_agents()` accessor. |
| `src/ai_harness/commands/set_models.py` | Add `-a`/`--agent` `typer.Option` (default `"loop"`); validate `value ∈ {"loop", "change"}`; thread into `run_wizard_or_bail`. |
| `src/ai_harness/modules/wizard/tui.py` | `run_wizard_or_bail`/`run_wizard`/`run_opencode_wizard` accept `agent_mode`; opencode branch selects `opencode_wizard_agents()` vs `opencode_change_agents()`; claude branch accepts the parameter and ignores it. |
| `tests/test_set_models.py` | New tests: pure vocab (`opencode_change_agents`); CLI validation (`-a bogus` rejects, `-a` defaults to `loop`, `-a change` happy path scripted, claude silent-ignore); help-text mentions `-a` and valid values. |
| `e2e/set_models_lifecycle.py` | One new arg-validation case: `set-models -o opencode -a bogus` exits non-zero with the valid-values hint. |

**Not touched:**

- `src/ai_harness/modules/harness/renderers.py` — `_discover_loop_agents()` already walks both `loop-agent/` and `change-agent/` (confirmed by `tests/test_renderers.py::test_discover_loop_agents_excludes_underscore_prefixed_files`, which asserts all 12 names).
- `src/ai_harness/modules/harness/operations.py` — `re_render_for_agent_clis([AgentCli.OPENCODE])` already covers the change-agent files via the same `render_agents` call.
- `src/ai_harness/modules/harness/models.py` — `AgentCli` enum is fine as-is.

## Risks

1. **Re-render scope for `-a change` is wider than it looks.** `_discover_loop_agents()` returns all 12 names (4 loop + 8 change). When the user confirms, all 12 `.config/opencode/agent/*.md` files are re-emitted — including the loop-agent files the user did not edit. **This is the right behavior** (every on-disk prompt reflects the fresh override state) but the design must spell it out to avoid a future "narrow the re-render to only what the wizard touched" scope-creep. No new discoverer, no per-mode subset.
2. **`minimax/MiniMax-M3` template-default on a fresh machine.** The change-agent template defaults are `minimax/MiniMax-M3` — unlikely to be in a typical user's opencode catalog. On a fresh machine running `-a change` and confirming without edits, the rendered change-agent frontmatter still contains `model: minimax/MiniMax-M3` (template default + empty override store). The picker pre-selects nothing (catalog lookup returns `cost_input=None`, `reasoning=False` for unknown ids — same "unknown" rendering today already uses). Pre-existing behavior; out of scope for this slice. A future slice may add a CLI catalog fetch fallback.
3. **Help-text drift.** The `-a` help must stay honest about the claude-ignored behavior and the two valid values. Unit test on `--help` output pins this so a future refactor cannot silently weaken it.
4. **Override-store key collisions.** Already verified safe — the 8 change-agent names are distinct from the 4 loop-agent names, no shared prefixes, no shared slugs. The `write_override_store` deep-merge handles the side-by-side layout without migration.

## Rollback Plan

The slice is additive and isolated. Rollback is a single revert of the five affected files. No migrations, no data-loss surface, no on-disk state changes beyond what today's wizard already writes. The override store, once written with change-agent keys, survives rollback harmlessly — the next loop run simply ignores those keys (the wizard only reads the keys in its own agent list).

## Dependencies

- **Existing vocabulary.** `OPENCODE_REASONING_EFFORTS` (`("low", "medium", "high")`) is reused unchanged for both branches — effort is gated per-model on the catalog's `reasoning` boolean via `opencode_model_is_reasoning`, the same code path today uses.
- **Existing catalog join.** `join_opencode_catalog(model_ids, catalog)` is reused unchanged for both branches.
- **Existing re-render.** `re_render_for_agent_clis([AgentCli.OPENCODE])` is reused unchanged; it already covers all 12 files via `_discover_loop_agents()`.
- **Existing renderer seam.** `_discover_loop_agents()` already walks both `loop-agent/` and `change-agent/` resource dirs (`_AGENT_RESOURCE_DIRS = ("loop-agent", "change-agent")`).
- **Existing override-store writer.** `write_override_store` is reused unchanged; deep-merge handles the loop + change side-by-side layout.
- **Locked decisions** (from the orchestrator seed — see "Scope → Out" for the full list):
  - `-a` / `--agent` flag shape, optional, default `loop`, values `loop`/`change`, case-sensitive lowercase.
  - For `-o claude`: silently ignored.
  - Both opencode branches use the same model source and the same effort source.
  - Re-render scope is 12 files (no narrowing).
  - `minimax/MiniMax-M3` template-default limitation is out of scope.

## Success Criteria

### GIVEN/WHEN/THEN scenarios

**1. Opencode `-a change` targets the 8 change agents.**
- GIVEN a fresh `~/.ai-harness/overrides.json` (or any prior state) AND the `opencode` binary on PATH AND the catalog present
- WHEN the user runs `ai-harness set-models -o opencode -a change` and walks through the wizard
- THEN the agent chooser lists exactly `change-orchestrator`, `change-explorer`, `change-implementor`, `change-validator`, `propose`, `design`, `specs`, `tasks` (orchestrator first)
- AND the override store, after confirm, contains only those 8 agent keys (plus any pre-existing loop-agent keys, untouched)
- AND `re_render_for_agent_clis([AgentCli.OPENCODE])` re-emits all 12 `.config/opencode/agent/*.md` files (4 loop + 8 change) with fresh frontmatter.

**2. Opencode `-a loop` preserves today's behavior byte-for-byte.**
- GIVEN any prior state
- WHEN the user runs `ai-harness set-models -o opencode -a loop`
- THEN the wizard runs identically to the pre-`-a` `set-models -o opencode` flow — 4-agent agent chooser, same model source, same effort source, same re-render.

**3. Claude with `-a change` runs the Claude loop wizard silently.**
- GIVEN the claude wizard prerequisites (Claude installed, TTY present)
- WHEN the user runs `ai-harness set-models -o claude -a change`
- THEN the Claude loop wizard runs unchanged
- AND no notice about the ignored flag is printed
- AND the override store, after confirm, contains only claude wizard keys (no change-agent keys, no `change-orchestrator` / `propose` / etc. pollution).

**4. Claude with no `-a` runs the Claude loop wizard (today's behavior).**
- GIVEN the claude wizard prerequisites
- WHEN the user runs `ai-harness set-models -o claude` (no `-a`)
- THEN the Claude loop wizard runs unchanged
- AND the override store, after confirm, contains only claude wizard keys.

**5. `-a` omitted with `-o opencode` defaults to `loop`.**
- GIVEN any prior state
- WHEN the user runs `ai-harness set-models -o opencode` (no `-a`)
- THEN the wizard routes through the loop-agent branch (4-agent chooser, today's behavior).

**6. `-a bogus` is rejected with a typer error naming valid values.**
- GIVEN any state
- WHEN the user runs `ai-harness set-models -o opencode -a bogus`
- THEN typer exits non-zero
- AND the error message names the valid values (`loop`, `change`).

**7. `-a LOOP` (uppercase) is rejected — strict lowercase.**
- GIVEN any state
- WHEN the user runs `ai-harness set-models -o opencode -a LOOP`
- THEN typer exits non-zero with the same valid-values hint as scenario 6
- (Decision: strict-lowercase matches the existing `CLAUDE_MODELS` / `OPENCODE_REASONING_EFFORTS` vocabulary; case-insensitive matching is out of scope and the design can ratify this.)

**8. Ctrl+C at any prompt writes nothing.**
- GIVEN any state
- WHEN the user runs `ai-harness set-models -o opencode -a change` and presses Ctrl+C during any prompt
- THEN `~/.ai-harness/overrides.json` is unchanged
- AND no re-render runs
- AND the CLI exits non-zero with the existing cancel banner.

### User-visible behavior matrix

| `-o` | `-a` | Behavior |
| --- | --- | --- |
| `claude` | omitted | Claude loop wizard (today). |
| `claude` | `loop` | Claude loop wizard (today) — flag silently ignored. |
| `claude` | `change` | Claude loop wizard (today) — flag silently ignored, no notice. |
| `claude` | `bogus` / `LOOP` / any other | typer rejects with valid-values hint, exit 2. |
| `opencode` | omitted | Opencode wizard, loop-agent set (4 agents, today). |
| `opencode` | `loop` | Opencode wizard, loop-agent set (4 agents, today). |
| `opencode` | `change` | Opencode wizard, change-agent set (8 agents, new). |
| `opencode` | `bogus` / `LOOP` / any other | typer rejects with valid-values hint, exit 2. |

### Data persisted

- **`~/.ai-harness/overrides.json`** — keyed by agent name. For `-a loop` the 4 loop-agent keys (`loop-orchestrator`, `explorer`, `implementor`, `validator`); for `-a change` the 8 change-agent keys (`change-orchestrator`, `change-explorer`, `change-implementor`, `change-validator`, `propose`, `design`, `specs`, `tasks`). Each run writes only its own slice (selective-write contract from issue #44 — unchanged baseline/diff). Loop and change keys live side-by-side; no migration, no cleanup.

### Files re-rendered

- For `-o opencode`: all 12 files under `.config/opencode/agent/` — `loop-orchestrator.md`, `explorer.md`, `implementor.md`, `validator.md` (loop set) + `change-orchestrator.md`, `change-explorer.md`, `change-implementor.md`, `change-validator.md`, `propose.md`, `design.md`, `specs.md`, `tasks.md` (change set). Rendered via `re_render_for_agent_clis([AgentCli.OPENCODE])` → `render_agents(AgentCli.OPENCODE)` → `_discover_loop_agents()` → both resource dirs. **No narrowing** — the design must embrace this.
- For `-o claude`: today's claude-agent re-render (4 loop-agent files plus the Claude-side equivalents). `-a` is irrelevant on this path.

### Help text

`set-models --help` must show:

```
-a, --agent [loop|change]   Configure the agent set when targeting opencode
                            ('loop' for the four loop agents, 'change' for
                            the eight change agents). Ignored for claude.
                            [default: loop]
```

A unit test pins the text so a future refactor cannot silently weaken it (e.g. drop "Ignored for claude" or omit the default).

## Verification plan

### Unit tests (`tests/test_set_models.py`)

| Test | What it asserts |
| --- | --- |
| `test_opencode_change_agents_returns_eight_change_agents` | Pure vocab assertion mirroring `test_opencode_wizard_agents_includes_orchestrator_first`. |
| `test_cli_set_models_unknown_agent_flag_errors` | `set-models -o opencode -a bogus` exits non-zero; combined output names `loop` and `change`. |
| `test_cli_set_models_uppercase_agent_flag_errors` | `set-models -o opencode -a LOOP` exits non-zero (strict-lowercase decision pinned). |
| `test_cli_set_models_default_agent_flag_is_loop` | `set-models -o opencode` (no `-a`) still routes the 4-agent loop set. |
| `test_cli_set_models_agent_flag_with_claude_is_silently_ignored` | `set-models -o claude -a change` does not fail; override store after confirm contains no change-agent keys. |
| `test_cli_set_models_help_mentions_agent_flag_and_valid_values` | `--help` output mentions `-a`/`--agent`, the values `loop` and `change`, and the claude-ignored note. |
| `test_run_opencode_wizard_change_agent_set_writes_eight_overrides` | Scripted full-flow: `-a change` happy path; override file contains all 8 change-agent keys after confirm. |
| `test_run_opencode_wizard_change_agent_set_re_renders_change_agent_files` | After confirm, the 8 `.config/opencode/agent/<change-agent>.md` files exist on disk with the picked model in the frontmatter (and the 4 loop-agent files are untouched unless their keys already had overrides). |

### E2E sandbox (`e2e/set_models_lifecycle.py`)

| Test | What it asserts |
| --- | --- |
| `_test_set_models_unknown_agent_flag_errors` | Sandboxed non-interactive run: `set-models -o opencode -a bogus` exits non-zero; combined output names `loop` and `change`. Focused on the arg-validation rejection path — no help-text coverage (unit test covers that). |

### Gates

- `ruff`
- `mypy --strict`
- `pytest tests/test_set_models.py tests/test_renderers.py`
- e2e sandbox lifecycle