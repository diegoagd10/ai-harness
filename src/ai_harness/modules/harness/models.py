"""Harness domain models — target vocabulary and the install→uninstall contract.

No operations live here. This module is the typed vocabulary shared by the
harness operations and the command layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Target(StrEnum):
    GENERIC = "generic"
    CLAUDE = "claude"
    COPILOT = "copilot"
    OPENCODE = "opencode"


@dataclass(frozen=True, slots=True)
class InstallManifest:
    """The exact record ``uninstall_targets`` consumes.

    Persisted to ``~/.ai-harness/installed.json``.
    """

    targets: list[Target]
    written_paths: list[Path]
