# pylint: disable=duplicate-code
"""Unit tests for the commit-format resolver.

Locks the canonical messages and the line-selection rule from
``specs/implementor-reads-commit-format/resolve-commit-format-from-standards.md``
against the public ``resolve_commit_format`` seam. The resolver is the read
side of the orchestrator-injects pattern (design §Deep modules); these tests
pin the surface the orchestrator prompt depends on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.modules.commit import CommitFormatError, resolve_commit_format


def _write_standards(tmp_path: Path, body: str) -> Path:
    """Write a CODING_STANDARDS.md containing *body* (everything under the file heading)."""
    file_path = tmp_path / "CODING_STANDARDS.md"
    file_path.write_text(body, encoding="utf-8")
    return file_path


def test_resolve_commit_format_returns_first_non_blank_line_with_backticks_stripped(
    tmp_path: Path,
) -> None:
    """Happy path — `[{change_name}][{task_id}] {slug}` is returned without surrounding backticks."""
    _write_standards(
        tmp_path, "# Coding Standards\n\n## Commits\n\n`[{change_name}][{task_id}] {slug}`\n\n## Quality gates\n"
    )

    assert resolve_commit_format(tmp_path) == "[{change_name}][{task_id}] {slug}"


def test_resolve_commit_format_raises_when_standards_file_missing(tmp_path: Path) -> None:
    """Subtask 1.2 — absent CODING_STANDARDS.md surfaces the canonical path-named message."""
    expected_path = tmp_path / "CODING_STANDARDS.md"

    with pytest.raises(CommitFormatError) as exc_info:
        resolve_commit_format(tmp_path)

    assert str(exc_info.value) == f"CODING_STANDARDS.md not found at {expected_path}"


def test_resolve_commit_format_raises_when_commits_heading_missing(tmp_path: Path) -> None:
    """Subtask 1.3 — file exists but lacks the `## Commits` heading."""
    _write_standards(tmp_path, "# Coding Standards\n\n## Style\n\n- pep8\n")

    with pytest.raises(CommitFormatError) as exc_info:
        resolve_commit_format(tmp_path)

    assert str(exc_info.value) == "## Commits section missing in CODING_STANDARDS.md"


def test_resolve_commit_format_raises_when_commits_body_is_empty(tmp_path: Path) -> None:
    """Subtask 1.4 — heading present but no non-comment, non-blank body line."""
    _write_standards(tmp_path, "# Coding Standards\n\n## Commits\n\n## Quality gates\n")

    with pytest.raises(CommitFormatError) as exc_info:
        resolve_commit_format(tmp_path)

    assert str(exc_info.value) == "## Commits body is empty"


def test_resolve_commit_format_skips_comments_blanks_and_blockquotes(tmp_path: Path) -> None:
    """Subtask 1.5 — comment, blank, and blockquote lines precede the literal format line."""
    body = (
        "# Coding Standards\n"
        "\n"
        "## Commits\n"
        "\n"
        "<!-- experimental: try conventional commits later -->\n"
        "\n"
        "> legacy note: see README\n"
        "\n"
        "`[{change_name}][{task_id}] {slug}`\n"
        "\n"
        "## Quality gates\n"
    )
    _write_standards(tmp_path, body)

    assert resolve_commit_format(tmp_path) == "[{change_name}][{task_id}] {slug}"
