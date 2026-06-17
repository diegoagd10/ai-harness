"""Deep module — generic I/O policy for installing/uninstalling artifacts.

install(manifest, home, console) and uninstall(manifest, home, console)
hide backup, conflict rotation, template substitution, and file I/O.
Callers describe *what* to place; this module decides *how*.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from ai_harness.artifacts.manifest import (
    ArtifactManifest,
    ComposedFileArtifact,
    FileArtifact,
)


@dataclass
class InstallResult:
    """Outcome of an :func:`install` invocation.

    *success* is ``True`` when every file operation succeeded.  *errors*
    collects human-readable descriptions of any file that could not be
    installed.
    """

    success: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class UninstallResult:
    """Outcome of an :func:`uninstall` invocation."""

    success: bool
    errors: list[str] = field(default_factory=list)


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
    """Read body source and join with frontmatter_text, return concatenated text.

    Produces ``frontmatter_text + "\\n---\\n" + body`` verbatim.  Template
    substitution is applied to the FULL composed result.

    *frontmatter_text* is always required on the artifact.
    """
    frontmatter = artifact.frontmatter_text
    body = artifact.body_source.read_text(encoding="utf-8")
    text = frontmatter.rstrip("\n") + "\n" + body
    if artifact.template:
        for placeholder, replacement in artifact.template.items():
            text = text.replace(placeholder, replacement)
    return text


def _place_file(
    target: Path,
    prepared: str,
    backup_suffix: str,
    conflict_suffix: str,
    console: Console,
) -> None:
    """Write *prepared* to *target*, rotating a backup/conflict copy first.

    When *target* already exists with different content: the first divergent
    install copies it to ``<target><backup_suffix>``; subsequent ones copy to
    the next available ``<target><conflict_suffix>`` path.  Then *prepared* is
    written.  Hides the backup/conflict-rotation policy shared by every
    install loop.
    """
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and target.read_text(encoding="utf-8") != prepared:
        backup = target.with_name(target.name + backup_suffix)
        if not backup.exists():
            shutil.copyfile(target, backup)
            console.print(f"Backed up {target} to {backup}")
        else:
            conflict = target.with_name(target.name + conflict_suffix)
            conflict = _next_available_path(conflict)
            shutil.copyfile(target, conflict)
            console.print(f"Backed up {target} to {conflict}")

    target.write_text(prepared, encoding="utf-8")
    console.print(f"Installed {target}")


def _remove_file(
    target: Path,
    prepared: str,
    backup_suffix: str,
    console: Console,
) -> None:
    """Remove *target* when it matches *prepared*, then restore its backup.

    Mirrors :func:`_place_file`: removes the target only when its content is
    exactly what this installer wrote, then moves any ``<target><backup_suffix>``
    back into place.  Hides the remove-if-match + restore policy shared by
    every uninstall loop.
    """
    backup = target.with_name(target.name + backup_suffix)

    if target.exists() and target.read_text(encoding="utf-8") == prepared:
        target.unlink()
        console.print(f"Removed {target}")

    if not target.exists() and backup.exists():
        shutil.move(str(backup), str(target))
        console.print(f"Restored {target} from {backup}")


def install(manifest: ArtifactManifest, home: Path, console: Console) -> InstallResult:
    """Install every artifact in *manifest* into *home*.

    Each file operation is wrapped; the first failure short-circuits the
    remaining artifacts with ``success=False`` and an error description.
    """

    result = InstallResult(success=True)

    # --- FileArtifact ---
    for artifact in manifest.files:
        try:
            target = home / artifact.target_relative
            prepared = _prepare_content(artifact, home)
            _place_file(
                target,
                prepared,
                artifact.backup_suffix,
                artifact.conflict_suffix,
                console,
            )
        except OSError as exc:
            result.success = False
            result.errors.append(f"{artifact.target_relative}: {exc}")
            return result

    # --- ComposedFileArtifact ---
    for artifact in manifest.composed:
        try:
            target = home / artifact.target_relative
            prepared = _prepare_composed_content(artifact, home)
            _place_file(
                target,
                prepared,
                artifact.backup_suffix,
                artifact.conflict_suffix,
                console,
            )
        except OSError as exc:
            result.success = False
            result.errors.append(f"{artifact.target_relative}: {exc}")
            return result

    # --- DirArtifact ---
    for artifact in manifest.dirs:
        try:
            target_dir = home / artifact.target_relative
            target_dir.mkdir(parents=True, exist_ok=True)

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
        except OSError as exc:
            result.success = False
            result.errors.append(f"{artifact.target_relative}: {exc}")
            return result

    return result


def uninstall(
    manifest: ArtifactManifest, home: Path, console: Console
) -> UninstallResult:
    """Uninstall every artifact in *manifest* from *home*.

    FileArtifact:
        - Remove target when its content matches the prepared source content.
        - Restore the backup (if present) to the target path.
    DirArtifact:
        - Remove target subdirectories that match source subdirectories.

    The first OS-level failure short-circuits with ``success=False``.
    """

    result = UninstallResult(success=True)

    # --- FileArtifact ---
    for artifact in manifest.files:
        try:
            target = home / artifact.target_relative
            prepared = _prepare_content(artifact, home)
            _remove_file(target, prepared, artifact.backup_suffix, console)
        except OSError as exc:
            result.success = False
            result.errors.append(f"{artifact.target_relative}: {exc}")
            return result

    # --- ComposedFileArtifact ---
    for artifact in manifest.composed:
        try:
            target = home / artifact.target_relative
            prepared = _prepare_composed_content(artifact, home)
            _remove_file(target, prepared, artifact.backup_suffix, console)
        except OSError as exc:
            result.success = False
            result.errors.append(f"{artifact.target_relative}: {exc}")
            return result

    # --- DirArtifact ---
    for artifact in manifest.dirs:
        try:
            target_dir = home / artifact.target_relative
            for source_entry in artifact.source.iterdir():
                target_sub = target_dir / source_entry.name
                if target_sub.exists():
                    if target_sub.is_dir():
                        shutil.rmtree(target_sub)
                    else:
                        target_sub.unlink()
                    console.print(f"Removed {target_sub}")
        except OSError as exc:
            result.success = False
            result.errors.append(f"{artifact.target_relative}: {exc}")
            return result

    return result
