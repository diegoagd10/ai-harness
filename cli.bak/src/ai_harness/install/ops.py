"""Filesystem operations: copy, install_one, uninstall_entry.

These primitives are the only layer that touches the filesystem. They
own the rollback discipline and the path-safety contract; the higher
``install``/``uninstall`` orchestration layers stay pure and just compose
these operations over the Config mappings.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .manifest import (
    ManifestEntry,
    owned_roots,
    validate_manifest_entry,
)

# Action vocabulary for Outcome.action. Mirrors the Go installer so the CLI
# print path can stay identical regardless of which backend produced the
# report during the migration.
ACTION_COPIED = "copied"
ACTION_OVERWRITTEN = "overwritten"
ACTION_SOURCE_MISSING = "source missing"
ACTION_REMOVED = "removed"
ACTION_ABSENT = "absent"


@dataclass
class Outcome:
    """Per-target install/uninstall result.

    ``dest`` is the destination path the operation acted on, ``src`` is the
    repo path it was copied from (install only), ``action`` is the verb the
    CLI prints, and ``target`` is an optional secondary location for
    rendering (kept for parity with the Go install package).
    """

    dest: str
    src: str = ""
    action: str = ""
    target: str = ""


def _action_for(dest: Path) -> str:
    return ACTION_OVERWRITTEN if dest.exists() else ACTION_COPIED


def _write_file(src: Path, dest: Path) -> None:
    """Copy ``src`` to ``dest`` preserving source permissions."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_symlink() or not src.is_file():
        # shutil.copy2 follows symlinks, but we still want a regular file at
        # dest. Using copyfile (no metadata) keeps the install copy simple.
        shutil.copyfile(src, dest)
        os.chmod(dest, 0o644)
    else:
        shutil.copy2(src, dest, follow_symlinks=True)
        mode = src.stat().st_mode & 0o777
        os.chmod(dest, mode or 0o644)


def _copy_tree(src: Path, dest: Path) -> tuple[list[ManifestEntry], str]:
    """Copy a directory tree with rollback on failure.

    Tracks every file the copy created/overwrote and the directories it
    created so a failure mid-walk can undo the partial work. Files that
    pre-existed are restored to their original bytes; files that did not
    pre-exist are removed; newly created directories are removed only when
    they end up empty (we never delete dirs the user owned before).
    """
    src_root = src.resolve()
    dest_root = dest.resolve()
    pre_existing_top = dest_root.exists()
    created_dirs: list[Path] = []
    file_changes: list[tuple[Path, bytes | None, int]] = []
    try:
        if not pre_existing_top:
            dest_root.mkdir(parents=True, exist_ok=False)
            created_dirs.append(dest_root)
        # Sort entries so the rollback order is deterministic and so tests
        # that rely on alphabetical order see a stable copy sequence.
        paths: list[Path] = []
        for root, _dirs, files in os.walk(src_root, followlinks=False):
            root_path = Path(root)
            for name in sorted(files):
                paths.append(root_path / name)
        for source_path in paths:
            relative = source_path.relative_to(src_root)
            target_path = dest_root / relative
            if target_path.parent != dest_root and target_path.parent not in created_dirs:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                created_dirs.append(target_path.parent)
            previous = _snapshot(target_path)
            mode = _mode_of(source_path)
            # Record the file BEFORE writing so rollback can restore it
            # even when _write_file fails after partially mutating the
            # destination (e.g. disk full mid-write).
            file_changes.append((target_path, previous, mode))
            try:
                _write_file(source_path, target_path)
            except BaseException:
                _rollback(file_changes, created_dirs, dest_root, pre_existing_top)
                raise
    except BaseException:
        _rollback(file_changes, created_dirs, dest_root, pre_existing_top)
        raise
    entries = [
        ManifestEntry(
            dest=str(path),
            source=str(src_root / path.relative_to(dest_root)),
            kind="file",
        )
        for path, _previous, _mode in file_changes
    ]
    action = ACTION_OVERWRITTEN if pre_existing_top else ACTION_COPIED
    return entries, action


def _snapshot(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def _mode_of(path: Path) -> int:
    try:
        return path.stat().st_mode & 0o777
    except OSError:
        return 0o644


def _rollback(
    file_changes: list[tuple[Path, bytes | None, int]],
    created_dirs: list[Path],
    dest_root: Path,
    pre_existing_top: bool,
) -> None:
    """Best-effort rollback of partial copy work.

    Restores overwritten files to their previous bytes; removes files the
    copy created; and prunes created directories bottom-up when empty.
    Failures during cleanup are swallowed because the original error is
    more important to surface than the rollback noise. When the top-level
    dest pre-existed, we never remove it — only the subdirs we created
    inside it.
    """
    for path, previous, _mode in reversed(file_changes):
        try:
            if previous is None:
                path.unlink()
            else:
                path.write_bytes(previous)
        except OSError:
            pass
    for directory in reversed(created_dirs):
        if directory == dest_root and pre_existing_top:
            continue
        try:
            directory.rmdir()
        except OSError:
            pass


def install_one(src: Path, dest: Path) -> tuple[Outcome, list[ManifestEntry]]:
    """Copy one source tree/file to ``dest``; return the outcome and entries.

    A missing source raises :class:`FileNotFoundError`; a partial copy
    raises its underlying error AFTER rolling back. The returned entries
    are the files the copy created — they form the manifest slice for this
    mapping, not the whole-install manifest.
    """
    outcome = Outcome(dest=str(dest), src=str(src))
    if not src.exists():
        outcome.action = ACTION_SOURCE_MISSING
        raise FileNotFoundError(f"source missing, skipping: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        entries, action = _copy_tree(src, dest)
        outcome.action = action
    else:
        previous = _snapshot(dest)
        try:
            _write_file(src, dest)
        except BaseException:
            # Restore pre-existing content when a write fails after
            # partial mutation; clean up a newly created file.
            if previous is not None:
                try:
                    dest.write_bytes(previous)
                except OSError:
                    pass
            elif dest.exists():
                try:
                    dest.unlink()
                except OSError:
                    pass
            raise
        entries = [ManifestEntry(dest=str(dest), source=str(src), kind="file")]
        outcome.action = ACTION_OVERWRITTEN if previous is not None else ACTION_COPIED
    return outcome, entries


def _cleanup_empty_parents(path: Path, owned_roots: list[Path]) -> None:
    """Remove empty parent directories up to (but not including) any root.

    Stops at the first non-empty directory or at a managed root, so we
    never delete a directory that still has user files.
    """
    cleaned_roots = {root.resolve() for root in owned_roots}
    directory = path.resolve().parent
    while True:
        if directory in cleaned_roots:
            return
        try:
            directory.rmdir()
        except OSError:
            return
        parent = directory.parent
        if parent == directory:
            return
        directory = parent


def uninstall_entry(opencode_dir: Path, entry: ManifestEntry) -> Outcome:
    """Remove one manifest-owned file. Validates the entry first.

    Validation runs before any destructive operation, so an unsafe entry
    fails closed (no removals yet, no partial state). An absent target
    returns an ``absent`` outcome rather than raising — the user expected
    a clean slate and that is what they get.
    """
    safe = validate_manifest_entry(opencode_dir, entry)
    outcome = Outcome(dest=safe.as_posix(), src=entry.source, target=entry.source)
    if not safe.exists():
        outcome.action = ACTION_ABSENT
        return outcome
    safe.unlink()
    outcome.action = ACTION_REMOVED
    _cleanup_empty_parents(safe, owned_roots(opencode_dir))
    return outcome
