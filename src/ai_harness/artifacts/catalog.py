"""Slim, CLI-agnostic resource discovery.

ArtifactCatalog exposes four general-purpose methods that let per-CLI
installer modules build their own asset dataclasses from project resources.
The catalog knows nothing about opencode, claude, or copilot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# ------------------------------------------------------------------ path helpers ---

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"

AGENTS_MD_SRC = RESOURCES_DIR / "AGENTS.md"
SKILLS_SRC = RESOURCES_DIR / "skills"
OPENCODE_SDD_PROMPTS_SRC = RESOURCES_DIR / "prompts" / "sdd"
JD_PROMPTS_SRC = RESOURCES_DIR / "prompts" / "jd"
REVIEW_PROMPTS_SRC = RESOURCES_DIR / "prompts" / "review"
ORCHESTRATOR_PROMPTS_SRC = RESOURCES_DIR / "prompts" / "orchestrator"

AGENTS_MD_TARGETS: tuple[Path, ...] = (
    Path(".agents/AGENTS.md"),
    Path(".claude/CLAUDE.md"),
    Path(".copilot/copilot-instructions.md"),
)
SKILLS_TARGET_DIRS: tuple[Path, ...] = (
    Path(".agents/skills"),
    Path(".claude/skills"),
    Path(".copilot/skills"),
)
OPENCODE_JSON_TARGET = Path(".config/opencode/opencode.json")
OPENCODE_SDD_PROMPTS_TARGET_DIR = Path(".config/opencode/prompts/sdd")


# ------------------------------------------------------------------ catalog ---


@dataclass(frozen=True)
class Skill:
    """A project skill discovered by the catalog."""

    name: str
    source_dir: Path
    skill_md: Path


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

    def get_skills(self) -> list[Skill]:
        """Discover project skills under <root>/skills/.

        Returns a list of Skill dataclasses, one per directory that
        contains a SKILL.md file. Non-directory entries are skipped.
        """
        skills_dir = self._root / "skills"
        if not skills_dir.is_dir():
            return []

        result: list[Skill] = []
        for entry in sorted(skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if skill_md.is_file():
                result.append(
                    Skill(
                        name=entry.name,
                        source_dir=entry,
                        skill_md=skill_md,
                    )
                )
        return result

    def get_resource_dir(self, relative: Path) -> Path:
        """Return the absolute path for a *relative* resource dir or file."""
        return self._root / relative
