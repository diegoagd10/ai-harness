"""Resolve the canonical per-task commit format from ``CODING_STANDARDS.md``.

The resolver reads ``CODING_STANDARDS.md`` at the repo root, locates the
``## Commits`` heading, and returns the first non-blank, non-HTML-comment,
non-blockquote line of its body with a single pair of surrounding backticks
stripped. The orchestrator prompt inlines the returned string into the
implementor delegation block under the ``commit-format:`` directive.

Three failure modes surface :class:`CommitFormatError` with a canonical,
named-artefact message so the human owner of ``CODING_STANDARDS.md`` can
fix the exact problem:

- file missing -> ``CODING_STANDARDS.md not found at <absolute path>``
- heading missing -> ``## Commits section missing in CODING_STANDARDS.md``
- body empty -> ``## Commits body is empty``
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = ["CommitFormatError", "resolve_commit_format"]


_HEADING_PATTERN = re.compile(r"^## Commits\s*$")
_BLOCKQUOTE_PATTERN = re.compile(r"^\s*>\s?")
_HTML_COMMENT_PATTERN = re.compile(r"^\s*<!--.*-->\s*$")


class CommitFormatError(ValueError):
    """Raised when ``CODING_STANDARDS.md`` cannot be parsed into a usable commit format.

    Carries the exact human-facing message that the orchestrator must surface
    verbatim in its ``status: blocked`` envelope so the validator's
    downstream grep can match on the canonical string.
    """


def resolve_commit_format(repo_root: Path) -> str:
    """Return the canonical per-task commit format string from *repo_root*.

    Reads ``CODING_STANDARDS.md`` at *repo_root*, locates the
    ``## Commits`` heading, and returns the first non-blank,
    non-HTML-comment line of its body with surrounding backticks stripped.

    Raises :class:`CommitFormatError` with one of the canonical messages
    when the file is missing, the heading is absent, or the body is empty.
    """
    standards_path = repo_root / "CODING_STANDARDS.md"
    if not standards_path.is_file():
        raise CommitFormatError(f"CODING_STANDARDS.md not found at {standards_path}")

    text = standards_path.read_text(encoding="utf-8")
    body = _select_commits_body(text)
    if body is None:
        raise CommitFormatError("## Commits section missing in CODING_STANDARDS.md")

    selected = _select_format_line(body)
    if selected is None:
        raise CommitFormatError("## Commits body is empty")

    return _strip_surrounding_backticks(selected)


def _select_commits_body(text: str) -> str | None:
    """Return the body lines under the first ``## Commits`` heading.

    The body runs until the next ``## …`` heading or end of file. Returns
    ``None`` when the heading is absent.
    """
    lines = text.splitlines()
    heading_idx = next((i for i, line in enumerate(lines) if _HEADING_PATTERN.match(line)), -1)
    if heading_idx == -1:
        return None

    end_idx = len(lines)
    for j in range(heading_idx + 1, len(lines)):
        line = lines[j]
        if line.startswith("## ") and not line.startswith("## #"):
            end_idx = j
            break
    return "\n".join(lines[heading_idx + 1 : end_idx])


def _select_format_line(body: str) -> str | None:
    """Return the first surviving body line under the ``## Commits`` heading.

    Skips blank lines, HTML-comment lines (``<!-- … -->``), and blockquote
    continuations (``>``). Strips a single pair of surrounding backticks if
    present. Returns ``None`` when no line survives.
    """
    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if _HTML_COMMENT_PATTERN.match(stripped):
            continue
        if _BLOCKQUOTE_PATTERN.match(stripped):
            continue
        return _strip_surrounding_backticks(stripped)
    return None


def _strip_surrounding_backticks(line: str) -> str:
    """Strip a single pair of surrounding backticks from *line* if present."""
    if len(line) >= 2 and line.startswith("`") and line.endswith("`"):
        return line[1:-1]
    return line
