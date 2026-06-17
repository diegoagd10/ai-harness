# Tasks: consolidate-agent-roster

## Overview

Create `agents.py` catalog (16-row identity registry), refactor three installers to thin adapters consuming `all_agents()`, rewrite tests that import private installer symbols, verify e2e passes with Copilot `jd-fix-agent` tool gain. Catalog first, adapters one at a time (Claude → Copilot → Opencode), tests after. Single PR, exception-ok delivery.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~950 |
| 400-line budget risk | High |
| 800-line budget risk | Medium |
| Delivery strategy | exception-ok |

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: High
800-line budget risk: Medium

**Breakdown**: agents.py +110 (new), claude.py Δ170, copilot.py Δ160, opencode.py Δ240, tests Δ330, e2e Δ40. Reformatting of per-id description/model data inflates diff; real semantic diff ~550 lines.

---

## Phase 1: Catalog (infrastructure)

- [x] 1.1 Create `src/ai_harness/artifacts/agents.py` — `Capability` StrEnum (ORCHESTRATOR/EDITS/READ_ONLY), frozen `Agent(id, namespace, capability)`, 16-row `AGENT_CATALOG`, `all_agents()` (ordered), `get(id)` raises KeyError. RED test first, then GREEN impl. Spec: agent-catalog §1-3. **(M, ~140 lines, depends: none, skills: coding-guidelines/read-task-spec/tdd-implement)**

- [x] 1.2 Catalog smoke tests — verify 1 ORCHESTRATOR, 9 EDITS, 6 READ_ONLY; namespace explicit (sdd/jd/review); `sdd-init` absent; Agent frozen. Public API imports only. **(S, ~50 lines, depends: 1.1, skills: tdd-implement)**

## Phase 2: Adapters

- [x] 2.1 Refactor `claude.py` — add `_TOOLS_BY_CAPABILITY` (3 rows), `_MODEL_BY_ID`, `_DESCRIPTION_BY_ID`. Rewrite `_build_manifest` to iterate `all_agents()`, branching `capability == ORCHESTRATOR` for orchestrator SKILL.md. Rewrite `_install_permissions` from capability tools. Remove `_PHASE_NAMES`, `_INLINE_AGENTS`, `_METADATA`. Byte-identical output for all 16 agents. **(L, ~170 Δ, depends: 1.1, skills: coding-guidelines/read-task-spec/tdd-implement)**

- [x] 2.2 Refactor `copilot.py` — add `_TOOLS_BY_CAPABILITY` (EDITS row includes Read/Glob/Grep for jd-fix gain), `_MODEL_BY_ID`, `_DESCRIPTION_BY_ID`. Rename `_build_hook_json` → `build_hook_json` (public). Derive `agents:` field + hook allowlist from catalog. Remove `_PHASE_NAMES`, `_INLINE_AGENTS`, `_SUBAGENT_NAMES`, `_METADATA`. **(L, ~160 Δ, depends: 1.1, skills: read-task-spec/tdd-implement)**

- [x] 2.3 Refactor `opencode.py` — add `_TOOLS_BY_CAPABILITY`, `_MODEL_BY_ID`, `_DESCRIPTION_BY_ID`, `_MODE_BY_CAPABILITY`, `_HIDDEN_BY_CAPABILITY`, `_PERMISSION_BY_CAPABILITY`, `_PROMPT_KIND_BY_NS`. Rename `_build_opencode_config` → `build_opencode_config` (public, catalog-driven). Rewrite `_build_orchestrator_allowlist` from catalog. Remove `AgentDefinition`, `AGENT_DEFINITIONS`, `_prompt_ns`, `_build_agent_entry`. Byte-identical JSON output. **(L, ~240 Δ, depends: 1.1, skills: coding-guidelines/read-task-spec/tdd-implement)**

## Phase 3: Test Rewrite

- [x] 3.1 Rewrite `tests/test_claude_installer.py` — replace `_METADATA` import with catalog; replace local agent-name lists with catalog-derived sets. Keep functional test logic intact. **(M, ~100 Δ, depends: 2.1, skills: read-task-spec/tdd-implement)**

- [x] 3.2 Rewrite `tests/test_copilot_installer.py` — replace `_METADATA`/`_SUBAGENT_NAMES` with catalog; replace `_build_hook_json` with public `build_hook_json`. Self-compose frontmatter via adapter API. Keep budget/idempotency/mutation/uninstall tests. **(M, ~180 Δ, depends: 2.2, skills: read-task-spec/tdd-implement)**

- [x] 3.3 Rewrite `tests/test_opencode_installer.py` — replace `AGENT_DEFINITIONS`/`AgentDefinition`/`_build_agent_entry`/`_build_opencode_config`/`_prompt_ns` with catalog + public `build_opencode_config`. Remove dataclass-shape tests. Keep `_load_inlined_prompt` tests. **(M, ~120 Δ, depends: 2.3, skills: read-task-spec/tdd-implement)**

## Phase 4: E2E + Verification

- [x] 4.1 Rewrite `e2e/test_harness_lifecycle.py` — replace `_CLAUDE_METADATA`/`_build_opencode_config` imports with catalog + public adapter APIs. Self-compose expected content from catalog. **(S, ~50 Δ, depends: 2.1 + 2.3, skills: read-task-spec/tdd-implement)**

- [x] 4.2 Rewrite `e2e/test_copilot_cli_lifecycle.py` — replace `_build_hook_json` with public `build_hook_json`. Verify `jd-fix-agent` frontmatter includes Read/Glob/Grep (self-composed from production, no fixture file). **(S, ~10 Δ, depends: 2.2, skills: read-task-spec/tdd-implement)**

- [x] 5.1 Gate: run `uv run ruff format --check .`, `uv run ruff check .`, `uv run pytest`. Zero failures. **(S, depends: all above, skills: none)**

- [x] 5.2 Dead code audit: grep for `_METADATA`, `AGENT_DEFINITIONS`, `AgentDefinition`, `_PHASE_NAMES`, `_INLINE_AGENTS`, `_SUBAGENT_NAMES`, `_ALL_AGENT_IDS`, `_prompt_ns` across `src/` and `tests/`. Zero hits → done. **(S, depends: 5.1, skills: none)**
