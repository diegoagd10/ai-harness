# Tasks: Refactor Agent-CLIs Installer Architecture

## Review Workload Forecast

Estimated changed lines: 600–700. 400-line risk: High. 800-line risk: Medium. Delivery: exception-ok.

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: High
800-line budget risk: Medium

## Phase 1: Canonical Prompt Sources

- [x] 1.1 **RED** `tests/test_prompt_inventory.py` — all prompt files under `prompts/{jd,review,orchestrator,sdd}/` lack YAML frontmatter. Covers: "One body per agent".
- [x] 1.2 **GREEN** `prompts/jd/jd-{fix-agent,judge-a,judge-b}.md` (3 files) — extract bodies from `claude/agents/`.
- [x] 1.3 **GREEN** `prompts/review/review-{risk,readability,reliability,resilience}.md` (4 files) — extract bodies.
- [x] 1.4 **GREEN** `prompts/orchestrator/sdd-orchestrator-agent.md` — copy body from `claude/sdd-orchestrator/SKILL.md`.

## Phase 2: Manifest Extension

- [x] 2.1 **RED** `tests/test_manifest.py` — `ComposedFileArtifact(frontmatter_text="...")` → `TypeError`.
- [x] 2.2 **GREEN** `manifest.py` — add `frontmatter_text: str | None = None`; make `frontmatter_source` optional.
- [x] 2.3 **GREEN** `installer.py` — branch `_prepare_composed_content` on `frontmatter_text is not None`.

## Phase 3: Claude Installer Rewire

- [x] 3.1 **RED** `tests/test_claude_installer.py` — inline agents use `ComposedFileArtifact(frontmatter_text=...)` + shim writes. Covers: "Metadata separated", "Shim written on install".
- [x] 3.2 **GREEN** `claude.py` — embed `_METADATA` dict per agent; switch `_INLINE_AGENTS` from `FileArtifact` to composed.
- [x] 3.3 **GREEN** `claude.py` — shim writes to `agent-clis/claude/agents/` post-install.
- [x] 3.4 Strip bodies from 7 `agent-clis/claude/agents/{jd,review}-*.md` → frontmatter only.

## Phase 4: Copilot Installer Rewire

- [x] 4.1 **RED** `tests/test_copilot_installer.py` — composed inline agents + budget check with `frontmatter_text`.
- [x] 4.2 **GREEN** `copilot.py` — embed `_METADATA` with Copilot tools; switch inline loop.
- [x] 4.3 **GREEN** `copilot.py` — shim writes to `agent-clis/copilot-cli/agents/`.
- [x] 4.4 **GREEN** `copilot.py` — `_validate_composed_budget` handles `frontmatter_text` length.
- [x] 4.5 Strip bodies from 7 `agent-clis/copilot-cli/agents/{jd,review}-*.md` → frontmatter only.

## Phase 5: OpenCode Installer Rewire

- [x] 5.1 **RED** `tests/test_install.py` — `jd/`, `review/`, `orchestrator/` prompts copied; `opencode.json` inline strings → `{file:}` refs. Covers: "OpencodeInstaller produces valid opencode.json".
- [x] 5.2 **GREEN** `opencode.json` — replace inline `prompt` strings for jd/review with `{file:{{HOME}}/...}`.
- [x] 5.3 **GREEN** `opencode.py` — glob `prompts/{jd,review,orchestrator}/` → `FileArtifact` targets.
- [x] 5.4 **GREEN** `opencode.py` — shim: substituted `opencode.json` → `agent-clis/opencode/opencode.json`.

## Phase 6: Claude Permissions Rewire

- [x] 6.1 **RED** `tests/test_permissions.py` — tool lists (not paths) → permissions; only installed agents contribute. Covers: "Metadata-driven tool union".
- [x] 6.2 **GREEN** `permissions.py` — `install_permissions_from_tools(list[list[str]])`; map `TOOL_TO_RULE`.
- [x] 6.3 **GREEN** `claude.py._install_permissions` — call with `_METADATA[agent_id]["tools"]` + orchestrator.

## Phase 7: Verification

- [x] 7.1 `uv run pytest` — all green, zero e2e modifications.
- [x] 7.2 `e2e/docker-test.sh` — full e2e green, byte-equivalent output.

## Phase 8: Catalog Cleanup

- [x] 8.1 `catalog.py` — add `JD_PROMPTS_SRC`, `REVIEW_PROMPTS_SRC`, `ORCHESTRATOR_PROMPTS_SRC`.
- [x] 8.2 `catalog.py` — remove dead path refs.

## TDD Ordering

Phases 1→8 sequentially. Each phase: RED → GREEN → verify `uv run pytest` green.

## Out-of-Scope

Hook JSON file-sourced. Permission blocks static. Template engines, new providers, AGENTS.md/skills unchanged.
