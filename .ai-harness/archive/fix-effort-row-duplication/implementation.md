# Implementation — fix-effort-row-duplication

## Commits
- 2017e2a — task 1: fix(wizard): dedupe effort-phase agent row prefix in both wizards; tests: `uv run pytest tests/test_set_models.py::test_run_claude_wizard_effort_phase_shows_unset_for_untouched_agent tests/test_set_models.py::test_run_opencode_wizard_effort_phase_shows_unset_for_reasoning_model tests/test_set_models.py::test_run_opencode_wizard_effort_phase_shows_na_for_non_reasoning_model tests/test_set_models.py::test_run_opencode_wizard_effort_phase_mixed_agent_set tests/test_set_models.py::test_ask_continue_or_agent_effort_phase_no_agent_dash_agent_substring tests/test_set_models.py::test_ask_opencode_continue_or_agent_effort_phase_no_agent_dash_agent_substring tests/test_set_models.py::test_ask_continue_or_agent_uses_dash_label_format tests/test_set_models.py::test_ask_opencode_continue_or_agent_uses_dash_label_format` (targeted, 8 passed) and `uv run pytest tests/ -q` (full gate, 562 passed).

## Subtasks
- 1.1 — Updated the four effort-phase scripted-wizard tests in `tests/test_set_models.py` (`test_run_claude_wizard_effort_phase_shows_unset_for_untouched_agent`, `test_run_opencode_wizard_effort_phase_shows_unset_for_reasoning_model`, `test_run_opencode_wizard_effort_phase_shows_na_for_non_reasoning_model`, `test_run_opencode_wizard_effort_phase_mixed_agent_set`) to assert the corrected single-prefix shape and to explicitly forbid the duplicated prefix.
- 1.2 — Added `test_ask_continue_or_agent_effort_phase_no_agent_dash_agent_substring` — a Claude regression test that drives `_ask_continue_or_agent` directly through the `_filterable_select` capture harness and asserts no choice title contains `f"{agent} - {agent}:"` for any agent whose label is passed in.
- 1.3 — Added `test_ask_opencode_continue_or_agent_effort_phase_no_agent_dash_agent_substring` — the OpenCode counterpart covering all three effort states (`high` / `(unset)` / `(NA)`).
- 1.4 — Branched `_ask_continue_or_agent` title assembly on `phase`: model phase keeps `f"{agent} - {selections.get(agent, 'sonnet')}"`, effort phase uses `selections.get(agent, '(unset)')` verbatim.
- 1.5 — Branched `_ask_opencode_continue_or_agent` title assembly on `phase` with the same per-phase shape (effort uses the value verbatim, model keeps the dash prefix).
- 1.6 — Updated the docstrings on both prompt functions to spell out the per-phase `selections[agent]` shape contract so a future caller cannot silently re-introduce the duplication by passing the wrong shape to the wrong phase.
- 1.7 — Full pytest suite green: `uv run pytest tests/ -q` → 562 passed.

## Remaining
- none
