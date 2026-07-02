# Coding Standards

## Style

- **Python >=3.12** (3.12 baseline; `pyproject.toml [project] requires-python` is authoritative).
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
- **Ruff** (config in `pyproject.toml` is authoritative — see `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]` for the full rules):
  - `line-length = 120`
  - `target-version = "py312"`
  - Lint families selected: `E`, `F`, `I`, `W`, `B`, `UP`
- **Dataclasses**: result / value objects use `@dataclass(frozen=True, slots=True)`. Scoped to value-bearing types only — not for builders, accumulators, or mutable state.

### Boundary rules

- **Subprocess**: all calls go behind an injectable seam (parameter or factory). No inline `subprocess.run` in business logic.
- **Filesystem**: use `pathlib.Path`; no string-paths in business logic.
- **Output**: all Typer output (`typer.echo`, `print`, JSON writes) lives at the command edge.
- **Test isolation**: tests isolate host mutation via `tmp_path` / `typer.testing.CliRunner` / `monkeypatch`; e2e via Docker.

## Testing

- **Tests target public behaviour and module seams, not internal helpers**; one test per public function is the floor, not the goal. Tests live under `tests/`, discovered by pytest.
- **Test names explain expected behaviour**: `test_install_writes_agents_md_to_home_dir`, not `test_install_1`.
- **Prefer real fixtures over mocks** unless the dependency is external (network, subprocess, filesystem). When mocking, load the `tdd` skill (`~/.agents/skills/tdd/SKILL.md`) for the mocking checklist.
- **Unit tests**: `uv run pytest` from the repo root.
- **E2E tests** (`e2e/`): run via `./e2e/docker-test.sh`, only needed when the diff touches install/uninstall paths or `e2e/`. Never run on the host — it provisions an isolated CLI sandbox and otherwise mutates `~/.local/bin`.

  The e2e suite follows a one-file invariant: all behaviour tests live in
  `e2e/e2e_test.sh` (the canonical suite); helpers live in `e2e/lib.sh`.
  When adding a test, add a `test_*` function to `e2e/e2e_test.sh` in the
  appropriate tier section. Tier 1 runs by default; Tier 2 (`RUN_FULL_E2E=1`)
  covers install/uninstall/set-models lifecycle; Tier 3 (`RUN_BACKUP_TESTS=1`)
  covers backup/restore.

## Architecture

- Typer commands: `src/ai_harness/commands/`
- Deep modules: `src/ai_harness/modules/`
- **Commands are thin Typer adapters** — they parse args and dispatch to module entry points. Business logic lives under `modules/` (deep modules per Ousterhout); commands contain **no business logic beyond parsing + dispatch**.

### CLI contract

(Scoped to commands — the Typer edge. Internal library-style helpers return values normally.)

- **stdout** carries data; **stderr** carries diagnostics.
- Machine-readable commands emit **JSON** on stdout.
- **Exit codes**: `0` on success, non-zero on failure.

## Commits

`[{change_name}][{task_id}] {slug}`

## Quality gates

Run from the project root. The validator and implementor read this exact list by name — keep gate names stable if you edit this section.

- **ruff format**: `uv run ruff format --check .`
- **ruff check**: `uv run ruff check .`
- **pylint duplicate-code**: `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e`
- **pytest**: `uv run pytest`
- **e2e** (only if the diff touches `e2e/` or install/uninstall behavior, and Docker is available): `./e2e/docker-test.sh`
- **coverage** (informational, via `pytest-cov`): no enforced threshold; coverage report printed for visibility.

A gate FAILs if its command exits non-zero. No commented-out code, no `TODO` comments in committed code.
