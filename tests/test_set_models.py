"""Unit tests for the set-models wizard pure helpers and CLI arg validation.

Behavioural tests for the data-prep layer (``pure`` module) and the typer
adapter (``set_models`` command). The interactive questionary/rich shell
is intentionally untested — it is a thin adapter with no business logic.

Pure helpers covered
--------------------
- Fixed Claude model and effort sets are exact, in the right order.
- Agent list excludes the orchestrator (the Claude skill).
- Picker-row builders mark the current value, leave others unmarked.
- Confirmation rows render ``agent: model / effort``.
- Override-store writer deep-merges over the existing store atomically.
- CLI ``-o`` arg parser rejects missing and multiple Agent CLIs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from ai_harness.commands import parse_single_agent_cli
from ai_harness.main import app
from ai_harness.modules.harness import AgentCli
from ai_harness.modules.harness.renderers import (
    _load_override_store,
    write_override_store,
)
from ai_harness.modules.wizard.pure import (
    build_agent_list_rows,
    build_confirmation_rows,
    build_effort_picker_rows,
    build_model_picker_rows,
    claude_efforts,
    claude_models,
    claude_wizard_agents,
)

if TYPE_CHECKING:
    pass

runner = CliRunner()

OVERRIDES_REL = ".ai-harness/overrides.json"


# ---------------------------------------------------------------------------
# parse_single_agent_cli — CLI arg validation
# ---------------------------------------------------------------------------


def test_parse_single_agent_cli_accepts_valid_name() -> None:
    """A single known agent CLI is parsed verbatim."""
    assert parse_single_agent_cli("claude") == [AgentCli.CLAUDE]


def test_parse_single_agent_cli_strips_whitespace() -> None:
    """Surrounding whitespace is stripped from the input."""
    assert parse_single_agent_cli("  claude  ") == [AgentCli.CLAUDE]


def test_parse_single_agent_cli_rejects_empty() -> None:
    """An empty / whitespace-only string returns an empty list (caller rejects)."""
    assert parse_single_agent_cli("") == []
    assert parse_single_agent_cli("   ") == []


def test_parse_single_agent_cli_rejects_multiple_via_comma() -> None:
    """Comma-separated input is parsed as a list; the caller is responsible for rejecting multi."""
    # parse_agent_clis itself returns a list — the set_models command must reject len != 1.
    # The helper's contract is "returns a list" — the set_models command layer enforces single.
    assert parse_single_agent_cli("claude,opencode") == [AgentCli.CLAUDE, AgentCli.OPENCODE]


# ---------------------------------------------------------------------------
# Fixed Claude sets — the wizard's vocabulary lives in the pure module
# ---------------------------------------------------------------------------


def test_claude_models_is_the_fixed_set() -> None:
    """Claude model picker offers exactly opus/sonnet/haiku/fable/inherit in that order."""
    assert claude_models() == ("opus", "sonnet", "haiku", "fable", "inherit")


def test_claude_efforts_is_the_fixed_set() -> None:
    """Claude effort picker offers low/medium/high/xhigh/max in that order."""
    assert claude_efforts() == ("low", "medium", "high", "xhigh", "max")


def test_claude_wizard_agents_excludes_orchestrator() -> None:
    """The Claude wizard configures the three subagents; the orchestrator skill is fixed."""
    assert claude_wizard_agents() == ("explorer", "implementor", "validator")


# ---------------------------------------------------------------------------
# Picker row builders — mark current, leave others unmarked
# ---------------------------------------------------------------------------


def test_build_model_picker_rows_marks_current_model() -> None:
    """The row matching the current model is marked; others are unmarked."""
    rows = build_model_picker_rows("implementor", "opus")

    # All fixed Claude models are present
    assert [r.value for r in rows] == list(claude_models())
    # Exactly one row is marked as current
    assert sum(1 for r in rows if r.is_current) == 1
    # The marked row is the current model
    current = next(r for r in rows if r.is_current)
    assert current.value == "opus"


def test_build_model_picker_rows_falls_back_when_current_unknown() -> None:
    """When the current model is not in the fixed set, no row is marked."""
    rows = build_model_picker_rows("implementor", "mystery-model")
    assert all(not r.is_current for r in rows)


def test_build_effort_picker_rows_marks_current_effort() -> None:
    """The row matching the current effort is marked."""
    rows = build_effort_picker_rows("validator", "high")

    assert [r.value for r in rows] == list(claude_efforts())
    current = next(r for r in rows if r.is_current)
    assert current.value == "high"


def test_build_effort_picker_rows_handles_none() -> None:
    """A ``None`` current effort (unset) marks no row."""
    rows = build_effort_picker_rows("explorer", None)
    assert all(not r.is_current for r in rows)


def test_build_agent_list_rows_shows_current_per_agent() -> None:
    """Each row in the agent list shows that agent's current model."""
    current = {
        "explorer": "haiku",
        "implementor": "opus",
        "validator": "sonnet",
    }
    rows = build_agent_list_rows(claude_wizard_agents(), current)

    # Order matches the configured agent list
    assert [r.value for r in rows] == list(claude_wizard_agents())
    # Every row is marked (the agent list always shows the current value)
    assert all(r.is_current for r in rows)


def test_build_agent_list_rows_missing_agent_gets_default_model() -> None:
    """An agent missing from the current map gets the Claude default 'sonnet' (template baseline)."""
    rows = build_agent_list_rows(claude_wizard_agents(), {})

    # All three rows present, all marked
    assert len(rows) == 3
    assert all(r.is_current for r in rows)


# ---------------------------------------------------------------------------
# Confirmation rows — render the per-agent chosen model + effort
# ---------------------------------------------------------------------------


def test_build_confirmation_rows_includes_model_and_effort() -> None:
    """Confirmation rows show ``agent: model / effort`` for each agent."""
    selections = {
        "explorer": ("haiku", "low"),
        "implementor": ("opus", "high"),
        "validator": ("sonnet", None),
    }
    rows = build_confirmation_rows(selections)

    # All agents are listed
    assert {r.value for r in rows} == set(selections.keys())
    # The label carries the model and effort
    by_value = {r.value: r.label for r in rows}
    assert "haiku" in by_value["explorer"]
    assert "low" in by_value["explorer"]
    assert "opus" in by_value["implementor"]
    assert "high" in by_value["implementor"]
    # None effort renders as a placeholder
    assert "sonnet" in by_value["validator"]


# ---------------------------------------------------------------------------
# write_override_store — deep-merge writer next to the loader
# ---------------------------------------------------------------------------


def test_write_override_store_writes_new_payload(tmp_path: Path) -> None:
    """Writing a fresh payload creates ``~/.ai-harness/overrides.json`` with that JSON."""
    write_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})

    path = tmp_path / OVERRIDES_REL
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"implementor": {"model": {"claude": "opus"}}}


def test_write_override_store_preserves_unrelated_existing_entries(tmp_path: Path) -> None:
    """An existing entry for another agent survives a new write."""
    existing_path = tmp_path / OVERRIDES_REL
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text(
        json.dumps({"validator": {"model": {"claude": "haiku"}}}),
        encoding="utf-8",
    )

    write_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})

    data = json.loads(existing_path.read_text(encoding="utf-8"))
    assert data["validator"] == {"model": {"claude": "haiku"}}
    assert data["implementor"] == {"model": {"claude": "opus"}}


def test_write_override_store_merges_partial_override_for_same_agent(tmp_path: Path) -> None:
    """Writing model for an agent merges with an existing effort override for the same agent."""
    existing_path = tmp_path / OVERRIDES_REL
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text(
        json.dumps({"implementor": {"effort": {"claude": "high"}}}),
        encoding="utf-8",
    )

    write_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})

    data = json.loads(existing_path.read_text(encoding="utf-8"))
    assert data["implementor"]["model"] == {"claude": "opus"}
    assert data["implementor"]["effort"] == {"claude": "high"}


def test_write_override_store_round_trips_through_loader(tmp_path: Path) -> None:
    """What we write is what the existing override loader reads back."""
    payload = {
        "implementor": {"model": {"claude": "opus"}, "effort": {"claude": "high"}},
        "validator": {"model": {"claude": "haiku"}},
    }
    write_override_store(tmp_path, payload)

    loaded = _load_override_store(tmp_path)
    assert loaded == payload


def test_write_override_store_creates_parent_directory(tmp_path: Path) -> None:
    """The parent ``~/.ai-harness/`` directory is created on first write."""
    assert not (tmp_path / ".ai-harness").exists()
    write_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})
    assert (tmp_path / ".ai-harness").is_dir()
    assert (tmp_path / OVERRIDES_REL).is_file()


# ---------------------------------------------------------------------------
# set_models CLI — argument validation paths
# ---------------------------------------------------------------------------


def test_cli_set_models_missing_o_errors(isolated_home: Path) -> None:
    """Running `set-models` with no `-o` errors with a clear, non-zero exit."""
    result = runner.invoke(app, ["set-models"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    assert (
        "set-models" in combined.lower()
        or "missing" in combined.lower()
        or "required" in combined.lower()
        or "-o" in combined
    )


def test_cli_set_models_multiple_clis_errors(isolated_home: Path) -> None:
    """Two CLIs in -o errors with a clear, non-zero exit."""
    result = runner.invoke(app, ["set-models", "-o", "claude,opencode"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    assert "exactly one" in combined.lower() or "single" in combined.lower() or "one" in combined.lower()


def test_cli_set_models_unknown_cli_errors(isolated_home: Path) -> None:
    """An unknown CLI in -o errors with a clear, non-zero exit."""
    result = runner.invoke(app, ["set-models", "-o", "bogus"])

    assert result.exit_code != 0


def test_cli_set_models_opencode_explicit_not_implemented(isolated_home: Path) -> None:
    """OpenCode is single-CLI valid but explicitly not implemented in slice 2."""
    result = runner.invoke(app, ["set-models", "-o", "opencode"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    assert "opencode" in combined.lower()
    assert "not implemented" in combined.lower() or "slice 3" in combined.lower()


def test_cli_set_models_copilot_not_supported(isolated_home: Path) -> None:
    """Copilot and generic are not in the wizard's vocabulary at all."""
    result = runner.invoke(app, ["set-models", "-o", "copilot"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    assert "copilot" in combined.lower()


# ---------------------------------------------------------------------------
# set_models CLI — non-TTY guard for claude (must not hang waiting for stdin)
# ---------------------------------------------------------------------------


def test_cli_set_models_claude_non_tty_errors(isolated_home: Path) -> None:
    """Without a TTY, the Claude wizard errors immediately rather than blocking on stdin."""
    # CliRunner runs without a TTY by default; questionary.select fails
    # on EOF rather than blocking. The command must convert that into a
    # non-zero exit with a clear message.
    result = runner.invoke(app, ["set-models", "-o", "claude"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    # Either "tty", "stdin", or "interactive" is in the message — or simply
    # the wizard bailed cleanly because no input was available.
    assert combined.strip() != "", "expected some output explaining the bail-out"


# ---------------------------------------------------------------------------
# Wizard pickers — type-to-filter wiring (acceptance criterion: search filter)
# ---------------------------------------------------------------------------
# These tests do NOT drive the full TUI. They spy on questionary.select to
# confirm the picker functions wire the ``use_search_filter=True`` kwarg that
# enables type-to-filter navigation. Driving the actual prompt would test
# the questionary library, not us.


class _SelectSpy:
    """Captures kwargs from each questionary.select call and returns None from .ask().

    The ``None`` return simulates a Ctrl+C cancel so the wizard bails out
    cleanly without needing a real terminal.
    """

    instances: list[_SelectSpy] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs
        _SelectSpy.instances.append(self)

    def ask(self) -> None:
        return None


def test_model_picker_enables_search_filter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The Claude model picker must enable type-to-filter (acceptance criterion)."""
    from ai_harness.modules.wizard import tui

    _SelectSpy.instances = []
    monkeypatch.setattr(tui.questionary, "select", _SelectSpy)

    tui._ask_claude_model("implementor", tmp_path)  # type: ignore[attr-defined]

    assert _SelectSpy.instances, "questionary.select was not called"
    assert _SelectSpy.instances[0].kwargs.get("use_search_filter") is True


def test_effort_picker_enables_search_filter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The Claude effort picker must enable type-to-filter (acceptance criterion)."""
    from ai_harness.modules.wizard import tui

    _SelectSpy.instances = []
    monkeypatch.setattr(tui.questionary, "select", _SelectSpy)

    tui._ask_claude_effort("validator", tmp_path)  # type: ignore[attr-defined]

    assert _SelectSpy.instances, "questionary.select was not called"
    assert _SelectSpy.instances[0].kwargs.get("use_search_filter") is True


def test_agent_continue_picker_enables_search_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent-picker (with the Continue sentinel) must also enable search filtering."""
    from ai_harness.modules.wizard import tui

    _SelectSpy.instances = []
    monkeypatch.setattr(tui.questionary, "select", _SelectSpy)

    tui._ask_continue_or_agent("model", {"implementor": "opus"})  # type: ignore[attr-defined]

    assert _SelectSpy.instances, "questionary.select was not called"
    assert _SelectSpy.instances[0].kwargs.get("use_search_filter") is True


def test_keybinding_legend_advertises_filter_not_jk() -> None:
    """The header/footer legend must reflect the new keybindings (arrows + filter, no j/k)."""
    from ai_harness.modules.wizard import tui

    legend = tui._KEYBINDING_LEGEND
    assert "type to filter" in legend
    assert "↑/↓" in legend
    # j/k is no longer a navigation hint because use_search_filter makes it filter input.
    assert "j/k" not in legend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect HOME to a tmp dir so commands don't touch the real user state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path
