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

- **src layout**: all package code under `src/ai_harness/`. Subdirs: `commands/` (typer adapters), `modules/` (domain logic), `resources/` (files copied at install time).
- **Thin CLI adapters**: each `commands/<name>.py` is a typer entrypoint that delegates to a single `modules/` function. No business logic in typer callbacks.
- **Single responsibility per module.** Prefer composition over inheritance.
- **Idempotent install / uninstall.** Re-running `install` is a no-op (or only updates drifted files); `uninstall` removes exactly what `install` created.
- **No new top-level packages** without an ADR in `docs/adr/`. Read `docs/adr/` before changing module boundaries.
- **Tuples → named types when they escape a function**. A tuple literal or `tuple[...]` annotation is acceptable when:
  - The shape is homogeneous (`tuple[str, ...]`, `tuple[int, int]` coords used arithmetically), OR
  - It is consumed by immediate unpacking within the same function and never crosses a function boundary.
  Replace with a `NamedTuple` (preferred for pure value records) or `frozen dataclass` (when methods/defaults are needed) when **any** of the following holds:
  - The tuple is returned (RETURN) or accepted as a parameter (PARAM) across module boundaries.
  - The shape has ≥ 2 heterogeneous fields (different types or different semantic roles).
  - The same shape repeats in ≥ 3 sites — DRY the record into one named type.
  Do NOT replace:
  - `dict.items()` unpacking (`for k, v in d.items()`) — that is iteration, not a record.
  - Tuple unpacking in `for` loops / multiple assignment.
  - Fixed-vocabulary module-level constants of homogeneous tuples (`CLAUDE_MODELS = ("haiku", ...)`).
  - One-off 2-tuples whose meaning is documented in the function's docstring and used in a single site (e.g. `(children, index)`).

## Commits

This section is the loop's source of truth for commit-message format — the implementor and
orchestrator defer to it rather than hardcoding a convention. Edit this section to change
how the loop writes commits (e.g. `[{issue_number}] <description>`).

- **Conventional Commits**: `<type>(<scope>): <subject>`. Allowed types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`.
- Subject ≤ 72 chars, imperative mood ("add", not "added"), no trailing period.
- `Closes #<NUMBER>` on the last line is *optional* — nothing in loop automation depends on it (the orchestrator closes issues via `gh issue close`, and PRD drain scans issue bodies, not commit messages). Teams may omit or replace it.
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
