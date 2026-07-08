# Implementation — fix-test-prompt-decoupling

## Commits
- c7df2aa — task 1: rewrite install body assertion to containment
- 1fa2dc5 — task 2: delete five locked prompt/resource-coupled tests from test_renderers.py
- 36cd375 — task 3: add discovery-driven resource smoke test
- 8759262 — task 4: add native archiver render smoke test parametrized across agent CLIs

## TDD Evidence

| Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor |
|------|--------|----------------|------------|-------|------------|-----|-------|---------------|----------|
| 1 | c7df2aa  |  | tests/test_install.py | unit  | passed: 67/67 | written | passed | Single | clean    |
| 2 | 1fa2dc5  |  | tests/test_renderers.py | unit  | passed: 243/243 | written | passed | Single | clean    |
| 3 | 36cd375  |  | tests/test_renderers.py | unit  | passed: 311/311 | written | passed | Single | clean    |
| 4 | 8759262  |  | tests/test_renderers.py | unit  | passed: 313/313 | written | passed | 3 cases | clean    |

## Remaining
- none