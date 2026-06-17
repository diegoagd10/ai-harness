"""Thin Invoke dispatch: @task per CLI command delegates to lifecycle files.

No test bodies live here — every task is a single delegation to its lifecycle
file. The ``test`` task runs all categories in sequence, provisioning the CLI
binary once inside an isolated sandbox.
"""

from __future__ import annotations

from pathlib import Path

from invoke import task

REPO_ROOT = Path(__file__).resolve().parent.parent


def _provision_and_run(runner, ctx) -> None:
    """Provision ai-harness in a sandbox, then invoke *runner(bin_dir)*."""
    from . import harness

    bin_dir = harness.sandboxed_tool_install(str(REPO_ROOT))
    try:
        runner(bin_dir)
    finally:
        harness.sandboxed_tool_uninstall()


@task
def install(ctx) -> None:
    """End-to-end install: fresh install, reinstall, idempotent override."""
    from .test_harness_lifecycle import run_install_tests

    _provision_and_run(run_install_tests, ctx)


@task
def uninstall(ctx) -> None:
    """End-to-end uninstall: artifact removal, backup restore, user-file preservation."""
    from .test_harness_lifecycle import run_uninstall_tests

    _provision_and_run(run_uninstall_tests, ctx)


@task
def sdd_status(ctx) -> None:
    """End-to-end sdd-status: JSON, explicit/inferred change, error states."""
    from .test_sdd_lifecycle import run_sdd_status_tests

    _provision_and_run(run_sdd_status_tests, ctx)


@task
def sdd_continue(ctx) -> None:
    """End-to-end sdd-continue: markdown, --json mode, phase progression."""
    from .test_sdd_lifecycle import run_sdd_continue_tests

    _provision_and_run(run_sdd_continue_tests, ctx)


@task
def tool_lifecycle(ctx) -> None:
    """End-to-end binary provisioning lifecycle (sandboxed uv tool install/uninstall)."""
    from .test_tool_lifecycle import run

    run()


@task
def copilot_cli_lifecycle(ctx) -> None:
    """End-to-end copilot-cli install / uninstall lifecycle."""
    from .test_copilot_cli_lifecycle import run_install_tests, run_uninstall_tests

    def run_all(bin_dir: str) -> None:
        run_install_tests(bin_dir)
        run_uninstall_tests(bin_dir)

    _provision_and_run(run_all, ctx)


@task
def wizard_lifecycle(ctx) -> None:
    """End-to-end wizard bypass lifecycle: install --all -> state file, uninstall --all -> cleared."""
    from .test_wizard_lifecycle import run_state_file_tests

    _provision_and_run(run_state_file_tests, ctx)


@task(default=True)
def test(ctx) -> None:
    """Run all e2e categories (default task)."""
    tool_lifecycle(ctx)
    install(ctx)
    uninstall(ctx)
    copilot_cli_lifecycle(ctx)
    wizard_lifecycle(ctx)
    sdd_status(ctx)
    sdd_continue(ctx)
    # Verify workspace cleanup tracking (no binary needed).
    from .test_sdd_lifecycle import run_workspace_cleanup_tests

    run_workspace_cleanup_tests()
    print("\n=== All e2e categories passed ===")
