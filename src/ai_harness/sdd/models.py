"""Data model and constants for the SDD status contract.

These dataclasses use snake_case fields; the Go-compatible camelCase JSON shape is
produced by :mod:`ai_harness.compat`, keeping JSON-schema knowledge in one owner.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# SchemaName / SchemaVersion identify the Status JSON contract (Go parity).
SCHEMA_NAME = "ai-harness.sdd-status"
SCHEMA_VERSION = 1

# Reserved subdirectory under openspec/changes/ that holds archived changes; it is
# never treated as an active change.
ARCHIVE_DIR_NAME = "archive"

# Artifact completeness states.
ARTIFACT_MISSING = "missing"
ARTIFACT_PARTIAL = "partial"
ARTIFACT_DONE = "done"

# Phase readiness states in the SDD state machine.
DEP_BLOCKED = "blocked"
DEP_READY = "ready"
DEP_ALL_DONE = "all_done"

# Apply-phase classification (mirrors the dependency states).
APPLY_BLOCKED = "blocked"
APPLY_READY = "ready"
APPLY_ALL_DONE = "all_done"

ARTIFACT_STORE_OPENSPEC = "openspec"
ACTION_MODE_REPO_LOCAL = "repo-local"

# Next-recommended sentinels that are not concrete phases.
NEXT_RESOLVE_BLOCKERS = "resolve-blockers"
NEXT_SDD_NEW = "sdd-new"
NEXT_SELECT_CHANGE = "select-change"
PHASE_APPLY = "apply"
PHASE_VERIFY = "verify"
PHASE_ARCHIVE = "archive"


class SddError(Exception):
    """Raised when the workspace root or its artifacts cannot be resolved/read."""


@dataclass
class ArtifactPaths:
    """Discovered absolute paths per artifact kind; each is always a list."""

    proposal: list[str] = field(default_factory=list)
    specs: list[str] = field(default_factory=list)
    design: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    apply_report: list[str] = field(default_factory=list)
    verify_report: list[str] = field(default_factory=list)


@dataclass
class PlanningHome:
    mode: str
    path: str


@dataclass
class TaskProgress:
    total: int = 0
    completed: int = 0
    pending: int = 0
    all_complete: bool = False


@dataclass
class Dependencies:
    proposal: str = DEP_BLOCKED
    specs: str = DEP_BLOCKED
    design: str = DEP_BLOCKED
    tasks: str = DEP_BLOCKED
    apply: str = DEP_BLOCKED
    verify: str = DEP_BLOCKED
    archive: str = DEP_BLOCKED


@dataclass
class ActionContext:
    mode: str
    workspace_root: str
    allowed_edit_roots: list[str]


@dataclass
class Relationships:
    depends_on: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    amends: list[str] = field(default_factory=list)
    conflicts_with: list[str] = field(default_factory=list)
    same_domain_active_changes: list[str] = field(default_factory=list)


@dataclass
class PhaseInstructions:
    apply: list[str]
    verify: list[str]
    archive: list[str]


@dataclass
class Status:
    """Full resolved SDD state for one change."""

    schema_name: str
    schema_version: int
    change_name: str | None
    artifact_store: str
    planning_home: PlanningHome
    change_root: str | None
    artifact_paths: ArtifactPaths
    context_files: ArtifactPaths
    artifacts: dict[str, str]
    task_progress: TaskProgress
    dependencies: Dependencies
    apply_state: str
    action_context: ActionContext
    relationships: Relationships
    next_recommended: str
    blocked_reasons: list[str]
    phase_instructions: PhaseInstructions | None = None


def _missing_artifacts() -> dict[str, str]:
    return {
        "proposal": ARTIFACT_MISSING,
        "specs": ARTIFACT_MISSING,
        "design": ARTIFACT_MISSING,
        "tasks": ARTIFACT_MISSING,
        "applyReport": ARTIFACT_MISSING,
        "verifyReport": ARTIFACT_MISSING,
    }


def new_base_status(
    root: str,
    change_name: str | None,
    change_root: str | None,
    next_recommended: str,
    reasons: list[str] | None,
) -> Status:
    """Construct a Status at its blocked baseline; resolve_change overwrites the
    computed fields on top. Mirrors Go newBaseStatus."""
    if reasons is None:
        reasons = []
    return Status(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        change_name=change_name,
        artifact_store=ARTIFACT_STORE_OPENSPEC,
        planning_home=PlanningHome(
            mode=ACTION_MODE_REPO_LOCAL,
            path=os.path.join(root, "openspec"),
        ),
        change_root=change_root,
        artifact_paths=ArtifactPaths(),
        context_files=ArtifactPaths(),
        artifacts=_missing_artifacts(),
        task_progress=TaskProgress(),
        dependencies=Dependencies(),
        apply_state=APPLY_BLOCKED,
        action_context=ActionContext(
            mode=ACTION_MODE_REPO_LOCAL,
            workspace_root=root,
            allowed_edit_roots=[root],
        ),
        relationships=Relationships(),
        next_recommended=next_recommended,
        blocked_reasons=reasons,
    )
