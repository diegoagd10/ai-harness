"""Harness domain models — agent CLI vocabulary and the install→uninstall contract.

No operations live here. This module is the typed vocabulary shared by the
harness operations and the command layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class AgentCli(StrEnum):
    GENERIC = "generic"
    CLAUDE = "claude"
    COPILOT = "copilot"


@dataclass(frozen=True, slots=True)
class InstallManifest:
    """The exact record ``uninstall_for_agent_clis`` consumes.

    Persisted to ``~/.ai-harness/installed.json``.
    """

    agent_clis: list[AgentCli]
    written_paths: list[Path]
