"""Unit tests for marker-only selection rendering in the install wizard.

Targets ``MarkerOnlyControl`` directly: it must re-class the SELECTED
glyph under a dedicated style class while keeping the title neutral,
without touching unselected or focused-row tokens inherited from
``InquirerControl``.
"""

from __future__ import annotations

from questionary.prompts.common import Choice


def _make_control(choices: list[Choice]):
    from ai_harness.artifacts.wizard import MarkerOnlyControl

    return MarkerOnlyControl(choices=choices)


def _tokens_for_title(tokens: list[tuple[str, str]], title: str) -> list[tuple[str, str]]:
    """Return all tokens whose text contains *title*."""
    return [tok for tok in tokens if title in tok[1]]


# ==================================================== 3.1-3.3 RED tests ===


def test_selected_glyph_uses_dedicated_class() -> None:
    """The selected marker glyph is re-classed to class:checkbox-selected."""
    ic = _make_control([Choice(title="OpenCode", value="opencode")])
    ic.selected_options = ["opencode"]

    tokens = ic._get_choice_tokens()
    glyph_tokens = [tok for tok in tokens if "●" in tok[1]]

    assert len(glyph_tokens) == 1
    assert glyph_tokens[0][0] == "class:checkbox-selected"


def test_selected_title_stays_neutral() -> None:
    """The selected row's title is class:text, NOT class:selected."""
    ic = _make_control([Choice(title="OpenCode", value="opencode")])
    ic.selected_options = ["opencode"]

    tokens = ic._get_choice_tokens()
    title_tokens = _tokens_for_title(tokens, "OpenCode")

    assert len(title_tokens) == 1
    assert title_tokens[0][0] == "class:text"
    assert title_tokens[0][0] != "class:selected"


def test_unselected_and_focused_tokens_unchanged() -> None:
    """Unselected marker/title and the focused pointer are untouched."""
    choices = [
        Choice(title="OpenCode", value="opencode"),
        Choice(title="Claude Code", value="claude"),
    ]
    ic = _make_control(choices)
    # Nothing selected; pointed_at defaults to the first choice (index 0).
    ic.pointed_at = 0

    tokens = ic._get_choice_tokens()

    # Unselected glyph stays class:text with the unselected indicator.
    unselected_glyph_tokens = [tok for tok in tokens if "○" in tok[1]]
    assert len(unselected_glyph_tokens) == 2
    for tok in unselected_glyph_tokens:
        assert tok[0] == "class:text"

    # Focused row's title (index 0, unselected) renders as class:highlighted,
    # matching the base InquirerControl behavior — untouched by our override.
    focused_title_tokens = _tokens_for_title(tokens, "OpenCode")
    assert len(focused_title_tokens) == 1
    assert focused_title_tokens[0][0] == "class:highlighted"

    # The focus pointer glyph is still emitted under class:pointer.
    pointer_tokens = [tok for tok in tokens if tok[0] == "class:pointer"]
    assert len(pointer_tokens) == 1
    assert "»" in pointer_tokens[0][1]
