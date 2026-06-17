"""Shared fixtures and OpenSpec workspace seeders for the SDD CLI tests.

Ports the helpers from cli.bak/tests/conftest.py, omitting the Go oracle
fixture and sdd-continue helpers (both out of scope for this slice).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from prompt_toolkit.input import PipeInput, create_pipe_input


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


class _StubQuestion:
    """A fake ``questionary.Question`` whose ``.ask()`` returns a fixed value."""

    def __init__(self, return_value: object) -> None:
        self._return_value = return_value

    def ask(self) -> object:
        return self._return_value


class _StubCheckbox:
    """Replaces ``wizard._build_question`` with a configurable stub.

    Use via the ``monkeypatch_questionary`` fixture together with
    ``@pytest.mark.questionary_return(...)``:

    - ``@pytest.mark.questionary_return(["opencode"])`` — user chose items
    - ``@pytest.mark.questionary_return([])`` — user submitted empty selection
    - ``@pytest.mark.questionary_return(None)`` — user pressed Escape / cancelled

    Records each call as ``(title, kwargs)`` where ``kwargs["choices"]`` and
    ``kwargs["instruction"]`` mirror the wizard's footer/choice construction,
    independent of the real prompt_toolkit ``Application``.
    """

    def __init__(self, return_value: object, footer: str) -> None:
        self._return_value = return_value
        self._footer = footer
        self.calls: list[tuple] = []

    def __call__(self, title: str, choices: list) -> _StubQuestion:
        self.calls.append((title, {"choices": choices, "instruction": self._footer}))
        return _StubQuestion(self._return_value)


@pytest.fixture
def monkeypatch_questionary(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> _StubCheckbox:
    """Monkeypatch ``wizard._build_question`` with a configurable stub.

    Decorate your test with ``@pytest.mark.questionary_return(...)`` to
    control what ``.ask()`` returns:

    - ``["opencode"]`` → user selected items
    - ``[]`` → user submitted an empty selection
    - ``None`` → user pressed Escape (cancelled)
    """
    from ai_harness.artifacts import wizard

    marker = request.node.get_closest_marker("questionary_return")
    return_value = marker.args[0] if marker else None
    stub = _StubCheckbox(return_value, wizard._FOOTER)
    monkeypatch.setattr(wizard, "_build_question", stub)
    return stub


@pytest.fixture
def pipe_input() -> Iterator[PipeInput]:
    """Provide a prompt_toolkit ``PipeInput`` for driving real key events.

    Use ``pipe_input.send_text(...)`` to feed raw key sequences (e.g.
    ``"\\x1b"`` for Escape, ``" "`` for space, ``"\\r"`` for Enter) into an
    ``Application`` built with ``input=pipe_input``.
    """
    with create_pipe_input() as pipe:
        yield pipe


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "questionary_return(return_value): set return value for monkeypatch_questionary fixture",
    )
