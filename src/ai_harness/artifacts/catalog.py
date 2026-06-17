"""Slim, CLI-agnostic resource discovery.

ArtifactCatalog exposes general-purpose methods that let per-CLI
installer modules build their own asset dataclasses from project resources.
The catalog knows nothing about opencode, claude, or copilot.
"""

from __future__ import annotations

from pathlib import Path


class ArtifactCatalog:
    """Slim resource discovery — CLI-agnostic.

    Callers compose their own per-CLI asset views from the generic
    accessors this class provides.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def get_root(self) -> Path:
        """Return the project resources root directory."""
        return self._root

    def get_main_instructions(self) -> Path:
        """Return the path to the main instructions file (AGENTS.md)."""
        return self._root / "AGENTS.md"

    def get_resource_dir(self, relative: Path) -> Path:
        """Return the absolute path for a *relative* resource dir or file."""
        return self._root / relative
