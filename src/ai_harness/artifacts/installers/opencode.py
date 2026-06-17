"""OpencodeInstaller — builds a manifest for Opencode CLI artifacts.

Covers: opencode.json (built in memory), SDD/JD/Review/Orchestrator
prompts, AGENTS.md targets for opencode, and skills for .agents/.

The in-memory ``opencode.json`` is composed from the catalog-driven
``build_opencode_config()``. Prompt bodies for ``jd-*``/``review-*``
agents are inlined from on-disk ``.md`` files; ``sdd-*`` agents keep
``{file:{{HOME}}/...}`` template refs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ai_harness.artifacts.agents import Capability, all_agents
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

# ── per-capability dialect ─────────────────────────────────────────────────

_TOOLS_BY_CAPABILITY: dict[Capability, dict[str, bool]] = {
    Capability.ORCHESTRATOR: {"bash": True, "edit": True, "read": True, "task": True, "write": True},
    Capability.EDITS: {"bash": True, "edit": True, "read": True, "write": True},
    Capability.READ_ONLY: {"bash": True, "read": True},
}

_MODE_BY_CAPABILITY: dict[Capability, str] = {
    Capability.ORCHESTRATOR: "primary",
}

_PERMISSION_BY_CAPABILITY: dict[Capability, dict[str, str]] = {
    Capability.READ_ONLY: {"edit": "deny"},
}

_HIDDEN_BY_CAPABILITY: dict[Capability, bool] = {
    Capability.ORCHESTRATOR: False,
}

_PROMPT_KIND_BY_NS: dict[str, str] = {
    "sdd": "file_ref",
    "jd": "inline",
    "review": "inline",
}

# ── per-id model ─────────────────────────────────────────────────────────────

_MODEL_BY_ID: dict[str, str | None] = {
    "sdd-orchestrator": "openai/gpt-5.5",
    "sdd-apply": "opencode-go/deepseek-v4-pro",
    "sdd-archive": "opencode-go/deepseek-v4-flash",
    "sdd-design": "opencode-go/deepseek-v4-pro",
    "sdd-explore": "opencode-go/kimi-k2.7-code",
    "sdd-propose": "opencode-go/deepseek-v4-pro",
    "sdd-spec": "opencode-go/deepseek-v4-pro",
    "sdd-tasks": "opencode-go/deepseek-v4-pro",
    "sdd-verify": "opencode-go/kimi-k2.6",
    "jd-fix-agent": None,
    "jd-judge-a": None,
    "jd-judge-b": None,
    "review-readability": None,
    "review-reliability": None,
    "review-resilience": None,
    "review-risk": None,
}

# ── per-id description ───────────────────────────────────────────────────────

_DESCRIPTION_BY_ID: dict[str, str] = {
    "sdd-orchestrator": "SDD-Orchestrator - coordinates sub-agents, never does work inline",
    "sdd-apply": "Implement code changes from task definitions",
    "sdd-archive": "Archive completed change artifacts",
    "sdd-design": "Create technical design from proposals",
    "sdd-explore": "Investigate codebase and think through ideas",
    "sdd-propose": "Create change proposals from explorations",
    "sdd-spec": "Write detailed specifications from proposals",
    "sdd-tasks": "Break down specs and designs into implementation tasks",
    "sdd-verify": "Validate implementation against specs",
    "jd-fix-agent": "Surgical fix agent for judgment-day protocol",
    "jd-judge-a": "Adversarial code reviewer \u2014 blind judge A for judgment-day protocol",
    "jd-judge-b": "Adversarial code reviewer \u2014 blind judge B for judgment-day protocol",
    "review-readability": (
        "R2 Readability reviewer \u2014 naming, complexity, intention, "
        "maintainability, review size, and context clarity"
    ),
    "review-reliability": (
        "R3 Reliability reviewer \u2014 behavior-first tests, coverage value, "
        "edge cases, determinism, contracts, and regressions"
    ),
    "review-resilience": (
        "R4 Resilience reviewer \u2014 fallbacks, retry/backoff, "
        "graceful degradation, observability, load, rollback, and SLO risks"
    ),
    "review-risk": (
        "R1 Risk reviewer \u2014 security, privilege boundaries, data exposure, "
        "dependency risks, and merge-blocking vulnerabilities"
    ),
}


# ── helpers ──────────────────────────────────────────────────────────────────


def _load_inlined_prompt(prompts_root: Path, agent_id: str) -> str:
    """Read the ``.md`` body for an inline agent verbatim.

    Strips a single trailing newline so the inlined string matches the
    target reference's convention.
    """
    ns = _prompt_ns(agent_id)
    body = (prompts_root / ns / f"{agent_id}.md").read_text(encoding="utf-8")
    return body.rstrip("\n")


def _prompt_ns(agent_id: str) -> str:
    """Map an agent id to its on-disk prompt namespace.

    Uses the catalog's explicit namespace; this helper exists for the
    ``_load_inlined_prompt`` function which still reads from disk.
    """
    from ai_harness.artifacts.agents import get as catalog_get

    return catalog_get(agent_id).namespace


def _build_orchestrator_allowlist() -> dict[str, str]:
    """Build the orchestrator's task allowlist (all sub-agents, * deny).

    Derives the 15 sub-agent names from the catalog.
    """
    allow: dict[str, str] = {"*": "deny"}
    for agent in all_agents():
        if agent.capability != Capability.ORCHESTRATOR:
            allow[agent.id] = "allow"
    return allow


def _build_agent_entry(
    agent_id: str,
    description: str,
    mode: str,
    hidden: bool,
    model: str | None,
    permission: dict[str, str] | None,
    tools: dict[str, bool],
    prompt_kind: str,
    prompt_body: str | None,
) -> dict[str, object]:
    """Compose one agent's JSON dict."""
    entry: dict[str, object] = {
        "description": description,
        "mode": mode,
    }
    if hidden:
        entry["hidden"] = True
    if model is not None:
        entry["model"] = model
    if permission is not None:
        entry["permission"] = dict(permission)
    entry["tools"] = dict(tools)
    if prompt_kind == "file_ref":
        ns = _prompt_ns(agent_id)
        entry["prompt"] = f"{{file:{{{{HOME}}}}/.config/opencode/prompts/{ns}/{agent_id}.md}}"
    else:  # inline
        assert prompt_body is not None, f"inline agent {agent_id} missing body"
        entry["prompt"] = prompt_body
    return entry


def build_opencode_config(prompts_root: Path) -> dict[str, object]:
    """Build the opencode.json configuration dict entirely in memory.

    Iterates the agent catalog; reads inlined bodies for the 7
    ``jd-*``/``review-*`` agents from *prompts_root*. The orchestrator's
    task allowlist is attached last.
    """
    agents: dict[str, object] = {}
    for agent in all_agents():
        capability = agent.capability
        prompt_kind = _PROMPT_KIND_BY_NS.get(agent.namespace, "file_ref")
        prompt_body = _load_inlined_prompt(prompts_root, agent.id) if prompt_kind == "inline" else None

        entry = _build_agent_entry(
            agent_id=agent.id,
            description=_DESCRIPTION_BY_ID[agent.id],
            mode=_MODE_BY_CAPABILITY.get(capability, "subagent"),
            hidden=_HIDDEN_BY_CAPABILITY.get(capability, True),
            model=_MODEL_BY_ID.get(agent.id),
            permission=_PERMISSION_BY_CAPABILITY.get(capability),
            tools=_TOOLS_BY_CAPABILITY[capability],
            prompt_kind=prompt_kind,
            prompt_body=prompt_body,
        )
        agents[agent.id] = entry

    agents["sdd-orchestrator"]["permission"] = {"task": _build_orchestrator_allowlist()}

    return {
        "$schema": "https://opencode.ai/config.json",
        "permission": _PERMISSION_BLOCK,
        "agent": agents,
        "share": "disabled",
    }


# ── installer class ──────────────────────────────────────────────────────────


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
        config = build_opencode_config(prompts_root)
        config_json = json.dumps(config, indent=2) + "\n"
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
