# Implementation — deprecate-loop

## Commits
- da7ca41 — task 1: purge loop-agent resources and update renderer registry; tests: uv run pytest tests/test_set_models.py tests/test_renderers.py tests/test_install.py
- 653afa6 — task 2: collapse wizard vocabulary to change-only; tests: uv run pytest tests/test_set_models.py
- e1a0359 — task 3: clean loop prose from operations.py and worktree.py docstrings; tests: uv run pytest (533 passed)
- 327ce8b — task 4: add ADR deprecation headers and remove loop prose from docs; tests: uv run pytest (533 passed)
- 9facf01 — task 5 (fix loop): `_write_persona_and_skills` walked the destination tree to enumerate copied files; the first install's leftover `~/.claude/skills/change-orchestrator/SKILL.md` got double-counted on the second install, so the install manifest's claude entry grew to 16 paths and the md5 changed between reinstalls. Walk the source tree instead so the writer records what THIS call copied. Resolves the e2e CRITICAL on `test_idempotent_reinstall`; tests: uv run pytest (534 passed), uv run ruff format --check, uv run ruff check, RUN_FULL_E2E=1 ./e2e/docker-test.sh (Tier 1 43/43, Tier 2 30/30).

## Remaining
- none
