"""SDD command registration for the Typer app."""

from __future__ import annotations

import typer

from ai_harness.commands.sdd.continue_cmd import sdd_continue
from ai_harness.commands.sdd.status import sdd_status


def register(app: typer.Typer) -> None:
    """Register sdd-status and sdd-continue commands on *app*."""
    app.command(name="sdd-status")(sdd_status)
    app.command(name="sdd-continue")(sdd_continue)
