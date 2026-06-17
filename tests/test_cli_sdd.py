"""Typer CLI surface tests for sdd-status: command name, flags, exit codes.

Ported from cli.bak/tests/test_cli.py, scoped to sdd-status --json only.
sdd-continue, --instructions, and human-rendering tests are out of scope.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ai_harness.main import app
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


def test_apply_report_present_in_cli_json_output(tmp_path: Path):
    """applyReport key must appear in CLI JSON output; applyProgress absent."""
    seed_ready_change(tmp_path, "thin", "- [x] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "applyReport" in payload["artifactPaths"]
    assert "applyReport" in payload["artifacts"]
    assert "applyProgress" not in payload["artifactPaths"]
    assert "applyProgress" not in payload["artifacts"]


# --- sdd-continue CLI tests --------------------------------------------------


def test_sdd_continue_dispatcher_markdown(tmp_path: Path):
    seed_ready_change(tmp_path, "fix-auth", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-continue", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    out = result.stdout
    assert "## Native SDD Dispatcher: fix-auth" in out
    assert "### Dependency States" in out
    assert "next_recommended: apply" in out
    assert "### JSON" in out
    assert "```json" in out


def test_sdd_continue_json_includes_instructions(tmp_path: Path):
    seed_ready_change(tmp_path, "fix-auth", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-continue", "--json", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "phaseInstructions" in payload
    assert "apply" in payload["phaseInstructions"]
    assert "verify" in payload["phaseInstructions"]
    assert "archive" in payload["phaseInstructions"]


def test_sdd_continue_empty_workspace(tmp_path: Path):
    import os as _os

    _os.makedirs(tmp_path / "openspec" / "changes", exist_ok=True)
    result = runner.invoke(app, ["sdd-continue", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    out = result.stdout
    assert "## Native SDD Dispatcher: unresolved" in out
    assert "### Blocked Reasons" in out
    assert "no active openspec changes" in out.lower()
    assert "### Next Phase Instructions" not in out


def test_sdd_continue_missing_change(tmp_path: Path):
    seed_ready_change(tmp_path, "real", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-continue", "--cwd", str(tmp_path), "ghost"])
    assert result.exit_code == 0
    out = result.stdout
    assert "## Native SDD Dispatcher: ghost" in out
    assert "### Blocked Reasons" in out
    assert "ghost" in out
    assert "### Next Phase Instructions" not in out


def test_sdd_status_instructions_flag(tmp_path: Path):
    seed_ready_change(tmp_path, "fix-auth", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-status", "--json", "--instructions", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "phaseInstructions" in payload


def test_sdd_status_no_instructions_flag(tmp_path: Path):
    seed_ready_change(tmp_path, "fix-auth", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "phaseInstructions" not in payload
