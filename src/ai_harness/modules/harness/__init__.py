"""Harness package — core install/uninstall logic, no CLI.

Re-exports the public surface so callers import from the package root:
``from ai_harness.modules.harness import AgentCli, InstallManifest, install_for_agent_clis``.
"""

from ai_harness.modules.harness.labels import LabelResult, ensure_labels
from ai_harness.modules.harness.models import AgentCli
from ai_harness.modules.harness.operations import (
    InitResult,
    InstallManifest,
    init_repo,
    install_for_agent_clis,
    re_render_for_agent_clis,
    uninstall_for_agent_clis,
)
from ai_harness.modules.harness.tasks import (
    Subtask,
    SubtaskInput,
    Task,
    TaskId,
    TaskInput,
    TaskProgress,
    TaskStoreError,
    task_create,
    task_done,
    task_list,
    task_next,
    task_progress,
)
from ai_harness.modules.harness.worktree import (
    RemoveResult,
    WorktreeEntry,
    WorktreeResult,
    create_worktree,
    list_worktrees,
    remove_worktree,
)

__all__ = [
    "AgentCli",
    "InitResult",
    "InstallManifest",
    "LabelResult",
    "RemoveResult",
    "Subtask",
    "SubtaskInput",
    "Task",
    "TaskId",
    "TaskInput",
    "TaskProgress",
    "TaskStoreError",
    "WorktreeEntry",
    "WorktreeResult",
    "create_worktree",
    "ensure_labels",
    "init_repo",
    "install_for_agent_clis",
    "task_create",
    "task_done",
    "task_list",
    "task_next",
    "task_progress",
    "list_worktrees",
    "re_render_for_agent_clis",
    "remove_worktree",
    "uninstall_for_agent_clis",
]
