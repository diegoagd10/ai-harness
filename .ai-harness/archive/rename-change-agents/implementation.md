# Implementation — rename-change-agents

## Commits
- 640db6e — task 1: rename change-agent templates to change-* prefix; tests: `git ls-files src/ai_harness/resources/change-agent/` (9 change-* files), `git diff --cached --stat` (0 body mutations)
- 501e7c5 — task 2: align _AGENT_META keys, caps.spawn allowlist, OPENCODE_CHANGE_AGENTS to change-* prefix; tests: AST check (9 prefixed _AGENT_META keys, 8-entry orchestrator allowlist unchanged in cardinality, OPENCODE_CHANGE_AGENTS orchestrator-first order preserved)
- b08dc73 — task 3: align change-orchestrator prose spawn list (line 107) to change-* prefix; tests: `grep` artifact references intact (prd.md, design.md, specs/, tasks.json still present and byte-identical); renamed-agent set {change-propose, change-design, change-specs, change-tasks} appears in both prose and allowlist
- 42567b3 — task 4: align test fixtures (renderer paths, copilot names, dict keys, allowlist tuple, wizard assertion, install tuples) to change-* prefix; tests: `pytest tests/test_renderers.py tests/test_set_models.py tests/test_install.py` 383 passed; bare-name grep in test_renderers.py/set_models.py/install.py shows only artifact references and the explicitly-deferred forbidden_prefixes tuple
- 6e3df0c — task 5: full pytest sweep + grep smoke + cardinality invariant — rename validated; tests: `pytest tests/test_renderers.py tests/test_set_models.py tests/test_install.py tests/test_change.py -x -q` 407 passed; `git grep -nE '"(propose|design|specs|tasks)"' src/ tests/` shows only change-artifact references (out of PRD scope); `_discover_loop_agents()` returns 13 names

## Remaining
- none