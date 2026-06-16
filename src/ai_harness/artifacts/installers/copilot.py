"""CopilotInstaller — builds a manifest for GitHub Copilot CLI artifacts.

Covers: AGENTS.md → .copilot/copilot-instructions.md, 16 agent files
(9 composed SDD-phase + orchestrator, 7 inline JD/reviewer) under
.copilot/agents/, hook JSON under .copilot/hooks/, and skills under
.copilot/skills/.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installer import (
    InstallResult,
    UninstallResult,
    install as generic_install,
    uninstall as generic_uninstall,
)
from ai_harness.artifacts.manifest import (
    ArtifactManifest,
    ComposedFileArtifact,
    DirArtifact,
    FileArtifact,
)

# Nine SDD phases (including orchestrator) whose Copilot agent files are
# composed at install time from a frontmatter source (agent-clis/copilot-cli
# /agents/<phase>.md) and a body source (prompts/sdd/<phase>.md), joined
# with ``---``.
_PHASE_NAMES: tuple[str, ...] = (
    "sdd-orchestrator",
    "sdd-explore",
    "sdd-propose",
    "sdd-spec",
    "sdd-design",
    "sdd-tasks",
    "sdd-apply",
    "sdd-verify",
    "sdd-archive",
)

# Seven inline Copilot subagents that are copied verbatim (their complete
# Markdown body lives in the resource file itself — no composition needed).
_INLINE_AGENTS: tuple[str, ...] = (
    "jd-fix-agent",
    "jd-judge-a",
    "jd-judge-b",
    "review-risk",
    "review-readability",
    "review-reliability",
    "review-resilience",
)

# Maximum allowed character count for a composed agent file (frontmatter +
# separator + body). Enforced at manifest-build time.
_MAX_COMPOSED_CHARS: int = 30_000


@dataclass(frozen=True)
class CopilotAssets:
    """Paths the CopilotInstaller composes from the catalog."""

    agents_dir: Path
    prompts_dir: Path
    hooks_dir: Path


class CopilotInstaller:
    """Installs/uninstalls Copilot CLI-specific harness artifacts."""

    def __init__(self, catalog: ArtifactCatalog) -> None:
        self._catalog = catalog

    def install(self, home: Path, console: Console) -> InstallResult:
        """Build manifest from catalog and invoke generic installer."""
        manifest = self._build_manifest(home)
        return generic_install(manifest, home, console)

    def uninstall(self, home: Path, console: Console) -> UninstallResult:
        """Build manifest and invoke generic uninstall."""
        manifest = self._build_manifest(home)
        return generic_uninstall(manifest, home, console)

    def _build_manifest(self, home: Path) -> ArtifactManifest:
        """Build the full artifact manifest for Copilot CLI.

        Validates every agent's frontmatter (YAML with name/description/tools)
        and enforces the 30 000-character budget on composed agents.
        """
        assets = CopilotAssets(
            agents_dir=self._catalog.get_resource_dir(
                Path("agent-clis/copilot-cli/agents")
            ),
            prompts_dir=self._catalog.get_resource_dir(Path("prompts/sdd")),
            hooks_dir=self._catalog.get_resource_dir(
                Path("agent-clis/copilot-cli/hooks")
            ),
        )

        instructions_src = self._catalog.get_main_instructions()
        files: list[FileArtifact] = []
        composed: list[ComposedFileArtifact] = []

        # AGENTS.md → .copilot/copilot-instructions.md (simple copy).
        files.append(
            FileArtifact(
                source=instructions_src,
                target_relative=Path(".copilot/copilot-instructions.md"),
            )
        )

        # SDD-phase + orchestrator agents — composed (frontmatter + body).
        for name in _PHASE_NAMES:
            composed.append(
                ComposedFileArtifact(
                    frontmatter_source=assets.agents_dir / f"{name}.md",
                    body_source=assets.prompts_dir / f"{name}.md",
                    target_relative=Path(".copilot/agents") / f"{name}.md",
                )
            )

        # Inline subagents — verbatim copies.
        for name in _INLINE_AGENTS:
            files.append(
                FileArtifact(
                    source=assets.agents_dir / f"{name}.md",
                    target_relative=Path(".copilot/agents") / f"{name}.md",
                )
            )

        # Hook JSON — verbatim copy.
        hook_src = assets.hooks_dir / "sdd-pre-tool-use.json"
        if hook_src.is_file():
            files.append(
                FileArtifact(
                    source=hook_src,
                    target_relative=Path(".copilot/hooks/sdd-pre-tool-use.json"),
                )
            )

        dirs: list[DirArtifact] = []
        # Skills → .copilot/skills/
        skills_src = self._catalog.get_root() / "skills"
        if skills_src.is_dir():
            dirs.append(
                DirArtifact(
                    source=skills_src,
                    target_relative=Path(".copilot/skills"),
                )
            )

        # --- frontmatter + budget validation --------------------------------
        for artifact in composed:
            self._validate_agent_frontmatter(artifact.frontmatter_source)
            self._validate_composed_budget(artifact)

        for artifact in files:
            target_name = str(artifact.target_relative)
            if target_name.startswith(".copilot/agents/") and target_name.endswith(
                ".md"
            ):
                self._validate_agent_frontmatter(artifact.source)

        return ArtifactManifest(files=files, dirs=dirs, composed=composed)

    # ------------------------------------------------------------------ validation ---

    @staticmethod
    def _validate_agent_frontmatter(source: Path) -> None:
        """Raise ``ValueError`` if *source* lacks required frontmatter keys.

        Required keys: ``name``, ``description``, ``tools``.
        """
        import yaml  # deferred import — pyyaml is a dev dependency

        content = source.read_text(encoding="utf-8")
        if not content.startswith("---"):
            raise ValueError(
                f"Agent '{source.name}' missing opening frontmatter delimiter"
            )

        parts = content.split("---", 2)
        if len(parts) < 2:
            raise ValueError(
                f"Agent '{source.name}' invalid frontmatter structure"
            )

        fm_text = parts[1]
        try:
            fm = yaml.safe_load(fm_text)
        except yaml.YAMLError as exc:
            raise ValueError(
                f"Agent '{source.name}' invalid YAML frontmatter: {exc}"
            ) from exc

        if not isinstance(fm, dict):
            raise ValueError(
                f"Agent '{source.name}' frontmatter is not a mapping"
            )

        for key in ("name", "description", "tools"):
            if key not in fm:
                raise ValueError(
                    f"Agent '{source.name}' missing required frontmatter "
                    f"key: '{key}'"
                )

    @staticmethod
    def _validate_composed_budget(artifact: ComposedFileArtifact) -> None:
        """Raise ``ValueError`` if the composed file exceeds the char budget."""
        frontmatter = artifact.frontmatter_source.read_text(encoding="utf-8")
        body = artifact.body_source.read_text(encoding="utf-8")
        # Same join logic as installer._prepare_composed_content
        total = len(frontmatter.rstrip("\n")) + len("\n---\n") + len(body)
        if total > _MAX_COMPOSED_CHARS:
            raise ValueError(
                f"Composed agent '{artifact.target_relative.name}' "
                f"exceeds {_MAX_COMPOSED_CHARS} char budget: {total}"
            )
