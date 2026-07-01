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
CLAUDE_MD = "CLAUDE.md"
AGENTS_MD = "AGENTS.md"

# New init markers — the post-refactor block identity. The legacy
# `ai-harness:start/end` markers are only referenced by the migration tests
# that exercise the in-place legacy-block swap.
INIT_START = "<!-- ai-harness:init:start -->"
INIT_END = "<!-- ai-harness:init:end -->"
LEGACY_START = "<!-- ai-harness:start -->"
LEGACY_END = "<!-- ai-harness:end -->"


# ---------------------------------------------------------------------------
# init_repo — CODING_STANDARDS.md (unchanged behaviour)
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
# init_repo — agent docs always created when missing
# ---------------------------------------------------------------------------


def test_init_repo_creates_both_agent_docs_when_missing(tmp_path: Path) -> None:
    """A clean directory without CLAUDE.md/AGENTS.md receives both, each carrying the init block."""
    from ai_harness.modules.harness import init_repo

    assert not (tmp_path / CLAUDE_MD).exists()
    assert not (tmp_path / AGENTS_MD).exists()

    result = init_repo(tmp_path)

    assert result.wrote_init_block is True
    assert result.init_block_targets == (CLAUDE_MD, AGENTS_MD)

    claude = (tmp_path / CLAUDE_MD).read_text(encoding="utf-8")
    agents = (tmp_path / AGENTS_MD).read_text(encoding="utf-8")
    assert INIT_START in claude
    assert INIT_END in claude
    assert INIT_START in agents
    assert INIT_END in agents


def test_init_repo_creates_byte_identical_agent_docs(tmp_path: Path) -> None:
    """Fresh-init CLAUDE.md and AGENTS.md have matching bytes (same managed body)."""
    from ai_harness.modules.harness import init_repo

    init_repo(tmp_path)

    claude_bytes = (tmp_path / CLAUDE_MD).read_bytes()
    agents_bytes = (tmp_path / AGENTS_MD).read_bytes()
    assert claude_bytes == agents_bytes


def test_init_repo_managed_body_references_coding_standards(tmp_path: Path) -> None:
    """The new init block body explicitly points at CODING_STANDARDS.md so the agent knows what to read."""
    from ai_harness.modules.harness import init_repo

    init_repo(tmp_path)

    claude = (tmp_path / CLAUDE_MD).read_text(encoding="utf-8")
    agents = (tmp_path / AGENTS_MD).read_text(encoding="utf-8")
    assert "CODING_STANDARDS.md" in claude
    assert "CODING_STANDARDS.md" in agents


def test_init_repo_creates_only_missing_agent_doc(tmp_path: Path) -> None:
    """When AGENTS.md already has the init markers and CLAUDE.md is missing, only CLAUDE.md is created."""
    from ai_harness.modules.harness import init_repo

    managed = f"{INIT_START}\n\nFollow the repo's `CODING_STANDARDS.md`.\n\n{INIT_END}\n"
    agents = tmp_path / AGENTS_MD
    agents.write_text(managed, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_init_block is True
    assert result.init_block_targets == (CLAUDE_MD, AGENTS_MD)
    # AGENTS.md is left untouched (already at new markers).
    assert agents.read_text(encoding="utf-8") == managed
    # CLAUDE.md is created with the managed block.
    claude = (tmp_path / CLAUDE_MD).read_text(encoding="utf-8")
    assert INIT_START in claude
    assert INIT_END in claude


def test_init_repo_creates_agent_doc_when_only_other_exists_with_markers(tmp_path: Path) -> None:
    """If one agent doc already has new init markers and the other is missing, the missing one is created."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    claude.write_text(f"{INIT_START}\n\nManaged body.\n\n{INIT_END}\n", encoding="utf-8")

    result = init_repo(tmp_path)

    # CLAUDE.md is kept (already at new markers), AGENTS.md is created.
    assert result.wrote_init_block is True
    assert result.init_block_targets == (CLAUDE_MD, AGENTS_MD)
    assert INIT_START in (tmp_path / AGENTS_MD).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# init_repo — append (bare-file case)
# ---------------------------------------------------------------------------


def test_init_repo_appends_init_block_when_no_markers(tmp_path: Path) -> None:
    """An existing CLAUDE.md without markers receives the init block appended; original content preserved."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    original = "## Agent skills\n\nSome agent content.\n"
    claude.write_text(original, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_init_block is True
    assert result.init_block_targets == (CLAUDE_MD, AGENTS_MD)

    content = claude.read_text(encoding="utf-8")
    assert INIT_START in content
    assert INIT_END in content
    # Original content preserved at the head.
    assert original in content
    assert content.index(INIT_START) > content.index(original.strip())


def test_init_repo_appends_init_block_to_empty_claude_md(tmp_path: Path) -> None:
    """Empty CLAUDE.md is treated as a populated file: it receives the init block as the entire body."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    claude.write_text("", encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_init_block is True
    content = claude.read_text(encoding="utf-8")
    assert INIT_START in content
    assert INIT_END in content
    # First line is the start marker (no spurious blank line at the top).
    assert content.splitlines()[0] == INIT_START


def test_init_repo_appends_init_block_when_claude_md_no_trailing_newline(tmp_path: Path) -> None:
    """CLAUDE.md without trailing newline still receives cleanly separated block."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    original = "# No trailing newline"
    claude.write_text(original, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_init_block is True
    content = claude.read_text(encoding="utf-8")
    assert INIT_START in content
    # Block starts on a new line, not mashed against original.
    lines = content.splitlines()
    start_idx = next(i for i, line in enumerate(lines) if INIT_START in line)
    assert lines[start_idx - 1] == ""


# ---------------------------------------------------------------------------
# init_repo — skip (already-present case)
# ---------------------------------------------------------------------------


def test_init_repo_skips_when_new_markers_present(tmp_path: Path) -> None:
    """CLAUDE.md already at new init markers is left byte-identical; AGENTS.md seeded too so init is a true no-op."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    claude_original = (
        f"## Agent skills\n\nSome content.\n\n"
        f"{INIT_START}\n\nFollow the repo's `CODING_STANDARDS.md`.\n\n{INIT_END}\n"
    )
    claude.write_text(claude_original, encoding="utf-8")
    agents_original = f"{INIT_START}\n\nFollow the repo's `CODING_STANDARDS.md`.\n\n{INIT_END}\n"
    (tmp_path / AGENTS_MD).write_text(agents_original, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_init_block is False  # both kept → no modified files
    assert result.init_block_targets == (CLAUDE_MD, AGENTS_MD)
    assert claude.read_text(encoding="utf-8") == claude_original
    assert (tmp_path / AGENTS_MD).read_text(encoding="utf-8") == agents_original


def test_init_repo_skips_when_both_have_new_markers(tmp_path: Path) -> None:
    """Both files at new markers → no rewrite, both listed as kept targets."""
    from ai_harness.modules.harness import init_repo

    managed = f"{INIT_START}\n\nFollow the repo's `CODING_STANDARDS.md`.\n\n{INIT_END}\n"
    (tmp_path / CLAUDE_MD).write_text(managed, encoding="utf-8")
    (tmp_path / AGENTS_MD).write_text(managed, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_init_block is False
    assert result.init_block_targets == (CLAUDE_MD, AGENTS_MD)
    assert (tmp_path / CLAUDE_MD).read_text(encoding="utf-8") == managed
    assert (tmp_path / AGENTS_MD).read_text(encoding="utf-8") == managed


def test_init_repo_writes_only_missing_when_only_one_has_new_markers(tmp_path: Path) -> None:
    """CLAUDE.md has new markers, AGENTS.md missing → only AGENTS.md is written (the kept CLAUDE.md still appears in targets)."""
    from ai_harness.modules.harness import init_repo

    claude_original = f"{INIT_START}\n\nManaged body.\n\n{INIT_END}\n"
    (tmp_path / CLAUDE_MD).write_text(claude_original, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_init_block is True
    assert result.init_block_targets == (CLAUDE_MD, AGENTS_MD)
    assert (tmp_path / CLAUDE_MD).read_text(encoding="utf-8") == claude_original
    assert INIT_START in (tmp_path / AGENTS_MD).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# init_repo — legacy block migration
# ---------------------------------------------------------------------------


def test_init_repo_migrates_minimal_legacy_block(tmp_path: Path) -> None:
    """A CLAUDE.md containing only the legacy block is swapped for the new init block."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    legacy_only = (
        f"{LEGACY_START}\n\n## Loop label policy\n\nOld body.\n\n{LEGACY_END}\n"
    )
    claude.write_text(legacy_only, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_init_block is True
    content = claude.read_text(encoding="utf-8")
    assert INIT_START in content
    assert INIT_END in content
    assert LEGACY_START not in content
    assert LEGACY_END not in content
    # Body now references CODING_STANDARDS.md (not the old label policy).
    assert "CODING_STANDARDS.md" in content
    assert "Loop label policy" not in content


def test_init_repo_migration_preserves_user_prefix_and_suffix(tmp_path: Path) -> None:
    """User content above and below the legacy block survives byte-identical after migration."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    original = (
        "prefix line\n"
        f"{LEGACY_START}\n\n## Loop label policy\n\nOld body.\n\n{LEGACY_END}\n"
        "suffix line\n"
    )
    claude.write_text(original, encoding="utf-8")

    result = init_repo(tmp_path)

    assert result.wrote_init_block is True
    content = claude.read_text(encoding="utf-8")
    # Prefix and suffix survive byte-identical.
    assert content.startswith("prefix line\n")
    assert content.endswith("\nsuffix line\n")
    # New init markers are present, legacy markers are absent.
    assert INIT_START in content
    assert INIT_END in content
    assert LEGACY_START not in content
    assert LEGACY_END not in content


def test_init_repo_migration_handles_both_files(tmp_path: Path) -> None:
    """Both files with legacy blocks are migrated independently in deterministic order."""
    from ai_harness.modules.harness import init_repo

    (tmp_path / CLAUDE_MD).write_text(
        f"# Claude\n\n{LEGACY_START}\n\nOld.\n\n{LEGACY_END}\n", encoding="utf-8"
    )
    (tmp_path / AGENTS_MD).write_text(
        f"# Agents\n\n{LEGACY_START}\n\nOld.\n\n{LEGACY_END}\n", encoding="utf-8"
    )

    result = init_repo(tmp_path)

    assert result.wrote_init_block is True
    assert result.init_block_targets == (CLAUDE_MD, AGENTS_MD)
    for name in (CLAUDE_MD, AGENTS_MD):
        c = (tmp_path / name).read_text(encoding="utf-8")
        assert INIT_START in c
        assert INIT_END in c
        assert LEGACY_START not in c
        assert LEGACY_END not in c


def test_init_repo_new_markers_take_precedence_over_legacy(tmp_path: Path) -> None:
    """If both new and legacy markers happen to coexist, the new-marker skip branch wins."""
    from ai_harness.modules.harness import init_repo

    claude = tmp_path / CLAUDE_MD
    original = (
        f"{INIT_START}\n\nFollow the repo's `CODING_STANDARDS.md`.\n\n{INIT_END}\n"
        f"\n# A note about {LEGACY_START} appearing in prose.\n"
    )
    claude.write_text(original, encoding="utf-8")
    # Seed AGENTS.md with the new markers so it's also a kept target.
    agents_original = f"{INIT_START}\n\nFollow the repo's `CODING_STANDARDS.md`.\n\n{INIT_END}\n"
    (tmp_path / AGENTS_MD).write_text(agents_original, encoding="utf-8")

    result = init_repo(tmp_path)

    # Both kept — file is left exactly as it was.
    assert result.wrote_init_block is False
    assert result.init_block_targets == (CLAUDE_MD, AGENTS_MD)
    assert claude.read_text(encoding="utf-8") == original
    assert (tmp_path / AGENTS_MD).read_text(encoding="utf-8") == agents_original


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


def test_cli_init_reports_init_block_appended(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ai-harness init`` reports the init block landed when CLAUDE.md exists without markers."""
    monkeypatch.chdir(tmp_path)

    claude = tmp_path / CLAUDE_MD
    claude.write_text("## Agent skills\n", encoding="utf-8")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    assert "Managed init block on" in result.stdout
    assert CLAUDE_MD in result.stdout
    content = claude.read_text(encoding="utf-8")
    assert INIT_START in content
    assert INIT_END in content


def test_cli_init_reports_init_block_already_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ai-harness init`` reports unchanged when both agent docs already have new init markers."""
    monkeypatch.chdir(tmp_path)

    managed = f"{INIT_START}\n\nFollow the repo's `CODING_STANDARDS.md`.\n\n{INIT_END}\n"
    (tmp_path / CLAUDE_MD).write_text(managed, encoding="utf-8")
    (tmp_path / AGENTS_MD).write_text(managed, encoding="utf-8")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    assert "already present" in result.stdout.lower()
    assert "unchanged" in result.stdout.lower()


def test_cli_init_reports_init_block_appended_to_agents_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ai-harness init`` names AGENTS.md when it receives the init block."""
    monkeypatch.chdir(tmp_path)

    agents = tmp_path / AGENTS_MD
    agents.write_text("# Agent persona\n", encoding="utf-8")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    assert "Managed init block on" in result.stdout
    assert AGENTS_MD in result.stdout
    content = agents.read_text(encoding="utf-8")
    assert INIT_START in content
    assert INIT_END in content


def test_cli_init_no_label_or_gh_references_on_fresh_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ai-harness init`` on a clean directory emits no label / GitHub / gh / Warning strings."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.stderr
    stdout = result.stdout
    stderr = result.stderr
    combined = (stdout + "\n" + stderr).lower()
    for forbidden in ("created github labels", "warning:", "ready-for-agent", "gh cli"):
        assert forbidden not in combined, f"Found forbidden string {forbidden!r} in output:\n{result.stdout!r}\n{result.stderr!r}"


def test_cli_init_idempotent_re_run_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ai-harness init`` exits 0 on an idempotent re-run after the artifacts already exist."""
    monkeypatch.chdir(tmp_path)

    first = runner.invoke(app, ["init"])
    assert first.exit_code == 0, first.stderr

    second = runner.invoke(app, ["init"])
    assert second.exit_code == 0, second.stderr
    assert "already exists" in second.stdout.lower() or "already present" in second.stdout.lower()