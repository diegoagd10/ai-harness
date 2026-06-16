"""Interactive multi-select wizards for install and uninstall commands.

Hides: questionary invocation, agent display order, pre-selection rules,
header/footer text, and the answer-to-result translation.  Exposes only
two narrow functions + two sentinel types.
"""

from __future__ import annotations

from dataclasses import dataclass

import questionary

from ai_harness.artifacts.registry import AGENTS

# ---- shared UI text ----

_FOOTER = "(↑↓/j k move  ·  space toggle  ·  enter confirm  ·  esc cancel)"

# ---- sentinels ----

@dataclass(frozen=True)
class Empty:
    """User confirmed with zero selections."""


@dataclass(frozen=True)
class Cancelled:
    """User pressed Escape."""


# ----------------------------------------------------------------- helpers ---

def _run_checkbox(
    title: str,
    choices: list[questionary.Choice],
) -> list[str] | Empty | Cancelled:
    """Invoke questionary.checkbox and translate its raw result.

    Hides: the questionary call, the footer instruction, and the
    ``None`` / ``[]`` / ``list[str]`` → sentinel translation.
    """
    result: list[str] | None = questionary.checkbox(
        title,
        choices=choices,
        instruction=_FOOTER,
    ).ask()

    if result is None:
        return Cancelled()
    if len(result) == 0:
        return Empty()
    return result


# ------------------------------------------------------------------ select ---

def select_install_targets(
    currently_installed: set[str],
) -> list[str] | Empty | Cancelled:
    """Show the install checkbox wizard.

    Displays all three agents in fixed order.  Pre-selects agents that are
    *not* in *currently_installed*.
    """
    choices: list[questionary.Choice] = []
    for agent_id, label in AGENTS:
        choices.append(
            questionary.Choice(
                title=label,
                value=agent_id,
                checked=agent_id not in currently_installed,
            )
        )

    return _run_checkbox(
        "Select where to install ai-harness artifacts",
        choices,
    )


def select_uninstall_targets(
    currently_installed: set[str],
) -> list[str] | Empty | Cancelled:
    """Show the uninstall checkbox wizard.

    Displays only agents present in *currently_installed*, in fixed order.
    Nothing is pre-selected.
    """
    choices: list[questionary.Choice] = []
    for agent_id, label in AGENTS:
        if agent_id in currently_installed:
            choices.append(
                questionary.Choice(
                    title=label,
                    value=agent_id,
                    checked=False,
                )
            )

    return _run_checkbox("Select agents to remove", choices)
