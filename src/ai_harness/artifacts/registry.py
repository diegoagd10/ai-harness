"""Deep module — single source of truth for the agent catalog.

Hides: which agents exist, their display labels, their canonical IDs, and
which installer class implements each one.  Exposes a narrow surface: the
ordered agent listing, the supported ID tuple, and a class-resolver helper.
"""

from __future__ import annotations

from ai_harness.artifacts.installers.claude import ClaudeInstaller
from ai_harness.artifacts.installers.copilot import CopilotInstaller
from ai_harness.artifacts.installers.opencode import OpencodeInstaller

#: Ordered (canonical-id, display-label) pairs used by the wizard.
AGENTS: tuple[tuple[str, str], ...] = (
    ("opencode", "OpenCode"),
    ("claude", "Claude Code"),
    ("copilot", "Copilot CLI"),
)

#: Canonical IDs in the same fixed order (convenience for iteration).
SUPPORTED_AGENT_IDS: tuple[str, ...] = tuple(a[0] for a in AGENTS)

#: Internal mapping — not part of the public surface.
_installer_registry: dict[str, type] = {
    "opencode": OpencodeInstaller,
    "claude": ClaudeInstaller,
    "copilot": CopilotInstaller,
}


def get_installer(agent_id: str) -> type:
    """Return the installer class for *agent_id*.

    Raises :exc:`ValueError` when *agent_id* is unknown.
    """
    try:
        return _installer_registry[agent_id]
    except KeyError:
        raise ValueError(f"Unknown agent id: {agent_id!r}") from None
