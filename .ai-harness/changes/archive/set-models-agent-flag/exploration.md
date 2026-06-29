---
change: set-models-agent-flag
artifact: exploration
---

budget: 150

# Exploration — set-models-agent-flag

## Budget
**150 LOC** total touched (additions + deletions), split roughly:
- `commands/set_models.py` — 12 LOC (new `-a/--agent` Option + validation).
- `modules/wizard/tui.py` — 25 LOC (thread `agent_mode` through `run_wizard_or_bail` / `run_wizard` / `run_opencode_wizard`; branch opencode dispatch on the flag; pass agent-set name into baseline/selection).
- `modules/wizard/pure.py` — 8 LOC (new `OPENCODE_CHANGE_AGENTS` tuple + accessor).
- `tests/test_set_models.py` — 100 LOC (3-4 new tests: invalid `-a` value, claude ignores `-a`, opencode `-a change` happy path, opencode `-a loop` still routes today's set).
- `e2e/set_models_lifecycle.py` — 5 LOC (one new arg-validation case for unknown `-a` value).

Justification: additive flag with two opencode branches (today's 4-agent branch + a new 8-agent branch). The pure data layer only needs one new vocabulary tuple and one helper. The TUI branches in two places (model list, agent-list label) but most of the existing wizard body is reusable. No changes needed in `renderers.py` or `operations.py` (see "Re-render scope" below — `_discover_loop_agents` already walks `change-agent/`).

## Affected Files

| Path | Kind of change |
| --- | --- |
| `src/ai_harness/commands/set_models.py` | Add `-a/--agent` typer `Option` (optional, default `loop`); validate value ∈ {`loop`,`change`}; reject unknown with `typer.BadParameter` naming valid values; thread parsed value into `run_wizard_or_bail`. |
| `src/ai_harness/modules/wizard/tui.py` | New `AgentMode` enum (or reuse the string); thread through `run_wizard_or_bail` → `run_wizard` → `run_opencode_wizard`; branch opencode dispatch on `agent_mode` to pick agent list; claude path is a no-op for `-a`; `_ask_opencode_continue_or_agent` reads from a passed-in agent tuple instead of `opencode_wizard_agents()` directly so both branches share the header/footer code. |
| `src/ai_harness/modules/wizard/pure.py` | Add `OPENCODE_CHANGE_AGENTS` tuple (`change-orchestrator`, `change-explorer`, `change-implementor`, `change-validator`, `propose`, `design`, `specs`, `tasks`) and a `opencode_change_agents()` accessor. `OPENCODE_REASONING_EFFORTS` stays the same; the join logic stays the same. |
| `tests/test_set_models.py` | New tests: pure-vocab (`opencode_change_agents`); CLI validation (`-a bogus` rejects; `-a` defaults to `loop`; `-a change` for `-o claude` silently ignored); one scripted full-flow test for `-a change` happy path (mirrors today's opencode happy-path test shape but seeds 8 agents). |
| `e2e/set_models_lifecycle.py` | One new arg-validation case: `set-models -o opencode -a bogus` exits non-zero with the valid-values hint in stderr/stdout. |

**Not touched (despite appearing related):**
- `src/ai_harness/modules/harness/renderers.py` — `_discover_loop_agents()` already walks both `loop-agent/` AND `change-agent/` resource dirs (confirmed by `tests/test_renderers.py::test_discover_loop_agents_excludes_underscore_prefixed_files`, which asserts all 12 names including the 8 change agents). `render_agents(AgentCli.OPENCODE)` therefore already re-emits all 12 files. No new discoverer, no new helper.
- `src/ai_harness/modules/harness/operations.py` — `re_render_for_agent_clis([AgentCli.OPENCODE])` already covers the change-agent files via the same `render_agents` call. Re-render scope is correct out of the box for the `-a change` branch.
- `src/ai_harness/modules/harness/models.py` — `AgentCli` enum is fine as-is.

## Plan

- **Phase prd** — Capture the locked decisions verbatim and add the open question about the `minimax/MiniMax-M3` default (see Risks #1). State the claude-silent-ignore contract in the user-visible behaviour table. State that the re-render already covers change-agent files (no renderers/operations change).
- **Phase design** — Sketch the new `AgentMode` (or plain string literal type) as a thin enum living in `pure.py`; map the opencode branch to a callable that takes a `tuple[str, ...]` agent list and a header string. Spell out that `_discover_loop_agents` is the renderer's existing seam — the wizard does not need a parallel `discover_change_agents`. Note the help-text wording for `-a` must be honest about claude-ignores and opencode-default-loop.
- **Phase tasks** — Slice into ordered, independently-grabbable issues: (1) pure vocab + tests; (2) CLI flag + validation + tests; (3) `run_opencode_wizard` accepts `agent_mode`, branch on it, defaults to today's path; (4) claude branch ignores `agent_mode`; (5) full-flow scripted test for `-a change` happy path; (6) e2e case for unknown `-a`; (7) docs note in `--help`.

## Edge Cases

- `-a change` paired with `-o claude` — flag is silently ignored; claude wizard runs as today; override store is NOT polluted with change-agent keys.
- `-a change` paired with `-o opencode` — wizard lists the 8 change agents (orchestrator first like today's `loop-orchestrator`); re-render re-emits all 12 opencode files (existing `_discover_loop_agents` covers this).
- `-a` omitted — defaults to `loop`; today's behaviour preserved byte-for-byte for both CLIs.
- `-a bogus` — typer rejects with message naming valid values; exit code 2.
- `-a LOOP` (uppercase) — must be normalized or rejected. Decide at design time; lean toward "reject" to match the existing lowercase vocabulary in `CLAUDE_MODELS`/`OPENCODE_REASONING_EFFORTS`.
- `-a change` then user cancels (Ctrl+C) — no overrides written, no re-render; identical to today's cancel contract.
- `-a change` and the user picks no agent — confirm screen shows the 8 baseline (template-default) values; selective-write yields an empty payload; no overrides file written; no re-render.
- `-a change` followed by a re-run with `-a loop` — loop wizard reads its own 4 agents from `get_agent_meta`; loop-agent overrides and change-agent overrides live side-by-side in the store keyed by distinct names (no collisions). The second run touches only loop-agent overrides.
- OpenCode binary absent — `run_wizard_or_bail` already errors before the wizard starts; `-a` is irrelevant on this path (flag validation can still fire first if the binary check is in `run_wizard_or_bail`, which it is).

## Test Surface

- `tests/test_set_models.py::test_opencode_change_agents_returns_eight_change_agents` — pure vocab assertion mirroring `test_opencode_wizard_agents_includes_orchestrator_first`.
- `tests/test_set_models.py::test_cli_set_models_unknown_agent_flag_errors` — `set-models -o opencode -a bogus` exits non-zero; combined output names valid values.
- `tests/test_set_models.py::test_cli_set_models_default_agent_flag_is_loop` — `set-models -o opencode` (no `-a`) still uses the 4-agent loop set.
- `tests/test_set_models.py::test_cli_set_models_agent_flag_with_claude_is_silently_ignored` — `set-models -o claude -a change` does not fail and does not pollute the override store with change-agent keys.
- `tests/test_set_models.py::test_run_opencode_wizard_change_agent_set_writes_eight_overrides` — full-flow scripted test: `-a change` happy path; verifies override file contains the 8 change-agent keys after confirm.
- `tests/test_set_models.py::test_run_opencode_wizard_change_agent_set_re_renders_change_agent_files` — verifies that after confirm, the 8 `.config/opencode/agent/<change-agent>.md` files exist on disk with the picked model in the frontmatter.
- `e2e/set_models_lifecycle.py::_test_set_models_unknown_agent_flag_errors` — sandboxed non-interactive run confirming the help-text/typer error path.

Existing gates: `ruff`, `mypy --strict`, `pytest tests/test_set_models.py tests/test_renderers.py`, e2e sandbox lifecycle.

## Risks

1. **`minimax/MiniMax-M3` default in `_AGENT_META` for change agents is almost never in a user's opencode catalog** — `set_models.py` change-orchestrator / change-explorer / propose / design / specs / tasks / change-implementor / change-validator all default to this id. Two consequences: (a) the picker pre-selects nothing on a fresh machine (safe — `join_opencode_catalog` returns `cost_input=None`, `reasoning=False` for unknown ids, which is exactly today's "unknown" rendering); (b) if a user runs `-a change` and confirms without picking any agent, the rendered change-agent frontmatter still contains `model: minimax/MiniMax-M3` because that's the template default and the override store is empty. This is pre-existing behaviour and not blocking for this change, but the PRD should surface it as a known limitation (the renderer is contract-bound to template defaults when no override is set) and the design should note that it is out of scope to add a CLI catalog fetch fallback.
2. **Re-render scope for `-a change` is wider than it looks** — `_discover_loop_agents()` returns all 12 names (loop-agent + change-agent). When the user runs `-a change` and confirms, `re_render_for_agent_clis([AgentCli.OPENCODE])` re-emits all 12 `.config/opencode/agent/*.md` files (4 loop-agent + 8 change-agent). This is the right behaviour (all on-disk prompts reflect fresh overrides) but the design must spell it out explicitly to avoid a future "narrow the re-render to only what the wizard touched" scope-creep. The render plan in `operations.py` is unchanged.

## Open Questions

1. Should `-a LOOP` (uppercase) be accepted (case-insensitive match) or rejected (strict lowercase)? Lean toward strict-lowercase to match the existing lowercase vocabulary in `CLAUDE_MODELS` and `OPENCODE_REASONING_EFFORTS`.
2. Should `-a change` paired with `-o claude` emit a one-line informational note ("`-a change` ignored for claude") or be fully silent as locked? Locked decision says fully silent — confirming here.
3. Should the e2e test for unknown `-a` value exercise the help-text too (`set-models --help` mentions `-a` honestly) or only the rejection path? Lean toward one focused test (rejection) plus a unit test that asserts the help text mentions `-a` and the valid values.

## nextRecommended

**prd** — Pin down the user-visible behaviour: the locked decisions from the orchestrator seed (flag shape, claude silent-ignore, default `loop`, opencode `loop` ≡ today, opencode `change` ≡ 8 named agents, same model + effort source). State the override-store key uniqueness up-front (each of the 8 change-agent names already has a unique key — verified). Surface the `minimax/MiniMax-M3` template-default caveat as a known limitation explicitly out of scope for this slice. Acceptance criteria: a fresh e2e machine that runs `set-models -o opencode -a change` and confirms with edits sees those edits land in `~/.ai-harness/overrides.json` under the 8 change-agent keys and the 8 change-agent files under `.config/opencode/agent/` reflect the picks.

**design** — Sketch one thin `AgentMode` enum (`LOOP = "loop"`, `CHANGE = "change"`) in `pure.py` alongside the existing wizard vocab. Show the opencode wizard as a single body parameterised by an agent tuple (`agents: tuple[str, ...]`) and a header label (`"change"` vs `"loop"`); the only real branching is which tuple to pass in. Spell out that `_discover_loop_agents` is the existing renderer's seam — no parallel helper, no `renderers.py` change. Document that `re_render_for_agent_clis([AgentCli.OPENCODE])` re-emits all 12 files; the design embraces this rather than narrowing it. Write the honest help text: "Configure the agent set when targeting opencode (`loop` for the four loop agents, `change` for the eight change agents). Ignored for claude." Reject any value outside `{loop, change}` with a clear typer error naming the valid set.