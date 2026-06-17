"""Unit tests for the generic installer module — backup/restore/conflict-rotation.

Exercises install(manifest, home, console) and uninstall(manifest, home, console)
using tmp_path as the simulated HOME directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from ai_harness.artifacts.installer import install, uninstall
from ai_harness.artifacts.manifest import (
    ArtifactManifest,
    ComposedFileArtifact,
    DirArtifact,
    FileArtifact,
)


@pytest.fixture
def console() -> Console:
    return Console(force_terminal=True, width=120, no_color=True)


# ------------------------------------------------------------------ install ---


def test_fresh_file_install_no_backup(tmp_path: Path, console: Console) -> None:
    """Fresh file install: target doesn't exist → copy source; no backup."""
    src = tmp_path / "src.md"
    src.write_text("# content\n", encoding="utf-8")
    target_relative = Path(".config/target.md")

    manifest = ArtifactManifest(
        files=[FileArtifact(source=src, target_relative=target_relative)],
        dirs=[],
    )

    home = tmp_path / "home"
    home.mkdir()
    install(manifest, home, console)

    target = home / target_relative
    assert target.read_text(encoding="utf-8") == "# content\n"
    backup = home / (str(target_relative) + ".ai-harness-backup")
    assert not backup.exists()


def test_conflicting_file_is_backed_up(tmp_path: Path, console: Console) -> None:
    """Conflicting file: target exists with different content → back it up, overwrite."""
    src = tmp_path / "src.md"
    src.write_text("# project content\n", encoding="utf-8")
    target_relative = Path(".config/target.md")

    home = tmp_path / "home"
    target_path = home / target_relative
    target_path.parent.mkdir(parents=True)
    target_path.write_text("# user content\n", encoding="utf-8")

    manifest = ArtifactManifest(
        files=[FileArtifact(source=src, target_relative=target_relative)],
        dirs=[],
    )

    install(manifest, home, console)

    assert target_path.read_text(encoding="utf-8") == "# project content\n"
    backup = home / (str(target_relative) + ".ai-harness-backup")
    assert backup.read_text(encoding="utf-8") == "# user content\n"


def test_repeated_conflict_rotates_backup(tmp_path: Path, console: Console) -> None:
    """Repeated conflict: a second reinstall after user modification
    rotates to the conflict suffix with numeric fallback."""
    src = tmp_path / "src.md"
    src.write_text("# project content\n", encoding="utf-8")
    target_relative = Path(".config/target.md")

    home = tmp_path / "home"
    target_path = home / target_relative
    target_path.parent.mkdir(parents=True)
    target_path.write_text("# original user\n", encoding="utf-8")

    manifest = ArtifactManifest(
        files=[FileArtifact(source=src, target_relative=target_relative)],
        dirs=[],
    )

    # First install: creates backup from original user content.
    install(manifest, home, console)
    backup = home / (str(target_relative) + ".ai-harness-backup")
    assert backup.read_text(encoding="utf-8") == "# original user\n"

    # User modifies the target again.
    target_path.write_text("# modified user\n", encoding="utf-8")

    # Second install: backup already exists → rotate to conflict backup.
    install(manifest, home, console)
    conflict = home / (str(target_relative) + ".ai-harness-conflict-backup")
    assert conflict.read_text(encoding="utf-8") == "# modified user\n"
    # Original backup still intact.
    assert backup.read_text(encoding="utf-8") == "# original user\n"

    # Third install after another modification → .1
    target_path.write_text("# modified user 2\n", encoding="utf-8")
    install(manifest, home, console)
    conflict_1 = home / (str(target_relative) + ".ai-harness-conflict-backup.1")
    assert conflict_1.read_text(encoding="utf-8") == "# modified user 2\n"
    assert conflict.read_text(encoding="utf-8") == "# modified user\n"


def test_same_content_triggers_no_backup(tmp_path: Path, console: Console) -> None:
    """When target already has identical content, no backup is created and
    target is left as-is (idempotent install)."""
    src = tmp_path / "src.md"
    src.write_text("# content\n", encoding="utf-8")
    target_relative = Path(".config/target.md")

    home = tmp_path / "home"
    target_path = home / target_relative
    target_path.parent.mkdir(parents=True)
    target_path.write_text("# content\n", encoding="utf-8")

    manifest = ArtifactManifest(
        files=[FileArtifact(source=src, target_relative=target_relative)],
        dirs=[],
    )

    install(manifest, home, console)
    backup = home / (str(target_relative) + ".ai-harness-backup")
    assert not backup.exists()


def test_template_substitution(tmp_path: Path, console: Console) -> None:
    """Template placeholders in source are replaced before writing to target."""
    src = tmp_path / "template.json"
    src.write_text('{"home": "{{HOME}}", "static": "val"}\n', encoding="utf-8")
    target_relative = Path(".config/config.json")

    home = tmp_path / "home"
    home.mkdir()

    manifest = ArtifactManifest(
        files=[
            FileArtifact(
                source=src,
                target_relative=target_relative,
                template={"{{HOME}}": str(home)},
            )
        ],
        dirs=[],
    )

    install(manifest, home, console)

    target = home / target_relative
    expected = src.read_text(encoding="utf-8").replace("{{HOME}}", str(home))
    assert target.read_text(encoding="utf-8") == expected


def test_dir_artifact_replace_matching(tmp_path: Path, console: Console) -> None:
    """DirArtifact copies source subdirs, removing the matching target
    subdir first while leaving unrelated entries intact."""
    src_dir = tmp_path / "prompts"
    (src_dir / "a.md").parent.mkdir(parents=True)
    (src_dir / "a.md").write_text("# a\n", encoding="utf-8")
    (src_dir / "b.md").write_text("# b\n", encoding="utf-8")

    home = tmp_path / "home"
    target_dir = home / ".config" / "prompts"
    # Pre-create a stale "a.md" at target.
    target_dir.mkdir(parents=True)
    (target_dir / "a.md").write_text("# stale a\n", encoding="utf-8")
    # Also a custom unrelated file that should survive.
    (target_dir / "custom.md").write_text("# custom\n", encoding="utf-8")

    manifest = ArtifactManifest(
        files=[],
        dirs=[DirArtifact(source=src_dir, target_relative=Path(".config/prompts"))],
    )

    install(manifest, home, console)

    assert (target_dir / "a.md").read_text(encoding="utf-8") == "# a\n"
    assert (target_dir / "b.md").read_text(encoding="utf-8") == "# b\n"
    assert (target_dir / "custom.md").read_text(encoding="utf-8") == "# custom\n"


# ---------------------------------------------------------------- uninstall ---


def test_matching_content_removed_backup_restored(tmp_path: Path, console: Console) -> None:
    """Uninstall: matching content removed, backup restored to original path."""
    src = tmp_path / "src.md"
    src.write_text("# project content\n", encoding="utf-8")
    target_relative = Path(".config/target.md")

    home = tmp_path / "home"
    target_path = home / target_relative
    target_path.parent.mkdir(parents=True)
    target_path.write_text("# project content\n", encoding="utf-8")

    # Simulate a backup from a prior install-over-conflict.
    backup = home / (str(target_relative) + ".ai-harness-backup")
    backup.write_text("# user original\n", encoding="utf-8")

    manifest = ArtifactManifest(
        files=[FileArtifact(source=src, target_relative=target_relative)],
        dirs=[],
    )

    uninstall(manifest, home, console)

    # After restore, the target path should exist with the backup's content.
    assert target_path.read_text(encoding="utf-8") == "# user original\n"
    assert not backup.exists()


def test_modified_content_preserved(tmp_path: Path, console: Console) -> None:
    """Uninstall: modified target (content differs from source) is NOT removed."""
    src = tmp_path / "src.md"
    src.write_text("# project content\n", encoding="utf-8")
    target_relative = Path(".config/target.md")

    home = tmp_path / "home"
    target_path = home / target_relative
    target_path.parent.mkdir(parents=True)
    target_path.write_text("# user modified\n", encoding="utf-8")

    backup = home / (str(target_relative) + ".ai-harness-backup")
    backup.write_text("# user original\n", encoding="utf-8")

    manifest = ArtifactManifest(
        files=[FileArtifact(source=src, target_relative=target_relative)],
        dirs=[],
    )

    uninstall(manifest, home, console)

    assert target_path.read_text(encoding="utf-8") == "# user modified\n"
    assert backup.read_text(encoding="utf-8") == "# user original\n"


def test_idempotent_uninstall(tmp_path: Path, console: Console) -> None:
    """Uninstall on clean directory succeeds with no errors."""
    src = tmp_path / "src.md"
    src.write_text("# content\n", encoding="utf-8")
    target_relative = Path(".config/target.md")

    home = tmp_path / "home"
    home.mkdir()

    manifest = ArtifactManifest(
        files=[FileArtifact(source=src, target_relative=target_relative)],
        dirs=[],
    )

    # Should not raise, and everything stays as it was.
    uninstall(manifest, home, console)
    assert not (home / target_relative).exists()


# ------------------------------------------------------- ComposedFileArtifact ---


def test_composed_install_writes_frontmatter_and_body(tmp_path: Path, console: Console) -> None:
    """ComposedFileArtifact install produces frontmatter + --- + body."""
    body = tmp_path / "body.md"
    body.write_text("body content here", encoding="utf-8")

    target_rel = Path(".claude/agents/sdd-apply.md")
    artifact = ComposedFileArtifact(
        frontmatter_text="---\nname: test\n---\n",
        body_source=body,
        target_relative=target_rel,
    )
    manifest = ArtifactManifest(composed=[artifact])

    install(manifest, tmp_path, console)

    target = tmp_path / target_rel
    # _prepare_composed_content uses frontmatter.rstrip("\n") + "\n---\n" + body
    assert target.read_text(encoding="utf-8") == ("---\nname: test\n---\nbody content here")


def test_composed_install_rotates_existing_target_to_backup(tmp_path: Path, console: Console) -> None:
    """ComposedFileArtifact install backs up a different-content target before overwriting."""
    body = tmp_path / "body.md"
    body.write_text("new body", encoding="utf-8")

    target_rel = Path(".claude/agents/sdd-apply.md")
    target = tmp_path / target_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("OLD USER CONTENT — must be backed up", encoding="utf-8")

    artifact = ComposedFileArtifact(
        frontmatter_text="---\nname: test\n---\n",
        body_source=body,
        target_relative=target_rel,
    )
    manifest = ArtifactManifest(composed=[artifact])

    install(manifest, tmp_path, console)

    backup = tmp_path / (str(target_rel) + ".ai-harness-backup")
    assert backup.exists(), "backup should have been created"
    assert backup.read_text(encoding="utf-8") == ("OLD USER CONTENT — must be backed up")
    assert target.read_text(encoding="utf-8") == ("---\nname: test\n---\nnew body")


def test_composed_uninstall_removes_matching_target(tmp_path: Path, console: Console) -> None:
    """ComposedFileArtifact uninstall removes a target whose content matches the composed output."""
    body = tmp_path / "body.md"
    body.write_text("body content", encoding="utf-8")

    target_rel = Path(".claude/agents/sdd-apply.md")
    target = tmp_path / target_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    # Match the composed output exactly (using rstrip join as the installer does).
    target.write_text(
        "---\nname: test\n---\nbody content",
        encoding="utf-8",
    )

    artifact = ComposedFileArtifact(
        frontmatter_text="---\nname: test\n---\n",
        body_source=body,
        target_relative=target_rel,
    )
    manifest = ArtifactManifest(composed=[artifact])

    uninstall(manifest, tmp_path, console)

    assert not target.exists(), "matching target should have been removed by uninstall"


def test_composed_uninstall_restores_backup(tmp_path: Path, console: Console) -> None:
    """ComposedFileArtifact uninstall restores a backup when target is removed and backup exists."""
    body = tmp_path / "body.md"
    body.write_text("body content", encoding="utf-8")

    target_rel = Path(".claude/agents/sdd-apply.md")
    target = tmp_path / target_rel
    backup = tmp_path / (str(target_rel) + ".ai-harness-backup")
    # Target is gone (already removed). Backup holds the original user content.
    target.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("USER ORIGINAL", encoding="utf-8")

    artifact = ComposedFileArtifact(
        frontmatter_text="---\nname: test\n---\n",
        body_source=body,
        target_relative=target_rel,
    )
    manifest = ArtifactManifest(composed=[artifact])

    uninstall(manifest, tmp_path, console)

    assert target.exists(), "target should have been restored from backup"
    assert target.read_text(encoding="utf-8") == "USER ORIGINAL"


# ------------------------------------------------------- return contract ---


def test_install_returns_install_result(tmp_path: Path, console: Console) -> None:
    """install() returns an InstallResult, not None."""
    src = tmp_path / "src.md"
    src.write_text("# content\n", encoding="utf-8")
    manifest = ArtifactManifest(
        files=[FileArtifact(source=src, target_relative=Path(".config/target.md"))],
        dirs=[],
    )
    home = tmp_path / "home"
    home.mkdir()

    from ai_harness.artifacts.installer import InstallResult

    result = install(manifest, home, console)
    assert isinstance(result, InstallResult), f"Expected InstallResult, got {type(result).__name__}"


def test_install_result_success_fields(tmp_path: Path, console: Console) -> None:
    """InstallResult has success: bool and errors: list[str] on success."""
    src = tmp_path / "src.md"
    src.write_text("# content\n", encoding="utf-8")
    manifest = ArtifactManifest(
        files=[FileArtifact(source=src, target_relative=Path(".config/target.md"))],
        dirs=[],
    )
    home = tmp_path / "home"
    home.mkdir()

    result = install(manifest, home, console)
    assert result.success is True
    assert result.errors == []
