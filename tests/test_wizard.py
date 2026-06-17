"""Unit tests for wizard.py — install and uninstall checkbox wizards."""

from __future__ import annotations

import pytest
import questionary
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import PipeInput
from prompt_toolkit.keys import Keys
from prompt_toolkit.output import DummyOutput
from questionary.constants import INDICATOR_SELECTED
from questionary.prompts.common import Choice, InquirerControl, create_inquirer_layout

from ai_harness.artifacts.wizard import (
    Cancelled,
    Empty,
    select_install_targets,
    select_uninstall_targets,
)

# ================================================== 1.3 upgrade canary ===


def test_questionary_internals_contract_holds() -> None:
    """Upgrade canary: fails loudly if questionary 2.1.1 internals shift.

    ``MarkerOnlyControl`` and ``_checkbox_bindings`` depend on these
    semi-private internals.  If a questionary upgrade renames/removes them,
    this test fails BEFORE the real rendering/binding tests give a
    confusing AttributeError deep inside prompt_toolkit.
    """
    assert hasattr(InquirerControl, "_get_choice_tokens")
    assert callable(create_inquirer_layout)
    assert INDICATOR_SELECTED == "●"


# ===================================================== 2.1-2.2 RED/GREEN ===


def _make_inquirer_control() -> InquirerControl:
    return InquirerControl(choices=[Choice(title="A", value="a")])


def test_checkbox_bindings_includes_escape() -> None:
    """ESC must be bound so the prompt can be cancelled."""
    from ai_harness.artifacts.wizard import _checkbox_bindings

    ic = _make_inquirer_control()
    bindings = _checkbox_bindings(ic)

    matches = bindings.get_bindings_for_keys((Keys.Escape,))
    assert len(matches) > 0


def test_checkbox_bindings_preserves_defaults() -> None:
    """Existing checkbox defaults (abort/toggle/confirm/move) stay bound."""
    from ai_harness.artifacts.wizard import _checkbox_bindings

    ic = _make_inquirer_control()
    bindings = _checkbox_bindings(ic)

    for keys in (
        (Keys.ControlC,),
        (" ",),
        (Keys.ControlM,),
        (Keys.Up,),
        (Keys.Down,),
    ):
        matches = bindings.get_bindings_for_keys(keys)
        assert len(matches) > 0, f"missing default binding for {keys!r}"


# ========================================================== 4.1 RED/GREEN ===


def test_build_question_returns_questionary_question() -> None:
    """``_build_question`` wraps an Application using our control/bindings/style."""
    from prompt_toolkit.application import Application

    from ai_harness.artifacts.wizard import (
        _WIZARD_STYLE,
        MarkerOnlyControl,
        _build_question,
    )

    choices = [Choice(title="OpenCode", value="opencode")]
    question = _build_question("Select agents", choices)

    assert isinstance(question, questionary.Question)
    app = question.application
    assert isinstance(app, Application)

    # The control feeding the layout is our MarkerOnlyControl, not the base.
    controls = list(app.layout.find_all_controls())
    marker_controls = [c for c in controls if isinstance(c, MarkerOnlyControl)]
    assert len(marker_controls) == 1

    assert app.style == _WIZARD_STYLE
    # ESC must be bound on the application actually used.
    matches = app.key_bindings.get_bindings_for_keys((Keys.Escape,))
    assert len(matches) > 0


# ===================================================== 5.1-5.3 RED/GREEN ===


def _ask_via_pipe(pipe_input: PipeInput, sent: str, title: str = "Select agents"):
    """Build a real checkbox question, feed *sent* through *pipe_input*, run
    it through the full ``_build_question`` -> ``_run_checkbox`` pipeline."""
    from ai_harness.artifacts.wizard import _build_question, _run_checkbox

    choices = [Choice(title="OpenCode", value="opencode")]
    with create_app_session(input=pipe_input, output=DummyOutput()):
        pipe_input.send_text(sent)
        question = _build_question(title, choices)
        return _run_checkbox(question)


def test_escape_via_pipe_cancels(pipe_input: PipeInput) -> None:
    """Real ESC key event (via PipeInput) translates to Cancelled()."""
    result = _ask_via_pipe(pipe_input, "\x1b")
    assert isinstance(result, Cancelled)


def test_space_then_enter_via_pipe_returns_selection(pipe_input: PipeInput) -> None:
    """Real space (toggle) + Enter (confirm) returns the toggled choice."""
    result = _ask_via_pipe(pipe_input, " \r")
    assert result == ["opencode"]


def test_enter_only_via_pipe_returns_empty(pipe_input: PipeInput) -> None:
    """Real Enter with no prior toggle translates to Empty()."""
    result = _ask_via_pipe(pipe_input, "\r")
    assert isinstance(result, Empty)


# ============================================================= 3.1 RED ===


@pytest.mark.questionary_return(["claude"])
def test_select_install_shows_three(monkeypatch_questionary) -> None:
    """The install wizard displays all three agents in fixed order."""
    result = select_install_targets({"opencode"})

    assert len(monkeypatch_questionary.calls) == 1
    question, kwargs = monkeypatch_questionary.calls[0]
    assert "install" in question.lower()

    choices = kwargs["choices"]
    assert len(choices) == 3
    assert choices[0].title == "OpenCode"
    assert choices[1].title == "Claude Code"
    assert choices[2].title == "Copilot CLI"

    assert result == ["claude"]


@pytest.mark.questionary_return(["claude", "copilot"])
def test_select_install_preselects_non_installed(monkeypatch_questionary) -> None:
    """Pre-selects agents NOT in the installed set."""
    result = select_install_targets({"opencode"})

    _, kwargs = monkeypatch_questionary.calls[0]
    choices = kwargs["choices"]

    # OpenCode is installed → NOT pre-selected
    assert choices[0].title == "OpenCode"
    assert choices[0].checked is False

    # Claude Code is NOT installed → pre-selected
    assert choices[1].title == "Claude Code"
    assert choices[1].checked is True

    # Copilot CLI is NOT installed → pre-selected
    assert choices[2].title == "Copilot CLI"
    assert choices[2].checked is True

    assert result == ["claude", "copilot"]


@pytest.mark.questionary_return(["opencode"])
def test_select_install_targets_fresh_install_preselects_all_three(
    monkeypatch_questionary,
) -> None:
    """Fresh install (empty installed set) pre-selects all three agents."""
    result = select_install_targets(set())

    _, kwargs = monkeypatch_questionary.calls[0]
    choices = kwargs["choices"]

    assert len(choices) == 3
    for i, expected_title in enumerate(("OpenCode", "Claude Code", "Copilot CLI")):
        assert choices[i].title == expected_title
        assert choices[i].checked is True, f"{expected_title} must be pre-selected on fresh install"

    assert result == ["opencode"]


@pytest.mark.questionary_return(["opencode"])
def test_wizard_passes_key_hint_footer(monkeypatch_questionary) -> None:
    """The footer key hints are passed as ``instruction`` to questionary.checkbox."""
    select_install_targets(set())

    _, kwargs = monkeypatch_questionary.calls[0]
    assert "instruction" in kwargs, "questionary.checkbox must receive the instruction parameter"
    instruction = kwargs["instruction"]
    assert "↑↓" in instruction or "j k" in instruction, f"Footer key hints missing from instruction: {instruction!r}"
    assert "space" in instruction.lower() or "toggle" in instruction, (
        f"Toggle hint missing from instruction: {instruction!r}"
    )
    assert "enter" in instruction.lower(), f"Enter hint missing from instruction: {instruction!r}"
    assert "esc" in instruction.lower(), f"Escape hint missing from instruction: {instruction!r}"


# ============================================================= 3.2 RED ===


@pytest.mark.questionary_return([])
def test_select_install_zero_returns_empty(monkeypatch_questionary) -> None:
    """Confirm with zero selections returns Empty sentinel."""
    result = select_install_targets(set())
    assert isinstance(result, Empty)


@pytest.mark.questionary_return(None)
def test_select_install_escape_returns_cancelled(monkeypatch_questionary) -> None:
    """Pressing Escape returns Cancelled sentinel."""
    result = select_install_targets(set())
    assert isinstance(result, Cancelled)


# ============================================================= 3.4 RED ===


@pytest.mark.questionary_return(["opencode"])
def test_select_uninstall_only_installed(monkeypatch_questionary) -> None:
    """Only installed agents are shown in fixed order."""
    result = select_uninstall_targets({"opencode", "claude"})

    _, kwargs = monkeypatch_questionary.calls[0]
    choices = kwargs["choices"]

    # Only OpenCode and Claude Code shown (Copilot CLI is not installed)
    assert len(choices) == 2
    assert choices[0].title == "OpenCode"
    assert choices[1].title == "Claude Code"
    assert result == ["opencode"]


@pytest.mark.questionary_return([])
def test_select_uninstall_preselects_none(monkeypatch_questionary) -> None:
    """Nothing is pre-selected in the uninstall wizard."""
    select_uninstall_targets({"opencode", "claude"})

    _, kwargs = monkeypatch_questionary.calls[0]
    for choice in kwargs["choices"]:
        assert choice.checked is False


@pytest.mark.questionary_return(None)
def test_select_uninstall_escape_cancelled(monkeypatch_questionary) -> None:
    """Escape returns Cancelled sentinel for uninstall."""
    result = select_uninstall_targets({"opencode"})
    assert isinstance(result, Cancelled)
