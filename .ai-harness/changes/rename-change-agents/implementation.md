# Implementation — rename-change-agents

## Commits
- 640db6e — task 1: rename change-agent templates to change-* prefix; tests: `git ls-files src/ai_harness/resources/change-agent/` (9 change-* files), `git diff --cached --stat` (0 body mutations)
- 501e7c5 — task 2: align _AGENT_META keys, caps.spawn allowlist, OPENCODE_CHANGE_AGENTS to change-* prefix; tests: AST check (9 prefixed _AGENT_META keys, 8-entry orchestrator allowlist unchanged in cardinality, OPENCODE_CHANGE_AGENTS orchestrator-first order preserved)

## Remaining
- 3, 4, 5