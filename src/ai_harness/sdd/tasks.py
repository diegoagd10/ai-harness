"""Task-checkbox parsing for tasks.md."""

from __future__ import annotations

import re

from .models import TaskProgress

# Matches a markdown task line: a bullet (-, *) or ordered marker (1. / 1))
# followed by a [ ], [x], or [X] checkbox. The captured group is the checkbox
# character; lines that do not match are ignored. re.ASCII keeps \s/\d ASCII-only
# to match Go's RE2 engine (e.g. non-ASCII digits must not count as markers).
_TASK_CHECKBOX = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+\[([ xX])\]", re.ASCII)


def count_task_progress(tasks_path: str) -> TaskProgress:
    """Parse tasks.md and tally its checkbox tasks. An empty path (no tasks.md)
    yields a zero TaskProgress. all_complete requires at least one task and zero
    pending."""
    if not tasks_path:
        return TaskProgress()

    # errors="replace" mirrors Go's lossy string(bytes): invalid UTF-8 never
    # raises, the change still resolves, and the CLI exits 0 as Go does.
    with open(tasks_path, encoding="utf-8", errors="replace") as handle:
        content = handle.read()

    progress = TaskProgress()
    for line in content.split("\n"):
        match = _TASK_CHECKBOX.match(line)
        if match is None:
            continue
        progress.total += 1
        if _is_checked_mark(match.group(1)):
            progress.completed += 1
        else:
            progress.pending += 1
    progress.all_complete = progress.total > 0 and progress.pending == 0
    return progress


def _is_checked_mark(mark: str) -> bool:
    return mark in ("x", "X")
