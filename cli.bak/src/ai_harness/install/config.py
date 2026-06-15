"""Config: install paths, harness selection, and repo resolution.

The ``Config`` is the host-injection point: every filesystem path the
installer touches flows through it, so the install / uninstall / generate
functions stay testable against temp dirs without reading ``$HOME``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .harness import Harness

# Markers an ai-harness repo MUST carry; ``resolve_repo_dir`` rejects anything
# missing one of them so the installer cannot accidentally copy from a
# different project.
_REPO_MARKERS: tuple[str, ...] = ("skills", "AGENTS.md")


@dataclass(frozen=True)
class Config:
    """Per-invocation install configuration.

    Paths are absolute and rooted under the user's home directory; the CLI
    layer (the only place that knows ``$HOME``) is responsible for filling
    them in. An empty ``harnesses`` list selects every supported harness,
    matching the Go back-compat default.
    """

    repo_dir: Path
    claude_dir: Path
    agents_dir: Path
    copilot_dir: Path
    opencode_dir: Path
    harnesses: list[Harness] = field(default_factory=list)

    def wants(self, harness: Harness) -> bool:
        """Return whether the given harness is part of the current selection.

        An empty selection includes every harness (the back-compat / safe
        default), so callers do not need a separate "all" sentinel.
        """
        if not self.harnesses:
            return True
        return harness in self.harnesses

    def mappings(self) -> list[tuple[Path, Path]]:
        """Return the (source, dest) copy set for the current selection.

        The always-on generic ``.agents`` artifacts come first, then
        per-harness artifacts in the stable order ``claude, copilot,
        opencode``. Selection controls only the per-harness blocks.
        """
        links: list[tuple[Path, Path]] = [
            (self.repo_dir / "skills", self.agents_dir / "skills"),
            (self.repo_dir / "AGENTS.md", self.agents_dir / "AGENTS.md"),
        ]
        if self.wants(Harness.CLAUDE):
            links.extend(
                [
                    (self.repo_dir / "skills", self.claude_dir / "skills"),
                    (self.repo_dir / "AGENTS.md", self.claude_dir / "CLAUDE.md"),
                ]
            )
        if self.wants(Harness.COPILOT):
            links.extend(
                [
                    (self.repo_dir / "skills", self.copilot_dir / "skills"),
                    (self.repo_dir / "AGENTS.md", self.copilot_dir / "copilot-instructions.md"),
                ]
            )
        if self.wants(Harness.OPENCODE):
            links.extend(
                [
                    (self.repo_dir / "skills", self.opencode_dir / "skills"),
                    (self.repo_dir / "AGENTS.md", self.opencode_dir / "AGENTS.md"),
                    (
                        self.repo_dir / "prompts" / "sdd",
                        self.opencode_dir / "prompts" / "sdd",
                    ),
                    (
                        self.repo_dir / "agent-clis" / "opencode" / "plugins",
                        self.opencode_dir / "plugins",
                    ),
                ]
            )
        return links

    def owned_roots(self) -> list[Path]:
        """Return the directories the manifest validator considers managed.

        The manifest validator rejects any ``dest`` that escapes these
        roots, so listing them here is what makes uninstall safe against a
        tampered manifest file.
        """
        return [
            self.claude_dir,
            self.agents_dir,
            self.copilot_dir,
            self.opencode_dir,
            self.opencode_dir.parent / "ai-harness",
        ]


def resolve_repo_dir(explicit: str | None, cwd: str | None) -> Path:
    """Pick the repo root and verify it is a real ai-harness checkout.

    An explicit ``--repo`` wins; otherwise we fall back to ``cwd``. Either
    way, the directory must contain both ``skills/`` and ``AGENTS.md`` —
    missing markers raise :class:`ValueError` naming the offenders so the
    user can fix the path.
    """
    root = explicit or cwd
    if not root:
        raise ValueError("could not determine repo root: pass --repo or run from a checkout")
    root_path = Path(root)
    missing = [marker for marker in _REPO_MARKERS if not (root_path / marker).exists()]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{root_path} is not an ai-harness repo: missing {joined}")
    return root_path
