"""Claude artifacts administrator — owns Claude frontmatter and install paths.

This module is the single source of truth for everything Claude-specific in
the harness:

- skill-vs-agent mode dispatch (``mode == "primary"`` → skill directory,
  every other value → agents directory)
- the ``.claude/skills/<name>/SKILL.md`` and ``.claude/agents/<name>.md``
  install paths
- the Claude frontmatter shape (``name``, ``description``, ``model``,
  optional ``effort``, optional ``tools``)
- the spawn-allowlist prose injection for primary skills (Claude skill
  frontmatter has no field to enforce spawn restrictions)
- the caps → tools translation via :func:`_claude_tools`

Callers select this administrator and call
:meth:`render_artifacts` polymorphically — no per-provider branching
in :mod:`ai_harness.modules.harness.operations` or the wizard.

Cross-package boundary
----------------------
This file imports shared helpers (``Artifact``, ``AgentMetadata``, YAML
dump, template body read, override resolution, public discovery) from
``base``. It MUST NOT import from :mod:`ai_harness.opencode` or
:mod:`ai_harness.copilot` siblings — every cross-provider detail is
``base``'s responsibility.
"""

from __future__ import annotations

from pathlib import Path

from ai_harness.modules.harness.administrators.base import (
    AgentCaps,
    AgentMetadata,
    Artifact,
    ArtifactsAdministrator,
    _read_template_body,
    _yaml_dump_frontmatter,
)

__all__ = ["ClaudeArtifactsAdministrator"]


# ---------------------------------------------------------------------------
# Install-path constants — provider-local POSIX anchors relative to ``home``.
# ---------------------------------------------------------------------------

_CLAUDE_AGENTS_DIR = ".claude/agents"
_CLAUDE_SKILLS_DIR = ".claude/skills"


# ---------------------------------------------------------------------------
# Private provider helpers — used only by ClaudeArtifactsAdministrator.
# ---------------------------------------------------------------------------


def _claude_tools(caps: AgentCaps) -> list[str]:
    """Translate caps into a Claude ``tools`` allow-list.

    Claude's ``tools`` is a closed allow-list — set it and the agent gets
    ONLY these, nothing else. So this translation is necessarily coarse:
    it expresses "restricted minimal set" vs "everything" (omit tools),
    not fine-grained subtractions from Claude's full toolset. ``spawn``
    is not reflected here — every spawn-capable agent is ``mode=primary``
    and renders via :func:`_render_claude_skill_artifact`, never the
    agent renderer.
    """
    tools = ["Read", "Grep", "Glob"]
    if caps.write:
        tools += ["Edit", "Write"]
    if caps.bash:
        tools.append("Bash")
    return tools


def _render_claude_agent_artifact(name: str, meta: AgentMetadata) -> Artifact:
    """Render a Claude subagent as an Artifact at ``.claude/agents/<name>.md``."""
    body = _read_template_body(name)
    fm: dict[str, object] = {
        "name": name,
        "description": meta.description,
        "model": meta.model.get("claude"),
    }
    # ``model.claude`` is required for Claude rendering.
    if not isinstance(fm["model"], str):
        raise ValueError(f"Template {name}: missing or invalid model.claude")
    if "claude" in meta.effort and meta.effort["claude"] is not None:
        fm["effort"] = meta.effort["claude"]
    if meta.caps != AgentCaps():
        fm["tools"] = ", ".join(_claude_tools(meta.caps))
    yaml_text = _yaml_dump_frontmatter(fm)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return Artifact(install_path=f"{_CLAUDE_AGENTS_DIR}/{name}.md", content=rendered)


def _render_claude_skill_artifact(name: str, meta: AgentMetadata) -> Artifact:
    """Render a primary Claude change agent as a skill Artifact.

    Skills carry only ``description`` in frontmatter — no model, effort,
    or tools. Overrides are intentionally ignored for skills: they run
    on the session model and inherit the user's effort setting. If
    ``caps.spawn`` is non-empty, append a spawn allowlist prose section
    because Claude skill frontmatter cannot enforce spawn restrictions.
    """
    if meta.mode != "primary":
        raise ValueError(f"Template {name}: mode must be primary for a skill, got {meta.mode!r}")
    if not isinstance(meta.model.get("claude"), str):
        raise ValueError(f"Template {name}: missing or invalid model.claude")
    body = _read_template_body(name)
    fm: dict[str, object] = {"description": meta.description}
    spawn_note = ""
    if meta.caps.spawn:
        names = ", ".join(f"`{a}`" for a in meta.caps.spawn)
        spawn_note = (
            "\n\n## Subagent spawn allowlist\n\n"
            "Claude skills cannot enforce spawn restrictions in frontmatter. "
            "The following prose constraint replaces the OpenCode "
            f"``permission.task`` allowlist:\n\n"
            f"Only spawn these subagents: {names}.\n"
        )
    yaml_text = _yaml_dump_frontmatter(fm)
    rendered = f"---\n{yaml_text}\n---\n{body}{spawn_note}"
    return Artifact(install_path=f"{_CLAUDE_SKILLS_DIR}/{name}/SKILL.md", content=rendered)


# ---------------------------------------------------------------------------
# Public administrator — the seam callers select through ADMINISTRATORS.
# ---------------------------------------------------------------------------


class ClaudeArtifactsAdministrator(ArtifactsAdministrator):
    """Claude provider administrator — owns Claude frontmatter and install paths.

    See module docstring for the contract.
    """

    provider: str = "claude"

    def render_artifacts(
        self,
        names: list[str] | None = None,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> list[Artifact]:
        """Render Claude change agents to installable artifacts."""
        resolved_names = list(names) if names is not None else self.discover_agent_names()
        artifacts: list[Artifact] = []
        for name in resolved_names:
            metadata = self.get_agent_metadata(name, overrides=overrides, home=home)
            if metadata.mode == "primary":
                artifacts.append(_render_claude_skill_artifact(name, metadata))
            else:
                artifacts.append(_render_claude_agent_artifact(name, metadata))
        return artifacts
