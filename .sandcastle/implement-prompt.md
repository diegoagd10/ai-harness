# Context

## Open issues (AFK-ready only)

!`gh issue list --state open --label ready-for-agent --limit 100 --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`

This is the sole source of truth for what work exists. Do not run an unfiltered query. If the list is empty, there is nothing to do.

## Current branch

You are working on branch `{{BRANCH}}` for this iteration. The reviewer will inspect `git diff main...{{BRANCH}}` after you finish, so you MUST commit on this exact branch.

- Stay on `{{BRANCH}}`. Do NOT `git checkout` another branch.
- Do NOT create scratch / sub-branches for the work.
- Do NOT rebase, force-push, or amend commits already on this branch.
- All commits you make will appear in `git log main..{{BRANCH}}`.

## Recent commits on this branch's lineage

!`git log {{BRANCH}} --oneline -10`

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
- **Branch model**: each outer iteration in `main.mts` generates a fresh `{{BRANCH}}` (timestamp-suffixed) and shares one sandbox across implementer + reviewer. After the reviewer approves, it merges `{{BRANCH}}` into local `main`. The next iteration starts a new branch.

## Priority order

1. **Bug fixes** — broken behaviour affecting users.
2. **Tracer bullets** — thin end-to-end slices that prove an approach works.
3. **Polish** — error messages, UX, docs.
4. **Refactors** — internal cleanups with no user-visible change.

Pick the highest-priority open issue whose labels do NOT mark it blocked by another still-open issue. If the chosen issue references a parent PRD (look at the body), read the PRD first.

## Workflow

1. **Explore** — read the issue body and comments. If it references a parent PRD, read it. Skim the relevant source files and existing tests BEFORE writing any code. Pull in `~/.agents/skills/tdd/SKILL.md` BEFORE writing tests.
2. **Plan** — state, in one paragraph, what you will change and why. Keep the diff as small as possible.
3. **Execute (RGR)** — Red → Green → Repeat → Refactor. Write a failing test first, then the smallest implementation to pass it. Refactor once green.
4. **Verify code quality** — all must pass:
   - `uv run ruff format --check .`
   - `uv run ruff check .`
   - `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e`
5. **Verify tests** — run `uv run pytest`. If the change touches install/uninstall lifecycle or anything in `e2e/`, ALSO run `./e2e/docker-test.sh` if Docker is available in the sandbox. Fix any failures before proceeding.
6. **Commit** — ONE git commit on the current branch. The message MUST follow the project's conventional-commits style:
   - Format: `<type>(<scope>): <subject>` (e.g. `feat(install): ...`, `refactor(sdd): ...`, `fix: ...`).
   - Allowed types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`.
   - Subject ≤ 72 chars, imperative mood, no trailing period.
   - Body: list the issue number (e.g. `Closes #24`), key decisions, and files changed.
   - NEVER use the `RALPH:` prefix — it is not a convention in this repo.
7. **Close** — close the issue with a single comment summarising what changed:
   `gh issue close <NUMBER> --comment "..."` — comment should list the commit SHA, the branch, and a 2-3 line summary.

## Skills

Load these via the Skill tool or by reading the SKILL.md directly. MANDATORY:

- **tdd** — `~/.agents/skills/tdd/SKILL.md`. Load BEFORE writing any code in step 3.

## Rules

- One issue per iteration. Do not batch.
- Do NOT close an issue until the commit is in and tests are green.
- Do NOT leave commented-out code or TODO comments in committed code.
- Do NOT use the `RALPH:` commit prefix; use conventional commits (see step 6).
- Do NOT switch branches. Stay on `{{BRANCH}}` for every commit.
- If you are blocked (missing context, failing tests you cannot fix, external dependency), `gh issue comment <NUMBER> --body "BLOCKED: ..."` describing what you need, then output `<promise>COMPLETE</promise>` to hand off — do NOT close the issue.

# Done

When the open-issues list is empty, OR you are blocked on every remaining issue, output:

<promise>COMPLETE</promise>
