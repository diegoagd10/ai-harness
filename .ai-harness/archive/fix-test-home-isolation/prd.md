# PRD — fix-test-home-isolation

## Intent

Make the renderer unit tests deterministic across developer environments by eliminating ambient reads from the real user `HOME`. The production rendering and metadata APIs already expose the required seams (`home=` and `overrides=`); this Change applies those seams consistently in `tests/test_renderers.py` so pytest results no longer depend on a developer's local `.ai-harness/overrides.json`.

There is no end-user behavior change. The visible benefit is for contributors and CI maintainers: renderer tests become isolated, repeatable, and aligned with the repository rule that tests must not touch the user system.

## Scope

### In

- Update the locked 28 must-fix tests and helper call chains in `tests/test_renderers.py` that currently call `render_artifacts()` or `get_agent_metadata()` without explicit `home=` and `overrides=`.
- Add `tmp_path: Path` to affected tests and pass `home=tmp_path` plus `overrides={}` for tests that are not exercising the disk override store.
- Update `_change_orchestrator_body`, `_native_change_orchestrator_body`, and `_native_change_implementor_body` to accept an isolated home path and propagate `home=...` and `overrides={}` to their internal render calls.
- Preserve the 10 override-store-specific tests as disk-store coverage: keep omitted or `None` override semantics where that is the behavior under test, but always redirect `HOME` through `home=tmp_path`.
- Keep the change within the 142 LOC implementation budget identified by exploration.

### Out

- Prompt-content test deletions, install verbatim rewrite, and replacement smoke checks; those belong to Child C.
- Production code changes; the required isolation seam already exists.
- README, docstring, or architecture documentation edits.
- Adding new test coverage; this is a refactor of existing tests.
- Rewriting unrelated explicit-overrides tests unless needed incidentally to preserve formatting or helper signatures.

## Capabilities

- Must-fix renderer isolation: Existing tests that call `render_artifacts()` or `get_agent_metadata()` without isolation pass `home=tmp_path` and `overrides={}` so they cannot read the developer's real override store.
- Helper-driven renderer isolation: Shared body helpers receive an isolated home path and no longer hide transitive ambient `HOME` reads from their many callers.
- Override-store disk-path isolation: Tests that intentionally exercise override-store loading still cover the `overrides=None` or omitted-overrides path, but read from `tmp_path/.ai-harness/overrides.json` instead of the real user home.
- Regression-gate clarity: The implementation can be validated with targeted renderer pytest plus ruff checks, proving both behavior preservation and test isolation.

## Approach

Use a mechanical test-side refactor in `tests/test_renderers.py`.

For the 28 must-fix owners, add `tmp_path: Path` to the pytest function signature where needed and update renderer/metadata calls to pass `home=tmp_path, overrides={}`. For multi-call tests, update each relevant call rather than only the first occurrence.

For helper-backed body tests, change the helper signatures to accept `home: Path`, call `render_artifacts(..., home=home, overrides={})`, and update every helper caller to accept `tmp_path: Path` and pass it through. This avoids leaving a hidden ambient read behind a clean-looking test body.

For override-store-specific tests, preserve the disk-read semantics by keeping `overrides=None` or omitted overrides wherever the assertion depends on auto-loading behavior. Add or retain `home=tmp_path` so the disk-read path targets the temporary test home.

Do not change production behavior, prompt text assertions, install assertions, or legacy shim deletion work in this Change.

## Affected Areas

- `tests/test_renderers.py` — only implementation target; direct renderer/metadata calls, three shared body helpers, and helper callers.
- Override-store test family — semantics must remain intact while redirecting home.
- Pytest fixture signatures — affected tests gain `tmp_path: Path`; parametrized tests must remain valid.

## Risks

- Multi-line `render_artifacts(...)` or `get_agent_metadata(...)` calls can be missed by simple regex, leaving ambient reads behind.
- Shared helper functions hide transitive render calls; updating helpers without updating every caller will either raise `TypeError` or keep a real-home read.
- Tests that monkeypatch `Path.home()` or `HOME` directly are sensitive: changing `overrides=None` to `{}` there would silently remove disk-store coverage.
- The Child A validation and design artifacts were not available in this worktree during proposal authoring, so the PRD relies on the locked scope plus current child and parent exploration artifacts.

## Rollback Plan

Revert the `tests/test_renderers.py` edits from this Change. Because no production code or persistent fixtures are modified, rollback restores the prior test behavior without data migration or runtime compatibility concerns.

## Dependencies

- Existing renderer and administrator APIs must continue to support `home=` and `overrides=` parameters.
- Pytest `tmp_path` fixture and `Path` type imports remain available in `tests/test_renderers.py`.
- Parent Change `fix-bad-unit-tests` establishes the broader test-cleanup context.
- Child A's seam contract remains conceptually applicable: tests should use explicit home and override seams instead of ambient environment state.

## Success Criteria

- All locked 28 must-fix tests and helper paths in `tests/test_renderers.py` pass explicit isolated home handling and no longer read the real user home.
- All 10 override-store-specific tests still exercise the disk-read path where intended, but only under `tmp_path`.
- No production files are changed.
- No new tests are added and no Child C prompt/install/smoke work is performed.
- `uv run pytest tests/test_renderers.py` passes.
- `uv run ruff format --check tests/test_renderers.py` and `uv run ruff check tests/test_renderers.py` pass.
- A semantic audit confirms no remaining unintentional `render_artifacts()` or `get_agent_metadata()` call in `tests/test_renderers.py` can fall back to the real `Path.home()`.
