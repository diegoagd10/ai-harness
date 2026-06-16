# Tasks: Refactor Commands (Install/Uninstall)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~850–950 |
| 800-line budget risk | Medium |
| Size exception needed | No |
| Suggested work units | Not needed |
| Delivery strategy | exception-ok |
| Size exception | No |

Decision needed before apply: No
Maintainer-approved size exception: No
800-line budget risk: Medium

## Phase 1: Foundation (RED → GREEN)

- [x] 1.1 RED: Create `tests/test_catalog.py` — test `ArtifactCatalog` methods return correct types/paths (`get_root`, `get_main_instructions`, `get_skills`, `get_resource_dir`). Covers `artifact-installer` spec declarative descriptor scenario indirectly (catalog supplies paths to installers).
- [x] 1.2 GREEN: Create `src/ai_harness/artifacts/__init__.py` (package marker), `src/ai_harness/artifacts/manifest.py` (`FileArtifact`, `DirArtifact`, `ArtifactManifest` frozen dataclasses per design §Interfaces), and `src/ai_harness/artifacts/catalog.py` (`Skill` dataclass + `ArtifactCatalog` with 4 methods). Run `uv run pytest tests/test_catalog.py` — must pass.
- [x] 1.3 RED: Create `tests/test_installer.py` — test generic `install()` and `uninstall()`: fresh install, backup-on-conflict, conflict rotation, template substitution, restore, idempotent uninstall. Use `tmp_path`. Covers `artifact-installer` spec scenarios: fresh file install, conflicting file backed up, repeated conflict rotates backup, matching content removed + backup restored, modified content preserved, idempotent uninstall.
- [x] 1.4 GREEN: Create `src/ai_harness/artifacts/installer.py` — module-level `install(manifest, home, console)` and `uninstall(manifest, home, console)` per design §Interfaces. Run `uv run pytest tests/test_installer.py` — must pass.

## Phase 2: Per-CLI Installers

- [x] 2.1 Create `src/ai_harness/artifacts/installers/__init__.py` and `src/ai_harness/artifacts/installers/opencode.py` — `OpencodeAssets` dataclass + `OpencodeInstaller` class. Composes own assets from `ArtifactCatalog`, builds manifest, calls `installer.install`/`installer.uninstall`. Covers `opencode.json` + SDD prompts + AGENTS.md targets from `cli-artifact-commands` spec.
- [x] 2.2 Create `src/ai_harness/artifacts/installers/claude.py` — `ClaudeAssets` dataclass + `ClaudeInstaller`. Handles `.claude/` skills, AGENTS.md, and `agents/` + `sdd-orchestrator/` resource dirs. Covers skills + AGENTS.md from `cli-artifact-commands` spec.
- [x] 2.3 Create `src/ai_harness/artifacts/installers/copilot.py` — `CopilotAssets` dataclass + `CopilotInstaller`. Installs AGENTS.md to `.copilot/copilot-instructions.md`. Copilot-specific resources deferred per design open question. Covers copilot AGENTS.md from `cli-artifact-commands` spec.

## Phase 3: Command Packages

- [x] 3.1 Create `src/ai_harness/commands/__init__.py`, `src/ai_harness/commands/sdd/__init__.py`, `status.py`, `continue_cmd.py`, `_resolve.py`. Move `sdd_status`, `sdd_continue`, and `_run_sdd_resolve` from `main.py` into new files; register via `register(app)` in `__init__.py`. Signatures and behavior unchanged. Covers `cli-sdd-commands` spec all scenarios.
- [x] 3.2 Create `src/ai_harness/commands/artifacts/__init__.py`, `install.py`, `uninstall.py`. Thin orchestrators: instantiate `ArtifactCatalog` + 3 per-CLI installers in loop. Register via `register(app)`. Covers `cli-artifact-commands` spec all scenarios.

## Phase 4: Wiring + Test Imports

- [x] 4.1 Update `tests/test_install.py` imports — source-path constants from `ai_harness.artifacts.catalog` or `ai_harness.artifacts.manifest`; `app` stays from `ai_harness.main`. Update `tests/test_uninstall.py` same way. `tests/test_cli_sdd.py` requires no import changes (`app` unchanged).
- [x] 4.2 Shrink `src/ai_harness/main.py` to ~30 lines: keep `app`, `callback()`, `main()`. Import and call `register(app)` from `ai_harness.commands.sdd` and `ai_harness.commands.artifacts`. Remove old `install`, `uninstall`, `sdd_status`, `sdd_continue`, `_run_sdd_resolve` functions and all top-level constants.
- [x] 4.3 Run `uv run pytest tests/` — all existing tests (install, uninstall, sdd CLI) plus new `test_catalog` and `test_installer` must pass. CLI output strings must match current behavior per spec.

## Phase 5: Cleanup

- [x] 5.1 Run `uv run pytest --cov=ai_harness tests/` — verify no uncovered gap in catalog, installer, or per-CLI installers.
- [x] 5.2 Remove any stale re-exports or dead imports from `main.py`. Verify `main.py` line count under 40.
