# Task

Review the code changes on branch `{{BRANCH}}` and improve clarity, consistency, and maintainability while preserving exact functionality. Once the diff is clean, merge `{{BRANCH}}` into local `main` so the work lands.

# Context

## How to read the diff

Do NOT rely on any inlined diff in this prompt — large diffs blow past the OS
argument limit and the reviewer will fail to start. Read the diff yourself from
the sandbox worktree, which is the sandbox's CWD:

```bash
git diff main...{{BRANCH}}
git log main..{{BRANCH}} --oneline
```

If the diff is large, page it instead of dumping it all at once:

```bash
git diff main...{{BRANCH}} | wc -l            # size check
git diff main...{{BRANCH}} --stat             # map of touched files
git diff main...{{BRANCH}} -- <path>          # focus on one path
git diff main...{{BRANCH}} | less             # paginate
git show <commit-sha>                         # inspect a specific commit
```

Use `pwd` if you need to confirm the worktree path.

## Project context

- **Language / version**: Python 3.12 (see `.python-version`, `pyproject.toml [project] requires-python`).
- **Package manager / build**: `uv`. Install/sync with `uv sync` (dev group auto-included). CLI entrypoint: `ai-harness = "ai_harness.main:main"` (after `uv tool install .`).
- **Source layout**: src layout. Package code under `src/ai_harness/`. Subdirs: `commands/` (typer adapters), `modules/` (domain logic), `resources/` (files copied at install time).
- **Tests**:
  - Unit: `tests/` — run with `uv run pytest`. Pytest config in `pyproject.toml [tool.pytest.ini_options]`.
  - E2E: `e2e/` — Invoke tasks `install`, `uninstall`, `test`. Run on host with `uv run inv test`, or inside the e2e image with `./e2e/docker-test.sh` (requires Docker). The e2e suite provisions the CLI into an isolated sandbox, so DO NOT run it on the host unless you intend to mutate `~/.local/bin`.
- **Lint / format**:
  - `uv run ruff format --check .` — formatting gate.
  - `uv run ruff check .` — lint gate (uses config in `pyproject.toml [tool.ruff]`).
  - `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e` — duplicate-code check (no pylint project config; ad-hoc invocation).
- **Issue tracker**: GitHub via the `gh` CLI. Conventions in `docs/agents/issue-tracker.md`. Triage labels in `docs/agents/triage-labels.md`.
- **Skills available**: `~/.agents/skills/` is bind-mounted read-only. Load `tdd` from `~/.agents/skills/tdd/SKILL.md` (or via the Skill tool, if configured). Do NOT invent skills.
- **Branch model**: you are on `{{BRANCH}}`. The implementer has already pushed commits. After you commit any refinements, merge `{{BRANCH}}` into `main` locally — see Execution step 3.

## Coding standards

Apply the rules in `/.sandcastle/CODING_STANDARDS.md`. They are project-specific (conventional-commits format, src layout, type hints, docstring style, etc.) — load them BEFORE reviewing.

# Review process

1. **Understand the change** — read the diff and commits. Skim the surrounding code in the touched files.
2. **Look for improvements** — duplicated logic, unnecessary nesting, redundant abstractions, magic numbers, unclear names, deep nesting, nested ternaries, dead code. Prefer clarity over brevity.
3. **Check correctness** —
   - Does the implementation match the issue's intent? Are edge cases handled?
   - Are new/changed behaviours covered by tests?
   - Any unsafe casts, unchecked assumptions, injection vulnerabilities, credential leaks?
   - Any import / type / lint violations a quick `uv run ruff check` would catch?
4. **Maintain balance** — do NOT over-simplify. Don't merge two concerns into one function, don't strip helpful abstractions, don't remove error handling that prevents silent failures.
5. **Preserve functionality** — never change WHAT the code does, only HOW.

# Execution

1. **Apply refinements** directly on `{{BRANCH}}`. Commit each non-trivial refinement with a conventional-commits message (`refactor(<scope>): ...`, `fix(<scope>): ...`, etc.). NEVER use `RALPH:`.
2. **Verify** the refined branch is green:
   - `uv run ruff format --check .`
   - `uv run ruff check .`
   - `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e`
   - `uv run pytest`
   - `./e2e/docker-test.sh` if Docker is available and the diff touched `e2e/` or install/uninstall semantics.
3. **Merge to main** — once green and stable, fast-forward local `main` to `{{BRANCH}}`:
   ```
   git checkout main
   git merge --ff-only {{BRANCH}}
   ```
   If `main` has advanced (extremely unlikely in this sequential loop), rebase `{{BRANCH}}` onto `main` first, re-run the verification in step 2, then merge. Do NOT open a PR, do NOT push — this loop is local-only.
4. If the code is already clean, skip step 1 and proceed straight to step 3.

Output `<promise>COMPLETE</promise>` after the merge (or after step 4 if no refinements were needed).
