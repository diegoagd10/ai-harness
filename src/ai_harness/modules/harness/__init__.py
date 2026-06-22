"""Harness package — core install/uninstall logic, no CLI.

Re-exports the public surface so callers import from the package root:
``from ai_harness.modules.harness import AgentCli, InstallManifest, install_for_agent_clis``.
"""

from ai_harness.modules.harness.labels import LabelResult, ensure_labels
from ai_harness.modules.harness.models import AgentCli, InitResult, InstallManifest
from ai_harness.modules.harness.operations import (
    init_repo,
    install_for_agent_clis,
    re_render_for_agent_clis,
    uninstall_for_agent_clis,
)
from ai_harness.modules.harness.worktree import WorktreeResult, create_worktree

__all__ = [
    "AgentCli",
    "InitResult",
    "InstallManifest",
    "LabelResult",
    "WorktreeResult",
    "create_worktree",
    "ensure_labels",
    "init_repo",
    "install_for_agent_clis",
    "re_render_for_agent_clis",
    "uninstall_for_agent_clis",
]
