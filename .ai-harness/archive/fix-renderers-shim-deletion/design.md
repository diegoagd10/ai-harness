# Design — fix-renderers-shim-deletion

## Context

This change deletes the deprecated `ai_harness.modules.harness.renderers` compatibility shim and makes `ai_harness.modules.harness.administrators` the only load-bearing rendering/metadata API. User-visible install and wizard behavior must remain unchanged; this is a boundary cleanup plus test migration. The implementation loop must migrate all runtime imports, test imports, local imports, and monkeypatch strings before deleting `renderers.py`, because deleting the shim first creates collection-time failures that hide the real migration work.

Pre-change module shape:

```text
+---------------------+        +-------------------------------------+
| wizard/tui.py       |------->| harness/renderers.py (shim)         |
| imports             |        | re-exports public administrator API |
| ADMINISTRATORS      |        | owns legacy render_agents/get_meta  |
+---------------------+        +------------------+------------------+
                                            |
                                            v
                           +-----------------------------------------+
                           | harness/administrators/                 |
                           | __init__.py, base.py, claude.py,        |
                           | opencode.py, copilot.py                |
                           +------------------+----------------------+
                                              |
                                              v
                           +-----------------------------------------+
                           | override_store.py                       |
                           | deep_merge + optional disk-backed load  |
                           +-----------------------------------------+

+---------------------+        +-------------------------------------+
| tests/test_renderers.py ---->| harness/renderers.py                 |
| tests/test_install.py   |    | imports, local imports, monkeypatch  |
+---------------------+        | strings, legacy shim tests           |
                               +-------------------------------------+
```

Post-change module shape:

```text
+---------------------+        +-------------------------------------+
| wizard/tui.py       |------->| harness/administrators/__init__.py  |
| imports             |        | public dispatch + public types       |
| ADMINISTRATORS      |        +------------------+------------------+
+---------------------+                           |
                                                    v
                           +-----------------------------------------+
                           | administrators/base.py                  |
                           | Artifact, AgentMetadata, AgentCaps,    |
                           | ArtifactsAdministrator, shared helpers  |
                           +-----+----------------+------------------+
                                 |                |
                                 v                v
                     +-------------------+  +------------------------+
                     | override_store.py |  | provider modules       |
                     | deep_merge/load   |  | claude/opencode/copilot|
                     +-------------------+  +------------------------+

+---------------------+        +-------------------------------------+
| tests/test_renderers.py ---->| administrators/__init__.py          |
| public behavior      |        | public API imports                  |
|                     |        +-------------------------------------+
| private helper tests |------->| administrators/base.py              |
| provider helpers     |------->| administrators/{provider}.py        |
+---------------------+        +-------------------------------------+

+---------------------+        +-------------------------------------+
| tests/test_install.py|------->| administrators/__init__.py          |
+---------------------+        +-------------------------------------+
```

## Deep modules

### `administrators/__init__.py` — public administrator dispatch seam
- Seam: `ai_harness.modules.harness.administrators` is the public import boundary for runtime code and tests that need administrator dispatch, public dataclasses, concrete administrator classes, discovery, or metadata loading.
- Interface: `ADMINISTRATORS: dict[AgentCli, ArtifactsAdministrator]`; `AgentCaps`; `AgentMetadata`; `Artifact`; `ArtifactsAdministrator`; `ClaudeArtifactsAdministrator`; `OpenCodeArtifactsAdministrator`; `CopilotArtifactsAdministrator`; `discover_agent_names()`; `load_agent_metadata(name: str)`. Callers select `ADMINISTRATORS[AgentCli.X]` and call the common administrator contract instead of branching on provider internals.
- Hides: The package layout, concrete provider construction, import ordering between base/provider modules, and the fact that shared helper functions live in `base.py` while provider-specific rendering lives in sibling modules.
- Depth note: This is deep because a tiny dispatch/import surface hides all provider rendering, resource discovery, metadata decoding, and override behavior; deleting it would force every caller to know the provider modules directly.

### `administrators/base.py` — shared administrator contract and resource/metadata core
- Seam: Public types and shared helper implementation used by every provider administrator. Runtime callers normally reach the public names through `administrators/__init__.py`; existing private-helper tests may import `base.py` directly as an intentional intra-package seam.
- Interface: `Artifact(install_path: str, content: str)`; `AgentCaps(write=True, bash=True, spawn=None)`; `AgentMetadata(description, mode, model, effort, caps, permission, color)`; `ArtifactsAdministrator.render_artifacts(names=None, overrides=None, *, home=None)`; `ArtifactsAdministrator.get_agent_metadata(name, overrides=None, *, home=None)`; `ArtifactsAdministrator.discover_agent_names()`; public `load_agent_metadata(name)` and `discover_agent_names()`. Private helper test imports live here for `_validate_metadata_schema`, `_decode_agent_caps`, `_decode_effort_map`, `_decode_model_map`, `_decode_permission`, `_decode_agent_metadata`, `_AGENT_RESOURCE_DIRS`, and `files`.
- Hides: Importlib resource traversal, duplicate template detection, metadata JSON schema validation, capability decoding, model/effort/permission decoding, template body reads, deterministic YAML frontmatter dumping, and override resolution through `override_store.deep_merge`/`load_override_store`.
- Depth note: This module earns the seam because provider modules share substantial complexity through a small contract. The private helpers are not new public API; they are allowed only to preserve existing helper tests during shim deletion.

### `administrators/claude.py` — Claude artifact administrator
- Seam: `ClaudeArtifactsAdministrator`, selected through `ADMINISTRATORS[AgentCli.CLAUDE]`, owns all Claude-specific artifact rendering.
- Interface: Implements `render_artifacts(names=None, overrides=None, *, home=None)`, `get_agent_metadata(name, overrides=None, *, home=None)`, and `discover_agent_names()`. Provider-specific helper tests or monkeypatches for Claude-only behavior target this module, especially `_claude_tools` if needed.
- Hides: Claude install paths (`.claude/agents/<name>.md` and `.claude/skills/<name>/SKILL.md`), primary-skill vs subagent mode branching, Claude frontmatter shape, `model.claude` validation, optional effort emission, caps-to-tools translation, and spawn-allowlist prose injection for skills.
- Depth note: The public contract is the same three administrator operations while the implementation hides provider-specific path and frontmatter rules; deleting it would leak Claude branching into operations, wizard flows, and tests.

### `administrators/opencode.py` — OpenCode artifact administrator
- Seam: `OpenCodeArtifactsAdministrator`, selected through `ADMINISTRATORS[AgentCli.OPENCODE]`, owns all OpenCode-specific artifact rendering.
- Interface: Implements `render_artifacts(names=None, overrides=None, *, home=None)`, `get_agent_metadata(name, overrides=None, *, home=None)`, and `discover_agent_names()`. Provider-specific helper tests or monkeypatches for OpenCode-only behavior target this module, especially `_opencode_permission` if needed.
- Hides: OpenCode install path (`.config/opencode/agent/<name>.md`), frontmatter key ordering, `model.opencode` validation, `effort.opencode` to `reasoningEffort`, explicit permission precedence over caps-derived permission, color passthrough, mode passthrough, and caps-to-permission translation.
- Depth note: This is deep because callers see one administrator contract while the module owns OpenCode's idiosyncratic frontmatter and permission semantics.

### `administrators/copilot.py` — Copilot artifact administrator
- Seam: `CopilotArtifactsAdministrator`, selected through `ADMINISTRATORS[AgentCli.COPILOT]`, owns all Copilot-specific artifact rendering.
- Interface: Implements `render_artifacts(names=None, overrides=None, *, home=None)`, `get_agent_metadata(name, overrides=None, *, home=None)`, and `discover_agent_names()`.
- Hides: Copilot install path (`.copilot/agents/<name>.agent.md`), minimal `name` + `description` frontmatter, intentional omission of model/tools/user-invocable/disable-model-invocation/permission/mode/color, and the fact that Copilot has no per-agent model requirement.
- Depth note: The seam prevents Copilot's negative requirements from spreading; callers do not need special cases for fields Copilot ignores.

## Internal collaborators

- `override_store.py`: not a public test seam for this change. It provides `deep_merge` and `load_override_store` behind `base.py` metadata resolution. Tests must not add new mocks here; existing file-persistence behavior belongs to override-store-specific tests.
- `tests/test_renderers.py`: not a production seam. It is the migration harness that must point behavior tests at the public administrator package, private helper tests at `administrators.base`, and provider-specific helper checks at the owning provider module.
- `tests/test_install.py`: not a rendering seam. It should import install-test fixtures from the public administrator package only.

## Seam map

```text
wizard/tui.py
  -> administrators.ADMINISTRATORS
  -> override_store only for wizard override behavior

harness/operations.py
  -> administrators.ADMINISTRATORS

administrators/__init__.py
  -> base public types/helpers
  -> claude/opencode/copilot concrete administrators
  -> models.AgentCli

administrators/{claude,opencode,copilot}.py
  -> base.ArtifactsAdministrator + shared helpers
  -> no sibling-provider imports

administrators/base.py
  -> override_store.deep_merge/load_override_store
  -> importlib.resources.files("ai_harness.resources")

tests/test_renderers.py
  -> administrators for public API
  -> administrators.base for private shared-helper tests/mocks
  -> administrators.claude/opencode/copilot for provider-specific helpers
```

Test seam contract:

| Current reference | New target | Rule |
| --- | --- | --- |
| `from ai_harness.modules.harness.renderers import ADMINISTRATORS, AgentCaps, AgentMetadata, Artifact, ArtifactsAdministrator, ClaudeArtifactsAdministrator, OpenCodeArtifactsAdministrator, CopilotArtifactsAdministrator, discover_agent_names, load_agent_metadata` | `from ai_harness.modules.harness.administrators import ...` | Public API imports now come from the administrator package. |
| `from ai_harness.modules.harness.renderers import _validate_metadata_schema, _decode_agent_caps, _decode_effort_map, _decode_model_map, _decode_permission, _decode_agent_metadata` | `from ai_harness.modules.harness.administrators.base import ...` | Existing private shared-helper tests target the owning shared module. Do not expand this private surface. |
| `monkeypatch.setattr("ai_harness.modules.harness.renderers.get_agent_meta", ...)` | Prefer rewriting to avoid removed `get_agent_meta`; if the test needs metadata loading, patch/call the actual administrator metadata path. | `get_agent_meta` is a deleted legacy shim API and must not survive as a target. |
| `monkeypatch.setattr("ai_harness.modules.harness.renderers._AGENT_RESOURCE_DIRS", ...)` | `monkeypatch.setattr("ai_harness.modules.harness.administrators.base._AGENT_RESOURCE_DIRS", ...)` | Resource directory ownership is in `base.py`. |
| `monkeypatch.setattr("ai_harness.modules.harness.renderers.files", ...)` | `monkeypatch.setattr("ai_harness.modules.harness.administrators.base.files", ...)` | Patch the imported symbol used by `base.py`, not `importlib.resources.files` and not the deleted shim. |
| Provider-specific helper import/mock for `_claude_tools` | `ai_harness.modules.harness.administrators.claude._claude_tools` | Claude owns Claude helper behavior. |
| Provider-specific helper import/mock for `_opencode_permission` | `ai_harness.modules.harness.administrators.opencode._opencode_permission` | OpenCode owns OpenCode helper behavior. |
| Any import of `render_agents`, `RenderedFile`, `get_agent_meta`, or `renderers.__all__` | Delete or rewrite without shim coupling | These are shim-only concepts and have no post-change public equivalent. |

Migration order the implementation loop must follow:

1. Repoint `src/ai_harness/modules/wizard/tui.py:39` to import `ADMINISTRATORS` from `ai_harness.modules.harness.administrators`.
2. Repoint `tests/test_renderers.py` top-level imports.
3. Repoint local imports inside `tests/test_renderers.py` test bodies.
4. Repoint monkeypatch strings from `renderers.*` to `administrators.base.*` or the owning provider module.
5. Repoint `tests/test_install.py:20` import from `renderers` to `administrators`.
6. Delete the five shim-specific tests: `test_renderers_public_surface_excludes_old_apis`, `test_renderers_public_surface_includes_new_apis`, and the Claude/OpenCode/Copilot `render_agents` byte-compat tests.
7. Update wizard source-inspection assertions to require the administrator import boundary and no removed legacy calls.
8. Delete `src/ai_harness/modules/harness/renderers.py`.
9. Clean README/docstring/comment rot in `README.md`, `operations.py`, `override_store.py`, and `administrators/base.py`.

## Rejected alternatives

- Keep a thin `renderers.py` re-export module: rejected because it preserves the shallow seam and lets tests keep coupling to a dead compatibility boundary. It moves names around without deleting complexity.
- Delete `renderers.py` before migrating tests: rejected because collection fails before the implementation loop can see which behavior assertions still matter.
- Repoint all private helper tests to the public `administrators` package: rejected because private helpers are not public API. The honest owner is `administrators.base`, and the coupling should remain explicit and limited.
- Mock `importlib.resources.files` globally: rejected because `base.py` imports `files` into its own module namespace. Patching the global function is a broader, less local seam and may not affect the code under test.
- Rewrite Child B/Child C failures while touching nearby tests: rejected as scope bleed. Home isolation, prompt-content replacement, and install body superset assertions belong to sibling changes.

Risk-mitigation map:

| PRD risk | Implementation rule |
| --- | --- |
| Collection-time failures if any shim import remains after deletion. | Complete migration-order steps 1-5 and grep for `ai_harness.modules.harness.renderers` before step 8. |
| Missed local imports or monkeypatch strings inside `tests/test_renderers.py`. | Audit both import statements and string targets; specifically check `get_agent_meta`, `files`, `_AGENT_RESOURCE_DIRS`, and `render_agents`. |
| Incorrect mock target after migration. | Patch the owning module: shared helper/resource targets in `administrators.base`; provider helpers in `administrators.claude` or `administrators.opencode`; never patch the deleted shim. |
| Import-cycle regression in wizard code. | Keep `wizard/tui.py` dependent only on `administrators` public API and run `tests/test_set_models.py` with renderer/install tests. |
| Scope bleed into Child B or Child C failures. | Do not change render call `home`/`overrides` semantics, prompt prose assertions, install body exactness, or smoke-check strategy except where required to remove shim usage. |
| Documentation rot if prose still names `renderers.py`. | Treat README/docstring/comment grep cleanup as acceptance work after functional migration, not optional polish. |

Acceptance criteria checklist:

- [ ] `src/ai_harness/modules/harness/renderers.py` no longer exists.
- [ ] No production code imports `ai_harness.modules.harness.renderers`.
- [ ] `src/ai_harness/modules/wizard/tui.py` imports `ADMINISTRATORS` from `ai_harness.modules.harness.administrators`.
- [ ] `tests/test_renderers.py` and `tests/test_install.py` no longer import or monkeypatch the deleted shim.
- [ ] The five locked shim-specific tests are removed and not replaced with new shim-coupled assertions.
- [ ] Wizard source-inspection assertions expect the administrator import boundary.
- [ ] README/docstrings/comments no longer direct readers to `renderers.py` as the rendering/metadata home.
- [ ] Targeted gates pass (`uv run pytest tests/test_renderers.py`, `uv run pytest tests/test_install.py`, `uv run pytest tests/test_set_models.py`) and final gates pass or document only explicitly deferred Child B/Child C failures (`uv run pytest`, `uv run ruff format --check .`, `uv run ruff check .`).
