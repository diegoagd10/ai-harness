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
    OPENCODE = "opencode"


@dataclass(frozen=True, slots=True)
class InstallManifest:
    """The exact record ``uninstall_for_agent_clis`` consumes.

    Persisted to ``~/.ai-harness/installed.json``.
    """

    agent_clis: list[AgentCli]
    written_paths: list[Path]


@dataclass(frozen=True, slots=True)
class InitResult:
    """Observable outcome of ``init_repo``.

    Each field reports whether the corresponding artifact was written.
    ``wrote_labels_policy`` is ``False`` when markers are already present
    or when ``CLAUDE.md`` does not exist; ``claude_md_missing``
    distinguishes the two skip cases.
    """

    wrote_standards: bool
    wrote_labels_policy: bool
    claude_md_missing: bool = False
