# Exploration — fix-bad-unit-tests

## Budget
930 LOC estimate (additions + deletions).

Reasoning: deleting the deprecated shim is already ~565 deleted lines. The remaining work is broad but mostly mechanical: ~120 lines to repoint imports/mocks from `renderers` to administrator modules, ~90 lines to make renderer tests explicitly pass `home=tmp_path` and `overrides={}`, ~90 lines deleting prompt-prose and legacy-public-surface tests, ~40 lines for replacement smoke checks, ~15 lines in `tests/test_install.py`, and ~10 lines of production/docs cleanup. This is over 800 because the shim deletion dominates; the executable logic change is much smaller than the raw LOC budget suggests.

## Affected Files

### Production
- `src/ai_harness/modules/harness/renderers.py` — delete the deprecated shim entirely; this is the largest LOC component and removes legacy `render_agents`, `get_agent_meta`, `RenderedFile`, re-exports, and local helper copies.
- `src/ai_harness/modules/wizard/tui.py` — repoint `ADMINISTRATORS` import from `ai_harness.modules.harness.renderers` to `ai_harness.modules.harness.administrators`.
- `src/ai_harness/modules/harness/operations.py` — optional but recommended docstring/comment cleanup because it still says provider render is handled by `renderers.py`; runtime import already uses `administrators`.
- `src/ai_harness/modules/harness/override_store.py` — optional docstring cleanup because it references old private helpers inside `renderers.py`.

### Tests
- `tests/test_renderers.py` — main test surface: repoint top-level and local imports to `ai_harness.modules.harness.administrators` or `ai_harness.modules.harness.administrators.base`; repoint monkeypatch strings from `renderers.*` to `administrators.base.*`; delete prompt-prose assertions; delete legacy renderer public-surface assertions; delete or rewrite legacy `render_agents` parity tests; add smoke checks that validate resource/metadata wiring without asserting prompt prose; pass `home=tmp_path` and `overrides={}` for ambient-read-sensitive render/metadata calls.
- `tests/test_install.py` — repoint imports away from `renderers`; rewrite `test_install_claude_rendered_body_matches_template_verbatim` so rendered body is a superset (`template_body in rendered_body`) rather than byte-identical; keep module-level expected-frontmatter builders explicitly passing `overrides={}`.

### Documentation / Config
- `README.md` — optional but recommended: current architecture bullet says `renderers.py` owns `ADMINISTRATORS`; after deletion it should name `src/ai_harness/modules/harness/administrators/` instead.
- Config files — no expected changes.

## Plan
- Split into child Changes because the budget is >800 LOC, even though most work is mechanical.
- Phase 1: migrate production imports and documentation references. Delete `renderers.py`, update `wizard/tui.py`, and clean stale prose in `operations.py`, `override_store.py`, and README if in scope.
- Phase 2: migrate test imports and mocks. Use `ai_harness.modules.harness.administrators` for public types/dispatch and `ai_harness.modules.harness.administrators.base` for private helper tests/mocks such as `_AGENT_RESOURCE_DIRS`, `files`, `_decode_*`, and schema validation.
- Phase 3: isolate tests from user home. In `tests/test_renderers.py`, every render/default metadata call that does not intentionally test home-store loading should pass `home=tmp_path` and `overrides={}`. Existing override-store-specific tests should keep using `home=tmp_path` with `overrides=None` only when the disk-read behavior is the subject.
- Phase 4: remove prompt-prose coupling. Delete the locked prompt-content tests and replace them with smoke checks over discovery, metadata coverage, non-empty template bodies, and rendered body inclusion without prose keywords.
- Phase 5: remove legacy-shim tests. Delete the `renderers.__all__` tests and the legacy `render_agents` byte-compat tests at `tests/test_renderers.py:3218` and `3340`; rewrite only if the behavior still has value through `ADMINISTRATORS`.
- Phase 6: run gates: targeted `uv run pytest tests/test_renderers.py tests/test_install.py`, then full `uv run pytest`, ruff format/check. Run e2e only if install/uninstall observable behavior changes beyond test expectations; likely not required for this test-decoupling change.

## Edge Cases
- Tests that intentionally exercise override-store auto-loading must continue to pass `home=tmp_path` and leave `overrides=None`; replacing those with `overrides={}` would delete real behavior coverage.
- Some render calls span multiple lines, so a simple single-line search undercounts ambient `Path.home()` reads. Audit by semantic call sites, not only regex.
- `get_agent_metadata(..., overrides=None)` reads `home/.ai-harness/overrides.json`; calls without `home` default to `Path.home()`. These are as important as `render_artifacts()` calls.
- Monkeypatches currently targeting `ai_harness.modules.harness.renderers._AGENT_RESOURCE_DIRS` or `.files` must target `ai_harness.modules.harness.administrators.base`, otherwise tests will either fail at import time or patch a deleted module.
- Tests that inspect wizard source strings currently assert the old `renderers` import line; those assertions must align with the new administrator import or be rewritten as behavior-only checks.

## Test Surface
- `uv run pytest tests/test_renderers.py` — primary gate for administrator rendering, metadata decoding, discovery, overrides, prompt smoke checks, and removed shim references.
- `uv run pytest tests/test_install.py` — install path and rendered-body superset behavior.
- `uv run pytest tests/test_set_models.py` — recommended because wizard helpers call `ADMINISTRATORS.get_agent_metadata(..., home=home)` and can be affected by the import migration.
- `uv run pytest` — final regression gate.
- `uv run ruff format --check .` and `uv run ruff check .` — import ordering/unused import cleanup after mass migration.
- `./e2e/docker-test.sh` — optional/conditional; no direct e2e references to `renderers` were found, but install output changes should still be considered if rendered artifacts or counts drift.

## Risks
- Deleting `renderers.py` creates collection-time failures for any lingering `from ai_harness.modules.harness.renderers import ...`; grep found many in `tests/test_renderers.py` plus one in `tests/test_install.py` and one production import in `wizard/tui.py`.
- The top-level import block in `tests/test_renderers.py` currently imports `ADMINISTRATORS`, `AgentCaps`, `Artifact`, and helper functions from `renderers`; if not migrated first, the entire test module will fail before individual deletes can be validated.
- Private-helper tests will become more tightly coupled to `administrators.base`; that is acceptable for existing private-helper coverage but should not expand beyond the current surface.
- Ambient user-home reads are easy to reintroduce because `overrides=None` is a documented disk-read path. Use `overrides={}` by default in tests unless the test is explicitly about override-store loading.
- `test_install_claude_rendered_body_matches_template_verbatim` will still read bundled prompt templates. The new assertion must avoid prose exactness while still proving the rendered file contains the template body.
- README and docstrings can become stale if left pointing at `renderers.py`; not a test failure, but a discoverability/packaging risk after the file is deleted.
- Packaging/import smoke risk: deleting a Python module is safe only after all runtime imports are gone; `operations.py` already imports administrators directly, but `wizard/tui.py` does not.

## Open Design Questions
- Smoke check shape for replacing prompt-content tests:
  - Per-file literal list: assert exact expected template filenames. Simple, but still pins the prompt set tightly.
  - Discovery-driven: assert discovered agent names have metadata JSON and non-empty template bodies. Lowest coupling to prose and future agent count changes.
  - Discovery-driven + minimum count: same as discovery-driven, plus `len(names) >= 1` or current floor `>= 9`. Protects against accidental empty resource packaging while avoiding exact prose assertions.
- Recommendation: use discovery-driven + current minimum count (`>= 9`) for now. It catches empty packaging/resource drift, keeps metadata/template parity covered, and does not care about prompt wording. If adding/removing agents should be free in the future, lower the count to `>= 1` and rely on wizard-vocabulary tests for exact current sets.
- Decide whether to keep administrator parity tests by rewriting them as provider-shape tests. Recommendation: delete the legacy byte-compat tests because their only purpose was proving equivalence with the soon-to-be-deleted shim.

## Smoke Check Replacement Sketch

Recommended shape (sketch for design, not final implementation):

```python
def test_change_agent_resources_smoke_have_metadata_and_body() -> None:
    from importlib.resources import files

    from ai_harness.modules.harness.administrators import discover_agent_names, load_agent_metadata

    template_root = files("ai_harness.resources") / "change-agent"
    names = discover_agent_names()

    assert len(names) >= 9
    for name in names:
        template_path = template_root / f"{name}.md"
        assert template_path.is_file(), f"missing template for {name}"
        assert template_path.read_text(encoding="utf-8").strip(), f"empty template for {name}"
        assert load_agent_metadata(name).description
```

Optional rendered smoke that replaces prose-specific `change-archiver` checks without locking its body text:

```python
@pytest.mark.parametrize("cli", [AgentCli.CLAUDE, AgentCli.OPENCODE, AgentCli.COPILOT])
def test_change_archiver_renders_on_native_agent_clis(tmp_path: Path, cli: AgentCli) -> None:
    artifacts = ADMINISTRATORS[cli].render_artifacts(["change-archiver"], overrides={}, home=tmp_path)

    assert len(artifacts) == 1
    assert artifacts[0].content.startswith("---\n")
    assert artifacts[0].content.split("---", 2)[2].strip()
```

For `tests/test_install.py`, use a body-superset assertion rather than byte equality:

```python
assert template_body in rendered_body, f"{name}: rendered body does not include template body"
```

## semantic_facts
- budget: 930
- follow_up: Decompose implementation into child Changes because raw LOC is >800; decide final smoke-check shape before test edits; audit all ambient `overrides=None` render/metadata calls so only override-store tests read disk.
