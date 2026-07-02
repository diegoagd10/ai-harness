# Implementation — agent-cli-contracts

## Commits
- eca074e — task 1: Add CLI contracts section to change-orchestrator.md (change-new, change-continue, unknown-command rule); tests: `uv run pytest tests/test_renderers.py` (133 passed)
- 13304de — task 2: Add CLI contracts section to change-tasks.md and fix dependsOn → depends_on; tests: `uv run pytest tests/test_renderers.py` (133 passed)
- 27be711 — task 3: Add CLI contracts section to change-implementor.md (task-next, task-done); tests: `uv run pytest tests/test_renderers.py` (133 passed)
- 4d851c0 — task 4: Add CLI contracts section to change-validator.md (task-list); tests: `uv run pytest tests/test_renderers.py` (133 passed)
- c30451e — task 5: Add CLI contracts section to change-archiver.md (change-archive); tests: `uv run pytest tests/test_renderers.py` (133 passed)

## Verification (task 6)

No new test edits. Ran the unchanged test gates listed in the PRD.

- `uv run pytest tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords` — PASSED. Every asserted substring (`task-create`, `task-next`, `task-list`, `ai-harness change-archive`, `docs: archive`, `budget`, `nextRecommended`, `verdict`) is present in unchanged prose. The negative `change start` / `change ready` substrings remain absent (asserted inline in the same test).
- `uv run pytest tests/test_renderers.py` (full file) — 133 passed.
- `uv run pytest tests/test_tasks.py` (covers `test_cli_task_create_parses_input_and_outputs_json`) — 16 passed; the `dependsOn` → `depends_on` fix did not regress the snake_case parser.
- `uv run pytest tests/test_change.py` — 24 passed.
- `uv run pytest tests/test_install.py` — 63 passed.
- `uv run pytest tests/test_set_models.py` — 110 passed.
- `uv run pytest` (full suite) — 534 passed.

## Validator fixup

Validator verdict: `fail` (1 critical — stale `dependsOn` token survived in the input-snippet rejection prose on line 47 of `change-tasks.md`).

- 1bf7438 — fixup: reword the rejection parenthetical in `change-tasks.md` from `the CLI rejects \`dependsOn\`` to `the CLI rejects any non-snake_case variant` so the camelCase token no longer survives anywhere in the prompt. Re-ran the validator gates:
  - `grep dependsOn src/ai_harness/resources/change-agent/change-tasks.md` — no matches.
  - `uv run pytest tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords` — PASSED (existing prompt-rendering substring assertions still hold).
  - `uv run pytest tests/test_renderers.py tests/test_tasks.py` — 149 passed.
  - `uv run pytest` (full suite) — 534 passed.

## Remaining
- none
