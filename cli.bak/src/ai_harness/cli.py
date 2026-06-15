"""Typer CLI boundary for the Python SDD migration slice.

Typer owns parsing, help, and dispatch. Commands are registered with explicit
hyphenated names so the Go-compatible ``sdd-status`` / ``sdd-continue`` invocations
are preserved. Both commands share the same resolve/render/exit path through
:func:`_dispatch_command`; the only differences are the renderer (Rich for
``sdd-status`` terminal output, plain markdown for ``sdd-continue`` LLM
consumption) and whether instructions are forced on (yes for ``sdd-continue``,
opt-in for ``sdd-status``).

The ``install`` and ``uninstall`` commands route to the install package;
their interactive picker lives in :mod:`ai_harness.picker`.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from . import compat, picker, rendering
from .install.config import Config, resolve_repo_dir
from .install.harness import ALL_HARNESSES, Harness, parse_harness_list
from .install.install import install as install_run
from .install.uninstall import detect_installed_harnesses
from .install.uninstall import uninstall as uninstall_run
from .sdd import SddError, Status, resolve

app = typer.Typer(
    add_completion=False,
    help=(
        "ai-harness helper (Python migration slice: sdd-status, sdd-continue, "
        "install, uninstall)."
    ),
)


@app.callback()
def _main() -> None:
    """Route to a subcommand; preserves group dispatch for hyphenated names."""


def _dispatch_command(
    cwd: str,
    change: str,
    json_output: bool,
    always_instructions: bool,
    instructions_flag: bool,
    renderer: Callable[[Status], str | None],
) -> None:
    """Resolve a Status and route it to JSON or the caller's renderer.

    ``always_instructions`` forces per-phase instructions to be attached to the
    Status regardless of the user-facing ``--instructions`` flag; the flag is
    still accepted (Go-compatible) but ignored when ``always_instructions`` is
    true. Error and usage exits share one path so both commands fail identically.
    """
    include_instructions = always_instructions or instructions_flag
    try:
        status = resolve(cwd, "", change, include_instructions)
    except SddError as err:
        typer.echo(f"ai-harness: {err}", err=True)
        raise typer.Exit(code=compat.EXIT_ERROR) from err
    except OSError as err:
        typer.echo(f"ai-harness: {err}", err=True)
        raise typer.Exit(code=compat.EXIT_ERROR) from err

    if json_output:
        typer.echo(compat.status_to_json(status))
        return

    output = renderer(status)
    if output is not None:
        typer.echo(output)


@app.command(name="sdd-status")
def sdd_status(
    change: str | None = typer.Argument(
        None, help="Active OpenSpec change name; inferred when omitted."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit deterministic JSON instead of a rendered summary."
    ),
    instructions: bool = typer.Option(
        False, "--instructions", help="Attach per-phase instructions to the status."
    ),
    cwd: str = typer.Option("", "--cwd", help="Workspace directory to read openspec/ from."),
) -> None:
    """Report the SDD phase state for a change."""
    _dispatch_command(
        cwd=cwd,
        change=change or "",
        json_output=json_output,
        always_instructions=False,
        instructions_flag=instructions,
        renderer=rendering.render_status,
    )


@app.command(name="sdd-continue")
def sdd_continue(
    change: str | None = typer.Argument(
        None, help="Active OpenSpec change name; inferred when omitted."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit deterministic JSON instead of dispatcher markdown."
    ),
    instructions: bool = typer.Option(
        False,
        "--instructions",
        help="Accepted for Go-compatibility; instructions are always attached on sdd-continue.",
    ),
    cwd: str = typer.Option("", "--cwd", help="Workspace directory to read openspec/ from."),
) -> None:
    """Report the SDD dispatcher routing for a change.

    Always attaches per-phase instructions (Go-compatible: ``--instructions`` is
    accepted and ignored). Human output is plain markdown targeting LLM
    consumption, not a Rich-rendered terminal.
    """
    _dispatch_command(
        cwd=cwd,
        change=change or "",
        json_output=json_output,
        always_instructions=True,
        instructions_flag=instructions,
        renderer=rendering.render_dispatcher,
    )


def main() -> None:
    """Console-script entry point."""
    app()


# --- install / uninstall --------------------------------------------------


def _home_paths() -> dict[str, Path]:
    """Return the standard $HOME-anchored paths the installer writes to."""
    home = Path(os.environ.get("HOME", "/"))
    return {
        "claude": home / ".claude",
        "agents": home / ".agents",
        "copilot": home / ".copilot",
        "opencode": home / ".config" / "opencode",
    }


def _build_config(repo: Path, harnesses: list[Harness]) -> Config:
    paths = _home_paths()
    return Config(
        repo_dir=repo,
        claude_dir=paths["claude"],
        agents_dir=paths["agents"],
        copilot_dir=paths["copilot"],
        opencode_dir=paths["opencode"],
        harnesses=harnesses,
    )


@dataclass(frozen=True)
class _Selection:
    """The resolved harness selection for an install / uninstall run.

    ``cancelled`` short-circuits the run with a friendly message and
    exit 0; ``empty`` means "user confirmed with nothing checked".
    """

    harnesses: list[Harness]
    cancelled: bool = False
    empty: bool = False


def _resolve_selection(
    harness_flag: str | None,
    *,
    console: Console,
    title: str,
    installed_hint: list[Harness] | None = None,
    fail_on_picker_error: bool = False,
) -> _Selection:
    """Decide which harnesses the user picked, prompting on a TTY.

    Precedence:

    1. ``--harness`` flag: parsed and validated. An unknown token is an
       immediate error so the failure is loud rather than silent.
    2. Interactive TTY: the Rich multi-select picker runs with the
       supplied title. ``installed_hint`` (when given) pre-marks already
       installed harnesses in the menu.
    3. No TTY (CI / scripts / tests): every harness is selected. This
       preserves the Go install default and is the safe behaviour for
       non-interactive automation.

    When *fail_on_picker_error* is True, a :class:`RuntimeError` from the
    picker (e.g. POSIX-raw-mode unavailable) raises a hard exit instead
    of silently broadening the selection to every harness.  Callers that
    perform destructive operations (uninstall) must set this to True so
    the scope cannot widen unexpectedly.
    """
    if harness_flag is not None:
        try:
            harnesses = parse_harness_list(harness_flag)
        except ValueError as err:
            typer.echo(f"ai-harness: {err}", err=True)
            raise typer.Exit(code=compat.EXIT_USAGE) from err
        return _Selection(harnesses=harnesses)
    if sys.stdin.isatty():
        try:
            result = picker.prompt_harnesses(
                console, installed=installed_hint or [], title=title
            )
        except RuntimeError as err:
            if fail_on_picker_error:
                typer.echo(
                    f"ai-harness: picker unavailable ({err}); "
                    "pass --harness to select harnesses explicitly",
                    err=True,
                )
                raise typer.Exit(code=compat.EXIT_ERROR) from err
            # POSIX-raw-mode not available; fall back to "all".
            typer.echo(f"ai-harness: {err}; installing every harness", err=True)
            return _Selection(harnesses=list(ALL_HARNESSES))
        if result.kind == picker.PICKER_CANCELLED:
            return _Selection(harnesses=[], cancelled=True)
        if result.kind == picker.PICKER_EMPTY:
            return _Selection(harnesses=[], empty=True)
        return _Selection(harnesses=list(result.selection))
    return _Selection(harnesses=list(ALL_HARNESSES))


def _format_outcome(outcome) -> str:
    """Render one Outcome as a single human-readable line.

    Mirrors the Go ``formatOutcome`` so the Python install prints the
    same lines a Go-fallback user is used to seeing.
    """
    action = outcome.action
    if action in ("copied", "overwritten"):
        return f"  {action} {outcome.dest} <- {outcome.src}"
    if action == "source missing":
        return f"  source missing for {outcome.dest}: {outcome.src}"
    if action == "removed":
        if outcome.target:
            return f"  removed {outcome.dest} (from {outcome.target})"
        return f"  removed {outcome.dest}"
    if action == "absent":
        return f"  absent {outcome.dest}"
    return f"  {action} {outcome.dest}"


def _emit_report(outcomes) -> None:
    for outcome in outcomes:
        typer.echo(_format_outcome(outcome))


@app.command(name="install")
def install_cmd(
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="Repo root holding skills/ and AGENTS.md (default: cwd).",
    ),
    harness: str | None = typer.Option(
        None,
        "--harness",
        help=(
            "Comma-separated harnesses to install: claude,copilot,opencode. "
            "Omit to install all (CI default) or pick interactively on a TTY."
        ),
    ),
) -> None:
    """Install the ai-harness agents and harness files into your home."""
    try:
        repo_dir = resolve_repo_dir(repo, os.getcwd())
    except ValueError as err:
        typer.echo(f"ai-harness: {err}", err=True)
        raise typer.Exit(code=compat.EXIT_ERROR) from err
    console = Console()
    selection = _resolve_selection(
        harness,
        console=console,
        title="Select agents/harnesses to install",
        fail_on_picker_error=False,
    )
    if selection.cancelled:
        typer.echo("ai-harness: install cancelled", err=True)
        raise typer.Exit(code=compat.EXIT_OK)
    if selection.empty:
        typer.echo("ai-harness: nothing selected; nothing installed")
        raise typer.Exit(code=compat.EXIT_OK)
    cfg = _build_config(repo_dir, selection.harnesses)
    report, _entries, error = install_run(cfg)
    _emit_report(report)
    if error:
        typer.echo(f"ai-harness: {error}", err=True)
        raise typer.Exit(code=compat.EXIT_ERROR)


@app.command(name="uninstall")
def uninstall_cmd(
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="Repo root (unused; kept for Go-compatible CLI shape).",
    ),
    harness: str | None = typer.Option(
        None,
        "--harness",
        help=(
            "Comma-separated harnesses to uninstall. Omit to uninstall all "
            "(CI default) or pick interactively on a TTY."
        ),
    ),
) -> None:
    """Remove every ai-harness artifact the manifest still owns."""
    try:
        repo_dir = resolve_repo_dir(repo, os.getcwd())
    except ValueError as err:
        # Uninstall tolerates a non-repo cwd (the manifest is enough), but
        # if a --repo was passed and it is invalid, surface that loudly.
        if repo:
            typer.echo(f"ai-harness: {err}", err=True)
            raise typer.Exit(code=compat.EXIT_ERROR) from err
        repo_dir = Path(os.getcwd())
    console = Console()
    # Pre-flight: discover installed harnesses for the picker hint.
    pre_cfg = _build_config(repo_dir, [])
    installed = detect_installed_harnesses(pre_cfg)
    selection = _resolve_selection(
        harness,
        console=console,
        title="Select agents/harnesses to uninstall",
        installed_hint=installed,
        fail_on_picker_error=True,
    )
    if selection.cancelled:
        typer.echo("ai-harness: uninstall cancelled", err=True)
        raise typer.Exit(code=compat.EXIT_OK)
    if selection.empty:
        typer.echo("ai-harness: nothing selected; nothing uninstalled")
        raise typer.Exit(code=compat.EXIT_OK)
    cfg = _build_config(repo_dir, selection.harnesses)
    report, error = uninstall_run(cfg)
    _emit_report(report)
    if error:
        typer.echo(f"ai-harness: {error}", err=True)
        raise typer.Exit(code=compat.EXIT_ERROR)


if __name__ == "__main__":  # pragma: no cover
    main()
