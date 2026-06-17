# Exploration: build-agent-clis-from-prompts

## Context

Round 1 (`refactor-agent-clis-installer-architecture`) moved canonical prompt bodies to `src/ai_harness/resources/prompts/{jd,review,orchestrator,sdd}/` and embedded per-agent frontmatter as Python `_METADATA` dicts, but it kept the `src/ai_harness/resources/agent-clis/` tree as an e2e shim target. Installers wrote composed output back to those source paths on every install, which overwrote and corrupted the committed files (e.g., `opencode.json` now contains hard-coded `/tmp/pytest-of-diegoagd10/...` `{file:...}` paths). The user’s Round 2 intent is to delete every file under `agent-clis/` and have each installer build its artifacts entirely from canonical prompt bodies + embedded metadata + provider-specific glue. The five e2e path constants may be retargeted, but no e2e test logic may change.

## Canonical prompt inventory

| Body file | Provider consumers | Installer metadata entry |
|---|---|---|
| `prompts/sdd/sdd-explore.md` | opencode, claude, copilot | `_METADATA["sdd-explore"]` |
| `prompts/sdd/sdd-propose.md` | opencode, claude, copilot | `_METADATA["sdd-propose"]` |
| `prompts/sdd/sdd-spec.md` | opencode, claude, copilot | `_METADATA["sdd-spec"]` |
| `prompts/sdd/sdd-design.md` | opencode, claude, copilot | `_METADATA["sdd-design"]` |
| `prompts/sdd/sdd-tasks.md` | opencode, claude, copilot | `_METADATA["sdd-tasks"]` |
| `prompts/sdd/sdd-apply.md` | opencode, claude, copilot | `_METADATA["sdd-apply"]` |
| `prompts/sdd/sdd-verify.md` | opencode, claude, copilot | `_METADATA["sdd-verify"]` |
| `prompts/sdd/sdd-archive.md` | opencode, claude, copilot | `_METADATA["sdd-archive"]` |
| `prompts/sdd/sdd-orchestrator.md` | opencode, copilot | `_METADATA["sdd-orchestrator"]` (task variant) |
| `prompts/orchestrator/sdd-orchestrator-agent.md` | claude | `_METADATA["sdd-orchestrator"]` (Agent variant) |
| `prompts/jd/jd-fix-agent.md` | opencode, claude, copilot | `_METADATA["jd-fix-agent"]` |
| `prompts/jd/jd-judge-a.md` | opencode, claude, copilot | `_METADATA["jd-judge-a"]` |
| `prompts/jd/jd-judge-b.md` | opencode, claude, copilot | `_METADATA["jd-judge-b"]` |
| `prompts/review/review-risk.md` | opencode, claude, copilot | `_METADATA["review-risk"]` |
| `prompts/review/review-readability.md` | opencode, claude, copilot | `_METADATA["review-readability"]` |
| `prompts/review/review-reliability.md` | opencode, claude, copilot | `_METADATA["review-reliability"]` |
| `prompts/review/review-resilience.md` | opencode, claude, copilot | `_METADATA["review-resilience"]` |

Observations:
- All 17 bodies are provider-agnostic and contain no YAML frontmatter, tool names, or model keys.
- The orchestrator has two genuinely different bodies: the task variant references the platform `task` tool; the Agent variant references Claude’s `Agent` tool.

## Source files to delete

All files under `src/ai_harness/resources/agent-clis/` are obsolete once installers generate everything from code. Deleting the files will leave the `agent-clis/` directories empty; the directories themselves should also be removed.

**Claude (16 files)**
- `agent-clis/claude/agents/sdd-*.md` (8 phase frontmatter-only files)
- `agent-clis/claude/agents/jd-*.md` (3 files)
- `agent-clis/claude/agents/review-*.md` (4 files)
- `agent-clis/claude/sdd-orchestrator/SKILL.md` (orchestrator body)

Rationale: frontmatter moves to `ClaudeInstaller._METADATA`; bodies already live in `prompts/`. The orchestrator body is duplicated by `prompts/orchestrator/sdd-orchestrator-agent.md`.

**Copilot CLI (17 files)**
- `agent-clis/copilot-cli/agents/sdd-*.md` (9 files including orchestrator)
- `agent-clis/copilot-cli/agents/jd-*.md` (3 files)
- `agent-clis/copilot-cli/agents/review-*.md` (4 files)
- `agent-clis/copilot-cli/hooks/sdd-pre-tool-use.json`

Rationale: frontmatter and hook policy move to `CopilotInstaller._METADATA` and code-generated JSON.

**OpenCode (4 files)**
- `agent-clis/opencode/opencode.json`
- `agent-clis/opencode/blocks/sdd-model-assignments.md`
- `agent-clis/opencode/plugins/model-variants.ts`
- `agent-clis/opencode/plugins/model-variants.test.ts`

Rationale: `opencode.json` is generated from `OpencodeInstaller._METADATA`; the blocks and plugins are OpenCode-only runtime assets that are **not installed today** and have no Claude/Copilot analogue.

## Installer changes

### `src/ai_harness/artifacts/installers/opencode.py`
- Add a `_METADATA: dict[str, dict]` describing every agent (name, description, mode, hidden, model, tools, permission overrides, prompt path).
- Remove `OpencodeAssets.config_path` and all references to `agent-clis/opencode/opencode.json`.
- Build `opencode.json` in memory from `_METADATA` + `{file:{{HOME}}/...}` references.
- Remove `_write_shim`; add `_write_fixture` that writes the generated `opencode.json` to the e2e fixture path.

### `src/ai_harness/artifacts/installers/claude.py`
- Extend `_METADATA` to cover the 8 SDD phases and the orchestrator in addition to the 7 inline agents.
- Remove `ClaudeAssets.agents_dir` and `ClaudeAssets.orchestrator_dir`.
- Change all 15 agents to `ComposedFileArtifact(frontmatter_text=..., body_source=...)`, with SDD bodies from `prompts/sdd/` and inline-agent bodies from `prompts/jd/` / `prompts/review/`.
- Compose the orchestrator skill from metadata frontmatter + `prompts/orchestrator/sdd-orchestrator-agent.md`.
- Remove `_write_shims`; add `_write_fixtures` writing frontmatter-only/composed files to the new e2e fixture directory.
- `_install_permissions` already uses metadata; no functional change, just remove any lingering fallback that reads from `agent-clis/`.

### `src/ai_harness/artifacts/installers/copilot.py`
- Extend `_METADATA` to cover all 16 agents (8 phases + orchestrator + 7 inline).
- Remove `CopilotAssets.agents_dir` and `CopilotAssets.hooks_dir`.
- Build all 16 agents as `ComposedFileArtifact(frontmatter_text=..., body_source=...)`.
- Generate `sdd-pre-tool-use.json` in code from the tool allowlist and the deny-path list (mirroring OpenCode `permission.external_directory`).
- Remove `_write_shims`; add `_write_fixtures`.
- `_validate_composed_budget` can drop the `frontmatter_source` branch and measure `frontmatter_text` directly.

### `src/ai_harness/artifacts/installers/permissions.py`
- No shim write exists here. `install_permissions_from_tools` is already metadata-driven, so no changes are required.

### `src/ai_harness/artifacts/installer.py`
- `ComposedFileArtifact.frontmatter_text` remains the primary path.
- The dual-path handling in `_prepare_composed_content` can be simplified: make `frontmatter_text` required and remove the `frontmatter_source` extraction logic. Keeping the dual path is harmless but dead code after Round 2.

### `src/ai_harness/artifacts/manifest.py`
- Drop `frontmatter_source: Path | None` (or keep it optional for backward compatibility). If the proposal chooses the simpler model, make `frontmatter_text` required and remove `frontmatter_source`.

### `src/ai_harness/artifacts/catalog.py`
- Remove `OPENCODE_JSON_SRC` (no static opencode.json source exists anymore).
- Keep `JD_PROMPTS_SRC`, `REVIEW_PROMPTS_SRC`, `ORCHESTRATOR_PROMPTS_SRC`, `OPENCODE_SDD_PROMPTS_SRC`.
- Optionally add a generated-fixture constant if unit tests need it; otherwise leave fixture paths local to installers.

## Catalog changes

| Line | Current | Change |
|---|---|---|
| 19 | `OPENCODE_JSON_SRC = RESOURCES_DIR / "agent-clis" / "opencode" / "opencode.json"` | Delete this constant. `opencode.json` is generated, not sourced from a static file. |

`AGENTS_MD_SRC`, `SKILLS_SRC`, `OPENCODE_SDD_PROMPTS_SRC`, `JD_PROMPTS_SRC`, `REVIEW_PROMPTS_SRC`, and `ORCHESTRATOR_PROMPTS_SRC` remain correct.

## E2e constant updates

The existing e2e logic reads a source file/directory and compares it to the installed artifact. Because `agent-clis/` disappears, installers must write equivalent fixture files to a generated directory that the constants can target. `resources/generated/` should be created at install time and gitignored.

| Constant | Current path | Proposed new path | Justification |
|---|---|---|---|
| `OPENCODE_JSON_SRC` | `agent-clis/opencode/opencode.json` | `generated/opencode/opencode.json` | Installer generates `opencode.json`; this is the deterministic fixture copy. |
| `CLAUDE_AGENTS_SRC` | `agent-clis/claude/agents` | `generated/claude/agents` | Installer writes frontmatter-only SDD files and fully composed inline files here. |
| `CLAUDE_ORCHESTRATOR_SRC` | `agent-clis/claude/sdd-orchestrator/SKILL.md` | `generated/claude/sdd-orchestrator/SKILL.md` | Installer composes the orchestrator skill here. |
| `COPILOT_AGENTS_SRC` | `agent-clis/copilot-cli/agents` | `generated/copilot-cli/agents` | Same pattern as Claude. |
| `COPILOT_HOOKS_SRC` | `agent-clis/copilot-cli/hooks` | `generated/copilot-cli/hooks/sdd-pre-tool-use.json` | Installer generates the hook JSON here. |

All five constants live in `e2e/test_harness_lifecycle.py` and `e2e/test_copilot_cli_lifecycle.py`. Only the right-hand side of the assignment changes; the assertion logic is untouched.

## Test updates

| Test file | Required changes |
|---|---|
| `tests/test_prompt_inventory.py` | Remove or rewrite `test_no_byte_identical_copy_in_agent_clis` (the directory will not exist). Add a test asserting `agent-clis/` is absent. Update `_CANONICAL_PROMPT_PATHS` comments to reflect that orchestrator Agent variant is consumed by Claude. |
| `tests/test_manifest.py` | Remove tests for `frontmatter_source` if the proposal simplifies `ComposedFileArtifact`; keep `frontmatter_text` tests. |
| `tests/test_claude_installer.py` | Major rewrite: remove all `agent-clis/` fixture creation; assert all 15 agents use `frontmatter_text`; assert bodies come from `prompts/{sdd,jd,review}/`; assert orchestrator body comes from `prompts/orchestrator/sdd-orchestrator-agent.md`; assert fixtures are written to `generated/claude/`. |
| `tests/test_copilot_installer.py` | Major rewrite: same pattern as Claude; additionally assert hook JSON is generated in code, not a `FileArtifact`. |
| `tests/test_install.py` | Stop importing `OPENCODE_JSON_SRC` from `catalog`. Verify generated `opencode.json` content via the installer or fixture file. Keep prompt-copy assertions. |
| `tests/test_permissions.py` | No changes required; permissions are already metadata-driven. |
| `tests/test_catalog.py` | Update `test_get_resource_dir` to use a non-`agent-clis` example path. |

New tests should pin the build-from-code behavior (e.g., "no file under `agent-clis/` is read", "`opencode.json` prompt fields are `{file:{{HOME}}/...}` after substitution", "Copilot hook allowlist equals the 15 subagent names").

## Open decisions for proposal

1. **Orchestrator file disposition**: Keep both `prompts/sdd/sdd-orchestrator.md` (consumed by OpenCode and Copilot) and `prompts/orchestrator/sdd-orchestrator-agent.md` (consumed by Claude). The judgment-day dead-code flag is incorrect: the Agent variant is required because Claude’s orchestrator uses the `Agent` tool, while OpenCode/Copilot use `task`.
2. **OpenCode blocks/plugins**: Delete `opencode/blocks/sdd-model-assignments.md` and `opencode/plugins/*` along with the rest of `agent-clis/`. They are not installed today and have no cross-provider analogue.
3. **Copilot hook source**: Generate `sdd-pre-tool-use.json` entirely from code. The deny-path list should mirror OpenCode’s `permission.external_directory` entries.
4. **E2e fixture directory**: Use `src/ai_harness/resources/generated/` and gitignore it. The installer writes fixtures there on install so e2e constants resolve without logic changes. Confirm whether fixture writing should be unconditional or guarded by an env var to avoid production installs touching the source tree.

## Risks

- **E2e fixture coupling**: Moving constants to `resources/generated/` means the installer must write fixtures on every install. If fixture writing fails or is skipped, e2e will fail even though the user-facing install succeeded.
- **Production install side effects**: Writing generated fixtures under `src/ai_harness/resources/` during a normal `ai-harness install` could pollute the installation source tree or fail in read-only installs. A guard (e.g., only when `resources/generated/` already exists or an env var is set) is advisable.
- **Byte-equivalence drift**: Any difference between generated fixture content and installed content (trailing newlines, `{{HOME}}` substitution, JSON key order) will break e2e byte comparisons.
- **OpenCode JSON generation complexity**: `opencode.json` is the largest generated artifact. Encoding every agent entry, permission block, and model key in `_METADATA` will be verbose; a small schema helper is needed to keep the code readable.
- **Copilot hook policy drift**: The deny paths are duplicated between OpenCode `permission.external_directory` and Copilot hook JSON. A shared deny-path constant should be extracted to keep them in sync.
- **Coverage**: The installer modules already have sub-95% coverage on error branches. Generating more artifacts in code will add more branches; budget for new tests is needed.
- **Static resource packaging**: `pyproject.toml` does not explicitly declare package data. After deleting `agent-clis/`, verify that `uv_build` still packages `resources/prompts/` and `resources/skills/`.
