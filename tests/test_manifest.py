"""Tests for ComposedFileArtifact with frontmatter_text field.

Spec scenario: "ClaudeInstaller composes frontmatter + body"
  - GIVEN Claude metadata + canonical body for agent X
  - THEN output is Markdown: ``---\\nname: X\\n...\\n---\\n``
    followed by canonical body byte-for-byte

frontmatter_text allows installers to embed metadata strings directly
instead of reading from file sources.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.artifacts.manifest import ComposedFileArtifact


# ── 2.1 RED: frontmatter_text field ─────────────────────────────────────────


def test_composed_file_artifact_accepts_frontmatter_text(tmp_path: Path) -> None:
    """Constructing a ComposedFileArtifact with frontmatter_text must
    succeed (no TypeError) and the field value must be stored.

    Precondition (RED): frontmatter_text does NOT exist as a parameter
    on ComposedFileArtifact — this call will raise TypeError.

    Postcondition (GREEN): after adding the field + making
    frontmatter_source optional, this constructs cleanly.
    """
    body = tmp_path / "body.md"
    body.write_text("# Agent body\n", encoding="utf-8")

    artifact = ComposedFileArtifact(
        frontmatter_text="---\nname: test-agent\ntools: [Read]\n---\n",
        body_source=body,
        target_relative=Path(".claude/agents/test-agent.md"),
    )

    assert artifact.frontmatter_text == (
        "---\nname: test-agent\ntools: [Read]\n---\n"
    )
    assert artifact.body_source == body
    assert artifact.target_relative == Path(".claude/agents/test-agent.md")


def test_composed_artifact_frontmatter_source_is_optional(tmp_path: Path) -> None:
    """When frontmatter_text is provided, frontmatter_source may be None.

    Precondition (RED): ComposedFileArtifact has a required
    frontmatter_source field that must be a Path.
    """
    body = tmp_path / "body.md"
    body.write_text("# body\n", encoding="utf-8")

    artifact = ComposedFileArtifact(
        frontmatter_text="---\nname: agent\n---\n",
        body_source=body,
        target_relative=Path(".copilot/agents/agent.md"),
    )

    assert artifact.frontmatter_text == "---\nname: agent\n---\n"
    # frontmatter_source defaults to None when not given
    assert artifact.frontmatter_source is None


# ── Phase 1.1 RED: ComposedFileArtifact rejects without frontmatter_text ─────


def test_composed_rejects_without_frontmatter_text(tmp_path: Path) -> None:
    """ComposedFileArtifact MUST require frontmatter_text — construction
    without it raises TypeError.

    Spec: "Deterministic Claude composed agent"
      - GIVEN metadata for sdd-explore and body B
      - THEN frontmatter_text is mandatory for composed output
    """
    body = tmp_path / "body.md"
    body.write_text("# body\n", encoding="utf-8")

    with pytest.raises(TypeError):
        ComposedFileArtifact(
            body_source=body,
            target_relative=Path(".claude/agents/test.md"),
        )


# ── 2.3 RED: _prepare_composed_content handles frontmatter_text ──────────────


def test_prepare_composed_content_uses_frontmatter_text(tmp_path: Path) -> None:
    """_prepare_composed_content must use frontmatter_text directly
    when it is not None, bypassing file read.

    Precondition (RED): _prepare_composed_content only reads
    frontmatter_source from disk — passing frontmatter_text instead
    will either crash or produce wrong output.
    """
    from ai_harness.artifacts.installer import _prepare_composed_content

    body = tmp_path / "body.md"
    body.write_text("# Canonical prompt body\n", encoding="utf-8")

    artifact = ComposedFileArtifact(
        frontmatter_text="---\nname: my-agent\n---",
        body_source=body,
        target_relative=Path(".claude/agents/my-agent.md"),
    )

    content = _prepare_composed_content(artifact, tmp_path)
    assert content == "---\nname: my-agent\n---\n---\n# Canonical prompt body\n"


def test_prepare_composed_content_ignores_frontmatter_source(
    tmp_path: Path,
) -> None:
    """_prepare_composed_content uses frontmatter_text directly even when
    frontmatter_source is also set — the file is never read."""
    from ai_harness.artifacts.installer import _prepare_composed_content

    fm_file = tmp_path / "fm.md"
    fm_file.write_text("---\nname: stale\ntools: [BadTool]\n", encoding="utf-8")
    body = tmp_path / "body.md"
    body.write_text("# sdd-verify body\n", encoding="utf-8")

    artifact = ComposedFileArtifact(
        frontmatter_text="---\nname: sdd-verify\ndescription: verify\ntools: [Read, Bash]\n---",
        frontmatter_source=fm_file,
        body_source=body,
        target_relative=Path(".claude/agents/sdd-verify.md"),
    )

    content = _prepare_composed_content(artifact, tmp_path)
    # Must use frontmatter_text, NOT frontmatter_source from the file
    assert "---\nname: sdd-verify\ndescription: verify\ntools: [Read, Bash]\n---" in content
    assert "# sdd-verify body\n" in content
