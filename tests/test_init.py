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
from ai_harness.modules.harness.labels import LabelResult

runner = CliRunner()

CODING_STANDARDS = "CODING_STANDARDS.md"
CLAUDE_MD = "CLAUDE.md"

AI_HARNESS_START = "<!-- ai-harness:start -->"
AI_HARNESS_END = "<!-- ai-harness:end -->"


# ---------------------------------------------------------------------------
# init_repo — observable behaviour
# ---------------------------------------------------------------------------


def test_init_repo_writes_titles_only_skeleton_when_file_absent(tmp_path: Path) -> None:
    """Running init_repo on a directory without CODING_STANDARDS.md writes a headings-only skeleton."""
    from ai_harness.modules.harness import init_repo

    assert not (tmp_path / CODING_STANDARDS).exists()

    result = init_repo(tmp_path)

    assert result.wrote_standards is True
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

    assert result.wrote_standards is False
    assert existing.read_text(encoding="utf-8") == original


def test_init_repo_defaults_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """init_repo with no argument defaults to the current working directory."""
    from ai_harness.modules.harness import init_repo

    monkeypatch.chdir(tmp_path)

    result = init_repo()

    assert result.wrote_standards is True
    assert (tmp_path / CODING_STANDARDS).is_file()


def test_init_repo_returns_true_only_when_writes(tmp_path: Path) -> None:
    """init_repo returns InitResult, test for CODING_STANDARDS.md behaviour with InitResult."""
    from ai_harness.modules.harness import init_repo

    first = init_repo(tmp_path)
    second = init_repo(tmp_path)

    assert first.wrote_standards is True
    assert second.wrote_standards is False


# ---------------------------------------------------------------------------
# init_repo — CLAUDE.md labels-policy block
# ---------------------------------------------------------------------------


def test_init_repo_appends_labels_policy_when_claude_md_exists_and_no_markers(tmp_path: Path) -> None:
    """Running init_repo on a dir with CLAUDE.md lacking markers appends the labels-policy block."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    original = "## Agent skills\n\nSome agent content.\n"
    claude.write_text(original, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_labels_policy is True
    assert result.claude_md_missing is False

    content = claude.read_text(encoding="utf-8")
    assert AI_HARNESS_START in content
    assert AI_HARNESS_END in content
    assert "prd-issue" in content
    assert "sub-issue" in content
    assert "`ready-for-agent`" in content
    assert "`loop`" in content
    # Original content preserved
    assert original in content
    # Block appears after original content
    assert content.index(AI_HARNESS_START) > content.index(original.strip())


def test_init_repo_skips_labels_policy_when_markers_present(tmp_path: Path) -> None:
    """Running init_repo when CLAUDE.md already has markers makes no change."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    original = f"""## Agent skills

Some content.

{AI_HARNESS_START}

## Loop label policy

Already present.

{AI_HARNESS_END}
"""
    claude.write_text(original, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_labels_policy is False
    assert result.claude_md_missing is False
    assert claude.read_text(encoding="utf-8") == original


def test_init_repo_skips_labels_policy_when_no_claude_md(tmp_path: Path) -> None:
    """Running init_repo when CLAUDE.md does not exist skips without creating it."""
    from ai_harness.modules.harness import init_repo

    assert not (tmp_path / CLAUDE_MD).exists()

    result = init_repo(tmp_path)

    assert result.wrote_labels_policy is False
    assert result.claude_md_missing is True
    assert not (tmp_path / CLAUDE_MD).exists()


def test_init_repo_appends_labels_policy_to_empty_claude_md(tmp_path: Path) -> None:
    """Empty CLAUDE.md counts as existing and receives the labels-policy block."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    claude.write_text("", encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_labels_policy is True
    content = claude.read_text(encoding="utf-8")
    assert AI_HARNESS_START in content
    assert AI_HARNESS_END in content


def test_init_repo_appends_labels_policy_when_claude_md_no_trailing_newline(tmp_path: Path) -> None:
    """CLAUDE.md without trailing newline still receives cleanly separated block."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    original = "# No trailing newline"
    claude.write_text(original, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_labels_policy is True
    content = claude.read_text(encoding="utf-8")
    assert AI_HARNESS_START in content
    # Block starts on a new line, not mashed against original
    lines = content.splitlines()
    start_idx = next(i for i, line in enumerate(lines) if AI_HARNESS_START in line)
    assert lines[start_idx - 1] == ""


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


def test_cli_init_reports_labels_policy_appended(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ai-harness init`` reports labels-policy appended when CLAUDE.md exists without markers."""
    monkeypatch.chdir(tmp_path)

    claude = tmp_path / CLAUDE_MD
    claude.write_text("## Agent skills\n", encoding="utf-8")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    assert "Appended labels-policy" in result.stdout
    content = claude.read_text(encoding="utf-8")
    assert AI_HARNESS_START in content
    assert AI_HARNESS_END in content


def test_cli_init_reports_labels_policy_skipped_when_markers_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ai-harness init`` reports unchanged when CLAUDE.md already has markers."""
    monkeypatch.chdir(tmp_path)

    claude = tmp_path / CLAUDE_MD
    claude.write_text(f"{AI_HARNESS_START}\n\n{AI_HARNESS_END}\n", encoding="utf-8")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    assert "already present" in result.stdout.lower()
    assert "unchanged" in result.stdout.lower()


def test_cli_init_reports_labels_policy_skipped_when_no_claude_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ai-harness init`` reports skipping when no CLAUDE.md exists."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    assert "No CLAUDE.md found" in result.stdout
    assert not (tmp_path / CLAUDE_MD).exists()


# ---------------------------------------------------------------------------
# init_repo — label creation integration
# ---------------------------------------------------------------------------

_FAKE_LABEL_RESULT_OK = LabelResult(created=["ready-for-agent", "loop"], warnings=[])


def test_init_repo_includes_label_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """init_repo populates created_labels and label_warnings from ensure_labels."""
    from ai_harness.modules.harness import init_repo, operations

    monkeypatch.setattr(operations, "ensure_labels", lambda _root: _FAKE_LABEL_RESULT_OK)

    result = init_repo(tmp_path)

    assert result.created_labels == ["ready-for-agent", "loop"]
    assert result.label_warnings == []


def test_init_repo_label_skips_dont_block_scaffolding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When labels are skipped (already exist), scaffolding still completes."""
    from ai_harness.modules.harness import init_repo, operations

    monkeypatch.setattr(operations, "ensure_labels", lambda _root: LabelResult(created=[], warnings=[]))

    result = init_repo(tmp_path)

    assert result.created_labels == []
    assert result.label_warnings == []
    assert result.wrote_standards is True  # Scaffolding proceeds normally


def test_init_repo_label_warnings_dont_block_scaffolding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When label creation warns (gh unavailable), scaffolding still completes."""
    from ai_harness.modules.harness import init_repo, operations

    warnings = [
        "Could not create GitHub label 'ready-for-agent' (gh CLI not found). "
        "Run manually:\n  gh label create ready-for-agent --color 7057ff --description "
        '"Fully specified, ready for an AFK agent"',
    ]
    monkeypatch.setattr(operations, "ensure_labels", lambda _root: LabelResult(created=[], warnings=warnings))

    result = init_repo(tmp_path)

    assert result.created_labels == []
    assert len(result.label_warnings) == 1
    assert "gh CLI not found" in result.label_warnings[0]
    assert result.wrote_standards is True  # Scaffolding proceeds normally


# ---------------------------------------------------------------------------
# CLI adapter — label output
# ---------------------------------------------------------------------------


def test_cli_init_reports_created_labels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ai-harness init`` reports created GitHub labels."""
    from ai_harness.modules.harness import operations

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(operations, "ensure_labels", lambda _root: _FAKE_LABEL_RESULT_OK)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    assert "Created GitHub labels" in result.stdout
    assert "ready-for-agent" in result.stdout
    assert "loop" in result.stdout


def test_cli_init_reports_label_warnings_to_stderr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ai-harness init`` routes label warnings to stderr."""
    from ai_harness.modules.harness import operations

    monkeypatch.chdir(tmp_path)
    warnings = ["gh CLI not found — run manually"]
    monkeypatch.setattr(operations, "ensure_labels", lambda _root: LabelResult(created=[], warnings=warnings))

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    assert "Warning:" in result.stderr
    assert "gh CLI not found" in result.stderr
