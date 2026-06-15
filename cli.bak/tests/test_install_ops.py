"""Filesystem operations: copy, install_one, uninstall_entry.

These primitives are the only layer that touches the filesystem. They
own the rollback discipline and the path-safety contract; the higher
``install``/``uninstall`` orchestration layers stay pure and just compose
these operations over the Config mappings.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.install.manifest import ManifestEntry
from ai_harness.install.ops import (
    ACTION_ABSENT,
    ACTION_COPIED,
    ACTION_OVERWRITTEN,
    ACTION_REMOVED,
    Outcome,
    install_one,
    uninstall_entry,
)

# --- Outcome dataclass -----------------------------------------------------


def test_outcome_default_action_is_empty() -> None:
    out = Outcome(dest="/x", src="/y")
    assert out.action == "" and out.target == ""


# --- install_one: file copy -------------------------------------------------


def test_install_one_copies_a_file(tmp_path: Path) -> None:
    src = tmp_path / "src" / "a.md"
    src.parent.mkdir(parents=True)
    src.write_text("hi", encoding="utf-8")
    dest = tmp_path / "dest" / "a.md"

    outcome, entries = install_one(src, dest)

    assert outcome.action == ACTION_COPIED
    assert outcome.dest == str(dest)
    assert outcome.src == str(src)
    assert dest.read_text(encoding="utf-8") == "hi"
    assert entries == [
        ManifestEntry(dest=str(dest), source=str(src), kind="file"),
    ]


def test_install_one_overwrites_existing_destination(tmp_path: Path) -> None:
    src = tmp_path / "src" / "a.md"
    src.parent.mkdir(parents=True)
    src.write_text("new", encoding="utf-8")
    dest = tmp_path / "dest" / "a.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("old", encoding="utf-8")

    outcome, _ = install_one(src, dest)

    assert outcome.action == ACTION_OVERWRITTEN
    assert dest.read_text(encoding="utf-8") == "new"


def test_install_one_missing_source_returns_error(tmp_path: Path) -> None:
    src = tmp_path / "does-not-exist"
    dest = tmp_path / "dest" / "a.md"
    with pytest.raises(FileNotFoundError, match="missing"):
        install_one(src, dest)
    assert not dest.exists()


def test_install_one_creates_parent_dirs(tmp_path: Path) -> None:
    src = tmp_path / "src" / "a.md"
    src.parent.mkdir(parents=True)
    src.write_text("hi", encoding="utf-8")
    dest = tmp_path / "deep" / "nested" / "a.md"

    install_one(src, dest)

    assert dest.is_file()
    assert dest.parent.is_dir()


# --- install_one: directory copy -------------------------------------------


def test_install_one_copies_a_directory_tree(tmp_path: Path) -> None:
    src = tmp_path / "src_tree"
    (src / "sub").mkdir(parents=True)
    (src / "a.md").write_text("a", encoding="utf-8")
    (src / "sub" / "b.md").write_text("b", encoding="utf-8")
    dest = tmp_path / "dest_tree"

    outcome, entries = install_one(src, dest)

    assert outcome.action == ACTION_COPIED
    assert (dest / "a.md").read_text(encoding="utf-8") == "a"
    assert (dest / "sub" / "b.md").read_text(encoding="utf-8") == "b"
    # Tree expansion produces one manifest entry per copied file.
    dests = sorted(e.dest for e in entries)
    assert dests == [
        str(dest / "a.md"),
        str(dest / "sub" / "b.md"),
    ]


def test_install_one_tree_overwrite_preserves_unmanifested_user_files(
    tmp_path: Path,
) -> None:
    # Pre-existing user files that are not in the source tree must survive
    # a copy that lands in the same dest directory.
    src = tmp_path / "src_tree"
    src.mkdir()
    (src / "owned.md").write_text("owned", encoding="utf-8")
    dest = tmp_path / "dest_tree"
    dest.mkdir()
    (dest / "user.md").write_text("user", encoding="utf-8")

    outcome, entries = install_one(src, dest)

    assert outcome.action == ACTION_OVERWRITTEN
    assert (dest / "owned.md").read_text(encoding="utf-8") == "owned"
    assert (dest / "user.md").read_text(encoding="utf-8") == "user"
    user_dest = str(dest / "user.md")
    assert all(entry.dest != user_dest for entry in entries)


def test_install_one_tree_rollback_on_partial_failure(tmp_path: Path) -> None:
    # A broken symlink as the only file in the source tree forces the copy
    # to fail before producing any output, so the dest tree must stay clean.
    src = tmp_path / "src_tree"
    src.mkdir()
    (src / "broken.md").symlink_to(tmp_path / "no-such-target")
    dest = tmp_path / "dest_tree"

    with pytest.raises((OSError, FileNotFoundError)):
        install_one(src, dest)

    # The dest tree must not exist or be empty: failure leaves no trace.
    if dest.exists():
        assert list(dest.iterdir()) == []


def test_install_one_tree_rolls_back_partial_copies(tmp_path: Path) -> None:
    # Two files in alphabetical order; the second one is a broken symlink so
    # the copy of the first must succeed and then be rolled back when the
    # second fails. This proves rollback does more than skip the failing op.
    src = tmp_path / "src_tree"
    src.mkdir()
    (src / "a-good.md").write_text("good", encoding="utf-8")
    (src / "b-broken.md").symlink_to(tmp_path / "no-such-target")
    dest = tmp_path / "dest_tree"

    with pytest.raises((OSError, FileNotFoundError)):
        install_one(src, dest)

    # Either the dest tree does not exist or it is empty: the a-good.md
    # copy that landed before the b-broken.md failure must be undone.
    if dest.exists():
        assert list(dest.iterdir()) == []


# --- uninstall_entry --------------------------------------------------------


def test_uninstall_entry_removes_a_managed_file(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    target = opencode_dir / "AGENTS.md"
    target.parent.mkdir(parents=True)
    target.write_text("installed", encoding="utf-8")
    entry = ManifestEntry(dest=str(target), kind="file")

    outcome = uninstall_entry(opencode_dir, entry)

    assert outcome.action == ACTION_REMOVED
    assert outcome.dest == str(target)
    assert not target.exists()


def test_uninstall_entry_records_absent_when_missing(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    target = opencode_dir / "AGENTS.md"
    target.parent.mkdir(parents=True)
    entry = ManifestEntry(dest=str(target), kind="file")

    outcome = uninstall_entry(opencode_dir, entry)

    assert outcome.action == ACTION_ABSENT
    assert outcome.dest == str(target)


def test_uninstall_entry_rejects_unsafe_entry(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    entry = ManifestEntry(dest=str(outside), kind="file")

    with pytest.raises(ValueError, match="outside"):
        uninstall_entry(opencode_dir, entry)
    # The unsafe file must remain untouched.
    assert outside.read_text(encoding="utf-8") == "keep"


def test_uninstall_entry_rejects_directory_kind(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)
    target = opencode_dir / "skills"
    target.mkdir()
    (target / "leaf.txt").write_text("keep", encoding="utf-8")
    entry = ManifestEntry(dest=str(target), kind="file")

    with pytest.raises(ValueError, match="not a regular file"):
        uninstall_entry(opencode_dir, entry)
    # The directory's contents must remain untouched.
    assert (target / "leaf.txt").read_text(encoding="utf-8") == "keep"


def test_uninstall_entry_validates_atomically(tmp_path: Path) -> None:
    # When the first entry is safe and the second unsafe, the safe file
    # must NOT be removed before the unsafe check fires.
    opencode_dir = tmp_path / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)
    safe = opencode_dir / "AGENTS.md"
    safe.write_text("keep", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("keep outside", encoding="utf-8")

    safe_entry = ManifestEntry(dest=str(safe), kind="file")
    unsafe_entry = ManifestEntry(dest=str(outside), kind="file")

    # First entry alone succeeds.
    uninstall_entry(opencode_dir, safe_entry)
    assert not safe.exists()
    # Then validate the unsafe entry before any further mutation.
    with pytest.raises(ValueError):
        uninstall_entry(opencode_dir, unsafe_entry)
    assert outside.read_text(encoding="utf-8") == "keep outside"


# --- uninstall_entry: preserves pre-existing harness root directories --------


def test_uninstall_preserves_pre_existing_claude_root(tmp_path: Path) -> None:
    # When a file under the home-anchored .claude harness root is uninstalled,
    # the cleanup must stop at .claude/ and never remove a pre-existing root
    # directory the user owned before ai-harness.
    opencode_dir = tmp_path / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)
    claude_root = tmp_path / ".claude"
    claude_skills = claude_root / "skills"
    claude_skills.mkdir(parents=True)
    skill_file = claude_skills / "some_skill.md"
    skill_file.write_text("installed", encoding="utf-8")

    entry = ManifestEntry(dest=str(skill_file), kind="file")

    outcome = uninstall_entry(opencode_dir, entry)

    assert outcome.action == ACTION_REMOVED
    assert not skill_file.exists()
    # The empty skills/ directory may be cleaned up.
    assert not claude_skills.exists()
    # But the pre-existing .claude/ root must survive.
    assert claude_root.exists(), "pre-existing .claude/ root was removed"


def test_uninstall_preserves_pre_existing_agents_root(tmp_path: Path) -> None:
    # Same protection for the .agents harness root.
    opencode_dir = tmp_path / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)
    agents_root = tmp_path / ".agents"
    agents_skills = agents_root / "skills"
    agents_skills.mkdir(parents=True)
    skill_file = agents_skills / "some_skill.md"
    skill_file.write_text("installed", encoding="utf-8")

    entry = ManifestEntry(dest=str(skill_file), kind="file")

    outcome = uninstall_entry(opencode_dir, entry)

    assert outcome.action == ACTION_REMOVED
    assert not skill_file.exists()
    assert not agents_skills.exists()
    assert agents_root.exists(), "pre-existing .agents/ root was removed"


def test_uninstall_preserves_pre_existing_copilot_root(tmp_path: Path) -> None:
    # Same protection for the .copilot harness root.
    opencode_dir = tmp_path / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)
    copilot_root = tmp_path / ".copilot"
    copilot_skills = copilot_root / "skills"
    copilot_skills.mkdir(parents=True)
    skill_file = copilot_skills / "some_skill.md"
    skill_file.write_text("installed", encoding="utf-8")

    entry = ManifestEntry(dest=str(skill_file), kind="file")

    outcome = uninstall_entry(opencode_dir, entry)

    assert outcome.action == ACTION_REMOVED
    assert not skill_file.exists()
    assert not copilot_skills.exists()
    assert copilot_root.exists(), "pre-existing .copilot/ root was removed"


# --- uninstall_entry: rejects parent-directory symlink escape ----------------


def test_uninstall_entry_rejects_parent_symlink_pointing_outside(
    tmp_path: Path,
) -> None:
    """uninstall_entry must reject a manifest entry whose parent directory
    is a symlink outside managed roots, without removing the outside file.

    This proves the validator check propagates through uninstall_entry
    and is NOT defeated by the Path.unlink() call following the symlink.
    """
    opencode_dir = tmp_path / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)

    # Place a file outside all managed roots.
    outside_dir = tmp_path / "outside_ops"
    outside_dir.mkdir()
    outside_file = outside_dir / "keep.txt"
    outside_file.write_text("outside content", encoding="utf-8")

    # Symlink inside the managed root pointing to the outside directory.
    link = opencode_dir / "escape_link"
    link.symlink_to(outside_dir, target_is_directory=True)

    target_via_link = link / "keep.txt"
    entry = ManifestEntry(dest=str(target_via_link), kind="file")

    with pytest.raises(ValueError, match="parent"):
        uninstall_entry(opencode_dir, entry)

    # The outside file must survive.
    assert outside_file.read_text(encoding="utf-8") == "outside content"


# --- install_one: rollback on partial write ---------------------------------


def test_install_one_rolls_back_partial_file_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    """Pre-existing destination file must be restored when _write_file fails.

    Regression: install_one had no rollback around _write_file for single
    files.  If _write_file partially overwrote the destination and then
    raised, the original content was permanently lost.
    """
    from ai_harness.install import ops

    # Source file with "new" content.
    src = tmp_path / "src" / "a.md"
    src.parent.mkdir(parents=True)
    src.write_text("new content that is longer than original", encoding="utf-8")

    # Pre-existing destination with "original" content.
    dest = tmp_path / "dest" / "a.md"
    dest.parent.mkdir(parents=True)
    original_content = "original"
    dest.write_text(original_content, encoding="utf-8")

    # Fault-inject: _write_file partially overwrites dest then raises.
    def _failing_write_file(s, d):
        # Truncate and write partial content to simulate mid-write failure.
        d.write_text("partial", encoding="utf-8")
        raise OSError("simulated write failure")

    monkeypatch.setattr(ops, "_write_file", _failing_write_file)

    with pytest.raises(OSError, match="simulated write failure"):
        install_one(src, dest)

    # The pre-existing destination must be restored to its original content.
    restored = dest.read_text(encoding="utf-8")
    assert restored == original_content, (
        f"Expected original content {original_content!r}, got {restored!r}"
    )


def test_install_one_rolls_back_nonexistent_dest_on_partial_write(
    tmp_path: Path, monkeypatch
) -> None:
    """When dest didn't exist before, a failed write must leave it absent."""
    from ai_harness.install import ops

    src = tmp_path / "src" / "a.md"
    src.parent.mkdir(parents=True)
    src.write_text("new content", encoding="utf-8")

    dest = tmp_path / "dest" / "a.md"

    def _failing_write_file(s, d):
        d.write_text("partial", encoding="utf-8")
        raise OSError("simulated write failure")

    monkeypatch.setattr(ops, "_write_file", _failing_write_file)

    with pytest.raises(OSError, match="simulated write failure"):
        install_one(src, dest)

    # Since dest did not pre-exist, it should be removed after failure.
    assert not dest.exists(), (
        "Dest file created by partial write must be cleaned up"
    )


# --- _copy_tree: rollback on partial write -----------------------------------


def test_copy_tree_rolls_back_pre_existing_file_after_partial_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    """Pre-existing file in dest tree must be restored when _write_file fails
    after partially overwriting it.

    Regression: _copy_tree appended to the rollback list AFTER _write_file
    succeeded.  If _write_file partially mutated an existing dest file and
    then raised, the rollback had no record of the file and could not
    restore it.
    """
    from ai_harness.install import ops

    # Source tree with one file.
    src_tree = tmp_path / "src_tree"
    src_tree.mkdir()
    (src_tree / "managed.md").write_text("new managed content", encoding="utf-8")

    # Pre-existing destination tree with a file at the same path.
    dest_tree = tmp_path / "dest_tree"
    dest_tree.mkdir()
    original_content = "original managed content before install"
    (dest_tree / "managed.md").write_text(original_content, encoding="utf-8")

    # Fault-inject: _write_file partially overwrites then raises.
    def _failing_write_file(s, d):
        d.write_text("partial trash", encoding="utf-8")
        raise OSError("simulated disk full during copy")

    monkeypatch.setattr(ops, "_write_file", _failing_write_file)

    with pytest.raises(OSError, match="simulated disk full"):
        install_one(src_tree, dest_tree)

    # The pre-existing file must be restored.
    restored = (dest_tree / "managed.md").read_text(encoding="utf-8")
    assert restored == original_content, (
        f"Expected {original_content!r}, got {restored!r}"
    )


def test_copy_tree_rolls_back_new_file_after_partial_write_failure(
    tmp_path: Path, monkeypatch
) -> None:
    """New file created during tree copy must be removed if _write_file fails
    after writing partial content (the file didn't pre-exist).
    """
    from ai_harness.install import ops

    src_tree = tmp_path / "src_tree"
    src_tree.mkdir()
    (src_tree / "newfile.md").write_text("new content", encoding="utf-8")

    dest_tree = tmp_path / "dest_tree"
    # dest does NOT pre-exist — install_one will create it.

    def _failing_write_file(s, d):
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text("partial trash", encoding="utf-8")
        raise OSError("simulated write failure for new file")

    monkeypatch.setattr(ops, "_write_file", _failing_write_file)

    with pytest.raises(OSError):
        install_one(src_tree, dest_tree)

    # The dest tree must be clean: either it doesn't exist at all, or it
    # is empty (no partial file left behind).
    if dest_tree.exists():
        remaining = list(dest_tree.rglob("*"))
        assert len(remaining) == 0, (
            f"Partial file left behind: {remaining}"
        )
