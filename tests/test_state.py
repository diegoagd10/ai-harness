"""Unit tests for state.py — load / save / clear with atomic semantics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.artifacts.state import StateFileError, clear_state, load_state, save_state


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    """load_state returns an empty set when the state file does not exist."""
    home = tmp_path / "home"
    home.mkdir()
    result = load_state(home)
    assert result == set()


def test_load_valid_returns_set(tmp_path: Path) -> None:
    """load_state returns the installed set from a valid state file."""
    home = tmp_path / "home"
    home.mkdir()
    state_file = home / ".ai-harness" / "state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text('{"installed": ["opencode", "claude"]}', encoding="utf-8")

    result = load_state(home)
    assert result == {"opencode", "claude"}


def test_load_malformed_raises(tmp_path: Path) -> None:
    """load_state raises StateFileError on malformed JSON."""
    home = tmp_path / "home"
    home.mkdir()
    state_file = home / ".ai-harness" / "state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(StateFileError):
        load_state(home)


def test_load_missing_key_raises(tmp_path: Path) -> None:
    """load_state raises StateFileError when 'installed' key is absent."""
    home = tmp_path / "home"
    home.mkdir()
    state_file = home / ".ai-harness" / "state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text('{"wrong_key": ["opencode"]}', encoding="utf-8")

    with pytest.raises(StateFileError, match="missing the 'installed' key"):
        load_state(home)


def test_load_wrong_type_raises(tmp_path: Path) -> None:
    """load_state raises StateFileError when 'installed' is not a list."""
    home = tmp_path / "home"
    home.mkdir()
    state_file = home / ".ai-harness" / "state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text('{"installed": "not-a-list"}', encoding="utf-8")

    with pytest.raises(StateFileError, match="'installed' key must be a list"):
        load_state(home)


# ------------------------------------------------------------ save_state ---


def test_save_creates_dir_and_file(tmp_path: Path) -> None:
    """save_state creates the .ai-harness/ directory and writes the file."""
    home = tmp_path / "home"
    home.mkdir()

    save_state(home, {"opencode"})

    state_file = home / ".ai-harness" / "state.json"
    assert state_file.parent.is_dir()
    assert state_file.is_file()
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert set(data["installed"]) == {"opencode"}


def test_save_atomic_preserves_prior_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save_state preserves the original file when the write fails midway."""
    home = tmp_path / "home"
    home.mkdir()
    state_file = home / ".ai-harness" / "state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text('{"installed": ["opencode"]}', encoding="utf-8")

    # Simulate a crash during the temp-file write by making json.dumps fail.
    original_dumps = json.dumps

    def _failing_dumps(*args, **kwargs):
        raise OSError("simulated disk full")

    monkeypatch.setattr(json, "dumps", _failing_dumps)

    with pytest.raises(OSError, match="simulated disk full"):
        save_state(home, {"claude"})

    # Original file content is intact.
    assert state_file.read_text(encoding="utf-8") == '{"installed": ["opencode"]}'


# ------------------------------------------------------------ clear_state ---


def test_clear_deletes_file(tmp_path: Path) -> None:
    """clear_state removes the state file when it exists."""
    home = tmp_path / "home"
    home.mkdir()
    state_file = home / ".ai-harness" / "state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text('{"installed": ["opencode"]}', encoding="utf-8")

    clear_state(home)

    assert not state_file.exists()


def test_clear_idempotent_missing(tmp_path: Path) -> None:
    """clear_state on a missing file is a no-op (no error)."""
    home = tmp_path / "home"
    home.mkdir()

    # Should not raise.
    clear_state(home)
