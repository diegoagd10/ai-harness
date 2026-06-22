"""Harness domain models — agent CLI vocabulary shared across modules.

No operations live here. This module holds only the AgentCli enum.

Public surface
--------------
AgentCli
"""

from __future__ import annotations

from enum import StrEnum


class AgentCli(StrEnum):
    GENERIC = "generic"
    CLAUDE = "claude"
    COPILOT = "copilot"
    OPENCODE = "opencode"


__all__ = ["AgentCli"]
