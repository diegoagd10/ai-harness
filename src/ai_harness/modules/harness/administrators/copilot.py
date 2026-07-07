"""Copilot artifacts administrator — owns the minimal Copilot frontmatter.

This module is the single source of truth for everything Copilot-specific in
the harness:

- the corrected ``.copilot/agents/<name>.agent.md`` install path (this
  intentionally differs from the PRD's ``.github/instructions/...`` text —
  see design.md for the factual correction)
- the intentionally minimal ``name`` + ``description`` frontmatter
- the absence of any ``model``, ``tools``, ``user-invocable``,
  ``disable-model-invocation``, permission, mode, or color emission
  (Copilot CLI does not honor them — emitting them would write
  fields Copilot does not support)
- the absence of a ``model.copilot`` requirement (Copilot sets its
  model globally through ``/model`` or ``~/.copilot/settings.json``,
  not per-agent)

Callers select this administrator and call
:meth:`render_artifacts` polymorphically — no per-provider branching
in :mod:`ai_harness.modules.harness.operations` or the wizard.

Cross-package boundary
----------------------
This file imports shared helpers (``Artifact``, ``AgentMetadata``, YAML
dump, template body read, override resolution, public discovery) from
``base``. It MUST NOT import from :mod:`ai_harness.claude` or
:mod:`ai_harness.opencode` siblings — every cross-provider detail is
``base``'s responsibility.
"""

from __future__ import annotations

from pathlib import Path

from ai_harness.modules.harness.administrators.base import (
    AgentMetadata,
    Artifact,
    ArtifactsAdministrator,
    _read_template_body,
    _resolve_agent_metadata,
    _yaml_dump_frontmatter,
    discover_agent_names,
)

__all__ = ["CopilotArtifactsAdministrator"]


# ---------------------------------------------------------------------------
# Install-path constants — provider-local POSIX anchors relative to ``home``.
# ---------------------------------------------------------------------------

_COPILOT_AGENT_DIR = ".copilot/agents"


# ---------------------------------------------------------------------------
# Private provider helpers — used only by CopilotArtifactsAdministrator.
# ---------------------------------------------------------------------------


def _render_copilot_agent_artifact(name: str, meta: AgentMetadata) -> Artifact:
    """Render a Copilot change agent as an Artifact at ``.copilot/agents/<name>.agent.md``.

    Frontmatter is intentionally minimal — only ``name`` and ``description``.
    Copilot CLI ignores ``model``, ``tools``, ``user-invocable``,
    ``disable-model-invocation``, permission, mode, and color, so emitting
    more would write fields Copilot does not honor. ``model.copilot``
    is intentionally NOT required — the Copilot CLI's model is set
    globally (via ``/model`` or ``~/.copilot/settings.json``), not
    per-agent.
    """
    body = _read_template_body(name)
    fm: dict[str, object] = {
        "name": name,
        "description": meta.description,
    }
    yaml_text = _yaml_dump_frontmatter(fm)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return Artifact(install_path=f"{_COPILOT_AGENT_DIR}/{name}.agent.md", content=rendered)


# ---------------------------------------------------------------------------
# Public administrator — the seam callers select through ADMINISTRATORS.
# ---------------------------------------------------------------------------


class CopilotArtifactsAdministrator(ArtifactsAdministrator):
    """Copilot provider administrator — owns the minimal Copilot frontmatter.

    See module docstring for the contract.
    """

    provider: str = "copilot"

    def render_artifacts(
        self,
        names: list[str] | None = None,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> list[Artifact]:
        """Render Copilot change agents to installable artifacts."""
        resolved_names = list(names) if names is not None else self.discover_agent_names()
        artifacts: list[Artifact] = []
        for name in resolved_names:
            metadata = self.get_agent_metadata(name, overrides=overrides, home=home)
            artifacts.append(_render_copilot_agent_artifact(name, metadata))
        return artifacts

    def get_agent_metadata(
        self,
        name: str,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> AgentMetadata:
        """Return Copilot-resolved metadata for *name* with overrides applied."""
        return _resolve_agent_metadata(name, overrides=overrides, home=home)

    def discover_agent_names(self) -> list[str]:
        """Return visible Copilot change-agent template names.

        Discovery is provider-agnostic — every administrator sees the same
        visible template set, sourced from
        :func:`ai_harness.modules.harness.administrators.base.discover_agent_names`.
        """
        return discover_agent_names()
