# Tasks: copilot-hidden-subagents

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~315 |
| 400-line budget risk | Low |
| Size exception needed | No |
| Suggested work units | Not needed |
| Delivery strategy | exception-ok |
| Maintainer-approved size exception | No |

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: Low

## Phase 1 — Infrastructure (serializer + metadata)

- [x] 1.1 [RED] `tests/test_copilot_installer.py::test_copilot_frontmatter_sdd_orchestrator` — import `copilot_frontmatter`, compose orchestrator frontmatter; asserts 8 keys incl. `agents:` with 15 sorted names. Expects ImportError (function missing). Spec: `copilot_frontmatter emits Copilot-only keys`, `Orchestrator agents field lists exactly the 15 sub-agents`. Run: `uv run pytest tests/test_copilot_installer.py::test_copilot_frontmatter_sdd_orchestrator -x`
- [x] 1.2 [GREEN] `src/ai_harness/artifacts/installers/frontmatter.py` — add `copilot_frontmatter(metadata) -> str`. Emits 7 unconditional keys in fixed order: name, description, tools, target, user-invocable, disable-model-invocation, model. Conditionally emits 8th key `agents:` if `metadata.get("agents")` is truthy. `target` and `disable-model-invocation` are absorb-by-serializer constants. Re-run 1.1 → passes.
- [x] 1.3 [RED] `tests/test_copilot_installer.py::test_copilot_frontmatter_sdd_explore` — assert `copilot_frontmatter(_METADATA["sdd-explore"])` does NOT contain `agents:`. Spec: `Sub-agents lack an agents field`. Run: `uv run pytest tests/test_copilot_installer.py::test_copilot_frontmatter_sdd_explore -x`
- [x] 1.4 [RED] `tests/test_copilot_installer.py::test_metadata_model_assignment` — assert orchestrator entry has `model: "GPT-5 mini"` and `agents: sorted(_SUBAGENT_NAMES)`; 15 sub-agents have `model: "Claude Haiku 4.5"` and no `agents` key. Spec: `Model assignment is single-sourced`, `Model strings live in metadata, not the serializer`. Run: `uv run pytest tests/test_copilot_installer.py::test_metadata_model_assignment -x`
- [x] 1.5 [GREEN] `src/ai_harness/artifacts/installers/copilot.py` — update `_METADATA`: add `model` key per-agent (two module-level constants `_ORCHESTRATOR_MODEL`, `_SUBAGENT_MODEL`); orchestrator gets `agents: sorted(_SUBAGENT_NAMES)`; sub-agents lack `agents`. Re-run 1.4 → passes.
- [x] 1.6 [RED] `tests/test_copilot_installer.py::test_install_emits_agent_md` — snapshot-compose expected output via `copilot_frontmatter(m).rstrip() + "\n---\n" + prompt_bytes(...)`, deep-compare against installed file; asserts `.agent.md` extension and 7/8-key frontmatter. Spec: `File extension is .agent.md`, `Frontmatter keys are present and ordered`, `Self-composed expectation matches emitted output`. Run: `uv run pytest tests/test_copilot_installer.py::test_install_emits_agent_md -x`
- [x] 1.7 [GREEN] `src/ai_harness/artifacts/installers/copilot.py` — in `_build_manifest`: change `{id}.md` → `{id}.agent.md`; swap `metadata_to_frontmatter` call → `copilot_frontmatter`. Re-run 1.6 → passes.

## Phase 2 — Core Implementation

- [x] 2.1 [RED] `tests/test_copilot_installer.py::test_tools_agent_alias` — assert orchestrator `tools:` includes `agent` and excludes `Task`; assert all 15 sub-agents exclude `agent` (keep `Task`). Spec: `Orchestrator tool list includes agent`, `Subagents lack agent tool`, `agent tool presence is required when agents field is set`. Run: `uv run pytest tests/test_copilot_installer.py::test_tools_agent_alias -x`
- [x] 2.2 [GREEN] `src/ai_harness/artifacts/installers/copilot.py` — in `_METADATA["sdd-orchestrator"]["tools"]`: replace `"Task"` with `"agent"`. Sub-agent tool lists unchanged (keep `Task`). Re-run 2.1 → passes.
- [x] 2.3 [RED] `tests/test_copilot_installer.py::test_uninstall_removes_agent_md` — after uninstall, assert zero `.agent.md` files under `agents/`; hook removed; user-managed `.md` survives. Spec: `Uninstall removes all managed .agent.md files`, `User-managed non-.agent.md files survive uninstall`. Run: `uv run pytest tests/test_copilot_installer.py::test_uninstall_removes_agent_md -x`
- [x] 2.4 [GREEN] `src/ai_harness/artifacts/installers/copilot.py` — manifest-driven uninstall already iterates composed artifacts; verify `.agent.md` targets removed (`.md` not in manifest survives). Re-run 2.3 → passes.
- [x] 2.5 [RED] `tests/test_copilot_installer.py::test_allowlist_single_source_of_truth` — assert `_SUBAGENT_NAMES` == orchestrator `agents:` set == hook `preToolUse[0].allow` set == `user-invocable: false` agent ids set. Spec: `Allowlist matches hook allowlist (single source of truth)`, `Frontmatter subagent set matches hook allowlist`. Run: `uv run pytest tests/test_copilot_installer.py::test_allowlist_single_source_of_truth -x`

## Phase 3 — Testing / Verification

- [x] 3.1 [RED] `e2e/test_copilot_cli_lifecycle.py` — replace `f.stem` with `f.name.removesuffix(".agent.md")`; add assertions for 7/8-key order, `agents:` presence on orchestrator only, `agent` in orchestrator tools, model strings, `user-invocable` split. Spec: `Expected content built from production single source`. Run: full e2e suite.
- [x] 3.2 [RED] `tests/test_copilot_installer.py::test_mutation_prompt_body` — edit `resources/prompts/review/review-risk.md`, reinstall, assert emitted body changed byte-for-byte. Spec: `Mutation test catches prompt body changes`. Run: `uv run pytest tests/test_copilot_installer.py::test_mutation_prompt_body -x`
- [x] 3.3 [RED] `tests/test_copilot_installer.py::test_install_idempotent` — install twice, assert all 16 `.agent.md` files byte-identical between runs. Spec: `Reinstall idempotency`. Run: `uv run pytest tests/test_copilot_installer.py::test_install_idempotent -x`
- [x] 3.4 [RED] `tests/test_copilot_installer.py::test_claude_install_byte_identical` — snapshot pre-change Claude output; assert post-change byte-identical (no Copilot key leakage). Spec: `metadata_to_frontmatter is unchanged`, `Claude install is byte-identical after change`. Run: `uv run pytest tests/test_copilot_installer.py::test_claude_install_byte_identical -x`
- [x] 3.5 [RED] `tests/test_copilot_installer.py::test_copilot_hook_byte_identical` — assert `_build_hook_json()` output byte-identical to pre-change. Spec: `Hook allowlist covers all 15 subagents`. Run: `uv run pytest tests/test_copilot_installer.py::test_copilot_hook_byte_identical -x`

## Phase 4 — Verification

- [x] 4.1 Full unit test suite — `uv run pytest`; all green.
- [x] 4.2 Ruff format + lint — `uv run ruff format --check . && uv run ruff check .`; clean.
- [x] 4.3 E2E in Docker — `e2e/docker-test.sh`; clean.

## Acceptance Criteria (from proposal)

- [x] Fresh install: 16 `.agent.md` files; only orchestrator has `user-invocable: true`
- [x] Orchestrator `tools` includes `agent`; all 16 have `target: github-copilot`, `disable-model-invocation: true`
- [x] Orchestrator frontmatter carries `model: GPT-5 mini`; all 15 subagents carry `model: Claude Haiku 4.5`
- [x] Orchestrator frontmatter carries `agents: [<15 sub-agent names>]`; sub-agent files do NOT carry `agents:`
- [x] Reinstall: byte-identical to first install
- [x] Uninstall: zero `.agent.md` files under install root; hook removed
- [x] Claude install: byte-identical to before (no Copilot key leakage)
- [x] `sdd-pre-tool-use.json` unchanged, passes existing tests

## Out of Scope

- MCP server configuration, cloud-agent secrets, org-level agents
- Claude/OpenCode installer changes
- CLI flag rename, config rename, prompt body changes
