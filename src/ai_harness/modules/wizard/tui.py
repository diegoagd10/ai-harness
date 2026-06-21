"""Set-models wizard — thin questionary/rich interactive shell.

The TUI consumes the pure data-prep layer (:mod:`ai_harness.modules.wizard.pure`)
and never re-derives vocabulary. All decision logic lives in the pure module;
this file is a thin adapter that:

1. Renders a keybinding legend header/footer with rich.
2. Walks the user through the agent → model → effort → confirm flow.
3. Seeds each picker with the value currently in the override store.
4. Writes the chosen overrides atomically and re-renders Claude's installed
   loop agents when the user confirms.
5. Translates questionary's ``KeyboardInterrupt`` (Ctrl+C) into a no-op
   cancel that returns without writing.

This module is intentionally left untested. The pure helpers in
:mod:`ai_harness.modules.wizard.pure` carry all decision logic, and the
``set-models`` command layer covers the non-interactive arg validation
paths. Driving questionary from a non-TTY would test the library, not us.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import questionary
from rich.console import Console
from rich.panel import Panel

from ai_harness.modules.harness.models import AgentCli
from ai_harness.modules.harness.operations import install_for_agent_clis
from ai_harness.modules.harness.renderers import (
    get_agent_meta,
    write_override_store,
)
from ai_harness.modules.wizard.pure import (
    build_confirmation_rows,
    build_effort_picker_rows,
    build_model_picker_rows,
    build_override_payload,
    claude_wizard_agents,
)

if TYPE_CHECKING:
    pass

_console = Console()


# ---------------------------------------------------------------------------
# Keybinding legend — shown in the header/footer of every prompt.
# ---------------------------------------------------------------------------


_KEYBINDING_LEGEND = "↑/↓ + j/k: navigate · type to filter · enter: select · Ctrl+C: cancel"


# ---------------------------------------------------------------------------
# Helper — find the InquirerControl inside a questionary.select layout tree
# ---------------------------------------------------------------------------


def _find_inquirer_control(node: object) -> object | None:
    """Walk a prompt_toolkit layout tree and return questionary's ``InquirerControl``.

    ``questionary.select`` builds the InquirerControl locally and does not expose
    it. We recover it by walking ``Application.layout.container`` (an
    ``HSplit``) and looking at each ``Window``'s ``content``. The walk is
    defensive — any node that does not expose ``content`` / ``children`` is
    skipped. Returns ``None`` if no InquirerControl is found, which should
    not happen for a question built by ``questionary.select``.
    """
    from questionary.prompts.common import InquirerControl

    if node is None:
        return None

    # Window-like: content IS the InquirerControl.
    content = getattr(node, "content", None)
    if isinstance(content, InquirerControl):
        return content

    # Wrap-like containers (ConditionalContainer, Window): recurse into content.
    if content is not None and content is not node:
        found = _find_inquirer_control(content)
        if found is not None:
            return found

    # Split-like containers (HSplit, VSplit): recurse into each child.
    children = getattr(node, "children", None)
    if children:
        for child in children:
            if child is None or isinstance(child, str):
                continue
            found = _find_inquirer_control(child)
            if found is not None:
                return found

    return None


# ---------------------------------------------------------------------------
# Helper — questionary.select with j/k navigation + type-to-filter
# ---------------------------------------------------------------------------


def _filterable_select(
    message: str,
    *,
    choices: list[questionary.Choice],
) -> questionary.Question:
    """Build a questionary.select question that supports j/k AND type-to-filter.

    ``questionary.select`` raises ``ValueError`` if you combine
    ``use_jk_keys=True`` with ``use_search_filter=True`` — the library is
    right that 'j' and 'k' can be part of a search prefix, but the issue's
    acceptance criteria require BOTH vim-style navigation and type-to-filter
    simultaneously. This wrapper builds the question with the search filter
    enabled and ``use_jk_keys=False``, then attaches its own j/k bindings to
    the resulting prompt_toolkit ``Application`` that call
    ``select_next`` / ``select_previous`` on the underlying InquirerControl.

    prompt_toolkit's ``KeyProcessor._process`` calls ``matches[-1]`` — the
    LAST matching binding — for a given key. Our j/k bindings are appended
    to the registry AFTER questionary's eager search-filter bindings, so
    ours win for 'j' and 'k'. Other printable characters still hit
    questionary's search filter and feed ``InquirerControl.search_filter``
    as expected. Arrow keys and Ctrl+C/Ctrl+Q are untouched (they were
    added by questionary and remain functional).
    """
    question = questionary.select(
        message,
        choices=choices,
        use_arrow_keys=True,
        use_search_filter=True,
        use_jk_keys=False,
    )

    # ``question.application`` is a real prompt_toolkit Application in production
    # but a test-time fake (e.g. the ``_SelectSpy`` in tests/test_set_models.py)
    # may omit it. In that case we cannot attach j/k bindings — tests asserting
    # the kwargs reach questionary still pass, and the spy already short-circuits
    # ``.ask()`` so the user never sees a real prompt.
    application = getattr(question, "application", None)
    if application is None:
        return question

    inquirer_control = _find_inquirer_control(application.layout.container)
    if inquirer_control is None:
        # Defensive only — every questionary.select has exactly one InquirerControl.
        return question

    def _move_down(event: object) -> None:
        inquirer_control.select_next()
        while not inquirer_control.is_selection_valid():
            inquirer_control.select_next()

    def _move_up(event: object) -> None:
        inquirer_control.select_previous()
        while not inquirer_control.is_selection_valid():
            inquirer_control.select_previous()

    application.key_bindings.add("j", eager=True)(_move_down)
    application.key_bindings.add("k", eager=True)(_move_up)

    return question


def _print_header(title: str) -> None:
    """Print a header panel with the prompt title and keybinding legend."""
    _console.print(
        Panel(
            f"[bold]{title}[/bold]\n[dim]{_KEYBINDING_LEGEND}[/dim]",
            border_style="cyan",
        )
    )


def _print_footer() -> None:
    """Print a footer rule with the keybinding legend."""
    _console.print(f"[dim]{_KEYBINDING_LEGEND}[/dim]\n")


# ---------------------------------------------------------------------------
# Helper — resolve the current value (override → template default)
# ---------------------------------------------------------------------------


def _current_claude_model(agent: str, home: Path) -> str:
    """Return the current Claude model for *agent* (override wins, else template)."""
    return get_agent_meta(agent, home=home).get("model", {}).get("claude", "sonnet")


def _current_claude_effort(agent: str, home: Path) -> str | None:
    """Return the current Claude effort for *agent* (override wins, else None)."""
    return get_agent_meta(agent, home=home).get("effort", {}).get("claude")


# ---------------------------------------------------------------------------
# Wizard — Claude (slice 2)
# ---------------------------------------------------------------------------


def _ask_claude_model(agent: str, home: Path) -> str | None:
    """Ask the user to pick a model for *agent*; return None on Ctrl+C."""
    rows = build_model_picker_rows(agent, _current_claude_model(agent, home))
    choices = [questionary.Choice(title=row.label, value=row.value) for row in rows]
    return _filterable_select(
        f"Model for {agent}:",
        choices=choices,
    ).ask()


def _ask_claude_effort(agent: str, home: Path) -> str | None:
    """Ask the user to pick an effort for *agent*; return None on Ctrl+C."""
    rows = build_effort_picker_rows(agent, _current_claude_effort(agent, home))
    choices = [questionary.Choice(title=row.label, value=row.value) for row in rows]
    return _filterable_select(
        f"Effort for {agent}:",
        choices=choices,
    ).ask()


def _ask_continue_or_agent(
    phase: str,
    selections: dict[str, str],
) -> str | None:
    """Ask the user to either pick an agent to edit or continue to the next phase.

    A trailing "Continue → {next phase}" choice advances the wizard; selecting
    an agent opens the model/effort picker. ``None`` on Ctrl+C.
    """
    next_phase = {
        "model": "effort",
        "effort": "confirm",
    }.get(phase)
    if next_phase is None:
        next_phase = "confirm"

    agent_list = list(claude_wizard_agents())
    choices: list[questionary.Choice] = [
        questionary.Choice(
            title=f"{agent} (current: {selections.get(agent, 'sonnet')})",
            value=agent,
        )
        for agent in agent_list
    ]
    choices.append(
        questionary.Choice(
            title=f"Continue → {next_phase}",
            value="__continue__",
        )
    )

    return _filterable_select(
        f"Choose an agent to edit its {phase}, or continue:",
        choices=choices,
    ).ask()


def _ask_confirm(selections: dict[str, tuple[str, str | None]]) -> bool:
    """Ask the user to confirm; True on enter, False on Ctrl+C."""
    rows = build_confirmation_rows(selections)
    body = "\n".join(f"  • {row.label}" for row in rows)
    _console.print(
        Panel(
            f"[bold]Apply the following overrides?[/bold]\n{body}",
            border_style="green",
        )
    )
    return bool(
        questionary.confirm(
            "Press enter to write overrides and re-render Claude agents, Ctrl+C to cancel:",
            default=True,
        ).ask()
    )


def run_claude_wizard(*, home: Path) -> bool:
    """Run the full Claude wizard; return True if overrides were written, False on cancel.

    On success: writes the override store and re-renders Claude's installed
    loop agents (generic is NOT reinstalled — that would touch files
    outside the wizard's scope).
    """
    _print_header("set-models · claude")
    _print_footer()

    # Phase 1: model pass — snapshot the baseline so Phase 3 can tell what
    # the user actually changed. Seeding `models` from the baseline also
    # means "continue without picking an agent" leaves that agent at its
    # baseline value (no implicit default overwrite).
    baseline_models: dict[str, str] = {agent: _current_claude_model(agent, home) for agent in claude_wizard_agents()}
    baseline_efforts: dict[str, str | None] = {
        agent: _current_claude_effort(agent, home) for agent in claude_wizard_agents()
    }
    models: dict[str, str] = dict(baseline_models)
    while True:
        pick = _ask_continue_or_agent("model", models)
        if pick is None:  # Ctrl+C
            _console.print("[yellow]Cancelled — no overrides written.[/yellow]")
            return False
        if pick == "__continue__":
            break
        new_model = _ask_claude_model(pick, home)
        if new_model is None:
            _console.print("[yellow]Cancelled — no overrides written.[/yellow]")
            return False
        models[pick] = new_model

    # Phase 2: effort pass
    efforts: dict[str, str | None] = dict(baseline_efforts)
    while True:
        # Show current effort alongside (placeholder if unset)
        display = {agent: (efforts[agent] or "(unset)") for agent in efforts}
        pick = _ask_continue_or_agent("effort", display)
        if pick is None:
            _console.print("[yellow]Cancelled — no overrides written.[/yellow]")
            return False
        if pick == "__continue__":
            break
        new_effort = _ask_claude_effort(pick, home)
        if new_effort is None:
            _console.print("[yellow]Cancelled — no overrides written.[/yellow]")
            return False
        efforts[pick] = new_effort

    # Phase 3: confirm + apply
    selections = {agent: (models[agent], efforts[agent]) for agent in claude_wizard_agents()}
    if not _ask_confirm(selections):
        _console.print("[yellow]Cancelled — no overrides written.[/yellow]")
        return False

    # Selective write: only fields where the user's choice differs from the
    # baseline get serialized. Issue #44 mandates a partial override store;
    # writing every agent's current model would pollute overrides.json with
    # template defaults whenever the user opens the wizard and confirms
    # without changing anything.
    baseline = {
        agent: {"model": baseline_models[agent], "effort": baseline_efforts[agent]} for agent in claude_wizard_agents()
    }
    payload = build_override_payload(baseline, selections)
    if not payload:
        # Nothing changed — leave the override store (and Claude's rendered
        # agents) untouched. Returning True here is correct: the wizard ran
        # successfully, it just had nothing to write.
        _console.print("[green]No changes — overrides untouched.[/green]")
        return True
    write_override_store(home, payload)

    # Re-render Claude's installed loop agents. Generic is intentionally
    # NOT reinstalled — set-models is a scoped operation. If generic is
    # not yet installed, the call is a no-op for generic and only writes
    # the Claude agents that exist (install_for_agent_clis is idempotent
    # and only writes what's in the install plan).
    try:
        install_for_agent_clis([AgentCli.CLAUDE], home=home)
    except (OSError, ValueError) as exc:
        _console.print(f"[red]Failed to re-render Claude agents: {exc}[/red]")
        return False

    _console.print("[green]Overrides written and Claude agents re-rendered.[/green]")
    return True


# ---------------------------------------------------------------------------
# Public entry — dispatch to the right wizard by AgentCli
# ---------------------------------------------------------------------------


def run_wizard(cli: AgentCli, *, home: Path) -> bool:
    """Run the set-models wizard for *cli*; return True if overrides were written.

    Slice 2 supports Claude only. OpenCode is deferred to slice 3.
    Generic and Copilot are not wizard targets at all.
    """
    if cli == AgentCli.CLAUDE:
        return run_claude_wizard(home=home)
    raise NotImplementedError(
        f"set-models for {cli.value!r} is not implemented in this slice",
    )


# ---------------------------------------------------------------------------
# Non-TTY guard — `ai-harness set-models -o claude` without a TTY
# ---------------------------------------------------------------------------


def run_wizard_or_bail(cli: AgentCli, *, home: Path) -> bool:
    """Run the wizard, but bail with a clear error if stdin is not a TTY.

    The TUI needs a TTY to drive questionary's readline-style prompts.
    A non-TTY (e.g. CI, a piped subprocess, CliRunner) is a clear
    user-error path that should error rather than hang waiting for
    stdin that will never come.
    """
    if not sys.stdin.isatty():
        _console.print(
            "[red]set-models requires a TTY (interactive terminal). "
            "Run it directly in your shell, not via a pipe or non-interactive runner.[/red]"
        )
        return False
    return run_wizard(cli, home=home)
