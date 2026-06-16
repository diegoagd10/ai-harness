# Tasks: Compose Claude SDD Phase Bodies at Install Time

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~300–350 |
| 400-line budget risk | Low |
| 800-line budget risk | Low |
| Size exception needed | No |
| Suggested work units | Not needed |
| Delivery strategy | exception-ok |

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: Low

Breakdown: `manifest.py` +25, `installer.py` +50, `claude.py` +20 net, `tests/test_claude_install.py` +150, `tests/test_installer.py` +50, `e2e/test_harness_lifecycle.py` +25. Total ~320 lines.

---

## Phase 1: RED Gate (e2e-first)

- [x] 1.1 Extend `e2e/test_harness_lifecycle.py` with `_assert_claude_agents(home, label)` helper that asserts: 8 SDD-phase files have frontmatter + `---` + body matching `prompts/sdd/<phase>.md` verbatim; 7 inline subagents copied byte-for-byte; orchestrator `SKILL.md` present; total of 15 `.md` files in `~/.claude/agents/`. Wired into `run_install_tests()` alongside existing asserts.

- [x] 1.2 Run `e2e/docker-test.sh` — MUST fail against the current frontmatter-only installer (proves the bug). Failure captured in `apply-report.md` TDD Cycle Evidence (RED): `sdd-explore` mismatch — actual 129 bytes (frontmatter only) vs expected 6488 bytes (frontmatter + 6355-byte body).

## Phase 2: Implementation

- [x] 2.1 Add `ComposedFileArtifact` frozen dataclass to `manifest.py` (`frontmatter_source`, `body_source`, `target_relative`, `backup_suffix`, `conflict_suffix`). Add `composed: list[ComposedFileArtifact] = field(default_factory=list)` to `ArtifactManifest`.

- [x] 2.2 Handle in `installer.py`: add `_prepare_composed_content(artifact, home) -> str` (reads both sources, returns `frontmatter + "\n---\n" + body`). In `install()` and `uninstall()`, loop over `manifest.composed` reusing the same backup/rotation/content-match logic as `FileArtifact`.

- [x] 2.3 Rewrite `claude.py`: add `_PHASE_NAMES: list[str]` (8) and `_INLINE_AGENTS: list[str]` (7) constants. `_build_manifest()` emits one `ComposedFileArtifact` per phase, one `FileArtifact` per inline agent, plus the existing orchestrator `DirArtifact`, skills `DirArtifact`, and `CLAUDE.md` `FileArtifact`.

## Phase 3: GREEN Gate

- [x] 3.1 Run `e2e/docker-test.sh` and `uv run pytest tests/ -x -v`. Both PASS. GREEN gate confirmed.

## Phase 4: Unit Tests + Regression

- [x] 4.1 Extend `tests/test_installer.py`: composed install writes frontmatter+body; rotates backup on conflict; uninstall removes matching content; uninstall restores backup.

- [x] 4.2 Run `uv run pytest tests/`. All existing + new tests must pass.

- [x] 4.3 Extend `e2e/test_harness_lifecycle.py`: add `_assert_claude_agents(home)` helper asserting 8 composed, 7 inline, orchestrator present. Run `./e2e/docker-test.sh` or `uv run pytest e2e/ -x`. _(Completed as task 1.1 in Phase 1: helper was written, wired into `run_install_tests()`, and exercised in Phase 1 RED + Phase 2 GREEN. Path updated to `.claude/skills/sdd-orchestrator/SKILL.md` in the orchestrator-path delta.)_

- [x] 4.4 Manual check: `uv run ai-harness install --home /tmp/test-home && cat /tmp/test-home/.claude/agents/sdd-apply.md`.

---

## Risks

None. All source files exist; `installer.py` loops follow straightforward copy-paste from existing `FileArtifact` loops. The 8 frontmatter and 8 body files are confirmed present.
