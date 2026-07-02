"""set-models command — thin typer adapter that dispatches to the wizard.

Mandatory ``-o/--only`` accepting exactly one Agent CLI. Zero or multiple
CLIs error with a clear message. Slice 2 implements the Claude wizard
end-to-end; slice 3 implements the OpenCode wizard end-to-end; generic
and copilot are not wizard targets at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ai_harness.commands import parse_agent_clis
from ai_harness.modules.harness import AgentCli
from ai_harness.modules.wizard.pure import parse_agent_mode
from ai_harness.modules.wizard.tui import run_wizard_or_bail

_SUPPORTED = (AgentCli.CLAUDE, AgentCli.OPENCODE)


def set_models(
    to: Annotated[
        list[str],
        typer.Option(
            "-o",
            "--only",
            help="Exactly one Agent CLI to configure (claude or opencode).",
        ),
    ],
    agent: Annotated[
        str,
        typer.Option(
            "-a",
            "--agent",
            help=(
                "Configure the agent set when targeting opencode "
                "('change' for the nine change agents). Ignored for claude."
            ),
        ),
    ] = "change",
) -> None:
    """Run the set-models wizard for the given Agent CLI.

    ``-o`` is mandatory and must appear exactly once. Repeated ``-o``
    flags are rejected — typer would otherwise keep only the last
    occurrence and silently mask the user's mistake. A single ``-o``
    may carry a comma-separated list, which is also rejected by the
    same exactly-one check. Re-run the wizard to overwrite a previous
    selection. Press Ctrl+C at any prompt to cancel without writing.

    ``-a/--agent`` selects which agent set the opencode wizard targets
    (``change`` for the nine change agents). Strict-lowercase; the wizard
    ignores the flag when ``-o claude`` is selected — claude has only one
    agent set so the flag is a no-op there.
    """
    if len(to) > 1:
        valid = ", ".join(a.value for a in _SUPPORTED)
        raise typer.BadParameter(
            f"set-models accepts -o exactly once, got {len(to)} occurrences: {', '.join(to)}. Valid: {valid}."
        )

    # Flatten: a single -o may itself carry a comma-separated list.
    parsed: list[AgentCli] = []
    for raw in to:
        parsed.extend(parse_agent_clis(raw))

    if len(parsed) == 0:
        valid = ", ".join(a.value for a in _SUPPORTED)
        raise typer.BadParameter(f"set-models requires exactly one Agent CLI in -o. Got nothing. Valid: {valid}.")
    if len(parsed) > 1:
        valid = ", ".join(a.value for a in _SUPPORTED)
        raise typer.BadParameter(
            f"set-models requires exactly one Agent CLI in -o, got {len(parsed)}: "
            f"{', '.join(a.value for a in parsed)}. Valid: {valid}."
        )
    cli = parsed[0]

    if cli == AgentCli.GENERIC:
        raise typer.BadParameter("set-models does not support 'generic' — the generic agent has no model to configure.")
    if cli == AgentCli.COPILOT:
        raise typer.BadParameter(
            "set-models does not support 'copilot' — use /model in the Copilot CLI "
            "or edit ~/.copilot/settings.json to set the model."
        )

    # Validate -a/--agent. Strict-lowercase: typer accepts any string, so we
    # route through parse_agent_mode and surface its ValueError verbatim —
    # the message already names the valid set, which typer prepends with
    # "Invalid value for '-a'".
    try:
        agent_mode = parse_agent_mode(agent)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    # Both Claude and OpenCode now have a full wizard. The wizard itself
    # surfaces OpenCode-absent or non-TTY errors with clear messages; the
    # command layer just dispatches. agent_mode is threaded through to
    # run_wizard_or_bail; the claude branch ignores it (one agent set only).
    wrote = run_wizard_or_bail(cli, home=Path.home(), agent_mode=agent_mode)
    if not wrote:
        raise typer.Exit(code=1)
