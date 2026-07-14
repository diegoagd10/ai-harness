# Implementation — improve-change-flow

## Commits
- 07c91e03f79e1c30feebbb39948a21699170522e — task 1: Add capability-scoped task state view
- 388ce61a8e94bd216aabf9222e9e2396b18996c9 — task 2: Parse sliced PRD metadata and derive conservative risk
- b05c203fbb085b715f47c1abad8284585b7de2d1 — task 3: Derive first-slice routes and additive status
- 4402bcf6923c3ce81b4d9354079456bc04425c33 — task 4: Persist and enforce scope-fingerprinted approvals
- bc26cd2e8aeb0115ac8a20fc919002632f5c253d — task 5: Route approved slices through continuation and final validation
- 29c60ea4a7de8fa465d94a6683efb00ecaaa1e8e — task 6: Harden direct archive preflight for sliced changes
- 9c5b3d9a3351ccd1ac03bf299402fe735b677482 — task 7: Update change agents for capability-bound execution
- eb0f082e3d9b5555acea8efa7b37d6c61d583ceb — task 8: Run focused change-flow regression verification
- 494b65e00974951c6acf7d6f7798d20ede16045a — task 9: Gate approval scope to the gate's capability and reject stale initial slice validation
- 36a45f0c62da1d9598d5bdc0f6a39f6df8185b20 — task 10: Block sliced routing when approval entries are malformed
- 2612d21a8e009f83d62920ae181aee1bc4eb3a4a — task 11: Surface a safe routing diagnostic for unsafe task spec references
- 9eaa2d6460d38ab493dbe4d61ab560bcbac64cb2 — task 12: Deduplicate change-flow test fixtures for the pylint gate

## TDD Evidence

| Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor |
|------|--------|----------------|------------|-------|------------|-----|-------|---------------|----------|
| 1 | 07c91e03f79e1c30feebbb39948a21699170522e | src/ai_harness/modules/harness/tasks.py | tests/test_change_task_slice.py | unit | passed: 12/12 | written | passed | 12 cases | clean |
| 2 | 388ce61a8e94bd216aabf9222e9e2396b18996c9 | src/ai_harness/modules/harness/change_flow.py | tests/test_change_flow_internals.py | unit | passed: 25/25 | written | passed | 25 cases | clean |
| 3 | b05c203fbb085b715f47c1abad8284585b7de2d1 | src/ai_harness/modules/harness/change.py | tests/test_change_slice_status.py | unit | passed: 18/18 | written | passed | 18 cases | clean |
| 4 | 4402bcf6923c3ce81b4d9354079456bc04425c33 | src/ai_harness/modules/harness/change.py, src/ai_harness/commands/change.py, src/ai_harness/main.py, src/ai_harness/modules/harness/__init__.py | tests/test_change_approvals.py | unit | passed: 14/14 | written | passed | 14 cases | clean |
| 5 | bc26cd2e8aeb0115ac8a20fc919002632f5c253d | src/ai_harness/modules/harness/change.py | tests/test_change_continuation.py | unit | passed: 8/8 | written | passed | 8 cases | clean |
| 6 | 29c60ea4a7de8fa465d94a6683efb00ecaaa1e8e | src/ai_harness/modules/harness/change.py | tests/test_change_sliced_archive.py | unit | passed: 8/8 | written | passed | 8 cases | clean |
| 7 | 9c5b3d9a3351ccd1ac03bf299402fe735b677482 | src/ai_harness/resources/change-agent/*.md, expected/*.md | tests/test_renderers.py | mixed | passed: 257/257 | written | passed | N/A: existing covered | clean |
| 8 | eb0f082e3d9b5555acea8efa7b37d6c61d583ceb | .ai-harness/changes/improve-change-flow/design.md, .ai-harness/changes/improve-change-flow/exploration.md, .ai-harness/changes/improve-change-flow/implementation.md, .ai-harness/changes/improve-change-flow/prd.md, .ai-harness/changes/improve-change-flow/specs/ordered-slice-continuation.md, .ai-harness/changes/improve-change-flow/specs/risk-and-scope-governance.md, .ai-harness/changes/improve-change-flow/specs/safe-normal-risk-first-slice.md, .ai-harness/changes/improve-change-flow/tasks.json | tests/test_renderers.py, tests/test_change.py, tests/test_change_task_slice.py, tests/test_change_flow_internals.py, tests/test_change_approvals.py, tests/test_change_continuation.py, tests/test_change_slice_status.py, tests/test_change_sliced_archive.py | e2e | passed: 771/771 | written | passed | N/A: regression scope | clean |
| 9 | 494b65e00974951c6acf7d6f7798d20ede16045a | src/ai_harness/modules/harness/change.py, .ai-harness/changes/improve-change-flow/tasks.json | tests/test_change_approvals.py, tests/test_change_continuation.py, tests/test_change_slice_status.py, tests/test_change_sliced_archive.py | unit | passed: 5/5 | written | passed | 5 cases | clean |
| 10 | 36a45f0c62da1d9598d5bdc0f6a39f6df8185b20 | src/ai_harness/modules/harness/change_flow.py, .ai-harness/changes/improve-change-flow/tasks.json | tests/test_change_flow_internals.py | unit | passed: 5/5 | written | passed | 5 cases | clean |
| 11 | 2612d21a8e009f83d62920ae181aee1bc4eb3a4a | src/ai_harness/modules/harness/tasks.py, src/ai_harness/modules/harness/change.py, .ai-harness/changes/improve-change-flow/tasks.json | tests/test_change_task_slice.py | unit | passed: 8/8 | written | passed | 8 cases | clean |
| 12 | 9eaa2d6460d38ab493dbe4d61ab560bcbac64cb2 | tests/__init__.py, tests/_change_flow_fixtures.py, tests/test_change_approvals.py, tests/test_change_continuation.py, tests/test_change_slice_status.py, tests/test_change_sliced_archive.py, tests/test_change_task_slice.py, .ai-harness/changes/improve-change-flow/tasks.json | tests/test_change_approvals.py, tests/test_change_continuation.py, tests/test_change_slice_status.py, tests/test_change_sliced_archive.py, tests/test_change_task_slice.py | unit | passed: 789/789 | written | passed | N/A: refactor only | clean |

## Remaining
- none — all task records closed; final regression gate passes with 789/789 pytest, 29/29 e2e, ruff clean, pylint duplicate-code clean.
