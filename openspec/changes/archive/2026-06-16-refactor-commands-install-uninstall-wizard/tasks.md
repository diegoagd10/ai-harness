# Tasks: Interactive Install/Uninstall Wizard

## Review Workload Forecast

Estimated changed lines: ~600–700 (prod ~240, test ~410). Delivery: exception-ok, single PR.

Decision needed before apply: No
Maintainer-approved size exception: Yes
400-line budget risk: High

## Phase 1: Infrastructure

- [x] 1.1 Add `questionary` to `pyproject.toml` deps; `uv lock`; verify import works.
- [x] 1.2 Add `monkeypatch_questionary` fixture to `tests/conftest.py` — stub `questionary.checkbox`, configurable return list or `Cancelled` sentinel.
- [x] 1.3 RED: `test_install_returns_InstallResult` (not `None`) + `test_install_result_fields` (`success`, `errors`).
- [x] 1.4 GREEN: `InstallResult`/`UninstallResult` dataclasses in `installer.py`; try/except with short-circuit on first error; propagate in 3 per-CLI classes.
- [x] 1.5 REFACTOR: update existing `test_installer.py`, `test_install.py`, `test_uninstall.py` for new return contract; full suite green.

## Phase 2: state.py

- [x] 2.1 RED: `test_load_missing_empty`, `test_load_valid_returns_set`, `test_load_malformed_raises`.
- [x] 2.2 GREEN: `load_state(home) -> set[str]` covering missing→`{}`, valid→set, malformed→`StateFileError`.
- [x] 2.3 RED: `test_save_creates_dir`, `test_save_atomic` (crash mid-write→prior file intact).
- [x] 2.4 GREEN: `save_state(home, installed)` with temp-file + `os.rename`.
- [x] 2.5 RED: `test_clear_deletes_file`, `test_clear_idempotent` (missing→no error).
- [x] 2.6 GREEN: `clear_state(home)`.

## Phase 3: wizard.py

- [x] 3.1 RED: `test_select_install_shows_three` (order), `test_select_install_preselects_non_installed`.
- [x] 3.2 RED: `test_select_install_zero_returns_empty`, `test_select_install_escape_returns_cancelled`.
- [x] 3.3 GREEN: `select_install_targets(installed, console)` covering 3.1–3.2.
- [x] 3.4 RED: `test_select_uninstall_only_installed`, `test_select_uninstall_preselects_none`, `test_select_uninstall_escape_cancelled`.
- [x] 3.5 GREEN: `select_uninstall_targets(installed, console)` covering 3.4.

## Phase 4: install command

- [x] 4.1 RED: `test_install_all_bypasses_wizard` — `--all` invokes 3 installers, no questionary.
- [x] 4.2 GREEN: `--all` Typer option; bypass loops installers, `save_state` on full success.
- [x] 4.3 RED: `test_install_wizard_called_no_flag`, `test_install_empty_exits_zero`, `test_install_escape_exits_one`.
- [x] 4.4 RED: `test_install_state_on_success`, `test_install_no_tty_errors`, `test_install_all_or_nothing`.
- [x] 4.5 GREEN: wizard branch (TTY guard→load→wizard→match sentinel→execute→save_state).

## Phase 5: uninstall command

- [x] 5.1 RED: `test_uninstall_empty_state_exits_zero` — "Nothing to uninstall" + exit 0.
- [x] 5.2 GREEN: early return when `load_state` empty.
- [x] 5.3 RED: `test_uninstall_all_bypasses_wizard`; GREEN: `--all` Typer option, bypass loops, `clear_state`.
- [x] 5.4 RED: `test_uninstall_wizard_called_no_flag`, `test_uninstall_empty_exits_zero`, `test_uninstall_escape_exits_one`.
- [x] 5.5 RED: `test_uninstall_state_on_success`, `test_uninstall_last_deletes_state`, `test_uninstall_all_or_nothing`.
- [x] 5.6 GREEN: wizard branch (load→wizard→match sentinel→execute→save_state or clear_state).

## Phase 6: E2E

- [x] 6.1 Update `e2e/test_harness_lifecycle.py`: use `--all` flag on install/uninstall invocations.
- [x] 6.2 Add `e2e/test_wizard_lifecycle.py`: install `--all`→verify state; wizard uninstall→verify state delta.
- [x] 6.3 Run `e2e/docker-test.sh` to confirm Docker CI passes with `--all` bypass.
