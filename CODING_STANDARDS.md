# Coding Standards

## Style

- **Python 3.12 only.** `.python-version` and `pyproject.toml [project] requires-python` are authoritative.
- **Imports**: `from __future__ import annotations` MUST be the first import of every module that uses PEP-604 unions, generics, or forward references.
- **Type hints everywhere** — including private helpers and typer callbacks. Prefer builtin generics (`list[str]`, `dict[str, int]`) over `from typing import List/Dict`.
- **Docstrings**:
  - Module-level docstring REQUIRED on every module. Imperative tone, one line preferred.
  - Function docstrings REQUIRED on every public function. Imperative-tense one-liner; expand only when behaviour is non-obvious.
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `SCREAMING_SNAKE_CASE` for module-level constants. Private helpers prefixed with `_`.
- **Strings**: double quotes. f-strings for interpolation. Prefer `".".join(...)` over `+` concatenation.
- **Method ordering inside a class**:
  1. `__init__` first (PEP 8).
  2. All other dunder methods next (`__repr__`, `__eq__`, etc.).
  3. Public methods (no leading underscore), grouped by responsibility.
  4. Private methods (`_`-prefixed) last.
  - A private helper that is *only* called by the immediately preceding public method belongs next to that method, not at the bottom. Rule of thumb: if `bar` is called exclusively by `foo`, keep `bar` directly after `foo`.

## Testing

- **Every public function has at least one test.** Tests live under `tests/`, discovered by pytest.
- **Test names explain expected behaviour**: `test_install_writes_agents_md_to_home_dir`, not `test_install_1`.
- **Prefer real fixtures over mocks** unless the dependency is external (network, subprocess, filesystem). When mocking, load the `tdd` skill (`~/.agents/skills/tdd/SKILL.md`) for the mocking checklist.
- **Unit tests**: `uv run pytest` from the repo root.
- **E2E tests** (`e2e/`): run via `./e2e/docker-test.sh`, only needed when the diff touches install/uninstall paths or `e2e/`. Never run on the host — it provisions an isolated CLI sandbox and otherwise mutates `~/.local/bin`.

## Architecture

- Typer commands: `src/ai_harness/commands/`
- Deep modules: `src/ai_harness/modules/`

## Commits

`[{issue_number}] {slug}`

## Quality gates

Run from the project root. The validator and implementor read this exact list by name — keep gate names stable if you edit this section.

- **ruff format**: `uv run ruff format --check .`
- **ruff check**: `uv run ruff check .`
- **pylint duplicate-code**: `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e`
- **pytest**: `uv run pytest`
- **e2e** (only if the diff touches `e2e/` or install/uninstall behavior, and Docker is available): `./e2e/docker-test.sh`

A gate FAILs if its command exits non-zero. No commented-out code, no `TODO` comments in committed code.
