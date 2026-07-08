# Implementation — fix-test-home-isolation

## Commits
- 41990cd — task 1: three-shared-helpers-accept-home
- d8dc827 — task 2: orchestrator-body-callers-pass-home
- 23d8c7a — task 3: native-orchestrator-body-callers-pass-home
- 5bf0a91 — task 4: native-implementor-body-callers-pass-home
- ec27015 — task 5: direct-call-isolation-batch-1
- b2fd196 — task 6: direct-call-isolation-batch-2
- 4b44381 — task 7: direct-call-isolation-batch-3
- fe0cd65 — task 8: override-store-semantics-preserved
- 7fa8bf4 — task 9: finalize-format-and-gates

## TDD Evidence

| Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor |
|------|--------|----------------|------------|-------|------------|-----|-------|---------------|----------|
| 1 | 41990cd | tests/test_renderers.py | N/A: edited test file only | unit | N/A: precondition for caller propagation | written | passed | Single | clean |
| 2 | d8dc827 | tests/test_renderers.py | N/A: edited test file only | unit | passed: 28/28 borrowed-conductor body tests | written | passed | Single | clean |
| 3 | 23d8c7a | tests/test_renderers.py | N/A: edited test file only | unit | passed: 60/60 parametrized orchestrator body tests (14 base * 3 CLIs + 1 parity case) | written | passed | Single | clean |
| 4 | 5bf0a91 | tests/test_renderers.py | N/A: edited test file only | unit | passed: 15/15 implementor body parametrized tests (5 base * 3 CLIs) | written | passed | Single | clean |
| 5 | ec27015 | tests/test_renderers.py | N/A: edited test file only | unit | passed: 11/11 batch-1 must-fix tests; rescued test_claude_subagents_have_name_and_model from real-HOME ambient read | written | passed | Single | clean |
| 6 | b2fd196 | tests/test_renderers.py | N/A: edited test file only | unit | passed: 7/7 batch-2 must-fix tests; phase-prompts dict-comprehension loop and frontmatter parity covered | written | passed | Single | clean |
| 7 | 4b44381 | tests/test_renderers.py | N/A: edited test file only | unit | passed: 5/5 batch-3 must-fix tests; copilot renderer + archiver triple-CLI loop + polymorphic dispatch parity covered | written | passed | Single | clean |
| 8 | fe0cd65 | tests/test_renderers.py | N/A: edited test file only | unit | passed: 10/10 override-store tests; 8 already-isolated store-loading tests preserved, 2 byte-identical tests added tmp_path; full isolated suite passes with HOME=/tmp/no-such-home-dir-xyz | written | passed | Single | clean |
| 9 | 7fa8bf4 | tests/test_renderers.py | N/A: edited test file only | unit | passed: 627/627 full pytest + ruff format --check + ruff check; 515/515 targeted test_renderers+test_install+test_set_models | written | passed | Single | clean |

## Remaining
- none
