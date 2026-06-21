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

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import questionary
from rich.console import Console
from rich.panel import Panel

from ai_harness.modules.harness.models import AgentCli
from ai_harness.modules.harness.operations import re_render_for_agent_clis
from ai_harness.modules.harness.renderers import (
    get_agent_meta,
    write_override_store,
)
from ai_harness.modules.wizard.pure import (
    build_confirmation_rows,
    build_effort_picker_rows,
    build_model_picker_rows,
    build_opencode_effort_picker_rows,
    build_opencode_model_picker_rows,
    build_opencode_override_payload,
    build_override_payload,
    claude_wizard_agents,
    join_opencode_catalog,
    opencode_model_is_reasoning,
    opencode_wizard_agents,
)

if TYPE_CHECKING:
    pass


# Subprocess timeout for ``opencode models`` — bounded so a hung install
# can't block the wizard indefinitely.
_OPENCODE_MODELS_TIMEOUT_SECONDS = 10.0


class OpencodeUnavailable(Exception):
    """Raised when OpenCode cannot provide the data the wizard needs.

    Covers a missing binary, a non-zero exit from ``opencode models``, an
    empty id list, and a missing/malformed ``~/.cache/opencode/models.json``.
    The message is the user-facing guidance: install OpenCode, then run
    ``opencode auth login`` (or the provider of choice) so the local
    catalog reflects what the machine is authenticated for. There is no
    static fallback list — the user must fix their environment first.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _default_subprocess_runner(args: list[str], timeout: float) -> str:
    """Default runner: invoke the program via :mod:`subprocess` and return stdout."""
    completed = subprocess.run(  # noqa: S603 — args come from the wizard, not user input
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        stderr_tail = (completed.stderr or "").strip().splitlines()
        tail = stderr_tail[-1] if stderr_tail else ""
        raise OpencodeUnavailable(
            f"`{' '.join(args)}` failed (exit {completed.returncode}): {tail or 'no stderr'}. "
            "Install OpenCode and run `opencode auth login` so the wizard can list the "
            "models your machine is authenticated for."
        )
    return completed.stdout


def _load_opencode_catalog(
    home: Path,
    *,
    runner: Callable[[list[str], float], str] = _default_subprocess_runner,
) -> tuple[list[str], dict]:
    """Return ``(model_ids, catalog)`` for the wizard or raise :class:`OpencodeUnavailable`.

    Runs ``opencode models`` (defaults to the installed binary on PATH)
    and reads ``~/.cache/opencode/models.json``. The id list is filtered
    to non-empty lines; the catalog is the raw dict — flattening/joining
    is the pure layer's job. The *runner* parameter is injectable so
    tests can supply canned subprocess output without touching the host
    PATH.

    Any failure (missing binary, nonzero exit, empty ids, missing or
    malformed catalog) raises :class:`OpencodeUnavailable` with the same
    install/configure guidance — no static fallback. Subprocess
    exceptions (:class:`FileNotFoundError`,
    :class:`subprocess.CalledProcessError`,
    :class:`subprocess.TimeoutExpired`) are caught here so callers
    that don't pre-translate them (e.g. real subprocess wrappers) still
    get a typed :class:`OpencodeUnavailable` rather than a raw
    :class:`OSError`.
    """
    try:
        raw = runner(["opencode", "models"], _OPENCODE_MODELS_TIMEOUT_SECONDS)
    except OpencodeUnavailable:
        raise
    except FileNotFoundError as exc:
        raise OpencodeUnavailable(
            "OpenCode is not installed (no `opencode` binary on PATH). "
            "Install OpenCode and run `opencode auth login` so the wizard "
            "can list the models your machine is authenticated for."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr_tail = (exc.stderr or "").strip().splitlines()
        tail = stderr_tail[-1] if stderr_tail else ""
        raise OpencodeUnavailable(
            f"`opencode models` failed (exit {exc.returncode}): {tail or 'no stderr'}. "
            "Install OpenCode and run `opencode auth login` so the wizard can list the "
            "models your machine is authenticated for."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise OpencodeUnavailable(
            f"`opencode models` timed out after {_OPENCODE_MODELS_TIMEOUT_SECONDS}s. "
            "Check your OpenCode install or your network connection, then try again."
        ) from exc

    model_ids = [line.strip() for line in raw.splitlines() if line.strip()]
    if not model_ids:
        raise OpencodeUnavailable(
            "`opencode models` returned no model ids. Authenticate with your provider "
            "(`opencode auth login`) and try again — the wizard does not ship a "
            "fallback list of models."
        )

    catalog_path = home / ".cache" / "opencode" / "models.json"
    if not catalog_path.is_file():
        raise OpencodeUnavailable(
            f"OpenCode's local catalog was not found at {catalog_path}. Open OpenCode "
            "once so it can populate the cache, or run `opencode models` to trigger "
            "a refresh — the wizard needs cost and reasoning data from that file."
        )
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OpencodeUnavailable(
            f"OpenCode's local catalog at {catalog_path} could not be parsed "
            f"({type(exc).__name__}: {exc}). Re-run `opencode models` to rebuild it, "
            "or delete the file so OpenCode regenerates it on next start."
        ) from exc
    return model_ids, catalog


def _resolve_opencode_binary() -> str | None:
    """Return the path of the ``opencode`` binary on PATH, or ``None`` when missing.

    Used to give a precise error message when the wizard is launched in
    an environment where OpenCode is not installed — distinguishes
    "binary not on PATH" from "binary present but failing" so the user
    gets the right remediation step.
    """
    return shutil.which("opencode")


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
    """Clear the terminal, then print a header panel with the prompt title and legend.

    Folding the clear into the header render makes "clear + render header"
    one atomic unit: every phase render (including back-navigation and
    repeated agent-edit loop iterations) starts from a clean screen instead
    of stacking on prior output (#51).
    """
    if _console.is_terminal:
        _console.clear()
    _console.print(
        Panel(
            f"[bold]{title}[/bold]\n[dim]{_KEYBINDING_LEGEND}[/dim]",
            border_style="cyan",
        )
    )


# ---------------------------------------------------------------------------
# Helper — resolve the current value (override → template default)
# ---------------------------------------------------------------------------


def _current_claude_model(agent: str, home: Path) -> str:
    """Return the current Claude model for *agent* (override wins, else template)."""
    return get_agent_meta(agent, home=home).get("model", {}).get("claude", "sonnet")


def _current_claude_effort(agent: str, home: Path) -> str | None:
    """Return the current Claude effort for *agent* (override wins, else None)."""
    return get_agent_meta(agent, home=home).get("effort", {}).get("claude")


def _current_opencode_model(agent: str, home: Path) -> str | None:
    """Return the current OpenCode model for *agent* (override wins, else template).

    Unlike Claude, the template defaults differ per agent
    (e.g. ``loop-orchestrator`` defaults to ``openai/gpt-5.5``). A
    ``None`` return means the agent has no default for opencode — the
    picker just won't pre-select anything in that case.
    """
    return get_agent_meta(agent, home=home).get("model", {}).get("opencode")


def _current_opencode_effort(agent: str, home: Path) -> str | None:
    """Return the current OpenCode effort for *agent* (override wins, else None)."""
    return get_agent_meta(agent, home=home).get("effort", {}).get("opencode")


# ---------------------------------------------------------------------------
# Wizard — Claude (slice 2)
# ---------------------------------------------------------------------------


def _ask_claude_model(agent: str, home: Path) -> str | None:
    """Ask the user to pick a model for *agent*; return None on Ctrl+C.

    A leading "← Back" choice returns the ``"__back__"`` sentinel so the
    caller can re-show the agent chooser without recording a model change.
    """
    rows = build_model_picker_rows(agent, _current_claude_model(agent, home))
    choices = [questionary.Choice(title="← Back", value="__back__")]
    choices.extend(questionary.Choice(title=row.label, value=row.value) for row in rows)
    return _filterable_select(
        f"Model for {agent}:",
        choices=choices,
    ).ask()


def _ask_claude_effort(agent: str, home: Path) -> str | None:
    """Ask the user to pick an effort for *agent*; return None on Ctrl+C.

    A leading "← Back" choice returns the ``"__back__"`` sentinel so the
    caller can re-show the agent chooser without recording an effort change.
    """
    rows = build_effort_picker_rows(agent, _current_claude_effort(agent, home))
    choices = [questionary.Choice(title="← Back", value="__back__")]
    choices.extend(questionary.Choice(title=row.label, value=row.value) for row in rows)
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
    an agent opens the model/effort picker. ``None`` on Ctrl+C. Phases after
    the first ("model" has no predecessor) get a leading "← Back" choice
    returning ``"__back__"`` so the user can return to the previous phase.
    """
    next_phase = {
        "model": "effort",
        "effort": "confirm",
    }.get(phase)
    if next_phase is None:
        next_phase = "confirm"

    agent_list = list(claude_wizard_agents())
    choices: list[questionary.Choice] = []
    if phase != "model":
        choices.append(questionary.Choice(title="← Back", value="__back__"))
    choices.extend(
        questionary.Choice(
            title=f"{agent} (current: {selections.get(agent, 'sonnet')})",
            value=agent,
        )
        for agent in agent_list
    )
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


def _ask_confirm(title: str, selections: dict[str, tuple[str, str | None]]) -> bool:
    """Ask the user to confirm; True on enter, False on Ctrl+C.

    Clears and prints *title* as the header first so the confirm screen is
    also cleared+headed like every other phase render (#51).
    """
    _print_header(title)
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
    # Phase 1: model pass — snapshot the baseline so Phase 3 can tell what
    # the user actually changed. Seeding `models` from the baseline also
    # means "continue without picking an agent" leaves that agent at its
    # baseline value (no implicit default overwrite).
    baseline_models: dict[str, str] = {agent: _current_claude_model(agent, home) for agent in claude_wizard_agents()}
    baseline_efforts: dict[str, str | None] = {
        agent: _current_claude_effort(agent, home) for agent in claude_wizard_agents()
    }
    models: dict[str, str] = dict(baseline_models)
    efforts: dict[str, str | None] = dict(baseline_efforts)

    def run_model_phase() -> str:
        """Drive the model phase loop; return '__continue__', '__back__', or '__cancel__'."""
        while True:
            _print_header("set-models · claude — model")
            pick = _ask_continue_or_agent("model", models)
            if pick is None:  # Ctrl+C
                return "__cancel__"
            if pick in ("__continue__", "__back__"):
                return pick
            new_model = _ask_claude_model(pick, home)
            if new_model is None:
                return "__cancel__"
            if new_model == "__back__":
                continue
            models[pick] = new_model

    def run_effort_phase() -> str:
        """Drive the effort phase loop; return '__continue__', '__back__', or '__cancel__'."""
        while True:
            _print_header("set-models · claude — effort")
            # Show current effort alongside (placeholder if unset)
            display = {agent: (efforts[agent] or "(unset)") for agent in efforts}
            pick = _ask_continue_or_agent("effort", display)
            if pick is None:
                return "__cancel__"
            if pick in ("__continue__", "__back__"):
                return pick
            new_effort = _ask_claude_effort(pick, home)
            if new_effort is None:
                return "__cancel__"
            if new_effort == "__back__":
                continue
            efforts[pick] = new_effort

    # Phases 1-2 are driven by an index so the effort phase's "← Back" can
    # decrement back into the model phase without losing state — `models`
    # and `efforts` are closures shared across re-entries.
    phases = [run_model_phase, run_effort_phase]
    index = 0
    while index < len(phases):
        outcome = phases[index]()
        if outcome == "__cancel__":
            _console.print("[yellow]Cancelled — no overrides written.[/yellow]")
            return False
        if outcome == "__back__":
            index -= 1
            continue
        index += 1

    # Phase 3: confirm + apply
    selections = {agent: (models[agent], efforts[agent]) for agent in claude_wizard_agents()}
    if not _ask_confirm("set-models · claude — confirm", selections):
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

    # Re-render Claude's installed loop agents with the fresh overrides.
    # ``re_render_for_agent_clis`` writes only the rendered-agent files and
    # leaves ``~/.ai-harness/installed.json`` untouched — unlike
    # ``install_for_agent_clis`` with a single CLI, which would rewrite the
    # manifest to only contain Claude and silently drop entries for any
    # other installed CLIs (generic, copilot, opencode). Generic is
    # intentionally a no-op: set-models is a scoped operation that
    # re-emits only the loop-agent files whose override state just changed.
    try:
        re_render_for_agent_clis([AgentCli.CLAUDE], home=home)
    except (OSError, ValueError) as exc:
        _console.print(f"[red]Failed to re-render Claude agents: {exc}[/red]")
        return False

    _console.print("[green]Overrides written and Claude agents re-rendered.[/green]")
    return True


# ---------------------------------------------------------------------------
# Public entry — dispatch to the right wizard by AgentCli
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Wizard — OpenCode (slice 3)
# ---------------------------------------------------------------------------


def _ask_opencode_model(agent: str, joined, home: Path) -> str | None:
    """Ask the user to pick an OpenCode model for *agent*; return None on Ctrl+C.

    *joined* is a list of :class:`OpencodeModelEntry` produced by
    :func:`join_opencode_catalog` — the TUI never re-derives cost or
    reasoning from the catalog, it just renders the labels the pure
    layer produced. A leading "← Back" choice returns the ``"__back__"``
    sentinel so the caller can re-show the agent chooser without
    recording a model change.
    """
    rows = build_opencode_model_picker_rows(joined, _current_opencode_model(agent, home) or "")
    choices = [questionary.Choice(title="← Back", value="__back__")]
    choices.extend(questionary.Choice(title=row.label, value=row.value) for row in rows)
    return _filterable_select(
        f"Model for {agent}:",
        choices=choices,
    ).ask()


def _ask_opencode_effort(agent: str, home: Path) -> str | None:
    """Ask the user to pick an OpenCode reasoning effort for *agent*; None on Ctrl+C.

    The TUI is responsible for NOT calling this for non-reasoning models
    — :func:`run_opencode_wizard` checks the model's catalog entry
    before prompting. A leading "← Back" choice returns the ``"__back__"``
    sentinel so the caller can re-show the agent chooser without recording
    an effort change.
    """
    rows = build_opencode_effort_picker_rows(agent, _current_opencode_effort(agent, home))
    choices = [questionary.Choice(title="← Back", value="__back__")]
    choices.extend(questionary.Choice(title=row.label, value=row.value) for row in rows)
    return _filterable_select(
        f"Reasoning effort for {agent} (low → high):",
        choices=choices,
    ).ask()


def _ask_opencode_continue_or_agent(
    phase: str,
    selections: dict[str, str],
) -> str | None:
    """Pick an OpenCode agent to edit, or advance to the next phase.

    The agent list shows the current selection per agent (after the model
    pass) so the user can confirm what they just chose before moving on.
    Phases after the first ("model" has no predecessor) get a leading
    "← Back" choice returning ``"__back__"`` so the user can return to the
    previous phase.
    """
    next_phase = {
        "model": "effort",
        "effort": "confirm",
    }.get(phase)
    if next_phase is None:
        next_phase = "confirm"

    agent_list = list(opencode_wizard_agents())
    choices: list[questionary.Choice] = []
    if phase != "model":
        choices.append(questionary.Choice(title="← Back", value="__back__"))
    choices.extend(
        questionary.Choice(
            title=f"{agent} (current: {selections.get(agent, '(unset)')})",
            value=agent,
        )
        for agent in agent_list
    )
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


def run_opencode_wizard(*, home: Path) -> bool:
    """Run the full OpenCode wizard; return True if overrides were written, False on cancel.

    Phases mirror the Claude wizard (agent → model → effort → confirm)
    with two OpenCode-specific behaviours:

    - Model list comes from ``opencode models`` joined with the local
      catalog's cost and reasoning. If OpenCode is absent or its data
      is incomplete, the wizard errors with install/configure guidance
      and writes nothing.
    - Effort is offered only for agents whose selected model has
      ``reasoning: true`` per the catalog. Non-reasoning models skip the
      effort prompt and the wizard clears any stale effort override
      for that agent so the renderer stops emitting
      ``reasoningEffort`` in its frontmatter.

    On success: writes the override store and re-renders OpenCode's
    installed loop agents via :func:`re_render_for_agent_clis` so the
    change is live without touching the install manifest. Ctrl+C at any
    prompt cancels with no writes.
    """
    binary = _resolve_opencode_binary()
    if binary is None:
        _console.print(
            "[red]OpenCode is not installed (no `opencode` binary on PATH). "
            "Install OpenCode and run `opencode auth login` so the wizard "
            "can list the models your machine is authenticated for.[/red]"
        )
        return False

    try:
        model_ids, catalog = _load_opencode_catalog(home)
    except OpencodeUnavailable as exc:
        _console.print(f"[red]{exc.message}[/red]")
        return False

    joined = join_opencode_catalog(model_ids, catalog)

    # Phase 1: model pass — snapshot the baseline so Phase 3 can tell what
    # the user actually changed. Seeding `models` from the baseline also
    # means "continue without picking an agent" leaves that agent at its
    # baseline value (no implicit default overwrite).
    agents = opencode_wizard_agents()
    baseline_models: dict[str, str] = {agent: (_current_opencode_model(agent, home) or "") for agent in agents}
    baseline_efforts: dict[str, str | None] = {agent: _current_opencode_effort(agent, home) for agent in agents}
    models: dict[str, str] = dict(baseline_models)
    efforts: dict[str, str | None] = dict(baseline_efforts)

    def run_model_phase() -> str:
        """Drive the model phase loop; return '__continue__', '__back__', or '__cancel__'."""
        while True:
            _print_header("set-models · opencode — model")
            pick = _ask_opencode_continue_or_agent("model", models)
            if pick is None:  # Ctrl+C
                return "__cancel__"
            if pick in ("__continue__", "__back__"):
                return pick
            new_model = _ask_opencode_model(pick, joined, home)
            if new_model is None:
                return "__cancel__"
            if new_model == "__back__":
                continue
            models[pick] = new_model

    def run_effort_phase() -> str:
        """Drive the effort phase loop; return '__continue__', '__back__', or '__cancel__'.

        For non-reasoning models the wizard skips the effort prompt and
        clears the selection to None. For reasoning models the user picks
        a value from the fixed (low, medium, high) set. The TUI does not
        consult the model's catalog entry directly (that decision lives in
        the pure layer via opencode_model_is_reasoning) so the gate is
        testable in isolation.
        """
        while True:
            _print_header("set-models · opencode — effort")
            # Show the current effort alongside (placeholder if unset)
            display = {agent: (efforts[agent] or "(unset)") for agent in efforts}
            pick = _ask_opencode_continue_or_agent("effort", display)
            if pick is None:
                return "__cancel__"
            if pick in ("__continue__", "__back__"):
                return pick
            chosen_model = models[pick]
            if not opencode_model_is_reasoning(chosen_model, catalog):
                # Non-reasoning model: clear effort, render the skip explicitly,
                # do NOT prompt. The user can still continue or pick another agent.
                efforts[pick] = None
                _console.print(f"[dim]Skipping effort for {pick}: {chosen_model} is not a reasoning model.[/dim]")
                continue
            new_effort = _ask_opencode_effort(pick, home)
            if new_effort is None:
                return "__cancel__"
            if new_effort == "__back__":
                continue
            efforts[pick] = new_effort

    # Phases 1-2 are driven by an index so the effort phase's "← Back" can
    # decrement back into the model phase without losing state or re-running
    # the catalog loader subprocess above — `models`/`efforts` are closures
    # shared across re-entries.
    phases = [run_model_phase, run_effort_phase]
    index = 0
    while index < len(phases):
        outcome = phases[index]()
        if outcome == "__cancel__":
            _console.print("[yellow]Cancelled — no overrides written.[/yellow]")
            return False
        if outcome == "__back__":
            index -= 1
            continue
        index += 1

    # Phase 3: confirm + apply
    selections = {agent: (models[agent], efforts[agent]) for agent in agents}
    if not _ask_confirm("set-models · opencode — confirm", selections):
        _console.print("[yellow]Cancelled — no overrides written.[/yellow]")
        return False

    # Selective write under model.opencode / effort.opencode keys — same
    # contract as the Claude path. Cleared efforts (None) for non-reasoning
    # models emit {"effort": {"opencode": None}} so a prior reasoning-model
    # effort override is removed from the store.
    baseline = {agent: {"model": baseline_models[agent], "effort": baseline_efforts[agent]} for agent in agents}
    payload = build_opencode_override_payload(baseline, selections)
    if not payload:
        # Nothing changed — leave the override store (and OpenCode's rendered
        # agents) untouched. Returning True here is correct: the wizard ran
        # successfully, it just had nothing to write.
        _console.print("[green]No changes — overrides untouched.[/green]")
        return True
    write_override_store(home, payload)

    # Re-render OpenCode's installed loop agents with the fresh overrides.
    # ``re_render_for_agent_clis`` writes only the rendered-agent files and
    # leaves ``~/.ai-harness/installed.json`` untouched — same scoped
    # refresh as the Claude path uses.
    try:
        re_render_for_agent_clis([AgentCli.OPENCODE], home=home)
    except (OSError, ValueError) as exc:
        _console.print(f"[red]Failed to re-render OpenCode agents: {exc}[/red]")
        return False

    _console.print("[green]Overrides written and OpenCode agents re-rendered.[/green]")
    return True


def run_wizard(cli: AgentCli, *, home: Path) -> bool:
    """Run the set-models wizard for *cli*; return True if overrides were written.

    Supports Claude and OpenCode. Generic and Copilot are not wizard
    targets at all (the wizard command rejects them up front).
    """
    if _console.is_terminal:
        _console.clear()
    if cli == AgentCli.CLAUDE:
        return run_claude_wizard(home=home)
    if cli == AgentCli.OPENCODE:
        return run_opencode_wizard(home=home)
    raise NotImplementedError(
        f"set-models for {cli.value!r} is not implemented in this slice",
    )


# ---------------------------------------------------------------------------
# Non-TTY guard — `ai-harness set-models -o claude` without a TTY
# ---------------------------------------------------------------------------


def run_wizard_or_bail(cli: AgentCli, *, home: Path) -> bool:
    """Run the wizard, but bail with a clear error if the prerequisites are missing.

    Two distinct pre-flight checks fire BEFORE the wizard itself:

    1. **OpenCode binary present** (only when ``cli`` is
       :class:`AgentCli.OPENCODE`). There is no point asking the user
       to drive a TTY when their machine is missing the binary the
       wizard needs to call. Surfacing the install/configure guidance
       here — instead of inside ``run_opencode_wizard`` after the TTY
       check — means the absent-OpenCode path is reachable from
       non-TTY environments like e2e sandboxes and CI. The wizard
       itself repeats the check, which is intentional: calling
       ``run_opencode_wizard`` directly (unit tests) still gets the
       same guidance.
    2. **TTY present**. The TUI needs a TTY to drive questionary's
       readline-style prompts. A non-TTY (e.g. CI, a piped
       subprocess, CliRunner) is a clear user-error path that should
       error rather than hang waiting for stdin that will never come.
    """
    if cli == AgentCli.OPENCODE:
        binary = _resolve_opencode_binary()
        if binary is None:
            _console.print(
                "[red]OpenCode is not installed (no `opencode` binary on PATH). "
                "Install OpenCode and run `opencode auth login` so the wizard "
                "can list the models your machine is authenticated for.[/red]"
            )
            return False

    if not sys.stdin.isatty():
        _console.print(
            "[red]set-models requires a TTY (interactive terminal). "
            "Run it directly in your shell, not via a pipe or non-interactive runner.[/red]"
        )
        return False
    return run_wizard(cli, home=home)
