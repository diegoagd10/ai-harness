# Apply Report: copilot-hidden-subagents

## Summary

Implemented 18 tasks across 4 phases to make the GitHub Copilot installer emit first-class `.agent.md` custom-agent files. Added `copilot_frontmatter()` serializer in `frontmatter.py`, updated `_METADATA` with per-agent `model`/`user-invocable`/`agents` keys using two single-source constants (`_ORCHESTRATOR_MODEL`, `_SUBAGENT_MODEL`), swapped the orchestrator tools from `Task`→`agent`, changed all target paths from `.md`→`.agent.md`, and updated e2e assertions. All 273 tests pass; ruff format/lint clean; e2e Docker tests pass. ~315 lines changed.

## TDD Cycle Evidence

### Task 1.1 — [RED] test_copilot_frontmatter_sdd_orchestrator
- **Spec scenario**: `copilot_frontmatter emits Copilot-only keys`, `Orchestrator agents field lists exactly the 15 sub-agents`
- **File**: `tests/test_copilot_installer.py::test_copilot_frontmatter_sdd_orchestrator`
- **Red evidence**: `ImportError: cannot import name 'copilot_frontmatter' from 'ai_harness.artifacts.installers.frontmatter'`
- **Green evidence**: `PASSED` (after 1.2 added `copilot_frontmatter` and 1.5 populated metadata with model/agents/user-invocable)
- **Triangulate**: 3 additional assertions added: 8-key count, key order, specific value checks (name, target, user-invocable, disable-model-invocation, model, agents)
- **Refactor**: None needed

### Task 1.2 — [GREEN] add copilot_frontmatter()
- **Spec scenario**: All scenarios requiring Copilot serializer
- **File**: `src/ai_harness/artifacts/installers/frontmatter.py`
- **Red evidence**: ImportError confirmed in 1.1; function did not exist
- **Green evidence**: Import succeeds; `copilot_frontmatter()` returns properly formatted YAML frontmatter string
- **Triangulate**: Function tested with orchestrator (8 keys) and subagent (7 keys) metadata
- **Refactor**: Extracted tools serialization (list→flow sequence) following existing `metadata_to_frontmatter` pattern; `target` and `disable-model-invocation` absorbed as serializer constants

### Task 1.3 — [RED] test_copilot_frontmatter_sdd_explore
- **Spec scenario**: `Sub-agents lack an agents field`
- **File**: `tests/test_copilot_installer.py::test_copilot_frontmatter_sdd_explore`
- **Red evidence**: `AssertionError: expected 7 frontmatter keys, got 6` — metadata lacked `model` key at time of test writing
- **Green evidence**: `PASSED` (after 1.5 added `model` to subagent metadata)
- **Triangulate**: Asserts 7 keys, correct order, `user-invocable: false`, `disable-model-invocation: true`, `model: Claude Haiku 4.5`, AND no `agents:` key anywhere
- **Refactor**: None needed

### Task 1.4 — [RED] test_metadata_model_assignment
- **Spec scenario**: `Model assignment is single-sourced`, `Model strings live in metadata, not the serializer`
- **File**: `tests/test_copilot_installer.py::test_metadata_model_assignment`
- **Red evidence**: `AssertionError: orchestrator metadata missing 'model' key`
- **Green evidence**: `PASSED` (after 1.5 added model/agents/user-invocable to all 16 metadata entries)
- **Triangulate**: Tests orchestrator (model=GPT-5 mini, has agents, user-invocable=true) and all 15 subagents (model=Claude Haiku 4.5, no agents, user-invocable=false)
- **Refactor**: None needed

### Task 1.5 — [GREEN] update _METADATA
- **Spec scenario**: All model/scenario requirements
- **File**: `src/ai_harness/artifacts/installers/copilot.py`
- **Red evidence**: 1.4 failed with missing model key
- **Green evidence**: 1.4 passes; 1.1 passes; 1.3 passes
- **Triangulate**: N/A — structural change
- **Refactor**: Added `_ORCHESTRATOR_MODEL` and `_SUBAGENT_MODEL` module-level constants to avoid change amplification; `agents` uses `sorted(_SUBAGENT_NAMES)` for determinism

### Task 1.6 — [RED] test_install_emits_agent_md
- **Spec scenario**: `File extension is .agent.md`, `Frontmatter keys are present and ordered`, `Self-composed expectation matches emitted output`
- **File**: `tests/test_copilot_installer.py::test_install_emits_agent_md`
- **Red evidence**: `AssertionError: expected .agent.md extension, got '.copilot/agents/sdd-orchestrator.md'`
- **Green evidence**: `PASSED` (after 1.7 changed target paths to `.agent.md`)
- **Triangulate**: Iterates all 16 composed artifacts; asserts `.agent.md` extension, extracts agent id, self-composes expected frontmatter via `copilot_frontmatter`
- **Refactor**: None needed

### Task 1.7 — [GREEN] update _build_manifest
- **Spec scenario**: All install scenarios
- **File**: `src/ai_harness/artifacts/installers/copilot.py`
- **Red evidence**: 1.6 failed with `.md` extension
- **Green evidence**: 1.6 passes; all 16 targets use `.agent.md`
- **Triangulate**: N/A — structural change
- **Refactor**: Updated import to include both `copilot_frontmatter` and `metadata_to_frontmatter`; changed all three target path locations (phase agents + inline agents)

### Task 2.1 — [RED] test_tools_agent_alias
- **Spec scenario**: `Orchestrator tool list includes agent`, `Subagents lack agent tool`, `agent tool presence is required when agents field is set`
- **File**: `tests/test_copilot_installer.py::test_tools_agent_alias`
- **Red evidence**: `AssertionError: orchestrator tools must include 'agent': ['Task', 'Bash', 'Edit', 'View', 'Create', 'Glob', 'Grep', 'Read']`
- **Green evidence**: `PASSED` (after 2.2 replaced Task→agent)
- **Triangulate**: Asserts orchestrator has `agent` and NOT `Task`; all 15 sub-agents do NOT have `agent`
- **Refactor**: None needed

### Task 2.2 — [GREEN] replace Task with agent in orchestrator tools
- **Spec scenario**: Orchestrator tool list includes agent
- **File**: `src/ai_harness/artifacts/installers/copilot.py`
- **Red evidence**: 2.1 failed — `Task` present, `agent` absent
- **Green evidence**: 2.1 passes
- **Triangulate**: N/A — one-line change
- **Refactor**: None needed

### Task 2.3 — [RED] test_uninstall_removes_agent_md
- **Spec scenario**: `Uninstall removes all managed .agent.md files`, `User-managed non-.agent.md files survive uninstall`
- **File**: `tests/test_copilot_installer.py::test_uninstall_removes_agent_md`
- **Red evidence**: Test passed immediately — manifest-driven uninstall already handles `.agent.md` targets correctly (manifest changed in 1.7)
- **Green evidence**: `PASSED` — zero `.agent.md` after uninstall; user `.md` survives
- **Triangulate**: Verifies install produces 16 `.agent.md` files, uninstall removes them all, user `.md` untouched
- **Refactor**: None needed

### Task 2.4 — [GREEN] verify uninstall for .agent.md
- **Spec scenario**: Uninstall spec
- **File**: `src/ai_harness/artifacts/installers/copilot.py` (no changes needed)
- **Red evidence**: 2.3 was green on first run — architecture already correct
- **Green evidence**: 2.3 passes
- **Triangulate**: N/A
- **Refactor**: None

### Task 2.5 — [RED] test_allowlist_single_source_of_truth
- **Spec scenario**: `Allowlist matches hook allowlist (single source of truth)`, `Frontmatter subagent set matches hook allowlist`
- **File**: `tests/test_copilot_installer.py::test_allowlist_single_source_of_truth`
- **Red evidence**: Test passed immediately — all three sources already aligned from 1.5 metadata changes
- **Green evidence**: `PASSED` — orchestrator `agents:` = hook `preToolUse[0].allow` = `user-invocable: false` ids = `sorted(_SUBAGENT_NAMES)`
- **Triangulate**: Compares three source sets as sorted lists
- **Refactor**: None needed

### Task 3.1 — [RED] e2e test_copilot_cli_lifecycle.py updates
- **Spec scenario**: `Expected content built from production single source`
- **File**: `e2e/test_copilot_cli_lifecycle.py`
- **Red evidence**: Test would fail on e2e assertions — `f.stem` incorrectly parsed `.agent.md` names; `f.suffix != ".md"` filter missed `.agent.md` files; frontmatter checks didn't validate Copilot keys
- **Green evidence**: All e2e categories passed (Docker e2e test)
- **Triangulate**: Multiple changes: `f.stem`→`f.name.removesuffix(".agent.md")`, `f.suffix`→`f.name.endswith(".agent.md")`, new `_assert_agent_frontmatter` with 7/8-key checks, model string assertions, `agents:` presence/absence, `agent` tool verification, uninstall assertions use `.agent.md` paths
- **Refactor**: Updated stale agent backup path to `.agent.md.ai-harness-backup`; removed noqa comment

### Task 3.2 — [RED] test_mutation_prompt_body
- **Spec scenario**: `Mutation test catches prompt body changes`
- **File**: `tests/test_copilot_installer.py::test_mutation_prompt_body`
- **Red evidence**: Test passed immediately — mutation correctly detected with current architecture
- **Green evidence**: `PASSED` — edited prompt body produces different output
- **Triangulate**: Installs, mutates a prompt, reinstalls, asserts byte-level difference
- **Refactor**: None needed

### Task 3.3 — [RED] test_install_idempotent
- **Spec scenario**: `Reinstall idempotency`
- **File**: `tests/test_copilot_installer.py::test_install_idempotent`
- **Red evidence**: Test passed immediately — deterministic composition ensures idempotency
- **Green evidence**: `PASSED` — two consecutive installs produce byte-identical files
- **Triangulate**: Installs twice into separate homes, compares all 16 files byte-for-byte
- **Refactor**: Added `strict=True` to `zip()` call

### Task 3.4 — [RED] test_claude_install_byte_identical
- **Spec scenario**: `metadata_to_frontmatter is unchanged`, `Claude install is byte-identical after change`
- **File**: `tests/test_copilot_installer.py::test_claude_install_byte_identical`
- **Red evidence**: Test passed immediately — `metadata_to_frontmatter` was never modified
- **Green evidence**: `PASSED` — no Copilot keys (`target:`, `user-invocable:`, `disable-model-invocation:`) in `metadata_to_frontmatter` output
- **Triangulate**: Tested with orchestrator metadata and sub-agent metadata; asserts no Copilot key leakage
- **Refactor**: None needed

### Task 3.5 — [RED] test_copilot_hook_byte_identical
- **Spec scenario**: `Hook allowlist covers all 15 subagents`
- **File**: `tests/test_copilot_installer.py::test_copilot_hook_byte_identical`
- **Red evidence**: Test passed immediately — `_build_hook_json()` was never modified
- **Green evidence**: `PASSED` — deterministic hook generation; allowlist equals `sorted(_SUBAGENT_NAMES)`
- **Triangulate**: Two calls produce identical dicts; serialized JSON identical; structure assertions (version, preToolUse, task matcher)
- **Refactor**: None needed

### Task 4.1 — Full unit test suite
- **Spec scenario**: All
- **File**: `uv run pytest`
- **Result**: 273 passed, 0 failed (0.07s for copilot tests, 1.54s total)

### Task 4.2 — Ruff format + lint
- **Spec scenario**: N/A (validation)
- **File**: `uv run ruff format --check . && uv run ruff check .`
- **Result**: Clean — 64 files already formatted; all checks passed
- **Auto-fixes applied**: `ruff format .` reformatted 1 file; `ruff check --fix .` fixed 6 issues (unused imports, f-string, import sorting)

### Task 4.3 — E2E in Docker
- **Spec scenario**: All e2e
- **File**: `e2e/docker-test.sh`
- **Result**: All e2e categories passed

## Files Modified

| File | Action | What Was Done |
|------|--------|---------------|
| `src/ai_harness/artifacts/installers/frontmatter.py` | Modified | Added `copilot_frontmatter()` — pure function, 7 unconditional keys + conditional `agents:` |
| `src/ai_harness/artifacts/installers/copilot.py` | Modified | Added `_ORCHESTRATOR_MODEL`/`_SUBAGENT_MODEL` constants; updated all 16 `_METADATA` entries with `model`, `user-invocable`, `agents`; orchestrator tools `Task`→`agent`; target paths `.md`→`.agent.md`; serializer swap `metadata_to_frontmatter`→`copilot_frontmatter` |
| `tests/test_copilot_installer.py` | Modified | Added 11 new tests (tasks 1.1, 1.3, 1.4, 1.6, 2.1, 2.3, 2.5, 3.2, 3.3, 3.4, 3.5); updated imports |
| `e2e/test_copilot_cli_lifecycle.py` | Modified | Updated `f.stem`→`f.name.removesuffix(".agent.md")`; file suffix checks; new `_assert_agent_frontmatter` with Copilot key assertions; stale agent and uninstall paths to `.agent.md` |
| `openspec/changes/copilot-hidden-subagents/tasks.md` | Modified | All 18 task checkboxes + 8 acceptance criteria marked `[x]` |

## Validation

- `uv run pytest` — **273 passed, 0 failed**
- `uv run ruff format --check .` — **Clean** (64 files already formatted; 1 auto-fixed during implementation)
- `uv run ruff check .` — **Clean** (6 auto-fixes applied during implementation)
- `e2e/docker-test.sh` — **All e2e categories passed**

## Deviations

None — implementation matches design.

## Open Items for Verify

- Check that `metadata_to_frontmatter` is still used by `opencode.py` (it imports from `frontmatter.py` — verify byte-identity of OpenCode output)
- Confirm `.agent.md` files are picked up by GitHub Copilot CLI (requires actual Copilot installation, out of scope for automated testing)
- Verify model display names (`GPT-5 mini`, `Claude Haiku 4.5`) match the current supported-models page
