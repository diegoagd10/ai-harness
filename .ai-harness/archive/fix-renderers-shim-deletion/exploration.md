# Exploration — fix-renderers-shim-deletion

## Budget
820

Reasoning: this child is dominated by deleting `src/ai_harness/modules/harness/renderers.py` (~565 deleted LOC). The remaining implementation is mostly mechanical but broad: ~140 LOC for replacing `renderers` imports, local imports, and monkeypatch targets across `tests/test_renderers.py`; ~75-85 deleted LOC for legacy shim tests; ~20 LOC for `tests/test_install.py`, `wizard/tui.py`, and source-string assertions; and ~20 LOC for README/docstring/comment cleanup. Line edits count as additions plus deletions, so the raw LOC budget is higher than the conceptual change.

## Affected Files

### Production
- `src/ai_harness/modules/harness/renderers.py` — delete the deprecated shim entirely; it still contains legacy `render_agents`, `get_agent_meta`, `RenderedFile`, shim-local helpers, and re-exports.
- `src/ai_harness/modules/wizard/tui.py` — repoint the `ADMINISTRATORS` import from `ai_harness.modules.harness.renderers` to `ai_harness.modules.harness.administrators`.
- `src/ai_harness/modules/harness/operations.py` — clean stale docstring text that says provider-specific rendering lives in `renderers.py`; runtime import already uses `administrators`.
- `src/ai_harness/modules/harness/override_store.py` — clean stale module docstring text referring to private helpers inside `renderers.py`.
- `src/ai_harness/modules/harness/administrators/base.py` — optional comment cleanup for the line that still describes helpers as used by deprecated `renderers` shims.

### Tests
- `tests/test_renderers.py` — primary migration surface. Current grep finds 70 `ai_harness.modules.harness.renderers` string occurrences, 62 direct `from ...renderers import` occurrences, 6 monkeypatch targets under `ai_harness.modules.harness.renderers.*`, and 66 distinct test functions containing shim references.
- `tests/test_install.py` — repoint the top-level import of `ADMINISTRATORS`, `AgentCaps`, and `discover_agent_names` from `renderers` to `administrators`; optionally clean the stale comment around the default OpenCode model expectation.

### Documentation
- `README.md` — update the architecture bullet that currently names `src/ai_harness/modules/harness/renderers.py` as the home of `ADMINISTRATORS` so it names `src/ai_harness/modules/harness/administrators/` instead.
- `.ai-harness/changes/fix-bad-unit-tests/exploration.md` — parent context only; do not edit for this child.

## Test-count delta
- Deleted tests: 5 likely deletions if the legacy byte-compat tests are removed rather than rewritten. The locked scope listed the OpenCode and Copilot `render_agents` parity tests at current lines 3216 and 3338, and exploration also found the same legacy parity pattern for Claude at current line 3064. The two `renderers.__all__` public-surface tests at current lines 3373 and 3389 have no equivalent after deleting the module.
- Preserved/repointed tests: about 61 distinct test functions with shim references should be preserved by repointing imports/mocks/assertions, plus the module-level import block. This excludes the 5 likely deletions above.
- Assertion-only edits: preserve the wizard migration tests, but replace/delete the old assertions that require `from ai_harness.modules.harness.renderers import ...` in `wizard/tui.py` source.

## Plan
- Use the parent exploration at `.ai-harness/changes/fix-bad-unit-tests/exploration.md` as the full decomposition context; this child handles only the deprecated shim deletion plus import/mock migration.
- First repoint runtime imports: move `src/ai_harness/modules/wizard/tui.py` to import `ADMINISTRATORS` from `ai_harness.modules.harness.administrators`.
- Then repoint test imports in `tests/test_renderers.py`: public types and dispatch (`ADMINISTRATORS`, `AgentCaps`, `AgentMetadata`, `Artifact`, `ArtifactsAdministrator`, concrete administrators, `discover_agent_names`, `load_agent_metadata`) should come from `ai_harness.modules.harness.administrators`; private helper tests (`_validate_metadata_schema`, `_decode_agent_caps`, `_decode_effort_map`, `_decode_model_map`, `_decode_permission`, `_decode_agent_metadata`, resource constants, `files`) should target `ai_harness.modules.harness.administrators.base`.
- Repoint monkeypatch strings from `ai_harness.modules.harness.renderers.*` to the owning administrator module. Most shared helper/resource patches belong under `ai_harness.modules.harness.administrators.base`; provider-specific helpers such as `_claude_tools` and `_opencode_permission` belong under their provider modules if local imports are needed.
- Repoint `tests/test_install.py` from `renderers` to `administrators`.
- Delete or rewrite legacy `render_agents` byte-compat tests. Deletion is lighter because their only subject is equivalence with the module being removed; if rewritten, assert administrator behavior directly without referencing the deleted shim.
- Delete the two `renderers.__all__` public-surface tests because the module no longer exists.
- Update wizard source-inspection assertions so they require the administrator import and no removed legacy calls, rather than requiring a `renderers` import line.
- Delete `src/ai_harness/modules/harness/renderers.py` after, or in the same commit as, the import/mock migration. Deleting first will cause collection-time import failures.
- Clean README/docstring/comment rot after the functional migration so no surviving docs point readers at the deleted module.
- Suggested gates for the implementor: `uv run pytest tests/test_renderers.py tests/test_install.py`, `uv run pytest tests/test_set_models.py`, full `uv run pytest`, then `uv run ruff format --check .` and `uv run ruff check .`.

## Edge Cases
- The top-level import block in `tests/test_renderers.py` currently imports public names from the shim; if missed, the whole file fails to collect before more focused failures are visible.
- `test_copilot_no_model_validation_required` patches `ai_harness.modules.harness.renderers.get_agent_meta`, a removed legacy API. It must be rewritten to patch the administrator metadata path or otherwise avoid the shim.
- The scope seed named two `render_agents` parity tests, but exploration found a third Claude parity test at current line 3064. Leaving any of these behind keeps a hard dependency on the deleted module.
- Monkeypatching `administrators.base.files` affects helper code that imported `files` in that module; patching `importlib.resources.files` or a deleted `renderers.files` name will not cover the same seam.
- Private helper coverage will become explicitly coupled to `administrators.base`. That is acceptable for existing helper tests, but this child should not expand private-helper coverage beyond the migration.
- Child B owns `home=tmp_path` and `overrides={}` cleanup. Do not rewrite render call semantics here except when necessary to remove direct shim usage.
- Child C owns prompt-content test deletion/replacement and the install-body superset assertion. Do not delete or rewrite those tests while doing this import migration.

## Test Surface
- `uv run pytest tests/test_renderers.py` — primary collection and behavior gate for all import/mocking changes.
- `uv run pytest tests/test_install.py` — verifies install tests collect after the import repoint.
- `uv run pytest tests/test_set_models.py` — recommended regression gate because the wizard imports `ADMINISTRATORS` and set-model behavior depends on administrator metadata queries.
- `uv run pytest` — final regression gate.
- `uv run ruff format --check .` and `uv run ruff check .` — catches unused imports and import-order drift after mass migration.

## Risks
- Import-cycle risk: `administrators.base` imports `override_store`, and `wizard/tui.py` imports both `administrators` and `override_store`; verify there is no new module-level path from administrators back into wizard.
- Collection-time failure risk: any lingering `from ai_harness.modules.harness.renderers import ...` will fail once the shim is deleted.
- Non-obvious shim dependency: local tests still patch `get_agent_meta`, `files`, `_AGENT_RESOURCE_DIRS`, and legacy `render_agents`; these are easy to miss because many imports are inside test bodies.
- Scope bleed risk: `tests/test_renderers.py` also contains Child B and Child C failures. Keep this child limited to imports/mocks, shim-specific deletes, and wizard source-string expectations.
- Documentation rot risk: README and docstrings/comments currently identify `renderers.py` as the administrator home; leaving them stale makes the deleted module discoverable in docs even if tests pass.

## semantic_facts
- budget: 820
- follow_up: Implement import/mock migration before deleting `renderers.py`; handle the extra Claude `render_agents` parity test found during exploration; keep Child B home/overrides cleanup and Child C prompt/install assertion changes out of this child.
