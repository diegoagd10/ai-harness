# Coding Standards

These rules apply to every commit on every branch. The reviewer (`.sandcastle/review-prompt.md`) enforces them.

## Style

- **Python 3.12 only.** `.python-version` and `pyproject.toml [project] requires-python` are authoritative.
- **Line length: 120** (`tool.ruff.line-length`).
- **Imports**: isort-ordered (`I` rule). `from __future__ import annotations` MUST be the first import of every module that uses PEP-604 unions, generics, or forward references.
- **Type hints everywhere** — including `@task(ctx) -> None`, typer callbacks, and private helpers. Prefer builtin generics (`list[str]`, `dict[str, int]`) over `from typing import List/Dict`.
- **Docstrings**:
  - Module-level docstring REQUIRED on every module. Imperative tone, one line preferred (`"""Install command — thin typer adapter over install_targets."""`).
  - Function docstrings REQUIRED on every public function. Imperative-tense one-liner; expand only when behaviour is non-obvious.
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `SCREAMING_SNAKE_CASE` for module-level constants. Private helpers prefixed with `_` (e.g. `_with_generic`, `_cleanup`).
- **Strings**: use double quotes. f-strings for interpolation. Prefer `".".join(...)` over `+` concatenation.
- **User-facing CLI help text** uses unicode arrows for direction (e.g. `"Omit → generic only."`) — this is established repo style.

## Testing

- **Every public function has at least one test.** Tests live under `tests/` and are discovered by pytest.
- **Test names explain expected behaviour**: `test_install_writes_agents_md_to_home_dir`, not `test_install_1`.
- **Prefer real fixtures over mocks** unless the dependency is external (network, subprocess, filesystem). When mocking, load the `tdd` skill (`~/.agents/skills/tdd/SKILL.md`) for the mocking checklist.
- **Unit tests**: `uv run pytest` from the repo root.
- **E2E tests** (`e2e/`): Invoke tasks — `uv run inv install`, `uv run inv uninstall`, `uv run inv test`. The full suite runs inside a Docker image via `./e2e/docker-test.sh` and provisions an isolated CLI sandbox; never run it on the host unless you intend to mutate `~/.local/bin`.
- **Coverage**: `uv run pytest --cov`. `tool.coverage.report.show_missing = true` so missing lines are explicit.

## Architecture

- **src layout**: all package code under `src/ai_harness/`. Subdirs: `commands/` (typer adapters), `modules/` (domain logic), `resources/` (files copied at install time).
- **Thin CLI adapters**: each `commands/<name>.py` is a typer entrypoint that delegates to a single `modules/` function. No business logic in typer callbacks.
- **Single responsibility per module**. Prefer composition over inheritance.
- **Idempotent install / uninstall**. Re-running `install` is a no-op (or only updates drifted files); `uninstall` removes exactly what `install` created.
- **No new top-level packages** without an ADR in `docs/adr/`. Read `docs/adr/` before changing module boundaries.

## Commits

- **Conventional Commits only**: `<type>(<scope>): <subject>`. Allowed types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`.
- Subject ≤ 72 chars, imperative mood ("add", not "added"), no trailing period.
- Body references the issue: `Closes #<NUMBER>` on the last line.
- **NEVER use the `RALPH:` prefix** — it is not a convention in this repo.
- One logical change per commit. Do not mix refactors with feature changes.

## What the reviewer will check

- `uv run ruff format --check .` — must pass.
- `uv run ruff check .` — must pass.
- `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e` — must pass.
- `uv run pytest` — must be green.
- `./e2e/docker-test.sh` if the diff touched `e2e/` or install/uninstall behaviour.
- Conventional-commits format on every new commit.
- No commented-out code, no `TODO` comments in committed code.
