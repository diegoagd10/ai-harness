"""ClaudeInstaller — builds a manifest for Claude Code CLI artifacts.

Covers: AGENTS.md → .claude/CLAUDE.md, skills → .claude/skills/,
composed SDD-phase agent files (frontmatter + prompt body), composed
inline subagents with embedded metadata, and the sdd-orchestrator skill
at .claude/skills/sdd-orchestrator/SKILL.md.
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

from ai_harness.artifacts.installers.permissions import (
    uninstall_permissions,
)

# Eight SDD phases whose Claude agent files are composed at install time
# from a frontmatter source (agent-clis/claude/agents/<phase>.md) and a
# body source (prompts/sdd/<phase>.md), joined with ``---``.
_PHASE_NAMES: list[str] = [
    "sdd-explore", "sdd-propose", "sdd-spec", "sdd-design",
    "sdd-tasks", "sdd-apply", "sdd-verify", "sdd-archive",
]

# Seven inline Claude subagents whose frontmatter is embedded as metadata
# and whose body comes from canonical prompt files under prompts/<ns>/.
_INLINE_AGENTS: list[str] = [
    "jd-fix-agent", "jd-judge-a", "jd-judge-b",
    "review-readability", "review-reliability", "review-resilience",
    "review-risk",
]

_MARKER_FILENAME = ".ai-harness-managed-allow.json"

# Each inline agent's frontmatter metadata — used to compose artifacts
# without reading agent-clis/ as a source.  The body comes from the
# canonical prompt file under prompts/<ns>/<name>.md.
_METADATA: dict[str, dict[str, object]] = {
    # Eight SDD phase agents
    "sdd-explore": {
        "name": "sdd-explore",
        "description": "SDD Explore — explores the codebase to build understanding for design decisions",
        "tools": ["Read", "Edit", "Write", "Bash"],
        "model": "inherit",
    },
    "sdd-propose": {
        "name": "sdd-propose",
        "description": "SDD Propose — drafts architectural proposals from exploration findings",
        "tools": ["Read", "Edit", "Write", "Bash"],
        "model": "inherit",
    },
    "sdd-spec": {
        "name": "sdd-spec",
        "description": "SDD Spec — writes formal specification scenarios",
        "tools": ["Read", "Edit", "Write", "Bash"],
        "model": "inherit",
    },
    "sdd-design": {
        "name": "sdd-design",
        "description": "SDD Design — produces architecture and design documents",
        "tools": ["Read", "Edit", "Write", "Bash"],
        "model": "inherit",
    },
    "sdd-tasks": {
        "name": "sdd-tasks",
        "description": "SDD Tasks — generates implementation task checklists",
        "tools": ["Read", "Edit", "Write", "Bash"],
        "model": "inherit",
    },
    "sdd-apply": {
        "name": "sdd-apply",
        "description": "SDD Apply — implements tasks from the checklist",
        "tools": ["Read", "Edit", "Write", "Bash"],
        "model": "inherit",
    },
    "sdd-verify": {
        "name": "sdd-verify",
        "description": "SDD Verify — validates implementation against specs",
        "tools": ["Read", "Edit", "Write", "Bash"],
        "model": "inherit",
    },
    "sdd-archive": {
        "name": "sdd-archive",
        "description": "SDD Archive — finalizes and archives completed changes",
        "tools": ["Read", "Edit", "Write", "Bash"],
        "model": "inherit",
    },
    # Seven inline Claude subagents
    "jd-fix-agent": {
        "name": "jd-fix-agent",
        "description": "Surgical fix agent for judgment-day protocol",
        "tools": ["Read", "Edit", "Write", "Bash"],
        "model": "inherit",
    },
    "jd-judge-a": {
        "name": "jd-judge-a",
        "description": "Adversarial code reviewer — blind judge A for judgment-day protocol",
        "tools": ["Read", "Bash"],
        "model": "opus",
    },
    "jd-judge-b": {
        "name": "jd-judge-b",
        "description": "Adversarial code reviewer — blind judge B for judgment-day protocol",
        "tools": ["Read", "Bash"],
        "model": "opus",
    },
    "review-risk": {
        "name": "review-risk",
        "description": "R1 Risk reviewer — security, privilege boundaries, data exposure, dependency risks, and merge-blocking vulnerabilities",
        "tools": ["Read", "Bash"],
        "model": "opus",
    },
    "review-readability": {
        "name": "review-readability",
        "description": "R2 Readability reviewer — naming, complexity, intention, maintainability, review size, and context clarity",
        "tools": ["Read", "Bash"],
        "model": "sonnet",
    },
    "review-reliability": {
        "name": "review-reliability",
        "description": "R3 Reliability reviewer — behavior-first tests, coverage value, edge cases, determinism, contracts, and regressions",
        "tools": ["Read", "Bash"],
        "model": "sonnet",
    },
    "review-resilience": {
        "name": "review-resilience",
        "description": "R4 Resilience reviewer — fallbacks, retry/backoff, graceful degradation, observability, load, rollback, and SLO risks",
        "tools": ["Read", "Bash"],
        "model": "sonnet",
    },
    # Orchestrator (Agent variant — uses prompts/orchestrator/sdd-orchestrator-agent.md)
    "sdd-orchestrator": {
        "name": "sdd-orchestrator",
        "description": "SDD-Orchestrator - coordinates sub-agents, never does work inline",
        "tools": ["Read", "Edit", "Write", "Bash", "Agent"],
        "model": "inherit",
    },
}


def _metadata_to_frontmatter(m: dict[str, object]) -> str:
    """Serialize a _METADATA entry to YAML frontmatter text.

    Produces lines like::

        ---
        name: jd-judge-a
        description: ...
        tools: [Read, Bash]
        model: opus
        ---
    """
    tools_list = m["tools"]
    if isinstance(tools_list, list):
        tools_yaml = ", ".join(str(t) for t in tools_list)
    else:
        tools_yaml = str(tools_list)
    return (
        f"---\n"
        f"name: {m['name']}\n"
        f"description: {m['description']}\n"
        f"tools: [{tools_yaml}]\n"
        f"model: {m['model']}\n"
        f"---"
    )


@dataclass(frozen=True)
class ClaudeAssets:
    """Paths the ClaudeInstaller composes from the catalog."""

    prompts_dir: Path
    orchestrator_prompts_dir: Path
    jd_prompts_dir: Path
    review_prompts_dir: Path


class ClaudeInstaller:
    """Installs/uninstalls Claude-Code-specific harness artifacts."""

    def __init__(self, catalog: ArtifactCatalog) -> None:
        self._catalog = catalog

    def install(self, home: Path, console: Console) -> InstallResult:
        """Build manifest, install subagent permission rules, invoke
        the generic installer, and write generated fixtures.
        """
        assets = ClaudeAssets(
            prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/sdd")
            ),
            orchestrator_prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/orchestrator")
            ),
            jd_prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/jd")
            ),
            review_prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/review")
            ),
        )
        manifest = self._build_manifest(home, assets)
        errors: list[str] = []
        try:
            self._install_permissions(manifest, assets)
        except Exception as exc:
            errors.append(f"claude permissions: {exc}")
        result = generic_install(manifest, home, console)
        if not result.success:
            errors.extend(result.errors)
        # Write generated fixtures for e2e
        self._write_fixtures(manifest, console)
        if errors:
            return InstallResult(success=False, errors=errors)
        return result

    def uninstall(self, home: Path, console: Console) -> UninstallResult:
        """Build manifest, invoke generic uninstall, then remove the
        managed permission rules.
        """
        assets = ClaudeAssets(
            prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/sdd")
            ),
            orchestrator_prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/orchestrator")
            ),
            jd_prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/jd")
            ),
            review_prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/review")
            ),
        )
        manifest = self._build_manifest(home, assets)
        result = generic_uninstall(manifest, home, console)
        try:
            self._uninstall_permissions()
        except Exception as exc:
            return UninstallResult(
                success=False,
                errors=[f"claude permissions: {exc}"] + result.errors,
            )
        return result

    def _install_permissions(
        self, manifest: ArtifactManifest, assets: ClaudeAssets
    ) -> None:
        """Collect tool lists from metadata for installed agents,
        including SDD phases and the orchestrator, and delegate to
        :func:`~ai_harness.artifacts.installers.permissions.install_permissions_from_tools`.
        """
        from ai_harness.artifacts.installers.permissions import (
            install_permissions_from_tools,
        )

        tool_lists: list[list[str]] = []

        # SDD phase agents all share these Claude-native tools
        sdd_tools = ["Read", "Edit", "Write", "Bash"]
        for _ in _PHASE_NAMES:
            tool_lists.append(sdd_tools)

        # Orchestrator tools
        tool_lists.append(["Read", "Edit", "Write", "Bash", "Agent"])

        # Inline agents from metadata
        for name in _INLINE_AGENTS:
            if name in _METADATA:
                meta = _METADATA[name]
                tools = meta.get("tools")
                if isinstance(tools, list):
                    tool_lists.append([str(t) for t in tools])

        install_permissions_from_tools(tool_lists)

    def _uninstall_permissions(self) -> None:
        """Delegate the uninstall sequence."""
        uninstall_permissions()

    def _build_manifest(self, home: Path, assets: ClaudeAssets) -> ArtifactManifest:
        instructions_src = self._catalog.get_main_instructions()
        files: list[FileArtifact] = []
        composed: list[ComposedFileArtifact] = []

        # AGENTS.md → .claude/CLAUDE.md (simple copy).
        files.append(
            FileArtifact(
                source=instructions_src,
                target_relative=Path(".claude/CLAUDE.md"),
            )
        )

        # SDD-phase agents — composed (frontmatter from metadata + body from prompts/sdd/).
        for name in _PHASE_NAMES:
            metadata = _METADATA[name]
            fm_text = _metadata_to_frontmatter(metadata)
            composed.append(
                ComposedFileArtifact(
                    frontmatter_text=fm_text,
                    body_source=assets.prompts_dir / f"{name}.md",
                    target_relative=Path(".claude/agents") / f"{name}.md",
                )
            )

        # Inline JD agents — composed (frontmatter_text from metadata + canonical body).
        for name in _INLINE_AGENTS:
            namespace = "jd" if name.startswith("jd-") else "review"
            prompts_subdir = (
                assets.jd_prompts_dir if namespace == "jd"
                else assets.review_prompts_dir
            )
            metadata = _METADATA[name]
            fm_text = _metadata_to_frontmatter(metadata)
            composed.append(
                ComposedFileArtifact(
                    frontmatter_text=fm_text,
                    body_source=prompts_subdir / f"{name}.md",
                    target_relative=Path(".claude/agents") / f"{name}.md",
                )
            )

        dirs: list[DirArtifact] = []
        # Skills → .claude/skills/
        skills_src = self._catalog.get_root() / "skills"
        if skills_src.is_dir():
            dirs.append(
                DirArtifact(
                    source=skills_src,
                    target_relative=Path(".claude/skills"),
                )
            )

        # SDD orchestrator SKILL.md — composed (metadata frontmatter + Agent-variant body).
        orch_metadata = _METADATA["sdd-orchestrator"]
        orch_fm = _metadata_to_frontmatter(orch_metadata)
        composed.append(
            ComposedFileArtifact(
                frontmatter_text=orch_fm,
                body_source=assets.orchestrator_prompts_dir / "sdd-orchestrator-agent.md",
                target_relative=Path(".claude/skills/sdd-orchestrator/SKILL.md"),
            )
        )

        return ArtifactManifest(files=files, dirs=dirs, composed=composed)

    # ── generated fixtures for e2e ────────────────────────────────────────────

    _GENERATED_DIR = (
        Path(__file__).resolve().parent.parent.parent / "resources" / "generated"
    )

    @staticmethod
    def _write_fixtures(
        manifest: ArtifactManifest, console: Console,
    ) -> None:
        """Write generated fixtures to resources/generated/claude/ so e2e
        source-path constants resolve.

        Guarded by ``os.access(os.W_OK)`` — silent skip on read-only
        source trees (pip installs, CI).
        """
        import os

        from ai_harness.artifacts.installer import _prepare_composed_content

        claude_gen = ClaudeInstaller._GENERATED_DIR / "claude"
        if not os.access(claude_gen.parent, os.W_OK):
            return  # read-only source tree — silent skip

        agents_dir = claude_gen / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        for artifact in manifest.composed:
            target_name = artifact.target_relative.name
            if ".claude/agents/" not in str(artifact.target_relative):
                continue  # skip orchestrator (handled below)

            fixture_path = agents_dir / target_name

            if any(
                target_name.startswith(f"{p}.") for p in _PHASE_NAMES
                if p in target_name
            ):
                # SDD phases: write frontmatter-only.
                # The e2e reads this as frontmatter and composes
                # ``frontmatter.rstrip("\n") + "\n---\n" + body`` itself.
                content = artifact.frontmatter_text
            else:
                # Inline agents: write fully composed
                content = _prepare_composed_content(artifact, Path("/dev/null"))

            fixture_path.write_text(content, encoding="utf-8")
            console.print(f"Fixture written {fixture_path}")

        # Orchestrator fixture
        orch_dir = claude_gen / "sdd-orchestrator"
        orch_dir.mkdir(parents=True, exist_ok=True)
        # Find orchestrator artifact from manifest
        orch_artifacts = [
            a for a in manifest.composed
            if str(a.target_relative) == ".claude/skills/sdd-orchestrator/SKILL.md"
        ]
        if orch_artifacts:
            orch_content = _prepare_composed_content(
                orch_artifacts[0], Path("/dev/null")
            )
            (orch_dir / "SKILL.md").write_text(orch_content, encoding="utf-8")
            console.print(f"Fixture written {orch_dir / 'SKILL.md'}")
