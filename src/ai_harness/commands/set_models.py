"""set-models command — thin typer adapter that dispatches to the wizard.

Mandatory ``-o/--only`` accepting exactly one Agent CLI. Zero or multiple
CLIs error with a clear message. Slice 2 implements the Claude wizard
end-to-end; OpenCode is deferred to slice 3 with an explicit not-yet
error; generic/copilot are not wizard targets at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ai_harness.commands import parse_single_agent_cli
from ai_harness.modules.harness import AgentCli
from ai_harness.modules.wizard.tui import run_wizard_or_bail


def set_models(
    to: Annotated[
        str,
        typer.Option(
            "-o",
            "--only",
            help="Exactly one Agent CLI to configure (claude for now; opencode comes in slice 3).",
        ),
    ],
) -> None:
    """Run the set-models wizard for the given Agent CLI.

    ``-o`` is mandatory and accepts exactly one value. Re-run the wizard
    to overwrite a previous selection. Press Ctrl+C at any prompt to
    cancel without writing.
    """
    parsed = parse_single_agent_cli(to)
    if len(parsed) == 0:
        valid = ", ".join(a.value for a in AgentCli)
        raise typer.BadParameter(f"set-models requires exactly one Agent CLI in -o. Got nothing. Valid: {valid}.")
    if len(parsed) > 1:
        valid = ", ".join(a.value for a in AgentCli)
        raise typer.BadParameter(
            f"set-models requires exactly one Agent CLI in -o, got {len(parsed)}: "
            f"{', '.join(a.value for a in parsed)}. Valid: {valid}."
        )
    cli = parsed[0]

    if cli == AgentCli.GENERIC:
        raise typer.BadParameter("set-models does not support 'generic' — the generic agent has no model to configure.")
    if cli == AgentCli.COPILOT:
        raise typer.BadParameter(
            "set-models does not support 'copilot' — Copilot has no per-agent model configuration."
        )
    if cli == AgentCli.OPENCODE:
        raise typer.BadParameter("set-models for 'opencode' is not yet implemented (slice 3). Use 'claude' for now.")

    # cli is Claude here — the only supported wizard in this slice.
    wrote = run_wizard_or_bail(cli, home=Path.home())
    if not wrote:
        raise typer.Exit(code=1)
