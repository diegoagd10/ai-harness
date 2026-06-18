from __future__ import annotations

from typer.testing import CliRunner

from ai_harness.main import app

runner = CliRunner()


def test_install_prints_expected_output() -> None:
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "Hellow Muppet"
