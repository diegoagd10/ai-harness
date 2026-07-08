# PRD — fix-renderers-shim-deletion

## Intent

Delete the deprecated `ai_harness.modules.harness.renderers` compatibility shim and make the `ai_harness.modules.harness.administrators` package the only load-bearing rendering/metadata API. This removes architectural debt, prevents tests from coupling to a dead module, and keeps install/set-models wizard behavior routed through the modern administrator implementation.

User-visible behavior should not change: `ai-harness` users should still be able to install agents and use wizard flows such as install and set-models with the same rendered artifacts and metadata behavior. The change is an internal module boundary cleanup plus test migration.

## Scope

### In

- Delete `src_ai_harness/modules/harness/renderers.py` entirely.
- Repoint the runtime `ADMINISTRATORS` import in `src_ai_harness/modules/wizard/tui.py` to `ai_harness.modules.harness.administrators`.
- Clean stale references to the deleted shim in:
  - `src_ai_harness/modules/harness/operations.py`
  - `src_ai_harness/modules/harness/override_store.py`
  - `src_ai_harness/modules/harness/administrators/base.py`
  - `README.md`
- Repoint `tests/test_renderers.py` imports, local imports, mocks, and monkeypatch targets from `renderers` to the owning administrator modules:
  - public administrator API via `ai_harness.modules.harness.administrators`
  - private helper seams via `ai_harness.modules.harness.administrators.base`
  - provider-specific helper seams via the provider module that owns them, when applicable
- Repoint `tests/test_install.py` top-level imports from `renderers` to `administrators`.
- Delete shim-specific tests with no equivalent after module deletion:
  - `test_renderers_public_surface_excludes_old_apis`
  - `test_renderers_public_surface_includes_new_apis`
  - Claude `render_agents` parity test
  - OpenCode `render_agents` parity test
  - Copilot `render_agents` parity test
- Update wizard source-inspection assertions that currently require the old `renderers` import line.

### Out

- Home-isolation cleanup (`home=tmp_path` plus `overrides={}` across 60+ render/metadata tests). This belongs to Child B.
- Deleting broken prompt-content tests, rewriting install verbatim assertions, or adding prompt/resource smoke checks. This belongs to Child C.
- Behavior redesign for administrator rendering, metadata loading, model defaults, override-store semantics, or wizard workflows.
- Expanding private-helper test coverage beyond the existing migration from the deleted shim.
- Publishing, release, or GitHub workflow changes.

## Capabilities

- Runtime administrator import migration: wizard code resolves `ADMINISTRATORS` from `ai_harness.modules.harness.administrators` with no dependency on the deleted shim.
- Shim deletion: the deprecated `ai_harness.modules.harness.renderers` module is removed from production code and no supported runtime path imports it.
- Test import migration: renderer/administrator tests collect against the modern administrator package rather than the deleted shim.
- Mock target migration: monkeypatches and private-helper tests target the actual owning administrator modules, especially `administrators.base` for shared helpers.
- Legacy shim test removal: tests whose only purpose was validating `renderers.__all__` or byte-parity with `render_agents` are removed.
- Documentation cleanup: README, docstrings, and comments describe the administrator package as the rendering/metadata home and no longer point readers to `renderers.py`.
- Wizard assertion alignment: source-inspection tests verify the new administrator import boundary instead of the deleted shim import line.

## Approach

Migrate all runtime and test references before deleting the shim so collection-time failures are easier to diagnose. Treat `ai_harness.modules.harness.administrators` as the public API for administrator dispatch, metadata types, artifacts, concrete administrators, and discovery/loading helpers. Treat `ai_harness.modules.harness.administrators.base` as the explicit target for existing private helper tests that already validate shared decoding, schema, resource, or `files` behavior.

Delete only tests whose subject disappears with the shim: legacy public-surface assertions and `render_agents` parity checks. Preserve behavior tests by repointing imports/mocks instead of rewriting semantics. Keep Child B and Child C concerns out of this change even where nearby failing tests are visible.

After the code/test migration, delete `renderers.py` and clean stale prose. Validate with targeted renderer/install/set-model tests, then the full test and ruff gates.

## Affected Areas

- `src_ai_harness/modules/harness/renderers.py` — deleted deprecated shim.
- `src_ai_harness/modules/wizard/tui.py` — runtime import boundary for `ADMINISTRATORS`.
- `src_ai_harness/modules/harness/operations.py` — stale rendering architecture prose.
- `src_ai_harness/modules/harness/override_store.py` — stale helper-location prose.
- `src_ai_harness/modules/harness/administrators/base.py` — stale comment/docstring references to shim helpers.
- `README.md` — architecture documentation for administrator rendering.
- `tests/test_renderers.py` — primary import/mock migration and shim-specific test deletions.
- `tests/test_install.py` — install test imports.
- `tests/test_set_models.py` — recommended regression surface because wizard behavior depends on administrator metadata.

## Risks

- Collection-time failures if any `ai_harness.modules.harness.renderers` import remains after deletion. Mitigation: migrate top-level imports first and search for all direct/import-string references before deleting the file.
- Missed local imports or monkeypatch strings inside `tests/test_renderers.py`. Mitigation: audit both import statements and string targets, including references to `get_agent_meta`, `files`, `_AGENT_RESOURCE_DIRS`, and `render_agents`.
- Incorrect mock target after migration. Mitigation: patch the module that owns the symbol now, commonly `administrators.base` for shared helper/resource seams and provider modules for provider-specific helpers.
- Import-cycle regression in wizard code. Mitigation: run wizard-adjacent tests (`tests/test_set_models.py`) in addition to renderer/install tests.
- Scope bleed into Child B or Child C failures. Mitigation: do not change render call home/override semantics, prompt prose assertions, install body exactness, or smoke-check strategy in this child.
- Documentation rot if prose still names `renderers.py`. Mitigation: include README/docstring/comment grep cleanup as an acceptance item, not an optional polish step.

## Rollback Plan

Restore `src_ai_harness/modules/harness/renderers.py` and revert imports/mocks/docs to the previous shim boundary if the administrator package proves unable to support an existing runtime path. Because the intended user-visible behavior is unchanged, rollback should be limited to restoring the compatibility module and its import consumers; no data migration is involved.

## Dependencies

- Existing administrator package at `ai_harness.modules.harness.administrators` must expose the public names currently consumed through the shim.
- Existing shared helper implementation in `ai_harness.modules.harness.administrators.base` must remain importable for migrated private-helper tests.
- Parent change `fix-bad-unit-tests` defines the decomposition boundaries; Child B and Child C must handle their deferred test failures separately.
- Tooling: Python >=3.12, uv, pytest, ruff.

## Success Criteria

- `src_ai_harness/modules/harness/renderers.py` no longer exists.
- No production code imports `ai_harness.modules.harness.renderers`.
- `src_ai_harness/modules/wizard/tui.py` imports `ADMINISTRATORS` from `ai_harness.modules.harness.administrators`.
- `tests/test_renderers.py` and `tests/test_install.py` no longer import or monkeypatch the deleted shim.
- The five locked shim-specific tests are removed and not replaced with new shim-coupled assertions.
- Wizard source-inspection assertions expect the administrator import boundary.
- README/docstrings/comments no longer direct readers to `renderers.py` as the rendering/metadata home.
- Targeted gates pass: `uv run pytest tests/test_renderers.py`, `uv run pytest tests/test_install.py`, and `uv run pytest tests/test_set_models.py`.
- Final gates pass or have only explicitly deferred Child B/Child C failures documented: `uv run pytest`, `uv run ruff format --check .`, and `uv run ruff check .`.
