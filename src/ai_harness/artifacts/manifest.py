"""Declarative, immutable artifact descriptors.

These dataclasses describe *what* to place; the installer module in
ai_harness.artifacts.installer decides *how*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileArtifact:
    """A single file to install from *source* to *home/target_relative*."""

    source: Path
    target_relative: Path
    backup_suffix: str = ".ai-harness-backup"
    conflict_suffix: str = ".ai-harness-conflict-backup"
    template: dict[str, str] | None = None


@dataclass(frozen=True)
class DirArtifact:
    """A directory tree to install from *source* to *home/target_relative*.

    Install removes a matching target subdir before copying each source
    subdir, leaving unrelated entries untouched.
    """

    source: Path
    target_relative: Path


@dataclass(frozen=True)
class ComposedFileArtifact:
    """An artifact whose target is produced at install time by joining a
    frontmatter string with a body source.

    The two are concatenated as::

        frontmatter_text + "\\n---\\n" + body

    The composed result is written to ``home / target_relative`` with the
    same backup, conflict-rotation, and uninstall-restore policy as
    ``FileArtifact``.

    *frontmatter_text* is always required.
    """

    frontmatter_text: str
    body_source: Path
    target_relative: Path
    template: dict[str, str] = field(default_factory=dict)
    backup_suffix: str = ".ai-harness-backup"
    conflict_suffix: str = ".ai-harness-conflict-backup"


@dataclass(frozen=True)
class ArtifactManifest:
    """A complete install/uninstall plan — a bag of file & dir descriptors."""

    files: list[FileArtifact] = field(default_factory=list)
    dirs: list[DirArtifact] = field(default_factory=list)
    composed: list[ComposedFileArtifact] = field(default_factory=list)
