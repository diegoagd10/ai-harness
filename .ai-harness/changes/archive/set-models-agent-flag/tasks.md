# Tasks — set-models-agent-flag

Five tracer-bullet vertical slices. Each slice lands as one commit and leaves
the harness green (`ruff`, `mypy --strict`, `pytest tests/test_set_models.py
tests/test_renderers.py`, `e2e/set_models_lifecycle.py`).

Implementation order matches the slice numbering. After each slice, the
implementor updates `tests/test_set_models.py` and `e2e/set_models_lifecycle.py`
in the same commit (single commit per slice = single task).

Schema note: `ai-harness task-create` persists only `title / spec / phase /
depends_on / subtasks` (verified in `src/ai_harness/commands/change.py`). The
description / references / acceptance text below lives in this table for human
reviewers; subtask `scenario` fields carry the req-id / G-W-T scenario linkage
that survives into `tasks.json`.

| id | title | files touched | spec req ids | prd scenarios | done-when |
| --- | --- | --- | --- | --- | --- |
| 1 | Add opencode change-agent vocabulary in `pure.py` | `src/ai_harness/modules/wizard/pure.py` (+8), `tests/test_set_models.py` (+~15) | `req:vocab-opencode-change-agents-001`, `req:vocab-opencode-change-agents-002` | (pure data — no end-user scenario) | `OPENCODE_CHANGE_AGENTS` tuple exported, `opencode_change_agents()` accessor returns the 8 named agents in pinned order, `AgentMode` StrEnum + `parse_agent_mode` helper exported; `test_opencode_change_agents_returns_eight_change_agents` and `test_parse_agent_mode_accepts_loop_and_change` pass |
| 2 | Add `-a`/`--agent` typer flag with strict validation | `src/ai_harness/commands/set_models.py` (+12), `tests/test_set_models.py` (+~30) | `req:cli-flag-agent-001`, `req:cli-flag-agent-002`, `req:cli-flag-agent-003`, `req:help-text-honest-001` | Scenarios 5, 6, 7 | typer exposes `-a`/`--agent` (default `"loop"`), routes through `parse_agent_mode`, rejects unknown / uppercase with `typer.BadParameter` naming the valid set `{loop, change}`, help text pins flag + valid values; wizard ignores the new param for now; `test_cli_set_models_default_agent_flag_is_loop`, `test_cli_set_models_unknown_agent_flag_errors`, `test_cli_set_models_uppercase_agent_flag_errors`, `test_cli_set_models_help_mentions_agent_flag_and_valid_values` pass |
| 3 | Thread `AgentMode` through opencode wizard dispatch | `src/ai_harness/modules/wizard/tui.py` (+~25), `tests/test_set_models.py` (+~50) | `req:wizard-opencode-agent-set-001`, `req:wizard-opencode-agent-set-002`, `req:wizard-opencode-agent-set-003`, `req:re-render-scope-001` | Scenarios 1, 2 (regression), 8 (regression) | `run_wizard_or_bail → run_wizard → run_opencode_wizard` accepts `agent_mode`; opencode branch picks `opencode_wizard_agents()` vs `opencode_change_agents()`; re-render call unchanged (relies on `_discover_loop_agents()` covering both dirs); `test_run_opencode_wizard_change_agent_set_writes_eight_overrides` (8 agents seeded → 8 override rows) and `test_run_opencode_wizard_change_agent_set_re_renders_change_agent_files` pass; existing opencode happy-path still green |
| 4 | Verify claude branch silently ignores `-a` flag | `src/ai_harness/modules/wizard/tui.py` (signature-only), `tests/test_set_models.py` (+~10) | `req:wizard-claude-agent-flag-ignored-001`, `req:wizard-claude-agent-flag-ignored-002` | Scenarios 3, 4 (regression) | claude branch accepts `agent_mode` for signature symmetry, ignores the value, runs existing claude loop wizard unchanged; no override-store pollution from `-a change`; `test_cli_set_models_agent_flag_with_claude_is_silently_ignored` passes (asserts no `change-*` / `propose` / `design` / `specs` / `tasks` keys after `set-models -o claude -a change`); existing claude happy-path still green |
| 5 | Add e2e sandbox arg-validation case | `e2e/set_models_lifecycle.py` (+~5) | `req:cli-flag-agent-002` (re-asserted at sandbox layer), `req:tests-and-e2e-coverage` | Scenario 6 (sandbox layer) | new case `_test_set_models_unknown_agent_flag_errors` runs `set-models -o opencode -a bogus`, asserts exit code 2 and the valid-values hint substring appears in combined stdout+stderr; full `e2e/set_models_lifecycle.py` file remains green |

## Slice ordering rationale

1 → 2 → 3 → 4 → 5 follows the call-graph: vocabulary (pure) → CLI plumbing
(typer) → wizard dispatch (opencode) → wizard dispatch (claude) → e2e
sandbox. Each commit is independently mergeable; running any single slice's
tests in isolation is sufficient to verify green (no slice's done-when
references a later slice).

## Files outside the budget

No edits to `src/ai_harness/modules/wizard/renderers.py` or
`src/ai_harness/modules/wizard/operations.py`. Re-render scope stays at 12
files via the existing `_discover_loop_agents()` walk (req:re-render-scope-001).

## Budget check

| file | estimated LOC delta |
| --- | --- |
| `src/ai_harness/commands/set_models.py` | +12 |
| `src/ai_harness/modules/wizard/tui.py` | +~25 |
| `src/ai_harness/modules/wizard/pure.py` | +8 |
| `tests/test_set_models.py` | +~100 |
| `e2e/set_models_lifecycle.py` | +~5 |
| **total** | **~150** |

Within the 150 LOC / 5 files envelope.