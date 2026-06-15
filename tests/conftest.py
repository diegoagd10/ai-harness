"""Shared fixtures and OpenSpec workspace seeders for the SDD CLI tests.

Ports the helpers from cli.bak/tests/conftest.py, omitting the Go oracle
fixture and sdd-continue helpers (both out of scope for this slice).
"""

from __future__ import annotations

from pathlib import Path


def write_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def seed_ready_change(root: Path, name: str, tasks: str) -> Path:
    """Create a change whose four core artifacts are all 'done' (Go seedReadyChange)."""
    change_root = root / "openspec" / "changes" / name
    write_file(change_root / "proposal.md", "# Proposal\n")
    write_file(change_root / "specs" / "auth" / "spec.md", "# Auth Spec\n")
    write_file(change_root / "design.md", "# Design\n")
    write_file(change_root / "tasks.md", tasks)
    return change_root
