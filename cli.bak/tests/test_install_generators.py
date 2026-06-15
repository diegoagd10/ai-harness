"""Generators: render the OpenCode-specific artifacts at install time.

Two outputs come from this module:

- ``opencode.json``: the per-host agent config; written verbatim from the
  canonical source with ``{{HOME}}`` substituted to the real home path.
- slash-command files: per-canonical-source ``*.md`` rendered with the
  OpenCode frontmatter dialect and four body placeholders substituted.

Both are host-injectable: the caller supplies every directory and the
``home`` value, so the generators stay testable against temp dirs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.install.generators import (
    ACTION_ABSENT,
    ACTION_GENERATED,
    ACTION_REMOVED,
    generate_commands,
    generate_opencode_json,
    remove_commands,
    remove_opencode_json,
    render_opencode_frontmatter,
    substitute,
)

# --- substitute (pure) -----------------------------------------------------


def test_substitute_replaces_every_placeholder() -> None:
    body = (
        "You are {{ORCHESTRATOR_AGENT}}.\n"
        "Skills: {{SKILLS_DIR}}\n"
        "Cwd{{CWD_NOTE}}\n"
        "Args: {{ARGS}}\n"
    )
    rendered = substitute(
        body,
        orchestrator_agent="sdd-orchestrator",
        skills_dir="/home/me/.config/opencode/skills",
        cwd_note=" (Electron)",
        args_token="$ARGUMENTS",
    )
    assert "You are sdd-orchestrator." in rendered
    assert "Skills: /home/me/.config/opencode/skills" in rendered
    assert "Cwd (Electron)" in rendered
    assert "Args: $ARGUMENTS" in rendered
    assert "{{" not in rendered


def test_substitute_keeps_unset_placeholders_untouched() -> None:
    # Substitute is intentionally minimal; unknown placeholders stay raw so
    # the user notices the bug rather than silently getting a partial render.
    body = "Keep {{NOT_A_PLACEHOLDER}} intact."
    rendered = substitute(
        body,
        orchestrator_agent="x",
        skills_dir="x",
        cwd_note="x",
        args_token="x",
    )
    assert "{{NOT_A_PLACEHOLDER}}" in rendered


# --- render_opencode_frontmatter ------------------------------------------


def test_render_opencode_frontmatter_emits_description_and_agent() -> None:
    rendered = render_opencode_frontmatter(
        "Continue the next phase", "sdd-orchestrator", subtask=False
    )
    assert rendered.startswith("---\n")
    assert "description: Continue the next phase" in rendered
    assert "agent: sdd-orchestrator" in rendered
    assert "subtask" not in rendered  # False: omit the key.
    assert rendered.endswith("---\n")


def test_render_opencode_frontmatter_includes_subtask_only_when_true() -> None:
    rendered = render_opencode_frontmatter("Do work", "sdd-orchestrator", subtask=True)
    assert "subtask: true" in rendered


# --- generate_opencode_json -----------------------------------------------


def test_generate_opencode_json_substitutes_home_and_writes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "agent-clis" / "opencode").mkdir(parents=True)
    (repo / "agent-clis" / "opencode" / "opencode.json").write_text(
        '{"prompt":"{file:{{HOME}}/.config/opencode/prompts/sdd/x.md}"}',
        encoding="utf-8",
    )
    opencode_dir = tmp_path / "home" / ".config" / "opencode"
    home = str(tmp_path / "home")

    outcome = generate_opencode_json(repo, opencode_dir, home)

    assert outcome.action == ACTION_GENERATED
    assert outcome.dest == opencode_dir / "opencode.json"
    written = (opencode_dir / "opencode.json").read_text(encoding="utf-8")
    assert "{{HOME}}" not in written
    assert f"{{file:{home}/.config/opencode/prompts/sdd/x.md}}" in written


def test_generate_opencode_json_missing_source_raises(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "agent-clis" / "opencode").mkdir(parents=True)
    # No opencode.json source.
    opencode_dir = tmp_path / "home" / ".config" / "opencode"
    with pytest.raises(FileNotFoundError):
        generate_opencode_json(repo, opencode_dir, str(tmp_path / "home"))


# --- remove_opencode_json --------------------------------------------------


def test_remove_opencode_json_records_action(tmp_path: Path) -> None:
    opencode_dir = tmp_path / "home" / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)
    target = opencode_dir / "opencode.json"
    target.write_text("{}", encoding="utf-8")
    outcome = remove_opencode_json(opencode_dir)
    assert outcome.action == ACTION_REMOVED
    assert not target.exists()


def test_remove_opencode_json_marks_absent_when_missing(tmp_path: Path) -> None:
    opencode_dir = tmp_path / "home" / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)
    outcome = remove_opencode_json(opencode_dir)
    assert outcome.action == ACTION_ABSENT
    assert outcome.dest == opencode_dir / "opencode.json"


# --- generate_commands -----------------------------------------------------


def test_generate_commands_writes_one_file_per_source(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    cmd_src = repo / "prompts" / "commands"
    cmd_src.mkdir(parents=True)
    _write_canonical(cmd_src / "sdd-continue.md", "Continue as {{ORCHESTRATOR_AGENT}}.")
    _write_canonical(cmd_src / "sdd-status.md", "Show status of {{ARGS}}.")
    command_dir = tmp_path / "home" / ".config" / "opencode" / "commands"

    outcomes = generate_commands(repo, command_dir)

    assert {o.action for o in outcomes} == {ACTION_GENERATED}
    dests = sorted(o.dest.name for o in outcomes)
    assert dests == ["sdd-continue.md", "sdd-status.md"]
    rendered = (command_dir / "sdd-continue.md").read_text(encoding="utf-8")
    assert "agent: sdd-orchestrator" in rendered
    assert "{{ORCHESTRATOR_AGENT}}" not in rendered
    assert "Continue as sdd-orchestrator." in rendered


def test_generate_commands_emits_subtask_frontmatter_when_canonical_says_so(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    cmd_src = repo / "prompts" / "commands"
    cmd_src.mkdir(parents=True)
    _write_canonical(
        cmd_src / "sdd-apply.md",
        "Apply the change.",
        subtask=True,
    )
    command_dir = tmp_path / "home" / ".config" / "opencode" / "commands"

    [outcome] = generate_commands(repo, command_dir)
    assert outcome.action == ACTION_GENERATED
    rendered = (command_dir / "sdd-apply.md").read_text(encoding="utf-8")
    assert "subtask: true" in rendered


def test_generate_commands_missing_canonical_dir_raises(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    # No prompts/commands directory.
    command_dir = tmp_path / "home" / ".config" / "opencode" / "commands"
    with pytest.raises(FileNotFoundError):
        generate_commands(repo, command_dir)


def test_generate_commands_rejects_malformed_frontmatter(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    cmd_src = repo / "prompts" / "commands"
    cmd_src.mkdir(parents=True)
    (cmd_src / "broken.md").write_text("No frontmatter at all.\n", encoding="utf-8")
    command_dir = tmp_path / "home" / ".config" / "opencode" / "commands"
    with pytest.raises(ValueError, match="frontmatter"):
        generate_commands(repo, command_dir)


# --- remove_commands -------------------------------------------------------


def test_remove_commands_removes_generated_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    cmd_src = repo / "prompts" / "commands"
    cmd_src.mkdir(parents=True)
    _write_canonical(cmd_src / "sdd-status.md", "Show status.")
    command_dir = tmp_path / "home" / ".config" / "opencode" / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "sdd-status.md").write_text("old", encoding="utf-8")

    outcomes = remove_commands(repo, command_dir)

    assert [o.action for o in outcomes] == [ACTION_REMOVED]
    assert not (command_dir / "sdd-status.md").exists()


def test_remove_commands_marks_absent_when_target_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    cmd_src = repo / "prompts" / "commands"
    cmd_src.mkdir(parents=True)
    _write_canonical(cmd_src / "sdd-status.md", "Show status.")
    command_dir = tmp_path / "home" / ".config" / "opencode" / "commands"
    command_dir.mkdir(parents=True)

    outcomes = remove_commands(repo, command_dir)

    assert [o.action for o in outcomes] == [ACTION_ABSENT]


# --- generate_commands rollback on partial failure ------------------------


def test_generate_commands_rolls_back_on_partial_failure(tmp_path: Path) -> None:
    """When one command generates successfully and a later one raises,
    the already-written command file must be removed so no untracked
    files survive the failure.

    Regression: generate_commands wrote files one-by-one with no rollback;
    if a later file had malformed frontmatter, the earlier files were left
    on disk but never tracked in the manifest.
    """
    repo = tmp_path / "repo"
    cmd_src = repo / "prompts" / "commands"
    cmd_src.mkdir(parents=True)
    # First command (alphabetically first): valid — will be written.
    _write_canonical(cmd_src / "a_first.md", "Good body.")
    # Second command (alphabetically second): missing frontmatter — will raise.
    (cmd_src / "z_second.md").write_text("No frontmatter here.\n", encoding="utf-8")
    command_dir = tmp_path / "home" / ".config" / "opencode" / "commands"

    with pytest.raises(ValueError, match="frontmatter"):
        generate_commands(repo, command_dir)

    # The a_first.md file must NOT survive the rollback.
    first_dest = command_dir / "a_first.md"
    assert not first_dest.exists(), (
        f"a_first.md must be rolled back, but found at {first_dest}"
    )


def test_generate_commands_restores_pre_existing_on_rollback(
    tmp_path: Path,
) -> None:
    """When a pre-existing command file is overwritten and a later command
    fails, the pre-existing file must be restored to its original content.
    """
    repo = tmp_path / "repo"
    cmd_src = repo / "prompts" / "commands"
    cmd_src.mkdir(parents=True)
    _write_canonical(cmd_src / "a_first.md", "Good body.")
    (cmd_src / "z_second.md").write_text("No frontmatter here.\n", encoding="utf-8")

    command_dir = tmp_path / "home" / ".config" / "opencode" / "commands"
    command_dir.mkdir(parents=True)

    # Pre-existing file with user content.
    first_dest = command_dir / "a_first.md"
    original_content = "user-crafted original content\n"
    first_dest.write_text(original_content, encoding="utf-8")

    with pytest.raises(ValueError, match="frontmatter"):
        generate_commands(repo, command_dir)

    # The pre-existing file must be restored to its original content.
    restored = first_dest.read_text(encoding="utf-8")
    assert restored == original_content, (
        f"Expected original {original_content!r}, got {restored!r}"
    )


# --- generate_commands rollback on write_text failure (partial mutation) ---


def test_generate_commands_rolls_back_partial_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When write_text mutates a command file partially then raises,
    the already-written but now-corrupted file must be cleaned up
    by rollback, even though the exception happened inside
    _generate_one_command rather than in the caller's loop."""
    repo = tmp_path / "repo"
    cmd_src = repo / "prompts" / "commands"
    cmd_src.mkdir(parents=True)
    _write_canonical(cmd_src / "a_first.md", "Good body.")
    _write_canonical(cmd_src / "z_second.md", "Also good body.")
    command_dir = tmp_path / "home" / ".config" / "opencode" / "commands"

    fail_dest = command_dir / "a_first.md"

    from pathlib import Path as _Path

    original_write_text = _Path.write_text

    def failing_write_text(self: _Path, *args: object, **kwargs: object) -> int:
        if self == fail_dest:
            # Simulate partial mutation: write truncated content,
            # then raise as if the OS failed mid-write.
            with open(str(self), "w", encoding="utf-8") as f:
                f.write("truncated content")
            raise OSError("Simulated partial write failure")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "write_text", failing_write_text)

    with pytest.raises(OSError, match="Simulated partial write failure"):
        generate_commands(repo, command_dir)

    # The partially-written file must NOT survive — rollback must remove it.
    assert not fail_dest.exists(), (
        f"a_first.md must be rolled back after partial write, "
        f"but found at {fail_dest}"
    )


def test_generate_commands_restores_pre_existing_after_partial_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When write_text partially overwrites a pre-existing command file
    then raises, the rollback must restore the original content."""
    repo = tmp_path / "repo"
    cmd_src = repo / "prompts" / "commands"
    cmd_src.mkdir(parents=True)
    _write_canonical(cmd_src / "a_first.md", "Good body.")
    _write_canonical(cmd_src / "z_second.md", "Also good body.")
    command_dir = tmp_path / "home" / ".config" / "opencode" / "commands"
    command_dir.mkdir(parents=True)

    fail_dest = command_dir / "a_first.md"
    original_content = "user-crafted original content\n"
    fail_dest.write_text(original_content, encoding="utf-8")

    from pathlib import Path as _Path

    original_write_text = _Path.write_text

    def failing_write_text(self: _Path, *args: object, **kwargs: object) -> int:
        if self == fail_dest:
            with open(str(self), "w", encoding="utf-8") as f:
                f.write("truncated")
            raise OSError("Simulated partial write failure")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "write_text", failing_write_text)

    with pytest.raises(OSError, match="Simulated partial write failure"):
        generate_commands(repo, command_dir)

    # Pre-existing file must be restored to its original content.
    restored = fail_dest.read_text(encoding="utf-8")
    assert restored == original_content, (
        f"Expected original {original_content!r}, got {restored!r}"
    )


# --- generate_opencode_json rollback on write_text failure -----------------


def test_generate_opencode_json_rolls_back_partial_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When write_text partially mutates opencode.json then raises,
    the partially-written file must be cleaned up by rollback."""
    repo = tmp_path / "repo"
    (repo / "agent-clis" / "opencode").mkdir(parents=True)
    (repo / "agent-clis" / "opencode" / "opencode.json").write_text(
        '{"prompt":"{file:{{HOME}}/.config/opencode/prompts/sdd/x.md}"}',
        encoding="utf-8",
    )
    opencode_dir = tmp_path / "home" / ".config" / "opencode"
    home = str(tmp_path / "home")

    dest = opencode_dir / "opencode.json"

    from pathlib import Path as _Path

    original_write_text = _Path.write_text

    def failing_write_text(self: _Path, *args: object, **kwargs: object) -> int:
        if self == dest:
            # Ensure the parent dir exists so the simulated partial write
            # can create a truncated file, mirroring real partial mutation.
            self.parent.mkdir(parents=True, exist_ok=True)
            with open(str(self), "w", encoding="utf-8") as f:
                f.write("truncated")
            raise OSError("Simulated partial write failure")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "write_text", failing_write_text)

    with pytest.raises(OSError, match="Simulated partial write failure"):
        generate_opencode_json(repo, opencode_dir, home)

    # The partially-written file must NOT survive.
    assert not dest.exists(), (
        f"opencode.json must be rolled back after partial write, "
        f"but found at {dest}"
    )


# --- helpers --------------------------------------------------------------


def _write_canonical(
    path: Path,
    body: str,
    *,
    description: str = "Test command",
    subtask: bool = False,
) -> None:
    frontmatter = (
        f"---\ndescription: {description}\nsubtask: {'true' if subtask else 'false'}\n---\n\n"
    )
    path.write_text(frontmatter + body, encoding="utf-8")
