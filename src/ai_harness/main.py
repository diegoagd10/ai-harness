from __future__ import annotations

import typer

from ai_harness.commands.artifacts import register as register_artifact_commands
from ai_harness.commands.sdd import register as register_sdd_commands

app = typer.Typer()


@app.callback()
def callback() -> None:
    pass


register_sdd_commands(app)
register_artifact_commands(app)


def main() -> None:
    app()
