"""Interactive multi-select wizards for install and uninstall commands.

Hides: questionary invocation, agent display order, pre-selection rules,
header/footer text, and the answer-to-result translation.  Exposes only
two narrow functions + two sentinel types.
"""

from __future__ import annotations

from dataclasses import dataclass

import questionary
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from questionary.constants import INDICATOR_SELECTED
from questionary.prompts.common import InquirerControl, create_inquirer_layout
from questionary.question import Question
from questionary.styles import merge_styles_default

from ai_harness.artifacts.registry import AGENTS

# ---- shared UI text ----

_FOOTER = "(↑↓/j k move  ·  space toggle  ·  enter confirm  ·  esc cancel)"

# ---- style ----

_WIZARD_STYLE = merge_styles_default(
    [
        Style(
            [
                ("checkbox-selected", "fg:#00FF00"),  # selected marker glyph
                ("selected", ""),  # no full-row highlight on selected titles
            ]
        )
    ]
)

# ---- sentinels ----

@dataclass(frozen=True)
class Empty:
    """User confirmed with zero selections."""


@dataclass(frozen=True)
class Cancelled:
    """User pressed Escape."""


# ----------------------------------------------------------------- helpers ---

class MarkerOnlyControl(InquirerControl):
    """An ``InquirerControl`` whose selected rows color ONLY the marker.

    questionary's base ``_get_choice_tokens`` emits both the selected glyph
    (``●``) and the title under the SAME ``class:selected`` token, so no
    style string can color one without the other (see ``common.py``
    ``_get_choice_tokens``). This subclass reuses ``super()``'s tokens and
    re-classes a selected row's glyph to ``class:checkbox-selected`` and its
    title to ``class:text``, leaving unselected and focused-row tokens
    untouched.
    """

    _SELECTED_GLYPH_CLASS = "class:checkbox-selected"
    _SELECTED_TITLE_CLASS = "class:text"

    def _get_choice_tokens(self) -> list[tuple[str, str]]:
        tokens = super()._get_choice_tokens()
        return [self._reclass_selected_token(token) for token in tokens]

    def _reclass_selected_token(self, token: tuple[str, str]) -> tuple[str, str]:
        style_class, text = token
        if style_class != "class:selected":
            return token
        if text.strip() == INDICATOR_SELECTED:
            return (self._SELECTED_GLYPH_CLASS, text)
        return (self._SELECTED_TITLE_CLASS, text)


def _checkbox_bindings(ic: InquirerControl) -> KeyBindings:
    """Build key bindings for a checkbox prompt over *ic*.

    Clones questionary's checkbox defaults (abort, toggle, arrow/j-k/emacs
    movement, confirm, catch-all) and adds an eager
    ``Keys.Escape`` binding that exits the application with ``result=None``
    so the ``None`` → ``Cancelled()`` translation in :func:`_run_checkbox`
    fires.  questionary's own ``checkbox()`` builds bindings internally and
    never accepts external ones, so this is the only way to make Escape
    cancel the prompt.
    """
    bindings = KeyBindings()

    @bindings.add(Keys.Escape, eager=True)
    def _cancel(event: object) -> None:
        event.app.exit(result=None)  # type: ignore[attr-defined]

    @bindings.add(Keys.ControlQ, eager=True)
    @bindings.add(Keys.ControlC, eager=True)
    def _abort(event: object) -> None:
        event.app.exit(  # type: ignore[attr-defined]
            exception=KeyboardInterrupt, style="class:aborting"
        )

    def _selected_values() -> list[object]:
        return [c.value for c in ic.get_selected_values()]

    @bindings.add(" ", eager=True)
    def _toggle(_event: object) -> None:
        pointed_choice = ic.get_pointed_at().value
        if pointed_choice in ic.selected_options:
            ic.selected_options.remove(pointed_choice)
        else:
            ic.selected_options.append(pointed_choice)

    def _move_down(_event: object) -> None:
        ic.select_next()
        while not ic.is_selection_valid():
            ic.select_next()

    def _move_up(_event: object) -> None:
        ic.select_previous()
        while not ic.is_selection_valid():
            ic.select_previous()

    bindings.add(Keys.Down, eager=True)(_move_down)
    bindings.add(Keys.Up, eager=True)(_move_up)
    bindings.add("j", eager=True)(_move_down)
    bindings.add("k", eager=True)(_move_up)
    bindings.add(Keys.ControlN, eager=True)(_move_down)
    bindings.add(Keys.ControlP, eager=True)(_move_up)

    @bindings.add(Keys.ControlM, eager=True)
    def _confirm(event: object) -> None:
        ic.is_answered = True
        event.app.exit(result=_selected_values())  # type: ignore[attr-defined]

    @bindings.add(Keys.Any)
    def _other(_event: object) -> None:
        """Disallow inserting other text."""

    return bindings


def _build_question(
    title: str,
    choices: list[questionary.Choice],
) -> questionary.Question:
    """Build a checkbox-style ``Question`` with marker-only rendering and ESC.

    Owns prompt construction end to end: a :class:`MarkerOnlyControl` for
    selection rendering, :func:`_checkbox_bindings` for navigation/ESC, and
    ``_WIZARD_STYLE`` for the dedicated marker color. Mirrors
    ``questionary.checkbox`` (which builds its own incompatible
    ``Application`` internally and cannot be handed external bindings).
    """
    ic = MarkerOnlyControl(choices=choices)

    def _get_prompt_tokens() -> list[tuple[str, str]]:
        return [
            ("class:qmark", "?"),
            ("class:question", f" {title} "),
            ("class:instruction", _FOOTER),
        ]

    layout = create_inquirer_layout(ic, _get_prompt_tokens)
    bindings = _checkbox_bindings(ic)

    return Question(
        Application(
            layout=layout,
            key_bindings=bindings,
            style=_WIZARD_STYLE,
        )
    )


def _run_checkbox(question: questionary.Question) -> list[str] | Empty | Cancelled:
    """Run *question* and translate its raw result.

    Hides: the ``.ask()`` call and the
    ``None`` / ``[]`` / ``list[str]`` → sentinel translation.
    """
    result: list[str] | None = question.ask()

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

    question = _build_question(
        "Select where to install ai-harness artifacts",
        choices,
    )
    return _run_checkbox(question)


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

    question = _build_question("Select agents to remove", choices)
    return _run_checkbox(question)
