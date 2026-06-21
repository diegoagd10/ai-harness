"""Harness package — core install/uninstall logic, no CLI.

Re-exports the public surface so callers import from the package root:
``from ai_harness.modules.harness import AgentCli, InstallManifest, install_for_agent_clis``.
"""

from ai_harness.modules.harness.models import AgentCli, InstallManifest
from ai_harness.modules.harness.operations import (
    install_for_agent_clis,
    re_render_for_agent_clis,
    uninstall_for_agent_clis,
)

__all__ = [
    "AgentCli",
    "InstallManifest",
    "install_for_agent_clis",
    "re_render_for_agent_clis",
    "uninstall_for_agent_clis",
]
