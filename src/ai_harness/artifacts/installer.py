"""Deep module — generic I/O policy for installing/uninstalling artifacts.

install(manifest, home, console) and uninstall(manifest, home, console)
hide backup, conflict rotation, template substitution, and file I/O.
Callers describe *what* to place; this module decides *how*.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console

from ai_harness.artifacts.manifest import (
    ArtifactManifest,
    ComposedFileArtifact,
    DirArtifact,
    FileArtifact,
)


def _next_available_path(path: Path) -> Path:
    """Find the next unused path by appending ``.N`` suffixes."""
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.name}.{index}")
        if not candidate.exists():
            return candidate
        index += 1


def _prepare_content(artifact: FileArtifact, home: Path) -> str:
    """Read source and apply template substitution (if any)."""
    text = artifact.source.read_text(encoding="utf-8")
    if artifact.template:
        for placeholder, replacement in artifact.template.items():
            text = text.replace(placeholder, replacement)
    return text


def _prepare_composed_content(artifact: ComposedFileArtifact, home: Path) -> str:
    """Read frontmatter and body sources, return concatenated text.

    Produces ``frontmatter + "\\n---\\n" + body`` verbatim.  Template
    substitution is applied to the FULL composed result (not to the
    frontmatter or body individually).
    """
    frontmatter = artifact.frontmatter_source.read_text(encoding="utf-8")
    body = artifact.body_source.read_text(encoding="utf-8")
    text = frontmatter.rstrip("\n") + "\n---\n" + body
    if artifact.template:
        for placeholder, replacement in artifact.template.items():
            text = text.replace(placeholder, replacement)
    return text


def install(manifest: ArtifactManifest, home: Path, console: Console) -> None:
    """Install every artifact in *manifest* into *home*."""

    # --- FileArtifact ---
    for artifact in manifest.files:
        target = home / artifact.target_relative
        target.parent.mkdir(parents=True, exist_ok=True)

        prepared = _prepare_content(artifact, home)

        if target.exists() and target.read_text(encoding="utf-8") != prepared:
            backup = home / (str(artifact.target_relative) + artifact.backup_suffix)
            if not backup.exists():
                shutil.copyfile(target, backup)
                console.print(f"Backed up {target} to {backup}")
            else:
                conflict = home / (str(artifact.target_relative) + artifact.conflict_suffix)
                conflict = _next_available_path(conflict)
                shutil.copyfile(target, conflict)
                console.print(f"Backed up {target} to {conflict}")

        target.write_text(prepared, encoding="utf-8")
        console.print(f"Installed {target}")

    # --- ComposedFileArtifact ---
    for artifact in manifest.composed:
        target = home / artifact.target_relative
        target.parent.mkdir(parents=True, exist_ok=True)

        prepared = _prepare_composed_content(artifact, home)

        if target.exists() and target.read_text(encoding="utf-8") != prepared:
            backup = home / (str(artifact.target_relative) + artifact.backup_suffix)
            if not backup.exists():
                shutil.copyfile(target, backup)
                console.print(f"Backed up {target} to {backup}")
            else:
                conflict = home / (str(artifact.target_relative) + artifact.conflict_suffix)
                conflict = _next_available_path(conflict)
                shutil.copyfile(target, conflict)
                console.print(f"Backed up {target} to {conflict}")

        target.write_text(prepared, encoding="utf-8")
        console.print(f"Installed {target}")

    # --- DirArtifact ---
    for artifact in manifest.dirs:
        target_dir = home / artifact.target_relative
        target_dir.mkdir(parents=True, exist_ok=True)

        if artifact.merge_mode == "replace_matching":
            for source_entry in artifact.source.iterdir():
                if source_entry.is_dir():
                    target_sub = target_dir / source_entry.name
                    if target_sub.exists():
                        shutil.rmtree(target_sub)
                    shutil.copytree(source_entry, target_sub)
                elif source_entry.is_file():
                    target_file = target_dir / source_entry.name
                    shutil.copyfile(source_entry, target_file)

        console.print(f"Installed {target_dir}")


def uninstall(manifest: ArtifactManifest, home: Path, console: Console) -> None:
    """Uninstall every artifact in *manifest* from *home*.

    FileArtifact:
        - Remove target when its content matches the prepared source content.
        - Restore the backup (if present) to the target path.
    DirArtifact:
        - Remove target subdirectories that match source subdirectories.
    """

    # --- FileArtifact ---
    for artifact in manifest.files:
        target = home / artifact.target_relative
        prepared = _prepare_content(artifact, home)
        backup = home / (str(artifact.target_relative) + artifact.backup_suffix)

        if target.exists() and target.read_text(encoding="utf-8") == prepared:
            target.unlink()
            console.print(f"Removed {target}")

        if not target.exists() and backup.exists():
            shutil.move(str(backup), str(target))
            console.print(f"Restored {target} from {backup}")

    # --- ComposedFileArtifact ---
    for artifact in manifest.composed:
        target = home / artifact.target_relative
        prepared = _prepare_composed_content(artifact, home)
        backup = home / (str(artifact.target_relative) + artifact.backup_suffix)

        if target.exists() and target.read_text(encoding="utf-8") == prepared:
            target.unlink()
            console.print(f"Removed {target}")

        if not target.exists() and backup.exists():
            shutil.move(str(backup), str(target))
            console.print(f"Restored {target} from {backup}")

    # --- DirArtifact ---
    for artifact in manifest.dirs:
        target_dir = home / artifact.target_relative
        for source_entry in artifact.source.iterdir():
            target_sub = target_dir / source_entry.name
            if target_sub.exists():
                if target_sub.is_dir():
                    shutil.rmtree(target_sub)
                else:
                    target_sub.unlink()
                console.print(f"Removed {target_sub}")
