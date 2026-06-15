"""Typer CLI surface tests for sdd-status: names, flags, exit codes."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ai_harness.cli import app
from conftest import seed_ready_change

runner = CliRunner()


def test_command_name_is_hyphenated_sdd_status(tmp_path: Path):
    result = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schemaName"] == "ai-harness.sdd-status"


def test_blocked_state_still_exits_zero(tmp_path: Path):
    # No openspec/changes at all -> blocked sdd-new, but a valid status (exit 0).
    result = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["nextRecommended"] == "sdd-new"
    assert payload["changeName"] is None


def test_cwd_flag_selects_workspace_and_change(tmp_path: Path):
    seed_ready_change(tmp_path, "add-auth", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["changeName"] == "add-auth"
    assert payload["nextRecommended"] == "apply"


def test_positional_change_argument(tmp_path: Path):
    seed_ready_change(tmp_path, "wanted", "- [ ] 1.1 Work\n")
    seed_ready_change(tmp_path, "other", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(tmp_path), "wanted"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["changeName"] == "wanted"


def test_instructions_flag_attaches_phase_instructions(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    with_flag = runner.invoke(
        app, ["sdd-status", "--json", "--instructions", "--cwd", str(tmp_path)]
    )
    without_flag = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(tmp_path)])
    assert "phaseInstructions" in json.loads(with_flag.stdout)
    assert "phaseInstructions" not in json.loads(without_flag.stdout)


def test_missing_workspace_root_exits_one(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    result = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(missing)])
    assert result.exit_code == 1


def test_unknown_flag_is_usage_error(tmp_path: Path):
    result = runner.invoke(app, ["sdd-status", "--bogus", "--cwd", str(tmp_path)])
    assert result.exit_code == 2


def test_too_many_positionals_is_usage_error(tmp_path: Path):
    result = runner.invoke(app, ["sdd-status", "--cwd", str(tmp_path), "one", "two"])
    assert result.exit_code == 2


def test_human_output_renders_change_name(tmp_path: Path):
    seed_ready_change(tmp_path, "add-auth", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-status", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    assert "add-auth" in result.stdout


# --- sdd-continue -----------------------------------------------------------


def test_sdd_continue_command_name_is_hyphenated(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-continue", "--json", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schemaName"] == "ai-harness.sdd-status"
    assert payload["changeName"] == "thin"


def test_sdd_continue_json_always_includes_phase_instructions(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    plain = runner.invoke(app, ["sdd-continue", "--json", "--cwd", str(tmp_path)])
    assert json.loads(plain.stdout)["phaseInstructions"]["apply"][0] == "Change: thin"


def test_sdd_continue_instructions_flag_is_accepted_and_ignored(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    with_flag = runner.invoke(
        app, ["sdd-continue", "--json", "--instructions", "--cwd", str(tmp_path)]
    )
    without_flag = runner.invoke(app, ["sdd-continue", "--json", "--cwd", str(tmp_path)])
    assert with_flag.exit_code == 0
    assert json.loads(with_flag.stdout) == json.loads(without_flag.stdout)


def test_sdd_continue_human_output_uses_dispatcher_markdown(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-continue", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    assert "## Native SDD Dispatcher: thin" in result.stdout
    assert "### Dependency States" in result.stdout
    assert "### JSON" in result.stdout
    assert "```json" in result.stdout
    # Dispatcher markdown targets LLM consumption; no Rich/ANSI noise.
    assert "\x1b" not in result.stdout


def test_sdd_continue_blocked_state_exits_zero_with_reasons(tmp_path: Path):
    # No openspec/changes at all -> blocked sdd-new, but a valid status (exit 0).
    result = runner.invoke(app, ["sdd-continue", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    assert "No active OpenSpec changes found" in result.stdout
    # Blocked reasons section appears because reasons are non-empty.
    assert "### Blocked Reasons" in result.stdout
    # No "Next Phase Instructions" when next_recommended is sdd-new.
    assert "### Next Phase Instructions" not in result.stdout
