"""Thin Invoke dispatch: @task per CLI command delegates to lifecycle files.

No test bodies live here — every task is a single delegation to its lifecycle
file. The ``test`` task runs all categories in sequence, provisioning the CLI
binary once inside an isolated sandbox.
"""

from __future__ import annotations

from pathlib import Path

from invoke import task

from e2e.install_lifecycle import run as run_install_lifecycle

REPO_ROOT = Path(__file__).resolve().parent.parent


@task
def install(ctx) -> None:
    """Run the install lifecycle e2e test."""
    run_install_lifecycle(str(REPO_ROOT))


@task(default=True)
def test(ctx) -> None:
    """Run all e2e categories (default task)."""
    install(ctx)
    print("\n=== All e2e categories passed ===")
