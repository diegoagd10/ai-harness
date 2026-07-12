# Exploration — init-config-scaffold

## Budget
560

## Affected Files
- `src/ai_harness/commands/init.py` — replace the `init_repo()` delegation and legacy scaffold reporting with construction of `ChangeConfigAdministrator` and a call to `initialize_config()`.
- `tests/test_init.py` — replace CLI expectations for root documentation mutation with coverage for config creation, template validity, idempotency, and preservation/absence of `CLAUDE.md`, `AGENTS.md`, and `CODING_STANDARDS.md`; existing direct `init_repo` tests are independent of the changed CLI unless that legacy API is explicitly retired.
- `e2e/e2e_test.sh` — rewrite the Tier 1 init scenarios and invocation list to assert `.ai-harness/config.yml` creation and content, idempotent reruns, preservation of pre-existing config, and no creation or mutation of root documentation.
- `src/ai_harness/modules/change_config/module.py` — existing dependency providing the requested behavior; likely no functional change, though its docstring still compares its default path behavior to `init_repo`.
- `src/ai_harness/modules/harness/operations.py` — owns the now-legacy `init_repo`, `InitResult`, scaffold constants, and root-document mutation helpers; no change is required to stop the CLI behavior, but retirement is a design-scope decision.
- `src/ai_harness/modules/harness/__init__.py` — publicly re-exports `init_repo` and `InitResult`; affected only if the legacy API is retired.

## Plan
- Update the thin Typer adapter to instantiate `ChangeConfigAdministrator()` at the current repository root and invoke `initialize_config()` directly.
- Keep output at the command edge and report the config path without implying root documentation was managed; decide whether output distinguishes creation from an idempotent no-op, since `initialize_config()` currently returns `None` in both cases.
- Replace command-level unit assertions with observable filesystem behavior: valid default YAML is created beneath `.ai-harness`, reruns preserve user-edited config, and all three root documentation files remain absent or byte-identical.
- Rewrite the default Tier 1 init e2e scenarios around the same contract, including config structure/content and rerun mtime preservation.
- Run `ruff format --check`, `ruff check`, `pytest`, duplicate-code lint, and the Docker-backed e2e gate because `e2e/e2e_test.sh` changes.

## Edge Cases
- `.ai-harness/` does not exist: `initialize_config()` creates it recursively.
- `.ai-harness/config.yml` already exists, including an empty, invalid, or user-edited file: initialization must not overwrite or validate it.
- Root `CLAUDE.md`, `AGENTS.md`, or `CODING_STANDARDS.md` already contain legacy/new managed markers: init must leave every byte unchanged rather than migrate or append blocks.
- Root documentation files are absent: init must not create them.
- Repeated init must exit zero and preserve the config file mtime/content.
- The administrator currently gives no created-versus-existing result, so precise status output cannot be derived after the call without changing its three-method seam or checking existence beforehand.

## Test Surface
- `tests/test_init.py`: invoke the public Typer app in `tmp_path`; assert exit zero, generated `.ai-harness/config.yml`, expected commit format and eight phase rule sections, preservation on rerun, and negative assertions for root-doc creation/modification.
- `tests/test_change_config.py`: existing tests already establish `initialize_config()` template shape, directory creation, validation, and non-overwrite behavior; retain as dependency-level coverage.
- `e2e/e2e_test.sh` Tier 1: execute the packaged binary in isolated temporary repositories and verify real disk behavior for fresh, pre-populated, and repeated init runs.
- Quality gates: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e`, `uv run pytest`, and `./e2e/docker-test.sh`.

## Risks
- Leaving `init_repo` publicly exported preserves an obsolete root-scaffolding capability and a large legacy test surface, but removing it broadens this change into an API cleanup; resolve explicitly during design.
- Existing e2e tests encode migration and append behavior in many scenarios, so partial updates could continue to require forbidden root files or leave stale functions in `TIER1_TESTS`.
- YAML assertions that compare raw text would be brittle; parse the file or assert only stable schema values and phase keys.
- Changing `ChangeConfigAdministrator.initialize_config()` to return creation state would violate the module's documented fixed three-method surface only if a new method were added, but it would still alter its return contract unnecessarily; prefer output that is truthful for both creation and no-op.

## Semantic Facts
- `budget`: 560
- `follow_up`: Decide whether to retain or remove the legacy public `init_repo`/`InitResult` API and its direct tests; settle the CLI message for an initializer that intentionally returns no creation status.
