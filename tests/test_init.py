"""Unit tests for the ``init`` command and its underlying ``init_repo`` operation.

Behavioural tests: they exercise the public surface (``init_repo`` and the typer
command) through a temporary directory so no real repo is ever touched. The
path-mapping knowledge is hidden inside ``operations`` — these tests assert
OBSERVABLE behaviour (which file is written / skipped), never internal helpers.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app

runner = CliRunner()

CODING_STANDARDS = "CODING_STANDARDS.md"


# ---------------------------------------------------------------------------
# init_repo — observable behaviour
# ---------------------------------------------------------------------------


def test_init_repo_writes_titles_only_skeleton_when_file_absent(tmp_path: Path) -> None:
    """Running init_repo on a directory without CODING_STANDARDS.md writes a headings-only skeleton."""
    from ai_harness.modules.harness import init_repo

    assert not (tmp_path / CODING_STANDARDS).exists()

    result = init_repo(tmp_path)

    assert result is True
    path = tmp_path / CODING_STANDARDS
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    # Must contain the main heading
    assert "# Coding Standards" in content
    # Must contain section headings — empty bodies only
    assert "## Style" in content
    assert "## Testing" in content
    assert "## Architecture" in content
    assert "## Commits" in content
    assert "## Quality gates" in content
    # No substantial body content: the only content between headings is blank lines
    sections = content.split("\n## ")
    for section in sections[1:]:  # skip "# Coding Standards" intro
        body = section.partition("\n")[2]
        # Body should be only blank lines (or nothing)
        non_blank = [line for line in body.splitlines() if line.strip()]
        assert not non_blank, f"Section has unexpected body content: {section.splitlines()[0]!r}"


def test_init_repo_skips_when_file_exists(tmp_path: Path) -> None:
    """Running init_repo when CODING_STANDARDS.md already exists leaves it untouched (idempotent)."""
    from ai_harness.modules.harness import init_repo

    existing = tmp_path / CODING_STANDARDS
    original = "# My Custom Standards\n\nCustom content here.\n"
    existing.write_text(original, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result is False
    assert existing.read_text(encoding="utf-8") == original


def test_init_repo_defaults_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """init_repo with no argument defaults to the current working directory."""
    from ai_harness.modules.harness import init_repo

    monkeypatch.chdir(tmp_path)

    result = init_repo()

    assert result is True
    assert (tmp_path / CODING_STANDARDS).is_file()


def test_init_repo_returns_true_only_when_writes(tmp_path: Path) -> None:
    """init_repo returns True on first call (writes), False on second call (skips, file exists)."""
    from ai_harness.modules.harness import init_repo

    first = init_repo(tmp_path)
    second = init_repo(tmp_path)

    assert first is True
    assert second is False


# ---------------------------------------------------------------------------
# CLI adapter — exercise through typer
# ---------------------------------------------------------------------------


def test_cli_init_writes_skeleton_and_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ai-harness init`` writes the skeleton and exits 0."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    assert (tmp_path / CODING_STANDARDS).is_file()
    content = (tmp_path / CODING_STANDARDS).read_text(encoding="utf-8")
    assert "# Coding Standards" in content
    # When file is written, stdout reports it was created
    assert "created" in result.stdout.lower()


def test_cli_init_skips_when_file_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ai-harness init`` exits 0 and reports unchanged when CODING_STANDARDS.md already exists."""
    monkeypatch.chdir(tmp_path)

    existing = tmp_path / CODING_STANDARDS
    original = "# Already here\n"
    existing.write_text(original, encoding="utf-8")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    assert existing.read_text(encoding="utf-8") == original
    assert "unchanged" in result.stdout.lower()
