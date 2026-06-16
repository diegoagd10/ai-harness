"""Artifact command registration for the Typer app.

Exposes install and uninstall as thin orchestrators that
instantiate a catalog and loop through per-CLI installers.
"""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    """Register install and uninstall commands on *app*."""
    from ai_harness.commands.artifacts.install import install
    from ai_harness.commands.artifacts.uninstall import uninstall

    app.command(name="install")(install)
    app.command(name="uninstall")(uninstall)
