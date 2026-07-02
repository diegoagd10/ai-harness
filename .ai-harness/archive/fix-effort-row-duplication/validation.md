# Validation — fix-effort-row-duplication

## Verdict
verdict: pass
critical: 0

## Coverage
- task 1 / spec regression-guard-against-duplication / scenario scripted-wizard assertions match the corrected shape: pass
- task 1 / spec effort-row-no-duplication-claude / scenario Claude regression test snapshots effort-phase choices: pass
- task 1 / spec effort-row-no-duplication-opencode / scenario OpenCode regression test covers all effort states: pass
- task 1 / spec effort-row-no-duplication-claude / scenario effort-phase titles use the pre-rendered label verbatim: pass
- task 1 / spec effort-row-no-duplication-opencode / scenario effort-phase branch does not affect model-phase behavior: pass
- task 1 / spec effort-row-no-duplication-claude / scenario docstring names the per-phase contract: pass
- task 1 / spec model-row-format-preserved / scenario model-phase rows keep the "agent - model" shape: pass

## Findings
### CRITICAL
- none

### WARNING
- none

### SUGGESTION
- none

## Gates
- command: `uv run pytest tests/test_set_models.py::test_run_claude_wizard_effort_phase_shows_unset_for_untouched_agent tests/test_set_models.py::test_run_opencode_wizard_effort_phase_shows_unset_for_reasoning_model tests/test_set_models.py::test_run_opencode_wizard_effort_phase_shows_na_for_non_reasoning_model tests/test_set_models.py::test_run_opencode_wizard_effort_phase_mixed_agent_set tests/test_set_models.py::test_ask_continue_or_agent_effort_phase_no_agent_dash_agent_substring tests/test_set_models.py::test_ask_opencode_continue_or_agent_effort_phase_no_agent_dash_agent_substring tests/test_set_models.py::test_ask_continue_or_agent_uses_dash_label_format tests/test_set_models.py::test_ask_opencode_continue_or_agent_uses_dash_label_format -q` → 8 passed
- command: `uv run pytest tests/ -q` → 562 passed
