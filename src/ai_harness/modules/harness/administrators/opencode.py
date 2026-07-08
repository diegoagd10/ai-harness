"""OpenCode artifacts administrator — owns OpenCode frontmatter and install paths.

This module is the single source of truth for everything OpenCode-specific in
the harness:

- the ``.config/opencode/agent/<name>.md`` install path
- the OpenCode frontmatter shape (``description``, ``mode``, ``model``,
  optional ``reasoningEffort``, optional ``permission``, optional ``color``)
- the ``effort.opencode`` → ``reasoningEffort`` mapping
- the explicit ``permission`` precedence over caps-derived permission
- the ``color`` passthrough
- the ``mode`` passthrough (default ``"subagent"``)
- the caps → permission translation via :func:`_opencode_permission`

Callers select this administrator and call
:meth:`render_artifacts` polymorphically — no per-provider branching
in :mod:`ai_harness.modules.harness.operations` or the wizard.

Cross-package boundary
----------------------
This file imports shared helpers (``Artifact``, ``AgentMetadata``, YAML
dump, template body read, override resolution, public discovery) from
``base``. It MUST NOT import from :mod:`ai_harness.claude` or
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

__all__ = ["OpenCodeArtifactsAdministrator"]


# ---------------------------------------------------------------------------
# Install-path constants — provider-local POSIX anchors relative to ``home``.
# ---------------------------------------------------------------------------

_OPENCODE_AGENT_DIR = ".config/opencode/agent"


# ---------------------------------------------------------------------------
# Private provider helpers — used only by OpenCodeArtifactsAdministrator.
# ---------------------------------------------------------------------------


def _opencode_permission(caps: AgentCaps) -> dict:
    """Translate caps into OpenCode's ``permission`` block.

    Only deviations from OpenCode's allow-by-default are emitted, so a
    full-capability agent yields ``{}`` (no permission block).
    """
    perm: dict = {}
    if not caps.write:
        perm["edit"] = "deny"
        perm["write"] = "deny"
    if not caps.bash:
        perm["bash"] = "deny"
    if caps.spawn is not None:
        perm["task"] = {"*": "deny", **{name: "allow" for name in caps.spawn}}
    return perm


def _render_opencode_agent_artifact(name: str, meta: AgentMetadata) -> Artifact:
    """Render an OpenCode change agent as an Artifact at ``.config/opencode/agent/<name>.md``.

    Frontmatter keys (ordered): ``description``, ``mode``, ``model``,
    optional ``reasoningEffort``, optional ``permission``, optional ``color``.

    ``model.opencode`` is required; missing/non-string raises
    :class:`ValueError`. ``effort.opencode = null`` (or missing) omits
    the ``reasoningEffort`` key — the wizard clears effort for
    non-reasoning models and a stale ``reasoningEffort: null`` would
    violate the renderer contract.

    Explicit ``permission`` (raw dict) wins over caps-derived permission.
    Caps-derived permission is omitted when empty (no ``{}`` block on
    disk). ``color`` passes through when present; OpenCode accepts hex
    colors of the form ``#RGB``/``#RRGGBB`` or named colors (validation
    is left to OpenCode itself).
    """
    body = _read_template_body(name)
    model_opencode = meta.model.get("opencode")
    if not isinstance(model_opencode, str):
        raise ValueError(f"Template {name}: missing or invalid model.opencode")

    fm: dict[str, object] = {
        "description": meta.description,
        "mode": meta.mode,
        "model": model_opencode,
    }

    if "opencode" in meta.effort and meta.effort["opencode"] is not None:
        fm["reasoningEffort"] = meta.effort["opencode"]

    if meta.permission is not None:
        fm["permission"] = dict(meta.permission)
    else:
        derived = _opencode_permission(meta.caps)
        if derived:
            fm["permission"] = derived

    if isinstance(meta.color, str):
        fm["color"] = meta.color

    yaml_text = _yaml_dump_frontmatter(fm)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return Artifact(install_path=f"{_OPENCODE_AGENT_DIR}/{name}.md", content=rendered)


# ---------------------------------------------------------------------------
# Public administrator — the seam callers select through ADMINISTRATORS.
# ---------------------------------------------------------------------------


class OpenCodeArtifactsAdministrator(ArtifactsAdministrator):
    """OpenCode provider administrator — owns OpenCode frontmatter and install paths.

    See module docstring for the contract.
    """

    provider: str = "opencode"

    def render_artifacts(
        self,
        names: list[str] | None = None,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> list[Artifact]:
        """Render OpenCode change agents to installable artifacts."""
        resolved_names = list(names) if names is not None else self.discover_agent_names()
        artifacts: list[Artifact] = []
        for name in resolved_names:
            metadata = self.get_agent_metadata(name, overrides=overrides, home=home)
            artifacts.append(_render_opencode_agent_artifact(name, metadata))
        return artifacts
