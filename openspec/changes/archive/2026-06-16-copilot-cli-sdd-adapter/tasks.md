# Tasks: GitHub Copilot CLI SDD adapter

## Goal

Stage 16 `*.agent.md` files, JSON hooks, and skills under `~/.copilot/` via `CopilotInstaller` compose-at-install. Generic-ify shared `prompts/sdd/*.md` for all three adapters.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1380 |
| 400-line budget risk | High |
| Size exception needed | Yes |
| Delivery strategy | exception-ok |
| Suggested work units | Not needed (single PR) |

Decision needed before apply: Yes
Maintainer-approved size exception: Yes
400-line budget risk: High

## Phase 1 — RED gate (failing tests first)

- [x] 1.1 New `e2e/test_copilot_cli_lifecycle.py` — mirror test_harness_lifecycle, assert 16 agents + hooks + skills on install, fails because `_build_manifest` is minimal (~120 lines)
- [x] 1.2 New `tests/test_copilot_installer.py` — assert 16 composed agents, frontmatter validity, 30k budget, hook JSON with `task` allowlist + fail-closed, skills DirArtifact (~150 lines)
- [x] 1.3 Wire `copilot-cli-lifecycle` invoke task — add to `e2e/tasks.py` + root `tasks.py` (~30 lines)
- [x] 1.4 Confirm RED — `uv run pytest tests/test_copilot_installer.py` and `uv run inv copilot-cli-lifecycle` both fail. Capture output.

## Phase 2 — Implementation (GREEN)

- [x] 2.1 Inline JD/reviewer bodies in copilot-cli `agents/*.md` files (Claude pattern). Revert opencode.json to keep inline bodies. Delete 7 shared JD/reviewer body files from `prompts/sdd/`. Verify opencode e2e still passes (~50 lines)
- [x] 2.2 Create 9 SDD phase + orchestrator `*.md` files under `copilot-cli/agents/` — `sdd-orchestrator.md` + `sdd-{explore,...,archive}.md`. Frontmatter only (name/description/tools) WITH closing `---`, no body (~45 lines)
- [x] 2.3 Create 7 JD/reviewer `*.md` files under `copilot-cli/agents/` — `jd-{fix-agent,judge-a,judge-b}.md` + `review-{risk,readability,reliability,resilience}.md`. Frontmatter + inline body (Claude pattern). JD fix-agent gets write tools; judges/reviewers get read-only + `task` (~45 lines)
- [x] 2.4 Create `copilot-cli/hooks/sdd-pre-tool-use.json` — `version:1`, `preToolUse` matcher for `task` with 15-name allowlist (deny default), deny path matchers for `bash`/`view`/`create`/`edit` (~80 lines)
- [x] 2.5 Create `docs/agents/copilot/README.md` — document 16-agent layout, hooks-based access, per-agent model gap, no `hidden` flag, natural-language triggers, 30k budget (~80 lines)
- [x] 2.6 Extend `CopilotInstaller._build_manifest` — `ComposedFileArtifact` for 16 agents, `FileArtifact` for hooks, `DirArtifact` for skills. Validate frontmatter + 30k budget (~150 lines)
- [x] 2.7 Add `Path(".copilot/skills")` to `SKILLS_TARGET_DIRS` in `catalog.py` (~5 lines)
- [x] 2.8 Generic-ify 9 `prompts/sdd/*.md` — replace "OpenCode's native `task` tool" with "the platform's native `task` tool" (2×), expand skill paths adding `.agents/skills/`, `.claude/skills/`, `.copilot/skills/`. Additive only (~72 lines)
- [x] 2.9 Add "Copilot CLI" section to root `README.md` linking to `docs/agents/copilot/README.md` (~10 lines)

## Phase 3 — GREEN gate (verify)

- [x] 3.1 Run full test suite — `uv run pytest` (149 passed) + `uv run inv copilot-cli-lifecycle` (all assertions pass) + opencode/claude tests all pass
- [x] 3.2 Coverage check — `uv run pytest --cov=ai_harness` → 96% global, copilot.py 90% (uncovered = validation error paths)
- [x] 3.3 Run `e2e/docker-test.sh` — all e2e categories passed (copilot lifecycle, sdd-status, sdd-continue, workspace cleanup)
- [x] pyyaml fix — moved from `[dependency-groups].dev` to `[project].dependencies` (validation runs at install time, was failing in e2e sandbox with `ModuleNotFoundError: yaml`)

## Phase 4 — Refactor and final regression

- [x] 4.1 Refactor `_build_manifest` — SKIPPED (code well-organized in clear loops: 9 phase composed + 7 inline + hook + skills; ~100 lines but no over-extraction needed)
- [x] 4.2 Final regression — `uv run pytest` 149/149 + `uv run inv copilot-cli-lifecycle` + `e2e/docker-test.sh` all pass

---

**Per-phase lines**: P1 ~300 | P2 ~1097 | P3 ~0 | P4 ~30 | **Total ~1427**

**Mitigation**: `exception-ok` delivery with maintainer-approved size exception. Single PR.
