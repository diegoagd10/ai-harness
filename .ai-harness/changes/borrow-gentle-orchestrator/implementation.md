# Implementation — borrow-gentle-orchestrator

## Commits
- 65f5273 — task 1: Tighten change-orchestrator.md with explicit start/resume route, artifact-change invalidation reopening review on resume/compaction, session-scoped (phase, task_fingerprint) duplicate-launch guard, exact SKILL.md path injection (`Skills to load before work`), auto/interactive session mode with phase gates, and preserved parent-decomposition carve-out + CLI/state authority; tests: `uv run pytest tests/test_renderers.py tests/test_change.py -q` (106 passed; 1 pre-existing failure unrelated to the prompt edit: `test_change_orchestrator_meta_declares_primary_restricted_agent` asserts `openai/gpt-5.5` vs `minimax/MiniMax-M3`; verified pre-existing with `git stash`). Targeted gate + prompt-set lock tests pass: `test_change_orchestrator_body_has_human_review_gate_heading`, `test_change_orchestrator_body_gate_names_every_artifact`, `test_change_orchestrator_body_gate_requires_explicit_confirmation`, `test_change_orchestrator_body_gate_invalidates_on_artifact_change`, `test_change_orchestrator_body_gate_carves_out_parent_decomposition`, `test_change_orchestrator_body_gate_encodes_resume_semantics`, `test_change_orchestrator_description_unaffected_by_body_only_gate`, `test_change_agent_prompt_set_contains_expected_contract_keywords`.

## Remaining
- 2: Normalize change-explorer.md result envelope with semantic facts
- 3: Normalize change-implementor.md result envelope with semantic facts
- 4: Normalize change-validator.md result envelope with semantic facts
- 5: Document borrowed conductor disciplines in docs/design/change-orchestrator.md
- 6: Add render contract tests for borrowed conductor disciplines
