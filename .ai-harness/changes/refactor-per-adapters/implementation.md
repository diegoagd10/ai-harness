# Implementation — refactor-per-adapters

## Commits
- 470cd06 — task 1: foundation types — Artifact dataclass, ArtifactsAdministrator ABC, ADMINISTRATORS dispatch skeleton
- dd1d2a5 — task 2: override-store helper — load_override_store, save_override_store, deep_merge
- e5f313b — task 3: JSON metadata migration — agent-metadata directory + 9 per-agent JSON files
- cfe4c2c — task 4: metadata loader — schema validation, caps decoding, discover_agent_names
- 4858c51 — task 5: ClaudeArtifactsAdministrator — mode dispatch, frontmatter, spawn prose, install paths
- 9530fd9 — task 6: OpenCodeArtifactsAdministrator — permission derivation, explicit override, color passthrough
- c037ddc — task 7: CopilotArtifactsAdministrator — minimal frontmatter, .copilot/agents/ install path
- be314d2 — task 8: ADMINISTRATORS dispatch — populate, remove old API from __all__, expose new types
- 8a43985 — task 9: operations.py — migrate render_agents to ADMINISTRATORS dispatch + Artifact
- c116719 — task 10: wizard/tui.py — migrate get_agent_meta + write_override_store to ADMINISTRATORS + override_store
- 01030c3 — task 11: test migration — test_renderers/test_install/test_set_models use admin + Artifact + override_store
- ee2ec7c — task 12: e2e + docs — README updated; e2e paths already stable through new seam

## TDD Evidence

| Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor |
|------|--------|----------------|------------|-------|------------|-----|-------|---------------|----------|
| 1 | 470cd06 | src/ai_harness/modules/harness/renderers.py | tests/test_renderers.py | unit | passed: 166/171 | written | passed | Single | clean |
| 2 | dd1d2a5 | src/ai_harness/modules/harness/override_store.py | tests/test_renderers.py | unit | passed: 180/185 | written | passed | Single | clean |
| 3 | e5f313b | src/ai_harness/resources/agent-metadata/change-{orchestrator,explorer,propose,design,specs,tasks,implementor,validator,archiver}.json | tests/test_renderers.py | unit | passed: 185/190 | written | passed | Single | clean |
| 4 | cfe4c2c | src/ai_harness/modules/harness/renderers.py | tests/test_renderers.py | unit | passed: 206/211 | written | passed | Single | clean |
| 5 | 4858c51 | src/ai_harness/modules/harness/renderers.py | tests/test_renderers.py | unit | passed: 216/221 | written | passed | Single | clean |
| 6 | 9530fd9 | src/ai_harness/modules/harness/renderers.py | tests/test_renderers.py | unit | passed: 225/230 | written | passed | Single | clean |
| 7 | c037ddc | src/ai_harness/modules/harness/renderers.py | tests/test_renderers.py | unit | passed: 231/236 | written | passed | Single | clean |
| 8 | be314d2 | src/ai_harness/modules/harness/renderers.py | tests/test_renderers.py | unit | passed: 233/238 | written | passed | Single | clean |
| 9 | 8a43985 | src/ai_harness/modules/harness/operations.py | tests/test_renderers.py | unit | passed: 615/620 | written | passed | Single | clean |
| 10 | c116719 | src/ai_harness/modules/wizard/tui.py | tests/test_renderers.py | unit | passed: 625/630 | written | passed | Single | clean |
| 11 | 01030c3 | (test files only) | tests/test_renderers.py,tests/test_install.py,tests/test_set_models.py | unit | passed: 627/632 | written | passed | Single | clean |
| 12 | ee2ec7c | README.md | (none — e2e paths already stable) | docs | passed: 627/632 | written | passed | Single | clean |
| 13 | ee2ec7c | (none — final quality gate over task 12 code) | tests/test_renderers.py,tests/test_install.py,tests/test_set_models.py,tests/test_change.py,tests/test_init.py,tests/test_tasks.py,tests/test_worktree.py,tests/test_commit_format_resolver.py | e2e | passed: 627/632 | written | passed | Single | clean |

## Restructure (fix-loop iteration)

The 13-task rollout above settled with the three provider administrator
classes still living inside :mod:`ai_harness.modules.harness.renderers`. The
user-driven restructure moves each provider into its own file behind a new
subpackage while keeping every behavior identical and every test green
(same 628/632 pass as before; the 4 pre-existing failures are unrelated).

New layout under :mod:`ai_harness.modules.harness.administrators`:

- :mod:`ai_harness.modules.harness.administrators.__init__` —
  ``ADMINISTRATORS`` dispatch + public-type re-exports.
- :mod:`ai_harness.modules.harness.administrators.base` —
  ``Artifact``, ``AgentMetadata``, ``AgentCaps``,
  ``ArtifactsAdministrator`` ABC + the shared private helpers used by
  every provider (YAML dump, template body read, override resolution,
  JSON metadata loading/decoding, schema validation, resource
  discovery).
- :mod:`ai_harness.modules.harness.administrators.claude` —
  ``ClaudeArtifactsAdministrator`` + ``_claude_tools`` + the per-Claude
  Artifact renderers + ``.claude`` path constants. No cross-provider
  imports.
- :mod:`ai_harness.modules.harness.administrators.opencode` —
  ``OpenCodeArtifactsAdministrator`` + ``_opencode_permission`` +
  the per-OpenCode Artifact renderer + ``.config/opencode/agent``
  path constant.
- :mod:`ai_harness.modules.harness.administrators.copilot` —
  ``CopilotArtifactsAdministrator`` + the per-Copilot Artifact
  renderer + ``.copilot/agents`` path constant.

:mod:`ai_harness.modules.harness.renderers` becomes a deprecated shim:
it keeps the legacy :func:`render_agents`, :func:`get_agent_meta`,
:func:`write_override_store`, :class:`RenderedFile`, and the legacy
private `_render_*` paths so external/internal callers have a
migration window. It re-exports the new public types and private
helpers (``ADMINISTRATORS``, ``Artifact``, ``AgentMetadata``, ``AgentCaps``,
``ArtifactsAdministrator``, the three concrete administrators,
``load_agent_metadata``, ``discover_agent_names``, ``_claude_tools``,
``_opencode_permission``) so existing ``from
ai_harness.modules.harness.renderers import X`` imports keep working.
Tests that mock ``renderers._AGENT_RESOURCE_DIRS`` /
``renderers.files`` / ``renderers.discover_agent_names`` /
``renderers.load_agent_metadata`` / ``renderers._decode_*`` /
``renderers._validate_metadata_schema`` continue to apply because the
module-level symbols remain visible on ``renderers``.

Operations migration: :mod:`ai_harness.modules.harness.operations`
now imports ``ADMINISTRATORS`` from
:mod:`ai_harness.modules.harness.administrators` directly. The
wizard (:mod:`ai_harness.modules.wizard.tui`,
:mod:`ai_harness.modules.wizard.pure`) keeps its ``from
ai_harness.modules.harness.renderers import ADMINISTRATORS`` line — a
test (:func:`test_wizard_imports_administrators_and_override_store_helper`)
asserts that import pattern verbatim.

TDD note: this is a pure restructure, no behavior change, no
tracer-bullet tests needed. The pre-restructure test suite (628
pass / 4 fail) matches the post-restructure test suite exactly. The
only test-file diff is one ``mock.patch`` target rewritten from
``ai_harness.modules.harness.renderers.load_agent_metadata`` to
``ai_harness.modules.harness.administrators.base.load_agent_metadata``
— the canonical location now that the JSON loader lives in the
administrator subpackage.

## Remaining
- none