"""Rich boundary: --json stays deterministic plain JSON, Rich is human-only."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from typer.testing import CliRunner

from ai_harness import compat, rendering
from ai_harness.cli import app
from ai_harness.sdd import resolve
from conftest import seed_ready_change

runner = CliRunner()

ESC = "\x1b"


def test_json_output_has_no_terminal_control_sequences(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(tmp_path)])
    assert ESC not in result.stdout
    json.loads(result.stdout)  # parses cleanly


def test_json_output_equals_compat_serializer(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    result = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(tmp_path)])
    status = resolve(str(tmp_path), "", "", False)
    assert result.stdout.rstrip("\n") == compat.status_to_json(status)


def test_compat_module_does_not_depend_on_rich():
    source = inspect.getsource(compat)
    assert "rich" not in source


def test_rendering_module_uses_rich():
    source = inspect.getsource(rendering)
    assert "rich" in source
