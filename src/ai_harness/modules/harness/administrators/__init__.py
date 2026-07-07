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
