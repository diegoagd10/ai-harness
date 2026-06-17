# Tasks: Build Agent CLIs from Prompts

## Review Workload Forecast

Estimated changed lines: ~695 (src +220/-105, tests +225/-140, e2e +5). 400-line risk: High. 800-line risk: Medium. Size exception: No. Delivery: exception-ok.

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: High
800-line budget risk: Medium

## Phase 1: Manifest Cleanup

- [x] 1.1 **RED** `tests/test_manifest.py` — `ComposedFileArtifact` rejects without `frontmatter_text`. Spec: *"Deterministic Claude composed agent"*.
- [x] 1.2 **GREEN** `manifest.py` — `frontmatter_text` required. `installer.py` — drop `frontmatter_source` fallback.

## Phase 2: Catalog Update

- [x] 2.1 **RED** `tests/test_catalog.py` — `import OPENCODE_JSON_SRC` fails. Spec: *"Catalog Drops OPENCODE_JSON_SRC"*.
- [x] 2.2 **GREEN** `catalog.py` — delete line 19. Update `test_get_resource_dir` example.

## Phase 3: Claude — SDD to Metadata

- [x] 3.1 **RED** `tests/test_claude_installer.py` — 15 agents use `frontmatter_text`. `_make_catalog_root` drops `agent-clis/claude/`. Spec: *"Metadata separated from prompt body"*.
- [x] 3.2 **GREEN** `claude.py` — add 8 SDD to `_METADATA`. Switch loop to `frontmatter_text`. Drop `agents_dir`.

## Phase 4: OpenCode — Build JSON in Memory

- [x] 4.1 **RED** `tests/test_install.py` — `{file:}` refs; no `OPENCODE_JSON_SRC`. Spec: *"Deterministic opencode.json"*, *"{file} refs preserve body"*.
- [x] 4.2 **GREEN** `opencode.py` — add `_METADATA` with `{file:}` templates. Build dict in memory. Drop `config_path`.

## Phase 5: Copilot — Metadata + Hook Code-Gen

- [x] 5.1 **RED** `tests/test_copilot_installer.py` — 16 agents `frontmatter_text`; hook from code. Spec: *"Deterministic Copilot hook JSON"*, *"Build survives agent-clis absence"*.
- [x] 5.2 **GREEN** `copilot.py` — add 9 SDD+orch to `_METADATA`. `_DENY_PATHS` constant. `_build_hook_json()`. Drop `agents_dir`, `hooks_dir`.

## Phase 6: Generated Fixtures

- [x] 6.1 **RED** installer tests — `_write_fixtures` → `generated/<provider>/`; skip if not writable. Spec: *"Fixtures written on writable tree"*, *"Fixtures skipped on read-only tree"*.
- [x] 6.2 **GREEN** 3 installers — `_write_fixtures()` + `os.access(os.W_OK)`. Drop shim methods. `.gitignore` add `generated/`.

## Phase 7: E2E Constant Retarget

- [x] 7.1 **GREEN** `e2e/test_harness_lifecycle.py` — 3 constants → `generated/opencode/opencode.json`, `generated/claude/agents`, `generated/claude/sdd-orchestrator/SKILL.md`.
- [x] 7.2 **GREEN** `e2e/test_copilot_cli_lifecycle.py` — 2 constants → `generated/copilot-cli/agents`, `generated/copilot-cli/hooks/sdd-pre-tool-use.json`.

## Phase 8: Delete agent-clis/ + Inventory Fix

- [x] 8.1 Delete `src/ai_harness/resources/agent-clis/` (37 files). Spec: *"Source-Tree Absence"*.
- [x] 8.2 **RED** `tests/test_prompt_inventory.py` — replace byte-copy test with `test_agent_clis_directory_absent`.
- [x] 8.3 **GREEN** assert `agent-clis/` absent.

## Phase 9: Orchestrator + Final Wiring

- [x] 9.1 **GREEN** `claude.py` — orchestrator from `_METADATA` + `prompts/orchestrator/sdd-orchestrator-agent.md`. Drop `orchestrator_dir`. Spec: *"Both orchestrator variants exist"*.
- [x] 9.2 **GREEN** `copilot.py` — `_validate_composed_budget` measures `frontmatter_text` directly.

## Phase 10: Verification

- [x] 10.1 `uv run pytest` — green. Verify: no `agent-clis/`, `generated/` fixtures, `{file:}` refs (no `/tmp`), no doubled `---`.
- [x] 10.2 `e2e/docker-test.sh` — green, byte-equivalent from generated fixtures.

## TDD Ordering

Phases 1→10 sequentially. Each: RED → GREEN → `uv run pytest` green.

## Out-of-Scope

`opencode.json` orphans `sdd-init`/`sdd-onboard` (pre-existing). `AGENTS.md`/skills/permissions unchanged from Round 1.

## CRITICAL Resolution

| CRITICAL | Tasks |
|----------|-------|
| opencode.json corrupted with `/tmp` paths | **4.1–4.2** |
| Doubled `---` from shim writes | **6.2 + 8.1** |
| E2e coupled to `agent-clis/` paths | **7.1–7.2 + 6.2** |
