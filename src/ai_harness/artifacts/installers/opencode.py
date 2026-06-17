"""OpencodeInstaller — builds a manifest for Opencode CLI artifacts.

Covers: opencode.json (built in memory), SDD/JD/Review/Orchestrator
prompts, AGENTS.md targets for opencode, and skills for .agents/.

The in-memory ``opencode.json`` is composed from a 16-row
``AGENT_DEFINITIONS`` table. The 7 ``jd-*``/``review-*`` prompts are
read at install time from on-disk ``.md`` files; the 9 ``sdd-*``
agents keep ``{file:{{HOME}}/...}`` template refs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rich.console import Console

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installer import (
    InstallResult,
    UninstallResult,
)
from ai_harness.artifacts.installer import (
    install as generic_install,
)
from ai_harness.artifacts.installer import (
    uninstall as generic_uninstall,
)
from ai_harness.artifacts.manifest import ArtifactManifest, DirArtifact, FileArtifact

# ── constants ────────────────────────────────────────────────────────────────

# Single consumer (this installer); kept literal rather than extracted.
_PERMISSION_BLOCK: dict[str, object] = {
    "external_directory": {
        "~/.ssh/**": "deny",
        "~/.aws/**": "deny",
        "~/.gnupg/**": "deny",
        "~/.zshrc": "deny",
        "~/.bashrc": "deny",
        "~/.bash_history": "deny",
        "~/.zsh_history": "deny",
        "~/.netrc": "deny",
        "~/.config/gh/**": "deny",
        "~/.docker/config.json": "deny",
        "/tmp/**": "deny",
        "/etc/**": "deny",
        "/proc/**": "deny",
        "/sys/**": "deny",
        "/var/**": "deny",
    },
    "read": {"*.env": "deny", "*.env.*": "deny"},
    "edit": {"*.env": "deny", "*.env.*": "deny"},
    "bash": {
        "env": "deny",
        "printenv": "deny",
        "set": "deny",
        "aws *": "deny",
        "curl *": "ask",
        "wget *": "ask",
    },
}


# ── dataclass ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentDefinition:
    """Immutable description of a single OpenCode agent entry."""

    agent_id: str
    description: str
    mode: Literal["primary", "subagent"]
    hidden: bool
    model: str | None
    permission: dict[str, str] | None
    tools: dict[str, bool]
    prompt_kind: Literal["file_ref", "inline"]


# ── helpers ──────────────────────────────────────────────────────────────────


def _prompt_ns(agent_id: str) -> str:
    """Map an agent id to its on-disk prompt namespace.

    Raises ``ValueError`` for ids that do not match a known prefix.
    """
    if agent_id.startswith("sdd-"):
        return "sdd"
    if agent_id.startswith("jd-"):
        return "jd"
    if agent_id.startswith("review-"):
        return "review"
    raise ValueError(f"Unknown agent id (no prompt namespace): {agent_id!r}")


def _load_inlined_prompt(prompts_root: Path, agent_id: str) -> str:
    """Read the ``.md`` body for an inline agent verbatim.

    Strips a single trailing newline so the inlined string matches the
    target reference's convention.
    """
    ns = _prompt_ns(agent_id)
    body = (prompts_root / ns / f"{agent_id}.md").read_text(encoding="utf-8")
    return body.rstrip("\n")


def _build_orchestrator_allowlist() -> dict[str, str]:
    """Build the orchestrator's task allowlist (all sub-agents, * deny)."""
    allow: dict[str, str] = {"*": "deny"}
    for agent in AGENT_DEFINITIONS:
        if agent.agent_id == "sdd-orchestrator":
            continue
        allow[agent.agent_id] = "allow"
    return allow


def _build_agent_entry(agent: AgentDefinition, prompt_body: str | None) -> dict[str, object]:
    """Compose one agent's JSON dict from its ``AgentDefinition``.

    Optional fields (``hidden``, ``model``, ``permission``) are emitted
    only when set. The orchestrator's task allowlist is attached
    separately by the caller.
    """
    entry: dict[str, object] = {
        "description": agent.description,
        "mode": agent.mode,
    }
    if agent.hidden:
        entry["hidden"] = True
    if agent.model is not None:
        entry["model"] = agent.model
    if agent.permission is not None:
        entry["permission"] = dict(agent.permission)
    entry["tools"] = dict(agent.tools)
    if agent.prompt_kind == "file_ref":
        ns = _prompt_ns(agent.agent_id)
        entry["prompt"] = f"{{file:{{{{HOME}}}}/.config/opencode/prompts/{ns}/{agent.agent_id}.md}}"
    else:  # inline
        assert prompt_body is not None, f"inline agent {agent.agent_id} missing body"
        entry["prompt"] = prompt_body
    return entry


# ── data table ───────────────────────────────────────────────────────────────

# 16 rows: 1 orchestrator + 7 sdd sub-phases + 3 jd + 4 review. Role-grouped.
AGENT_DEFINITIONS: list[AgentDefinition] = [
    # Orchestrator
    AgentDefinition(
        agent_id="sdd-orchestrator",
        description="SDD-Orchestrator - coordinates sub-agents, never does work inline",
        mode="primary",
        hidden=False,
        model="openai/gpt-5.5",
        permission=None,  # task allowlist is attached by _build_opencode_config
        tools={"bash": True, "edit": True, "read": True, "task": True, "write": True},
        prompt_kind="file_ref",
    ),
    # Seven SDD sub-phases
    AgentDefinition(
        agent_id="sdd-apply",
        description="Implement code changes from task definitions",
        mode="subagent",
        hidden=True,
        model="opencode-go/deepseek-v4-pro",
        permission=None,
        tools={"bash": True, "edit": True, "read": True, "write": True},
        prompt_kind="file_ref",
    ),
    AgentDefinition(
        agent_id="sdd-archive",
        description="Archive completed change artifacts",
        mode="subagent",
        hidden=True,
        model="opencode-go/deepseek-v4-flash",
        permission=None,
        tools={"bash": True, "edit": True, "read": True, "write": True},
        prompt_kind="file_ref",
    ),
    AgentDefinition(
        agent_id="sdd-design",
        description="Create technical design from proposals",
        mode="subagent",
        hidden=True,
        model="opencode-go/deepseek-v4-pro",
        permission=None,
        tools={"bash": True, "edit": True, "read": True, "write": True},
        prompt_kind="file_ref",
    ),
    AgentDefinition(
        agent_id="sdd-explore",
        description="Investigate codebase and think through ideas",
        mode="subagent",
        hidden=True,
        model="opencode-go/kimi-k2.7-code",
        permission=None,
        tools={"bash": True, "edit": True, "read": True, "write": True},
        prompt_kind="file_ref",
    ),
    AgentDefinition(
        agent_id="sdd-propose",
        description="Create change proposals from explorations",
        mode="subagent",
        hidden=True,
        model="opencode-go/deepseek-v4-pro",
        permission=None,
        tools={"bash": True, "edit": True, "read": True, "write": True},
        prompt_kind="file_ref",
    ),
    AgentDefinition(
        agent_id="sdd-spec",
        description="Write detailed specifications from proposals",
        mode="subagent",
        hidden=True,
        model="opencode-go/deepseek-v4-pro",
        permission=None,
        tools={"bash": True, "edit": True, "read": True, "write": True},
        prompt_kind="file_ref",
    ),
    AgentDefinition(
        agent_id="sdd-tasks",
        description="Break down specs and designs into implementation tasks",
        mode="subagent",
        hidden=True,
        model="opencode-go/deepseek-v4-pro",
        permission=None,
        tools={"bash": True, "edit": True, "read": True, "write": True},
        prompt_kind="file_ref",
    ),
    AgentDefinition(
        agent_id="sdd-verify",
        description="Validate implementation against specs",
        mode="subagent",
        hidden=True,
        model="opencode-go/kimi-k2.6",
        permission=None,
        tools={"bash": True, "edit": True, "read": True, "write": True},
        prompt_kind="file_ref",
    ),
    # Three JD agents — inlined bodies
    AgentDefinition(
        agent_id="jd-fix-agent",
        description="Surgical fix agent for judgment-day protocol",
        mode="subagent",
        hidden=True,
        model=None,
        # No `permission` key: jd-fix-agent APPLIES fixes (the other 6
        # jd-/review- agents are read-only).
        permission=None,
        tools={"bash": True, "edit": True, "read": True, "write": True},
        prompt_kind="inline",
    ),
    AgentDefinition(
        agent_id="jd-judge-a",
        description="Adversarial code reviewer \u2014 blind judge A for judgment-day protocol",
        mode="subagent",
        hidden=True,
        model=None,
        permission={"edit": "deny"},
        tools={"bash": True, "read": True},
        prompt_kind="inline",
    ),
    AgentDefinition(
        agent_id="jd-judge-b",
        description="Adversarial code reviewer \u2014 blind judge B for judgment-day protocol",
        mode="subagent",
        hidden=True,
        model=None,
        permission={"edit": "deny"},
        tools={"bash": True, "read": True},
        prompt_kind="inline",
    ),
    # Four Review agents — inlined bodies, all read-only
    AgentDefinition(
        agent_id="review-readability",
        description=(
            "R2 Readability reviewer \u2014 naming, complexity, intention, "
            "maintainability, review size, and context clarity"
        ),
        mode="subagent",
        hidden=True,
        model=None,
        permission={"edit": "deny"},
        tools={"bash": True, "read": True},
        prompt_kind="inline",
    ),
    AgentDefinition(
        agent_id="review-reliability",
        description=(
            "R3 Reliability reviewer \u2014 behavior-first tests, coverage value, "
            "edge cases, determinism, contracts, and regressions"
        ),
        mode="subagent",
        hidden=True,
        model=None,
        permission={"edit": "deny"},
        tools={"bash": True, "read": True},
        prompt_kind="inline",
    ),
    AgentDefinition(
        agent_id="review-resilience",
        description=(
            "R4 Resilience reviewer \u2014 fallbacks, retry/backoff, "
            "graceful degradation, observability, load, rollback, and SLO risks"
        ),
        mode="subagent",
        hidden=True,
        model=None,
        permission={"edit": "deny"},
        tools={"bash": True, "read": True},
        prompt_kind="inline",
    ),
    AgentDefinition(
        agent_id="review-risk",
        description=(
            "R1 Risk reviewer \u2014 security, privilege boundaries, data exposure, "
            "dependency risks, and merge-blocking vulnerabilities"
        ),
        mode="subagent",
        hidden=True,
        model=None,
        permission={"edit": "deny"},
        tools={"bash": True, "read": True},
        prompt_kind="inline",
    ),
]


def _build_opencode_config(prompts_root: Path) -> dict[str, object]:
    """Build the opencode.json configuration dict entirely in memory.

    Iterates ``AGENT_DEFINITIONS``; reads inlined bodies for the 7
    ``jd-*``/``review-*`` agents from *prompts_root*. The orchestrator's
    task allowlist is attached last from ``_build_orchestrator_allowlist()``.
    """
    agents: dict[str, object] = {}
    for agent in AGENT_DEFINITIONS:
        prompt_body = _load_inlined_prompt(prompts_root, agent.agent_id) if agent.prompt_kind == "inline" else None
        agents[agent.agent_id] = _build_agent_entry(agent, prompt_body)

    agents["sdd-orchestrator"]["permission"] = {"task": _build_orchestrator_allowlist()}

    return {
        "$schema": "https://opencode.ai/config.json",
        "permission": _PERMISSION_BLOCK,
        "agent": agents,
        "share": "disabled",
    }


# ── installer class (unchanged shape — only _build_opencode_config caller) ──


@dataclass(frozen=True)
class OpencodeAssets:
    """Paths the OpencodeInstaller composes from the catalog."""

    prompts_dir: Path
    jd_prompts_dir: Path
    review_prompts_dir: Path
    orchestrator_prompts_dir: Path


class OpencodeInstaller:
    """Installs/uninstalls Opencode-specific harness artifacts."""

    def __init__(self, catalog: ArtifactCatalog) -> None:
        self._catalog = catalog

    def _assets(self) -> OpencodeAssets:
        """Build the catalog-derived asset paths shared by install/uninstall."""
        return OpencodeAssets(
            prompts_dir=self._catalog.get_resource_dir(Path("prompts/sdd")),
            jd_prompts_dir=self._catalog.get_resource_dir(Path("prompts/jd")),
            review_prompts_dir=self._catalog.get_resource_dir(Path("prompts/review")),
            orchestrator_prompts_dir=self._catalog.get_resource_dir(Path("prompts/orchestrator")),
        )

    def install(self, home: Path, console: Console) -> InstallResult:
        """Build manifest from catalog and invoke the generic installer."""
        assets = self._assets()
        manifest = self._build_manifest(home, assets)
        return generic_install(manifest, home, console)

    def uninstall(self, home: Path, console: Console) -> UninstallResult:
        """Build manifest and invoke generic uninstall."""
        assets = self._assets()
        manifest = self._build_manifest(home, assets)
        return generic_uninstall(manifest, home, console)

    def _build_manifest(self, home: Path, assets: OpencodeAssets) -> ArtifactManifest:
        instructions_src = self._catalog.get_main_instructions()
        files: list[FileArtifact] = []

        # AGENTS.md → .config/opencode/AGENTS.md (with backup/restore).
        files.append(
            FileArtifact(
                source=instructions_src,
                target_relative=Path(".config/opencode/AGENTS.md"),
            )
        )

        # AGENTS.md → .agents/AGENTS.md (simple copy).
        files.append(
            FileArtifact(
                source=instructions_src,
                target_relative=Path(".agents/AGENTS.md"),
            )
        )

        # Build opencode.json in memory → write to temp file → install via FileArtifact.
        prompts_root = self._catalog.get_root() / "prompts"
        config = _build_opencode_config(prompts_root)
        config_json = json.dumps(config, indent=2) + "\n"
        # Write to temp file in home so the generic installer reads it.
        home.mkdir(parents=True, exist_ok=True)
        tmp_config = home / ".ai-harness-opencode-tmp.json"
        tmp_config.write_text(config_json, encoding="utf-8")
        files.append(
            FileArtifact(
                source=tmp_config,
                target_relative=Path(".config/opencode/opencode.json"),
                template={"{{HOME}}": str(home)},
            )
        )

        # SDD prompt files → .config/opencode/prompts/sdd/*.md
        for prompt_file in assets.prompts_dir.glob("*.md"):
            files.append(
                FileArtifact(
                    source=prompt_file,
                    target_relative=Path(".config/opencode/prompts/sdd") / prompt_file.name,
                )
            )

        # JD prompt files → .config/opencode/prompts/jd/*.md
        if assets.jd_prompts_dir.is_dir():
            for prompt_file in assets.jd_prompts_dir.glob("*.md"):
                files.append(
                    FileArtifact(
                        source=prompt_file,
                        target_relative=Path(".config/opencode/prompts/jd") / prompt_file.name,
                    )
                )

        # Review prompt files → .config/opencode/prompts/review/*.md
        if assets.review_prompts_dir.is_dir():
            for prompt_file in assets.review_prompts_dir.glob("*.md"):
                files.append(
                    FileArtifact(
                        source=prompt_file,
                        target_relative=Path(".config/opencode/prompts/review") / prompt_file.name,
                    )
                )

        # Orchestrator prompt files → .config/opencode/prompts/orchestrator/*.md
        if assets.orchestrator_prompts_dir.is_dir():
            for prompt_file in assets.orchestrator_prompts_dir.glob("*.md"):
                files.append(
                    FileArtifact(
                        source=prompt_file,
                        target_relative=Path(".config/opencode/prompts/orchestrator") / prompt_file.name,
                    )
                )

        dirs: list[DirArtifact] = []
        # Skills → .agents/skills/
        skills_src = self._catalog.get_root() / "skills"
        if skills_src.is_dir():
            dirs.append(
                DirArtifact(
                    source=skills_src,
                    target_relative=Path(".agents/skills"),
                )
            )

        return ArtifactManifest(files=files, dirs=dirs)
