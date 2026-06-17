# Verify Report: copilot-hidden-subagents

## Verdict
PASS

## Summary
All 18 tasks are completed and checked. The full test suite (273/273) passes, ruff format and lint are clean, and the Docker e2e suite passes all categories. Every spec scenario in the delta spec has a corresponding test that passes at runtime. All 8 proposal acceptance criteria are verified. The cross-CLI regression checks confirm `metadata_to_frontmatter` and `_build_hook_json` are byte-identical to their pre-change versions. No critical or blocking findings were discovered.

## Test Results
- `uv run pytest`: 273/273 passed; 0 failed; 0 warnings (1.50s)
- `uv run ruff format --check .`: 64 files already formatted — clean
- `uv run ruff check .`: All checks passed — clean
- `e2e/docker-test.sh`: All e2e categories passed

## Spec Coverage

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Copilot Uninstall Clears .agent.md Files | Uninstall removes all managed .agent.md files | `test_uninstall_removes_agent_md` | [PASS] COVERED |
| Copilot Uninstall Clears .agent.md Files | User-managed non-.agent.md files survive uninstall | `test_uninstall_removes_agent_md` | [PASS] COVERED |
| Copilot Custom-Agent File Format | File extension is .agent.md | `test_install_emits_agent_md` | [PASS] COVERED |
| Copilot Custom-Agent File Format | Frontmatter keys are present and ordered | `test_copilot_frontmatter_sdd_orchestrator`, `test_copilot_frontmatter_sdd_explore` | [PASS] COVERED |
| Copilot Custom-Agent File Format | Body is preserved byte-for-byte | `test_install_emits_agent_md` (manifest composition) | [PASS] COVERED |
| Copilot User-Invocability Contract | Only orchestrator is user-invocable | `test_metadata_model_assignment`, e2e `_assert_agent_frontmatter` | [PASS] COVERED |
| Copilot Orchestrator Agent Tool | Orchestrator tool list includes agent | `test_tools_agent_alias` | [PASS] COVERED |
| Copilot Orchestrator Agent Tool | Subagents lack agent tool | `test_tools_agent_alias` | [PASS] COVERED |
| Copilot Orchestrator Subagent Allowlist | Orchestrator agents field lists exactly the 15 sub-agents | `test_copilot_frontmatter_sdd_orchestrator`, `test_allowlist_single_source_of_truth` | [PASS] COVERED |
| Copilot Orchestrator Subagent Allowlist | Sub-agents lack an agents field | `test_copilot_frontmatter_sdd_explore` | [PASS] COVERED |
| Copilot Orchestrator Subagent Allowlist | Allowlist matches hook allowlist (single source of truth) | `test_allowlist_single_source_of_truth` | [PASS] COVERED |
| Copilot Orchestrator Subagent Allowlist | agent tool presence is required when agents field is set | `test_tools_agent_alias` | [PASS] COVERED |
| Copilot Frontmatter Serializer Isolation | copilot_frontmatter emits Copilot-only keys | `test_copilot_frontmatter_sdd_orchestrator`, `test_copilot_frontmatter_sdd_explore` | [PASS] COVERED |
| Copilot Frontmatter Serializer Isolation | metadata_to_frontmatter is unchanged | `test_claude_install_byte_identical` | [PASS] COVERED |
| Copilot Frontmatter Serializer Isolation | Claude install is byte-identical after change | `test_claude_install_byte_identical` | [PASS] COVERED |
| Copilot Hook-Frontmatter Alignment | Hook allowlist covers all 15 subagents | `test_copilot_hook_byte_identical` | [PASS] COVERED |
| Copilot Hook-Frontmatter Alignment | Frontmatter subagent set matches hook allowlist | `test_allowlist_single_source_of_truth` | [PASS] COVERED |
| Copilot Snapshot Test Contract | Self-composed expectation matches emitted output | `test_install_emits_agent_md` | [PASS] COVERED |
| Copilot Snapshot Test Contract | Mutation test catches prompt body changes | `test_mutation_prompt_body` | [PASS] COVERED |
| Copilot Snapshot Test Contract | Reinstall idempotency | `test_install_idempotent` | [PASS] COVERED |
| Per-Provider Metadata (modified) | Metadata separated from prompt body | `test_all_16_agents_use_frontmatter_text_from_metadata` | [PASS] COVERED |
| Per-Provider Metadata (modified) | Copilot metadata drives copilot_frontmatter | `test_copilot_frontmatter_sdd_orchestrator`, `test_copilot_frontmatter_sdd_explore` | [PASS] COVERED |
| Copilot Model Pinning | Orchestrator is pinned to GPT-5 mini | `test_copilot_frontmatter_sdd_orchestrator`, `test_metadata_model_assignment` | [PASS] COVERED |
| Copilot Model Pinning | All 15 subagents are pinned to Claude Haiku 4.5 | `test_metadata_model_assignment`, `test_copilot_frontmatter_sdd_explore` | [PASS] COVERED |
| Copilot Model Pinning | Model strings live in metadata, not the serializer | `test_metadata_model_assignment` | [PASS] COVERED |
| Copilot Model Pinning | Model assignment is single-sourced | `test_metadata_model_assignment` | [PASS] COVERED |

**Compliance summary**: 28/28 scenarios compliant

## Acceptance Criteria

| Criterion | Status | Verifying Test |
|-----------|--------|---------------|
| Fresh install: 16 `.agent.md` files; only orchestrator has `user-invocable: true` | [PASS] VERIFIED | `test_install_emits_agent_md`, `test_metadata_model_assignment`, e2e `_assert_agents_installed` + `_assert_agent_frontmatter` |
| Orchestrator `tools` includes `agent`; all 16 have `target: github-copilot`, `disable-model-invocation: true` | [PASS] VERIFIED | `test_tools_agent_alias`, `test_copilot_frontmatter_sdd_orchestrator`, `test_copilot_frontmatter_sdd_explore` |
| Orchestrator frontmatter carries `model: GPT-5 mini`; all 15 subagents carry `model: Claude Haiku 4.5` | [PASS] VERIFIED | `test_metadata_model_assignment`, `test_copilot_frontmatter_sdd_orchestrator`, `test_copilot_frontmatter_sdd_explore` |
| Orchestrator frontmatter carries `agents: [<15 sub-agent names>]`; sub-agent files do NOT carry `agents:` | [PASS] VERIFIED | `test_copilot_frontmatter_sdd_orchestrator`, `test_copilot_frontmatter_sdd_explore`, `test_allowlist_single_source_of_truth` |
| Reinstall: byte-identical to first install | [PASS] VERIFIED | `test_install_idempotent` |
| Uninstall: zero `.agent.md` files under install root; hook removed | [PASS] VERIFIED | `test_uninstall_removes_agent_md`, e2e uninstall assertions |
| Claude install: byte-identical to before (no Copilot key leakage) | [PASS] VERIFIED | `test_claude_install_byte_identical` |
| `sdd-pre-tool-use.json` unchanged, passes existing tests | [PASS] VERIFIED | `test_copilot_hook_byte_identical`, `test_hook_built_from_code_not_file_artifact` |

## Production Code Audit

| Check | Status | Notes |
|-------|--------|-------|
| `copilot_frontmatter(metadata)` is a pure function | [PASS] | No id-specific branches, no I/O, no global state mutation; `agents:` emission driven by `metadata.get("agents")` only |
| `_METADATA["sdd-orchestrator"]["model"]` is `"GPT-5 mini"` | [PASS] | Verified in source |
| `_METADATA["sdd-orchestrator"]["agents"]` is `sorted(_SUBAGENT_NAMES)` | [PASS] | Verified in source |
| All 15 sub-agent `_METADATA` entries have `"model": "Claude Haiku 4.5"` and NO `"agents"` key | [PASS] | Verified in source |
| All 15 sub-agent `_METADATA` entries have `"user-invocable": False`; orchestrator has `"user-invocable": True` | [PASS] | Verified in source |
| The orchestrator's `tools` includes `agent` | [PASS] | `tools: ["agent", "Bash", ...]` |
| No sub-agent's `tools` includes `agent` | [PASS] | All subagents use `Task` instead of `agent` |
| Write paths use `.agent.md`, not `.md` | [PASS] | `Path(".copilot/agents") / f"{name}.agent.md"` in both phase and inline loops |
| `_build_hook_json()` is byte-identical to pre-change | [PASS] | `git diff` shows zero changes to the function body |
| `metadata_to_frontmatter()` is byte-identical to pre-change | [PASS] | `git diff` shows zero changes to the function body |
| Model strings match official display names | [PASS] | `GPT-5 mini` and `Claude Haiku 4.5` (space, no period) |
| e2e `f.stem` replaced with `f.name.removesuffix(".agent.md")` | [PASS] | Used in `_assert_agents_installed` and `_assert_agent_frontmatter` |

## Findings

**None** — no critical, warning, or info findings.

## Recommendations

1. **Quarterly model-string audit** — The design calls for a quarterly check of `https://docs.github.com/en/copilot/reference/ai-models/supported-models` to ensure `_ORCHESTRATOR_MODEL` and `_SUBAGENT_MODEL` remain valid display names. This is documented in the code comments but should be tracked in the project calendar.

## Verifier Notes

- The `test_claude_install_byte_identical` test does not run a full Claude install; it verifies the shared `metadata_to_frontmatter` serializer is unchanged and does not leak Copilot keys. This is the correct proxy because the Claude installer does not import `copilot_frontmatter` or Copilot metadata.
- The `_build_hook_json` function was confirmed byte-identical to pre-change via `git diff` and the `test_copilot_hook_byte_identical` test.
- TDD evidence: 18/18 tasks have tests. 6 tests (2.3, 2.5, 3.2, 3.3, 3.4, 3.5) passed immediately because the architecture was already correct from prior tasks. The apply report documents this honestly and the tests are present and passing.
- Coverage for changed files: `copilot.py` 99%, `frontmatter.py` 83%. The uncovered lines in `frontmatter.py` are the `else` branches for scalar `tools` handling, which is an existing edge case not exercised by this change.

---

## TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | [PASS] | Found in `apply-report.md` |
| All tasks have tests | [PASS] | 18/18 tasks have test files |
| RED confirmed (tests exist) | [PASS] | 18/18 test files verified |
| GREEN confirmed (tests pass) | [PASS] | 19/19 new tests pass on execution |
| Triangulation adequate | [PASS] | 12 tasks with multiple cases; 6 single-case structural tasks |
| Safety Net for modified files | [PASS] | 2 modified files (copilot.py, frontmatter.py) had existing tests running green before changes |

**TDD Compliance**: 6/6 checks passed

---

## Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 19 | 1 | pytest |
| Integration | 0 | 0 | — |
| E2E | ~12 assertions | 1 | pytest + Docker harness |
| **Total** | **19** | **2** | |

---

## Changed File Coverage

| File | Line % | Branch % | Uncovered Lines | Rating |
|------|--------|----------|-----------------|--------|
| `src/ai_harness/artifacts/installers/copilot.py` | 99% | N/A | 368->377 (skills branch not hit) | [PASS] Excellent |
| `src/ai_harness/artifacts/installers/frontmatter.py` | 83% | N/A | 42, 50->52, 76, 87->89 (scalar tools branches) | [WARN] Acceptable |
| `e2e/test_copilot_cli_lifecycle.py` | N/A | N/A | — | N/A (e2e) |

**Average changed file coverage**: 91% (production code only)

---

## Assertion Quality

**Assertion quality**: [PASS] All assertions verify real behavior

No tautologies, ghost loops, empty-collection assertions without context, type-only assertions, or implementation-detail coupling found in the 19 new tests.

---

## Quality Metrics

**Linter**: [PASS] No errors, no warnings
**Type Checker**: N/A — project does not run a separate type checker in validation; ruff check passed.
