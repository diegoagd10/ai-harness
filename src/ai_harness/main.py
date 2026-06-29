from __future__ import annotations

import typer

from ai_harness.commands.change import (
    change_continue_cmd,
    change_new_cmd,
    task_create_cmd,
    task_done_cmd,
    task_list_cmd,
    task_next_cmd,
)
from ai_harness.commands.init import init
from ai_harness.commands.install import install
from ai_harness.commands.set_models import set_models
from ai_harness.commands.uninstall import uninstall
from ai_harness.commands.worktree import app as worktree_app

app = typer.Typer()
app.command()(init)
app.command()(install)
app.command()(set_models)
app.command(name="change-new")(change_new_cmd)
app.command(name="change-continue")(change_continue_cmd)
app.command(name="task-create")(task_create_cmd)
app.command(name="task-list")(task_list_cmd)
app.command(name="task-next")(task_next_cmd)
app.command(name="task-done")(task_done_cmd)
app.command()(uninstall)
app.add_typer(worktree_app, name="worktree")


@app.callback()
def callback() -> None:
    """ai-harness — install and manage AI coding harness configurations."""
    pass


def main() -> None:
    app()
