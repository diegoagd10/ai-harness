# Apply Report — claude-installer-composition

**Phase**: 1 of 2 (RED gate only — e2e tests written and failing; no production code yet)
**Date**: 2026-06-16
**Strict TDD**: red-first confirmed

## Tasks Completed This Round

- [x] **1.1** Extend `e2e/test_harness_lifecycle.py` with `_assert_claude_agents(home)` helper.
- [x] **1.2** Run e2e suite, capture failure, document it below.

## TDD Cycle Evidence

### RED — e2e test fails against current installer

**Command run**: `e2e/docker-test.sh`
**Exit code**: non-zero (Traceback / AssertionError)
**Failing test**: `_assert_claude_agents` called from `run_install_tests` (fresh install path)
**Failure excerpt**:
```
Traceback (most recent call last):
  File "/build/e2e/tasks.py", line 33, in install
    _provision_and_run(run_install_tests, ctx)
  File "/build/e2e/tasks.py", line 23, in _provision_and_run
    runner(bin_dir)
  File "/build/e2e/test_harness_lifecycle.py", line 184, in run_install_tests
    _assert_claude_agents(home1, "fresh")
  File "/build/e2e/test_harness_lifecycle.py", line 134, in _assert_claude_agents
    raise AssertionError(
AssertionError: claude subagent sdd-explore (fresh): missing composed body from prompts/sdd/sdd-explore.md
  actual length:   129
  expected length: 6488
  expected suffix:  ...--- + body(6355 chars)
```

**Why this failure proves the test is meaningful**: the current `installers/claude.py` uses `DirArtifact` to copy agent files from `agent-clis/claude/agents/` verbatim. The SDD phase files in that directory contain only YAML frontmatter (129 bytes for `sdd-explore.md`). The new `_assert_claude_agents` helper requires each SDD phase agent's installed file to be composed — frontmatter + `\n---\n` separator + the corresponding body from `prompts/sdd/<name>.md`. Because the body is missing, the asserted equality fails. Once `installers/claude.py` is rewritten to compose the files during installation, the same asserts will pass.

## Files Modified

- `e2e/test_harness_lifecycle.py` — added `CLAUDE_AGENTS_SRC` and `CLAUDE_ORCHESTRATOR_SRC` constants, `_SDD_PHASE_NAMES` and `_INLINE_AGENT_NAMES` tuples, `_assert_claude_agents()` helper function, and wired its call into `run_install_tests()` after the existing `_assert_sdd_prompts()` call.

## Files NOT Modified (intentional — Phase 2's job)

- `src/ai_harness/artifacts/manifest.py`
- `src/ai_harness/artifacts/installer.py`
- `src/ai_harness/artifacts/installers/claude.py`
- `tests/test_installer.py`
- `tests/test_claude_install.py` (does not exist yet)

## Tasks Remaining

- 2.1, 2.2, 2.3 — implement production code (next apply phase)
- 3.1 — re-run e2e, expect GREEN
- 4.1, 4.2, 4.3, 4.4 — unit tests + manual check

---

## TDD Cycle Evidence (Phase 2: Implementation + GREEN)

### Safety net (before Phase 2)
- **Command run**: `uv run pytest tests/ -x -v`
- **Exit code**: 0
- **Result**: 135 passed, 0 failed. Baseline captured — no pre-existing failures in the files being modified.

### Command run (e2e GREEN confirmation)
```
e2e/docker-test.sh
```

### Exit code
0

### Passing tests
Full e2e suite output includes:
```
=== Harness Lifecycle: fresh install
  PASS: fresh install assertions
=== Harness Lifecycle: reinstall with pre-existing state
  PASS: user-authored skill preserved
  PASS: user-authored custom prompt preserved
  PASS: reinstall with preservation assertions
  (pre-seed install done)
=== Harness Lifecycle: uninstall
  PASS: pre-existing opencode AGENTS.md restored
  PASS: pre-existing opencode.json restored
  PASS: pre-existing prompts/sdd/sdd-apply.md restored
  PASS: user-authored skill preserved after uninstall
  PASS: user-authored prompt preserved after uninstall
=== Harness Lifecycle: all uninstall assertions passed
...
=== All e2e categories passed ===
```

The `_assert_claude_agents()` helper now passes for all 15 subagent files:
- 8 SDD phases now correctly composed (frontmatter + `---` + body verbatim)
- 7 inline subagents copied byte-for-byte
- Orchestrator SKILL.md present
- Agent count = 15

### Regression check (post-Phase 2)
- **Command run**: `uv run pytest tests/ -x -v`
- **Exit code**: 0
- **Result**: 135 passed, 0 failed. All existing tests still pass; no regressions.

### Files modified in this phase
- **`src/ai_harness/artifacts/manifest.py`** — added `ComposedFileArtifact` frozen dataclass with `frontmatter_source`, `body_source`, `target_relative`, `template`, `backup_suffix`, `conflict_suffix` fields. Added `composed: list[ComposedFileArtifact]` field to `ArtifactManifest` with `default_factory=list` for backward compatibility. Added `field` to `dataclasses` import.
- **`src/ai_harness/artifacts/installer.py`** — imported `ComposedFileArtifact`. Added `_prepare_composed_content()` private function (reads both sources, joins with `\n---\n`, applies template substitution to full composed result). Added `ComposedFileArtifact` loops in `install()` (backup/rotation/content-prepare/write) and `uninstall()` (content-match removal + backup restore), mirroring the existing `FileArtifact` loops.
- **`src/ai_harness/artifacts/installers/claude.py`** — rewrote `_build_manifest()`: added module-level `_PHASE_NAMES` (8) and `_INLINE_AGENTS` (7) constants. Replaced `DirArtifact(agents_dir)` with 8 `ComposedFileArtifact` entries (frontmatter from `agent-clis/claude/agents/` + body from `prompts/sdd/`) and 7 `FileArtifact` entries for inline agents. Added `prompts_dir` to `ClaudeAssets`. Kept existing orchestrator `DirArtifact`, skills `DirArtifact`, and `CLAUDE.md` `FileArtifact`.

### Tasks completed this round
- [x] 2.1, 2.2, 2.3, 3.1

### Tasks remaining
- 4.1, 4.2 — unit tests for `ComposedFileArtifact` lifecycle (next apply launch).
- 4.3 — extend e2e (already done in Phase 1 as 1.1).
- 4.4 — manual check.

### Notes / Deviations
- **`ComposedFileArtifact` includes a `template` field** (`dict[str, str]`, default `{}`). The design notes this as a YAGNI risk since none of the 8 frontmatter files use `{{HOME}}`. Included per the task spec for symmetry with `FileArtifact` and future-proofing. Template substitution is applied to the FULL composed result (frontmatter + separator + body), not to the individual sources.
- **`_prepare_composed_content` accepts `home: Path`** parameter (unused in body) for signature consistency with `_prepare_content`. This avoids a confusing asymmetry between the two content-preparation helpers.
- **Implementation matches design**: ADR-1 (separate type), ADR-2 (inline in installer.py), ADR-3 (duplicated backup/rotation loops), ADR-4 (module-level constants), ADR-6 (one `FileArtifact` per inline agent) are all followed exactly.

---

## Risks / Notes

- None. The RED gate is clean: the current installer copies frontmatter-only source files, the new test demands composed content, and the failure is on the very first SDD phase agent checked (`sdd-explore`). The helper correctly iterates all 8 phases + 7 inline agents + orchestrator SKILL.md + file count (15). Since the first check fails, subsequent checks are not reached — they remain as untested but-correct assertions that will be exercised once Phase 2 composes the files.
- The Docker-based e2e runner (`e2e/docker-test.sh`) was used; it builds the CLI from source and exercises the full install lifecycle in an isolated container.

---

## Delta: Orchestrator moved to `.claude/skills/sdd-orchestrator/`

**Reason**: the SDD orchestrator is a Claude Code skill (not a subagent), and per Claude Code convention skills live under `.claude/skills/<name>/SKILL.md`. The previous install path `.claude/sdd-orchestrator/` placed it outside the skills namespace.

### TDD Cycle Evidence

#### RED — e2e test fails against current installer
- **Command**: `e2e/docker-test.sh`
- **Exit code**: non-zero (AssertionError)
- **Failing assertion**:
  ```
  AssertionError: claude sdd-orchestrator SKILL.md (fresh): missing — /tmp/e2e-home-cgz7yjbj/.claude/skills/sdd-orchestrator/SKILL.md
  ```
- **Why this proves the test is meaningful**: the helper now expects the orchestrator at `.claude/skills/sdd-orchestrator/SKILL.md`, but the installer still writes to `.claude/sdd-orchestrator/`.

#### GREEN — implementation matches the new path
- **Command**: `e2e/docker-test.sh`
- **Exit code**: 0
- **Passing tests**:
  ```
  === Harness Lifecycle: fresh install
    PASS: fresh install assertions
  === Harness Lifecycle: reinstall with pre-existing state
    PASS: user-authored skill preserved
    PASS: user-authored custom prompt preserved
    PASS: reinstall with preservation assertions
    (pre-seed install done)
  === Harness Lifecycle: uninstall
    PASS: pre-existing opencode AGENTS.md restored
    PASS: pre-existing opencode.json restored
    PASS: pre-existing prompts/sdd/sdd-apply.md restored
    PASS: user-authored skill preserved after uninstall
    PASS: user-authored prompt preserved after uninstall
  === Harness Lifecycle: all uninstall assertions passed
  ...
  === All e2e categories passed ===
  ```

### Files changed in this delta
- `src/ai_harness/artifacts/installers/claude.py` — line 132: `target_relative` updated from `.claude/sdd-orchestrator` to `.claude/skills/sdd-orchestrator`, comment and module docstring updated.
- `e2e/test_harness_lifecycle.py` — line 115: orchestrator path assert updated to `.claude/skills/sdd-orchestrator/SKILL.md`.
- `openspec/changes/claude-installer-composition/specs/claude-installer-composition/spec.md` — line 54: "Orchestrator skill unchanged" scenario path synced to `~/.claude/skills/sdd-orchestrator/SKILL.md`.
- `openspec/changes/claude-installer-composition/design.md` — no hardcoded paths; no changes needed.
- `openspec/changes/claude-installer-composition/apply-report.md` — this delta section.

### No tasks.md update
This is a small delta within Phase 2/3 work; tasks.md 2.1–3.1 already cover it (claude.py rewrite + GREEN confirmation). The original tasks 4.1–4.4 remain pending for the next apply launch.

---

## Phase 4: Unit Tests + Manual Check

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 4.1 (install) | `tests/test_installer.py` | Unit | ✅ 135/135 | ✅ Written | ✅ Passed | ✅ 2 cases (happy + conflict rotation) | ✅ Clean |
| 4.1 (uninstall) | `tests/test_installer.py` | Unit | ✅ 135/135 | ✅ Written | ✅ Passed | ✅ 2 cases (match removal + backup restore) | ✅ Clean |
| 4.2 | `tests/test_installer.py` | Unit | ✅ 135/135 | ✅ Written | ✅ Passed | ➖ Single (full suite run) | ➖ None needed |
| 4.4 | Manual | — | N/A | N/A | N/A | N/A | N/A |

### Unit tests added

4 new tests in `tests/test_installer.py`:

- `test_composed_install_writes_frontmatter_and_body` — happy path: `ComposedFileArtifact` install produces frontmatter + `---` separator + body. Verifies `_prepare_composed_content` uses `frontmatter.rstrip("\n") + "\n---\n" + body`.
- `test_composed_install_rotates_existing_target_to_backup` — conflict path: existing different-content target is backed up to `.ai-harness-backup` before being overwritten with composed content.
- `test_composed_uninstall_removes_matching_target` — uninstall path: matching composed content is removed from target.
- `test_composed_uninstall_restores_backup` — uninstall restoration: when target is absent but backup exists, backup is restored to target path.

All 4 tests follow the existing `tmp_path` / `console` fixture pattern and mirror the `FileArtifact` test conventions.

### Test suite result

**Command**: `uv run pytest tests/ -x -v`
**Exit code**: 0
**Tests run**: 139 passed, 0 failed (135 prior + 4 new)

### Manual sanity check

**Command**: `HOME=<tmp-dir> uv run ai-harness install`
**Result**:
- `sdd-apply.md` HEAD (first 10 lines) shows YAML frontmatter: `---\nname: sdd-apply\ndescription: ...\ntools: [Read, Edit, Write, Bash]\nmodel: sonnet\n---`
- `sdd-apply.md` TAIL (last 5 lines) shows body content from `prompts/sdd/sdd-apply.md` (model-small section closing marker)
- `.claude/agents/` contains 15 `.md` files: 8 SDD phases (`sdd-apply`, `sdd-archive`, `sdd-design`, `sdd-explore`, `sdd-propose`, `sdd-spec`, `sdd-tasks`, `sdd-verify`) + 7 inline agents (`jd-fix-agent`, `jd-judge-a`, `jd-judge-b`, `review-readability`, `review-reliability`, `review-resilience`, `review-risk`)
- `.claude/skills/sdd-orchestrator/SKILL.md` present

**Note**: The CLI does not accept a `--home` flag; install target is controlled via the `HOME` environment variable. This is the expected behavior.

### Files changed in this phase

- `tests/test_installer.py` — added `ComposedFileArtifact` import and 4 unit tests (lines 263–362).
- `openspec/changes/claude-installer-composition/tasks.md` — 4.1, 4.2, 4.4 marked `[x]`.
- `openspec/changes/claude-installer-composition/apply-report.md` — this Phase 4 section.

### Status

10/10 tasks complete. 4.3 was completed as task 1.1 in Phase 1: the `_assert_claude_agents(home, label)` helper was written, wired into `run_install_tests()`, and exercised in Phase 1 RED + Phase 2 GREEN. The orchestrator path was further updated to `.claude/skills/sdd-orchestrator/SKILL.md` in the orchestrator-path delta. All 10 tasks in `tasks.md` are now marked `[x]`. Ready for sdd-verify.
