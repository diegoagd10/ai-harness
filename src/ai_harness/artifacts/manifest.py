"""Declarative, immutable artifact descriptors.

These dataclasses describe *what* to place; the installer module in
ai_harness.artifacts.installer decides *how*.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    """A directory tree to install from *source* to *home/target_relative*."""

    source: Path
    target_relative: Path
    merge_mode: str = "replace_matching"
    # "replace_matching" removes target subdir if it exists before copying.
    # "merge_preserve" (future) merges without deleting unknown entries.


@dataclass(frozen=True)
class ArtifactManifest:
    """A complete install/uninstall plan — a bag of file & dir descriptors."""

    files: list[FileArtifact]
    dirs: list[DirArtifact]
