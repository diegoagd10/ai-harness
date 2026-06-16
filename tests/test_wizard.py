"""Unit tests for wizard.py — install and uninstall checkbox wizards."""

from __future__ import annotations

import pytest

from ai_harness.artifacts.wizard import (
    Cancelled,
    Empty,
    select_install_targets,
    select_uninstall_targets,
)


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
        assert choices[i].checked is True, (
            f"{expected_title} must be pre-selected on fresh install"
        )

    assert result == ["opencode"]


@pytest.mark.questionary_return(["opencode"])
def test_wizard_passes_key_hint_footer(monkeypatch_questionary) -> None:
    """The footer key hints are passed as ``instruction`` to questionary.checkbox."""
    select_install_targets(set())

    _, kwargs = monkeypatch_questionary.calls[0]
    assert "instruction" in kwargs, (
        "questionary.checkbox must receive the instruction parameter"
    )
    instruction = kwargs["instruction"]
    assert "↑↓" in instruction or "j k" in instruction, (
        f"Footer key hints missing from instruction: {instruction!r}"
    )
    assert "space" in instruction.lower() or "toggle" in instruction, (
        f"Toggle hint missing from instruction: {instruction!r}"
    )
    assert "enter" in instruction.lower(), (
        f"Enter hint missing from instruction: {instruction!r}"
    )
    assert "esc" in instruction.lower(), (
        f"Escape hint missing from instruction: {instruction!r}"
    )


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
