from __future__ import annotations

import typer

from ai_harness.commands.init import init
from ai_harness.commands.install import install
from ai_harness.commands.set_models import set_models
from ai_harness.commands.uninstall import uninstall
from ai_harness.commands.worktree import worktree

app = typer.Typer()
app.command()(init)
app.command()(install)
app.command()(set_models)
app.command()(uninstall)
app.command()(worktree)


@app.callback()
def callback() -> None:
    """ai-harness — install and manage AI coding harness configurations."""
    pass


def main() -> None:
    app()
