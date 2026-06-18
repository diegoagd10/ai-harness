from __future__ import annotations

import typer

from ai_harness.commands.install import install
from ai_harness.commands.uninstall import uninstall

app = typer.Typer()
app.command()(install)
app.command()(uninstall)


@app.callback()
def callback() -> None:
    """ai-harness — install and manage AI coding harness configurations."""
    pass


def main() -> None:
    app()
