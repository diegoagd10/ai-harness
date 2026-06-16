# Tasks: Claude Code SDD agent graph parity (`agent-clis/claude`)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1450 (15 agents + skill + README + main.py + tests + e2e) |
| 400-line budget risk | High |
| Size exception needed | No (slice into work units) |
| Suggested work units | 4 (see below) |
| Delivery strategy | single-pr |

Decision needed before apply: Yes
Maintainer-approved size exception: No
400-line budget risk: High

### Suggested Work Units (each ≤400 review lines; implement in order)

| Unit | Goal | Forecast | Delivery |
|------|------|----------|----------|
| 1 | Compose/install/uninstall plumbing in `main.py` + `write_with_backup`/`_compose_agent_body` helpers + 2 phase agents (`sdd-design`, `sdd-tasks`) + unit tests. Smallest coherent vertical: install→compose→backup→uninstall proven end-to-end. **Recommended first.** | ~360 | single PR |
| 2 | Remaining 6 phase agents (explore, propose, spec, apply, verify, archive) frontmatter files + per-agent compose/tools/model unit tests | ~330 | single PR |
| 3 | 7 inline agents (3 judgment-day + 4 R1–R4 reviewers) + read-only-tools unit tests | ~390 | single PR |
| 4 | Orchestrator `SKILL.md` + `README.md` + e2e lifecycle assertions (`e2e/docker-test.sh`) | ~370 | single PR |

## Phase 1: Infrastructure — helpers + plumbing (Unit 1)

- [ ] 1.1 RED: `tests/test_install.py` — assert `write_with_backup(target, content)` writes content when target absent; backs up to `.ai-harness-backup` then writes when target differs; is a no-op (no backup) when content is byte-identical
- [ ] 1.2 RED: `tests/test_install.py` — assert second differing write routes to `.ai-harness-conflict-backup` (and `.N`) when `.ai-harness-backup` exists
- [ ] 1.3 GREEN: extract `write_with_backup()` in `src/ai_harness/main.py` from the 3 inlined OpenCode backup blocks; refactor those call sites to use it
- [ ] 1.4 GREEN: add path constants `CLAUDE_AGENTS_SRC`, `CLAUDE_AGENTS_TARGET_DIR`, `CLAUDE_ORCH_SKILL_SRC`, `CLAUDE_ORCH_SKILL_TARGET_DIR` in `main.py` (reuse `OPENCODE_*_SUFFIX`)

## Phase 2: Implementation — compose + first agents (Unit 1)

- [ ] 2.1 Create `resources/agent-clis/claude/agents/sdd-design.md` (frontmatter only: `name`, `description`, `tools: [Read, Edit, Write, Bash]`, `model: opus`)
- [ ] 2.2 Create `resources/agent-clis/claude/agents/sdd-tasks.md` (frontmatter only; `tools: [Read, Edit, Write, Bash]`, `model: sonnet`)
- [ ] 2.3 RED: `tests/test_install.py` — `_compose_agent_body(src, home)` joins frontmatter + `prompts/sdd/<stem>.md` verbatim for `sdd-design`; substitutes `{{HOME}}`; passes inline (no shared prompt) files through unchanged
- [ ] 2.4 GREEN: implement `_compose_agent_body()` in `main.py` (derive phase from `prompts/sdd/<stem>.md` existence per design Decision 2)
- [ ] 2.5 RED: `tests/test_install.py` — `install()` stages `.claude/agents/sdd-design.md` whose body == `prompts/sdd/sdd-design.md` content under frontmatter; creates `.claude/agents/` when absent
- [ ] 2.6 GREEN: add Claude agents compose+install block to `install()` iterating `CLAUDE_AGENTS_SRC.iterdir()` via `write_with_backup`
- [ ] 2.7 RED: `tests/test_uninstall.py` — unmodified staged agent removed + `.ai-harness-backup` restored; user-modified file preserved; conflict backup not restored
- [ ] 2.8 GREEN: add Claude agents uninstall block (content-match guard, enumerate by `CLAUDE_AGENTS_SRC.iterdir()`)
- [ ] 2.9 GREEN: run `uv run pytest` — Unit 1 green

## Phase 3: Implementation — remaining phase agents (Unit 2)

- [ ] 3.1 Create 6 frontmatter-only phase files in `resources/agent-clis/claude/agents/`: `sdd-explore.md` (opus), `sdd-propose.md` (opus), `sdd-spec.md` (opus), `sdd-apply.md` (inherit), `sdd-verify.md` (sonnet), `sdd-archive.md` (haiku) — tools per design table
- [ ] 3.2 RED: `tests/test_install.py` — parametrized: each phase agent body == its `prompts/sdd/<stem>.md` verbatim; no `@import`/`{file:...}` present
- [ ] 3.3 RED: `tests/test_install.py` — exactly 8 phase agents staged; each frontmatter declares expected `model` alias and `tools` allow-list
- [ ] 3.4 GREEN: confirm compose block handles all 8; run `uv run pytest`

## Phase 4: Implementation — inline judge/reviewer agents (Unit 3)

- [ ] 4.1 Create 3 judgment-day agents (`jd-judge-a.md`, `jd-judge-b.md`, `jd-fix-agent.md`) with full inline bodies + frontmatter (judges `opus`/read-only `[Read, Bash]`; fix-agent `inherit`/`[Read, Edit, Write, Bash]`)
- [ ] 4.2 Create 4 reviewer agents (`review-risk.md` opus, `review-readability.md`/`review-reliability.md`/`review-resilience.md` sonnet) with inline bodies + read-only `tools: [Read, Bash]`
- [ ] 4.3 RED: `tests/test_install.py` — reviewers + judges grant read-style tools only, never `Edit`/`Write`; inline bodies install verbatim (no compose, no shared-prompt reference)
- [ ] 4.4 RED: `tests/test_install.py` — exactly 15 agents staged total; no `model-variants`/`sdd-model-assignments` asset under `agent-clis/claude/`
- [ ] 4.5 GREEN: run `uv run pytest`

## Phase 5: Implementation — orchestrator skill + docs + e2e (Unit 4)

- [ ] 5.1 Create `resources/agent-clis/claude/sdd-orchestrator/SKILL.md` (frontmatter `name`/`description`, NO `context: fork`; body from `prompts/sdd/sdd-orchestrator.md` embedded at authoring time)
- [ ] 5.2 RED: `tests/test_install.py` — `install()` stages `~/.claude/skills/sdd-orchestrator/SKILL.md`; frontmatter has no `context: fork`
- [ ] 5.3 GREEN: add orchestrator-skill flat-copy install + uninstall block in `main.py`; `tests/test_uninstall.py` restore/preserve coverage
- [ ] 5.4 Create `resources/agent-clis/claude/README.md` (graph description + `{{HOME}}` compose mechanism)

## Phase 6: Testing — e2e lifecycle (Unit 4)

- [ ] 6.1 RED: `e2e/e2e_test.sh` — assert fresh install stages 15 `.claude/agents/*.md` + orchestrator skill; a phase body matches its `prompts/sdd/<phase>.md`
- [ ] 6.2 RED: `e2e/e2e_test.sh` — assert reinstall is idempotent (no spurious backup) and uninstall removes the graph
- [ ] 6.3 GREEN: run `e2e/docker-test.sh` — full lifecycle passes
- [ ] 6.4 Run `uv run pytest` + `e2e/docker-test.sh` — all green; confirm no literal `{{HOME}}` in installed files
