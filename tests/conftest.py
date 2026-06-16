"""Shared fixtures and OpenSpec workspace seeders for the SDD CLI tests.

Ports the helpers from cli.bak/tests/conftest.py, omitting the Go oracle
fixture and sdd-continue helpers (both out of scope for this slice).
"""

from __future__ import annotations

from pathlib import Path

import pytest


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


# -------------------------------------------------------------------- wizard ---


class _StubCheckbox:
    """Replaces ``questionary.checkbox`` with a configurable stub.

    Use via the ``monkeypatch_questionary`` fixture together with
    ``@pytest.mark.questionary_return(...)``:

    - ``@pytest.mark.questionary_return(["opencode"])`` — user chose items
    - ``@pytest.mark.questionary_return([])`` — user submitted empty selection
    - ``@pytest.mark.questionary_return(None)`` — user pressed Escape / cancelled
    """

    def __init__(self, return_value: object) -> None:
        self._return_value = return_value
        self.calls: list[tuple] = []

    def __call__(self, question: str, **kwargs: object) -> _StubCheckbox:
        self.calls.append((question, kwargs))
        return self

    def ask(self) -> object:
        return self._return_value


@pytest.fixture
def monkeypatch_questionary(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> _StubCheckbox:
    """Monkeypatch ``questionary.checkbox`` with a configurable stub.

    Decorate your test with ``@pytest.mark.questionary_return(...)`` to
    control what ``.ask()`` returns:

    - ``["opencode"]`` → user selected items
    - ``[]`` → user submitted an empty selection
    - ``None`` → user pressed Escape (cancelled)
    """
    marker = request.node.get_closest_marker("questionary_return")
    return_value = marker.args[0] if marker else None
    stub = _StubCheckbox(return_value)
    monkeypatch.setattr("questionary.checkbox", stub)
    return stub


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "questionary_return(return_value): set return value for monkeypatch_questionary fixture",
    )
