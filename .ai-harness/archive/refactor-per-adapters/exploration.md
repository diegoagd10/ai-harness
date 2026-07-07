# Exploration — refactor-per-adapters

## Budget
950

## Affected Files
- `src/ai_harness/modules/harness/renderers.py` — primary refactor target; currently owns `RenderedFile`, `AgentCaps`, `_AGENT_META`, override loading/merging, template discovery, CLI-specific rendering, and install-path layout.
- `src/ai_harness/resources/agent-metadata.json` or `src/ai_harness/resources/agent-metadata/*.json` — new JSON resource location for data now hardcoded in `_AGENT_META`; no JSON metadata resources exist today.
- `src/ai_harness/resources/change-agent/*.md` — prompt templates are discovered by filename; admin classes should preserve sorted discovery, underscore exclusion, duplicate detection, and body-only template semantics.
- `src/ai_harness/resources/skills/` — Claude install copies this tree and Claude primary agents render as skills under `.claude/skills/<name>/SKILL.md`; path interactions must remain manifest-stable.
- `src/ai_harness/resources/AGENTS.md` — static persona copied by install; not directly rendered, but part of the same install surface and manifest expectations.
- `src/ai_harness/modules/harness/models.py` — `AgentCli` enum drives administrator selection (`CLAUDE`, `OPENCODE`, `COPILOT`, `GENERIC`).
- `src/ai_harness/modules/harness/operations.py` — imports `render_agents`; `_write_rendered_agents()` currently expects `.filename` and `.content` and writes returned home-relative paths.
- `src/ai_harness/modules/harness/__init__.py` — may need re-export changes only if the new renderer/admin public surface should be package-level; currently does not export renderers directly.
- `src/ai_harness/modules/wizard/tui.py` — imports `get_agent_meta` and `write_override_store`; current-value helpers read `model`/`effort`, and confirm phases persist overrides then call `re_render_for_agent_clis()`.
- `src/ai_harness/modules/wizard/pure.py` — hardcoded Claude/OpenCode change-agent tuples mirror renderer discovery; not importing renderers, but schema/name drift can break set-models assumptions.
- `tests/test_renderers.py` — largest direct test surface; imports `AgentCaps`, `_claude_tools`, `_discover_agents`, `_opencode_permission`, `get_agent_meta`, `render_agents`; asserts tuple unpacking, layouts, frontmatter, override semantics, private discovery, and metadata behavior.
- `tests/test_install.py` — imports `AgentCaps`, `_claude_tools`, `_opencode_permission`, `get_agent_meta`, and locally imports `_discover_agents`; asserts install/re-render paths, manifest stability, override behavior, and expected frontmatter derived from metadata.
- `tests/test_set_models.py` — imports `_load_override_store` and `write_override_store`; tests deep-merge writer and round-trip loading used by the wizard.
- `e2e/e2e_test.sh` — asserts installed rendered paths and override behavior for Claude/OpenCode, including `.config/opencode/agent/*`, `.claude/skills/change-orchestrator/SKILL.md`, and `~/.ai-harness/overrides.json`.
- `README.md` — documents install rendering, set-models override store, and Copilot agent layout; may need wording if public API/resource shape changes.

## Plan
- Introduce a new `Artifact` type with `install_path` and `content`; migrate operations/tests from `RenderedFile.filename` or tuple unpacking to `Artifact.install_path`.
- Define a common administrator contract for discovery, metadata loading, override merging, rendering, and install-path layout; implement `ClaudeArtifactsAdministrator`, `OpenCodeArtifactsAdministrator`, and `CopilotArtifactsAdministrator` behind a small provider-selection seam keyed by `AgentCli`.
- Move `_AGENT_META` to JSON resources under `src/ai_harness/resources/`; prefer a per-agent or per-CLI split only after deciding how `caps` and explicit `permission` encode. Keep resource names aligned with `change-agent/*.md` filenames.
- Preserve current behavior while moving ownership: sorted template discovery, `_`-prefixed template exclusion, duplicate detection, missing/malformed override-store behavior, deep-merge semantics, and explicit-overrides bypassing ambient `HOME`.
- Keep override-store read/write centralized or expose it through the new contract so `set-models` does not reimplement store paths; update wizard imports to the new API.
- Update tests from private function and tuple-based expectations toward public administrator behavior where possible; retain targeted tests for metadata schema decoding and permission/tool translation.

## Edge Cases
- JSON cannot serialize `AgentCaps` instances directly; the schema needs an explicit shape such as `{ "caps": { "write": false, "bash": true, "spawn": ["change-explorer"] } }`, decoded to `AgentCaps`, or renderers must operate on plain dict caps.
- Explicit OpenCode `permission` dict currently overrides caps-derived permissions for `change-orchestrator`; JSON schema must support both explicit `permission` and neutral `caps`, with deterministic precedence.
- `mode` has provider-specific meanings: `primary` routes Claude to a skill path, OpenCode emits `mode: primary`, and Copilot ignores mode for frontmatter/path.
- Claude primary skill overrides are currently mostly ignored for frontmatter/model/effort but `get_agent_meta()` is still consulted and spawn allowlist may inject prose; the admin split must preserve that subtle asymmetry.
- `overrides=None` means load `home/.ai-harness/overrides.json`; `overrides={}` means do not read disk. Mode dispatch must use the same explicit override object to avoid ambient `HOME` bleed.
- Discovery order is currently sorted by resource filename, producing `change-archiver`, `change-design`, `change-explorer`, etc.; changing metadata storage must not reorder install output or manifest contents.
- Resource/template mismatch needs a clear failure mode: template without metadata, metadata without template, duplicate template names, and missing provider model values should remain loud where currently loud.
- Copilot intentionally ignores model/effort/permission and requires no `model.copilot`; a shared contract must not force provider metadata that Copilot does not use.
- Existing user override stores may contain keys unrelated to current templates; current deep merge leaves unrelated entries untouched.

## Test Surface
- `pytest tests/test_renderers.py` — renderer/admin contract, layouts, frontmatter, metadata loading, overrides, discovery, caps/permission translation, Copilot behavior.
- `pytest tests/test_install.py` — install/re-render integration, absolute write paths, manifest idempotency, override application through operations.
- `pytest tests/test_set_models.py` — override-store writer/loader and wizard payload compatibility after API reshaping.
- `pytest` — catches cross-module imports from the removed/reshaped public API.
- `e2e/e2e_test.sh` or equivalent project e2e gate — validates installed file paths and override behavior in a real HOME sandbox.

## Risks
- **Schema fork:** one big JSON file is simplest and preserves global ordering, but increases merge conflicts; one file per agent localizes changes but needs explicit ordering/discovery validation; per-CLI split duplicates shared descriptions/modes and risks drift. A per-agent metadata file or one central `agent-metadata.json` with sorted template discovery are the safest candidates.
- **Dataclass-vs-JSON impedance:** `AgentCaps` and `permission.task` contain typed tuples and nested dicts; without a decoder/validator, plain dicts can silently change renderer behavior because current checks use `isinstance(caps, AgentCaps)`.
- **Private API coupling:** tests currently import private helpers (`_discover_agents`, `_claude_tools`, `_opencode_permission`, `_load_override_store`), so a clean admin design requires coordinated test migration rather than just product-code edits.
- **Public API removal blast radius:** `operations.py` and `wizard/tui.py` are direct production callers; removing `render_agents`, `get_agent_meta`, or `write_override_store` without replacement breaks install and set-models.
- **Path-layout ownership shift:** operations currently joins `home / rendered.filename`; changing to `install_path` is small but touches manifest/idempotency assertions and e2e path checks.
- **Behavioral drift:** YAML key ordering, omission of empty permission/effort fields, Claude skill prose injection, and Copilot frontmatter minimalism are all asserted behavior.

## semantic_facts
- `budget`: 950
- `follow_up`: Decide JSON metadata layout and caps/permission schema; choose the replacement public seam for install and set-models; migrate tests off tuple/private renderer assumptions where the new administrator contract should be authoritative.
