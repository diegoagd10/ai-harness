"""Provider-administrator dispatch — one concrete admin per supported CLI.

Callers select an administrator by :class:`AgentCli`:

    >>> from ai_harness.modules.harness.administrators import ADMINISTRATORS
    >>> from ai_harness.modules.harness.models import AgentCli
    >>> artifacts = ADMINISTRATORS[AgentCli.CLAUDE].render_artifacts()

The ``ADMINISTRATORS`` dispatch is built once at import time. CLIs not in
the dispatch (e.g. :attr:`AgentCli.GENERIC`) have no native agent
support — callers that need generic behavior should use
``ADMINISTRATORS.get(cli)`` and treat absence as no rendered artifacts.

Public surface (re-exported here for ergonomics)
-----------------------------------------------
``Artifact``, ``AgentMetadata``, ``AgentCaps``, ``ArtifactsAdministrator``,
``ClaudeArtifactsAdministrator``, ``OpenCodeArtifactsAdministrator``,
``CopilotArtifactsAdministrator``, ``ADMINISTRATORS``,
``load_agent_metadata``, ``discover_agent_names``.

Administrator Strategy dispatch
------------------------------
``ADMINISTRATORS`` is the Strategy seam for the harness. Callers select
a provider by :class:`AgentCli` and the dispatch hands them a concrete
``ArtifactsAdministrator`` whose ``render_artifacts`` carries the
provider-specific frontmatter + install-path knowledge. Only
``render_artifacts`` is provider-specific; metadata and discovery are
inherited from the ABC default.

::

    operations / wizard / commands
                |
                v
    ADMINISTRATORS[AgentCli.X]
                |
                v
    ArtifactsAdministrator (ABC)
      | render_artifacts(...)   abstract — per-provider
      | get_agent_metadata(...) default — _resolve_agent_metadata
      | discover_agent_names()  default — module-level discovery
                |
       +--------+--------+--------+
       v                 v                v
    Claude          OpenCode          Copilot
    admin           admin             admin
"""

from __future__ import annotations

from ai_harness.modules.harness.administrators.base import (
    AgentCaps,
    AgentMetadata,
    Artifact,
    ArtifactsAdministrator,
    discover_agent_names,
    load_agent_metadata,
)
from ai_harness.modules.harness.administrators.claude import ClaudeArtifactsAdministrator
from ai_harness.modules.harness.administrators.copilot import CopilotArtifactsAdministrator
from ai_harness.modules.harness.administrators.opencode import OpenCodeArtifactsAdministrator
from ai_harness.modules.harness.models import AgentCli

__all__ = [
    "ADMINISTRATORS",
    "AgentCaps",
    "AgentMetadata",
    "Artifact",
    "ArtifactsAdministrator",
    "ClaudeArtifactsAdministrator",
    "CopilotArtifactsAdministrator",
    "OpenCodeArtifactsAdministrator",
    "discover_agent_names",
    "load_agent_metadata",
]


# Dispatch table — populated with one administrator per supported CLI.
# Generic has no administrator; callers that need generic behavior should
# use ``ADMINISTRATORS.get(AgentCli.GENERIC)`` and treat absence as a no-op.
ADMINISTRATORS: dict[AgentCli, ArtifactsAdministrator] = {
    AgentCli.CLAUDE: ClaudeArtifactsAdministrator(),
    AgentCli.OPENCODE: OpenCodeArtifactsAdministrator(),
    AgentCli.COPILOT: CopilotArtifactsAdministrator(),
}
