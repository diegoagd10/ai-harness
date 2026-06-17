"""Unit tests for the shared ``metadata_to_frontmatter`` serializer.

Spec: "Per-Provider Metadata" + the shared serializer decision in design.md.
The serializer emits a ``model:`` line ONLY when the metadata dict carries a
``model`` key (Claude metadata always has it; Copilot never does), so the
divergence is a property of the data rather than a caller-side flag.
"""

from __future__ import annotations

from ai_harness.artifacts.installers.frontmatter import metadata_to_frontmatter


def test_claude_metadata_emits_model_line() -> None:
    """A Claude-style entry (with ``model``) must serialize the ``model:`` line.

    Spec: "Metadata separated from prompt body" — Claude tools + model.
    """
    meta = {
        "name": "jd-judge-a",
        "description": "blind judge A",
        "tools": ["Read", "Bash"],
        "model": "opus",
    }

    result = metadata_to_frontmatter(meta)

    assert result == (
        "---\n"
        "name: jd-judge-a\n"
        "description: blind judge A\n"
        "tools: [Read, Bash]\n"
        "model: opus\n"
        "---"
    )


def test_copilot_metadata_omits_model_line() -> None:
    """A Copilot-style entry (no ``model``) must NOT emit a ``model:`` line."""
    meta = {
        "name": "jd-judge-a",
        "description": "blind judge A",
        "tools": ["View", "Bash", "Glob", "Grep", "Task"],
    }

    result = metadata_to_frontmatter(meta)

    assert result == (
        "---\n"
        "name: jd-judge-a\n"
        "description: blind judge A\n"
        "tools: [View, Bash, Glob, Grep, Task]\n"
        "---"
    )
    assert "model:" not in result


def test_scalar_tools_value_serialized_as_is() -> None:
    """When ``tools`` is a scalar (not a list), it is rendered verbatim."""
    meta = {
        "name": "x",
        "description": "d",
        "tools": "Read",
    }

    result = metadata_to_frontmatter(meta)

    assert "tools: [Read]" in result
