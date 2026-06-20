# Coding Standards

These rules apply to every commit on every branch. `.opencode/agent/validator.md` enforces them for the autonomous loop; `.opencode/agent/implementor.md` follows them when writing code.

This file is project-specific by design. To reuse the `.opencode/agent/` loop in another project, drop a new `CODING_STANDARDS.md` at that project's root — the agent prompts themselves don't change.

## Style

- **Python 3.12 only.** `.python-version` and `pyproject.toml [project] requires-python` are authoritative.
- **Line length: 120** (`tool.ruff.line-length`).
- **Imports**: isort-ordered (`I` rule). `from __future__ import annotations` MUST be the first import of every module that uses PEP-604 unions, generics, or forward references.
- **Type hints everywhere** — including private helpers and typer callbacks. Prefer builtin generics (`list[str]`, `dict[str, int]`) over `from typing import List/Dict`.
- **Docstrings**:
  - Module-level docstring REQUIRED on every module. Imperative tone, one line preferred.
  - Function docstrings REQUIRED on every public function. Imperative-tense one-liner; expand only when behaviour is non-obvious.
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `SCREAMING_SNAKE_CASE` for module-level constants. Private helpers prefixed with `_`.
- **Strings**: double quotes. f-strings for interpolation. Prefer `".".join(...)` over `+` concatenation.

## Testing

- **Every public function has at least one test.** Tests live under `tests/`, discovered by pytest.
- **Test names explain expected behaviour**: `test_install_writes_agents_md_to_home_dir`, not `test_install_1`.
- **Prefer real fixtures over mocks** unless the dependency is external (network, subprocess, filesystem). When mocking, load the `tdd` skill (`~/.agents/skills/tdd/SKILL.md`) for the mocking checklist.
- **Unit tests**: `uv run pytest` from the repo root.
- **E2E tests** (`e2e/`): run via `./e2e/docker-test.sh`, only needed when the diff touches install/uninstall paths or `e2e/`. Never run on the host — it provisions an isolated CLI sandbox and otherwise mutates `~/.local/bin`.

## Architecture

- **src layout**: all package code under `src/ai_harness/`. Subdirs: `commands/` (typer adapters), `modules/` (domain logic), `resources/` (files copied at install time).
- **Thin CLI adapters**: each `commands/<name>.py` is a typer entrypoint that delegates to a single `modules/` function. No business logic in typer callbacks.
- **Single responsibility per module.** Prefer composition over inheritance.
- **Idempotent install / uninstall.** Re-running `install` is a no-op (or only updates drifted files); `uninstall` removes exactly what `install` created.
- **No new top-level packages** without an ADR in `docs/adr/`. Read `docs/adr/` before changing module boundaries.

## Commits

- **Conventional Commits only**: `<type>(<scope>): <subject>`. Allowed types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`.
- Subject ≤ 72 chars, imperative mood ("add", not "added"), no trailing period.
- Body references the issue: `Closes #<NUMBER>` on the last line.
- **NEVER use the `RALPH:` prefix** — it is not a convention in this repo.
- One logical change per commit. Do not mix refactors with feature changes.

## Quality gates

Run from the project root. The validator and implementor read this exact list by name — keep gate names stable if you edit this section.

- **ruff format**: `uv run ruff format --check .`
- **ruff check**: `uv run ruff check .`
- **pylint duplicate-code**: `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e`
- **pytest**: `uv run pytest`
- **e2e** (only if the diff touches `e2e/` or install/uninstall behavior, and Docker is available): `./e2e/docker-test.sh`

A gate FAILs if its command exits non-zero. No commented-out code, no `TODO` comments in committed code.
