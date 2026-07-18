"""CLI regressions for removed receipt-only commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.chdir(tmp_path)
    return CliRunner()


@pytest.mark.parametrize("command", ["change-gates-run", "change-receipt-seal"])
def test_removed_receipt_commands_are_unknown(runner: CliRunner, command: str) -> None:
    result = runner.invoke(app, [command])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_help_omits_removed_receipt_commands(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "change-gates-run" not in result.output
    assert "change-receipt-seal" not in result.output


def test_preserved_change_and_task_commands_remain_registered(runner: CliRunner) -> None:
    created = runner.invoke(app, ["change-new", "demo"])
    listed = runner.invoke(app, ["task-list", "-c", "demo"])

    assert created.exit_code == 0, created.output
    assert listed.exit_code == 0, listed.output
    assert listed.output.strip() == "[]"
