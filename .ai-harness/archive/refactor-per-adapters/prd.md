# PRD — refactor-per-adapters

## Intent

Refactor the change-agent rendering subsystem so each supported agent CLI is managed by a provider-specific artifacts administrator behind a common contract. The change should move provider metadata out of Python constants, make install paths part of each provider's ownership, and give callers a single polymorphic path for rendering installable artifacts.

This is Option 3: administrator classes own template discovery, metadata loading, override merging, rendering, and install-path layout. The user has explicitly approved keeping this as one change even though exploration estimates the implementation budget at 950 LOC.

## Scope

### In

- Introduce a common artifacts-administrator contract with a caller-facing method equivalent to `render_artifacts(names, overrides, *, home)`.
- Add three concrete administrators:
  - `ClaudeArtifactsAdministrator`
  - `OpenCodeArtifactsAdministrator`
  - `CopilotArtifactsAdministrator`
- Add an `ADMINISTRATORS` dispatch table keyed by `AgentCli` so callers select the administrator once and then call the shared contract polymorphically.
- Move hardcoded agent metadata out of `_AGENT_META` in `src/ai_harness/modules/harness/renderers.py` into JSON resources under `src/ai_harness/resources/`.
- Use one metadata JSON file per agent under `src/ai_harness/resources/agent-metadata/`, for example `agent-metadata/change-explorer.json`.
- Replace `RenderedFile` with a new `Artifact` type that exposes:
  - `install_path`: a home-relative POSIX path for installation.
  - `content`: the full file content to write.
- Update production callers in `operations.py`, `wizard/tui.py`, and `wizard/pure.py` to use the new administrator surface.
- Update tests in `tests/test_renderers.py`, `tests/test_install.py`, and `tests/test_set_models.py` to assert the new public administrator behavior rather than old tuple/private-helper coupling where possible.
- Update `e2e/e2e_test.sh` expectations only where names or paths are affected by the new public contract; provider-visible installed paths should remain stable.
- Preserve current behavior for sorted discovery, `_`-prefixed template exclusion, duplicate detection, deep override merging, explicit `overrides={}` semantics, malformed override-store failure, missing metadata failure, and provider-specific frontmatter/path behavior.

### Out

- No decomposition into child changes.
- No source-file changes outside the affected implementation, caller, test, e2e, and documentation surfaces needed for this refactor.
- No new supported agent CLI beyond Claude, OpenCode, and Copilot.
- No redesign of persona/static skills installation outside the existing interaction with rendered Claude skills.
- No exact JSON schema freeze for caps, explicit permission, model, effort, or mode fields; the PRD selects the metadata layout, while field-level schema belongs to design.
- No backward-compatibility promise for `render_agents`, `get_agent_meta`, `write_override_store`, or `RenderedFile` as public APIs.

## Capabilities

- Provider administrator dispatch: callers can select `ADMINISTRATORS[AgentCli.X]` and render installable artifacts through the same method without branching on provider internals.
- Claude artifact administration: Claude rendering owns discovery, metadata loading, override merging, skill-vs-agent mode dispatch, frontmatter generation, and `.claude/...` install paths.
- OpenCode artifact administration: OpenCode rendering owns discovery, metadata loading, override merging, permission/model/effort frontmatter generation, and `.config/opencode/agent/...` install paths.
- Copilot artifact administration: Copilot rendering owns discovery, metadata loading, override merging as applicable, prompt rendering, and `.github/instructions/...` install paths while preserving Copilot's minimal provider semantics.
- JSON-backed metadata resources: agent metadata is loaded from package resources under `src/ai_harness/resources/agent-metadata/*.json` instead of being embedded in `_AGENT_META`.
- Artifact output contract: renderer output is expressed as `Artifact(install_path, content)` so operations writes home-relative paths without knowing provider layout.
- Override-store continuity: existing `~/.ai-harness/overrides.json` behavior remains available through a shared override-store helper used by administrators and the wizard.
- Caller migration: install, re-render, set-models, tests, and e2e flows are updated in-place to the new administrator contract in the same change.

## Approach

The implementation should reshape `renderers.py` around a deep module boundary: provider administrators expose a small common contract, while hiding resource discovery, metadata decoding, override application, provider rendering, and install-path rules.

Product-level decisions:

- **JSON metadata layout: one file per agent.** Store metadata in `src/ai_harness/resources/agent-metadata/<agent-name>.json`. This keeps each template's metadata near its identity, reduces merge conflicts compared with a single monolithic `agent-metadata.json`, and avoids duplicating shared descriptions/modes across per-CLI files. Discovery should still be driven by sorted `change-agent/*.md` templates, then validated against metadata files so install order remains stable and template/metadata drift is loud.
- **Artifact vs RenderedFile: fully replace with `Artifact`.** The old `RenderedFile(filename, content)` name and field imply a renderer-owned filename rather than a provider-owned install artifact. This change should introduce a new `Artifact` type with `install_path` and `content`, remove direct use of `RenderedFile`, and update callers/tests in place rather than keeping a compatibility alias that would preserve the wrong abstraction.
- **Override-store ownership: shared helper, administrator-consumed.** The override store is not provider-specific product behavior; it is shared ai-harness state. Keep load/save/deep-merge behavior in a shared helper within the rendering/admin module boundary, and have each administrator consume it when `overrides is None`. The wizard should persist overrides through the same helper or through a narrow exported override-store function, not through any one provider administrator.
- **Discovery and mode dispatch: inside administrators.** Template discovery, provider metadata loading, and provider-specific routing all move into administrators. Claude owns its skill-vs-agent routing and install paths; OpenCode owns agent file routing and permission rendering; Copilot owns its instruction layout. Operations should no longer assemble rendered paths or know provider mode details.
- **Migration strategy: in-place break to the new seam.** Do not build a compatibility shim around `render_agents`, `get_agent_meta`, `write_override_store`, or `RenderedFile`. This is an internal coordinated refactor; production callers and tests should move to the administrator contract in the same change. Any retained helper should be named for its new responsibility, not for backwards compatibility.

The design phase should define the exact metadata JSON schema and decoder/validation rules, including how `AgentCaps`, explicit OpenCode `permission`, provider `model`, provider `effort`, and provider-specific mode values are represented.

## Affected Areas

- `src/ai_harness/modules/harness/renderers.py` — primary refactor target; introduce the administrator contract, `Artifact`, resource metadata loading, override helper usage, provider rendering, and `ADMINISTRATORS` dispatch.
- `src/ai_harness/resources/agent-metadata/*.json` — new resource directory holding one metadata file per change-agent template.
- `src/ai_harness/resources/change-agent/*.md` — existing prompt templates remain body-only and remain the source for sorted agent discovery.
- `src/ai_harness/resources/skills/` — Claude installation must continue to coexist with rendered primary skills under `.claude/skills/<name>/SKILL.md`.
- `src/ai_harness/modules/harness/models.py` — `AgentCli` remains the dispatch key; no new enum value is required.
- `src/ai_harness/modules/harness/operations.py` — replace `render_agents` usage with administrator dispatch and write `Artifact.install_path`.
- `src/ai_harness/modules/wizard/tui.py` — replace metadata and override-store imports with the new helper/administrator surface.
- `src/ai_harness/modules/wizard/pure.py` — keep wizard agent vocabulary aligned with administrator discovery/metadata expectations or explicitly validate drift in tests.
- `tests/test_renderers.py` — migrate renderer assertions to administrator contract, `Artifact`, metadata-resource loading, and provider-specific behavior.
- `tests/test_install.py` — update install/re-render integration assertions for `Artifact.install_path` and administrator dispatch.
- `tests/test_set_models.py` — keep deep-merge override-store coverage against the new helper surface.
- `e2e/e2e_test.sh` — preserve real install-path checks for Claude/OpenCode/Copilot and override behavior.
- `README.md` — update user-facing wording if it references the old renderer API, metadata location, or set-models override behavior.

## Risks

- Metadata-resource drift: a template without metadata or metadata without a template could silently omit or misconfigure an agent unless validation fails loudly.
- JSON decoding impedance: existing `AgentCaps` and explicit OpenCode permission behavior are typed in Python today; a weak decoder could silently change permissions or frontmatter.
- Claude asymmetry: primary Claude agents render as skills and currently ignore some frontmatter/model/effort concerns while still using metadata for orchestration prose and spawn behavior.
- Override semantics drift: `overrides=None` must continue to load from `home/.ai-harness/overrides.json`, while `overrides={}` must remain an explicit no-disk-read path.
- Test coupling: existing tests import private helpers and tuple fields, so incomplete migration can either overfit to internals or miss behavior regressions.
- Manifest stability: install-path ownership moving into administrators must not change installed path ordering or manifest content unless intentionally documented.
- Public API removal blast radius: even if these APIs are internal to the package, all production callers and tests must be updated in one pass.

## Rollback Plan

- Revert the refactor commit to restore `_AGENT_META`, `RenderedFile`, `render_agents`, `get_agent_meta`, and `write_override_store` behavior.
- Because this change should preserve installed file paths and override-store JSON location, rollback should not require user data migration.
- If JSON metadata resources are introduced but rollback is needed before release, remove the new resource directory and restore hardcoded metadata from version control.
- If a released build fails, ship a patch that restores the old rendering path while leaving `~/.ai-harness/overrides.json` untouched.

## Dependencies

- Python package-resource loading via `importlib.resources` continues to work for JSON files under `src/ai_harness/resources/`.
- Existing YAML frontmatter rendering behavior remains available.
- Existing `AgentCli` enum remains the product vocabulary for selecting providers.
- Existing override-store path remains `~/.ai-harness/overrides.json`.
- Test and e2e coverage must be updated alongside implementation to validate provider behavior end-to-end.

## Success Criteria

- `src/ai_harness/modules/harness/renderers.py` no longer contains `_AGENT_META` as the source of hardcoded metadata.
- Metadata for all current change agents exists as JSON resources under `src/ai_harness/resources/agent-metadata/` and is validated against discovered templates.
- `Artifact` replaces `RenderedFile` in production code and tests, with `install_path` and `content` as the output contract.
- `ADMINISTRATORS[AgentCli.CLAUDE]`, `ADMINISTRATORS[AgentCli.OPENCODE]`, and `ADMINISTRATORS[AgentCli.COPILOT]` render through a shared contract.
- Operations writes artifacts using `home / artifact.install_path` and no longer depends on provider-specific rendered filenames.
- Wizard set-models flows can read current metadata-derived model/effort values, persist overrides, and trigger re-render without importing the old public renderer functions.
- Existing installed paths remain stable for Claude, OpenCode, and Copilot unless a test documents an intentional product change.
- Override-store deep merge, malformed JSON failure, missing-file no-op, and explicit empty override semantics are preserved.
- `tests/test_renderers.py`, `tests/test_install.py`, `tests/test_set_models.py`, full `pytest`, and `e2e/e2e_test.sh` pass after implementation.
