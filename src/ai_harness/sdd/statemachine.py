"""Phase state machine: dependencies, apply state, next action, blockers."""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    APPLY_ALL_DONE,
    APPLY_BLOCKED,
    APPLY_READY,
    ARTIFACT_DONE,
    DEP_ALL_DONE,
    DEP_BLOCKED,
    DEP_READY,
    NEXT_RESOLVE_BLOCKERS,
    PHASE_APPLY,
    PHASE_ARCHIVE,
    PHASE_VERIFY,
    Dependencies,
    TaskProgress,
)


@dataclass
class StateMachine:
    apply_state: str
    dependencies: Dependencies
    next: str
    reasons: list[str]


def compute_state_machine(
    artifacts: dict[str, str], tasks: TaskProgress, verify_passing: bool
) -> StateMachine:
    """Derive the apply state, per-phase dependencies, the next recommended
    action, and the blocked reasons from the artifact states, task progress, and
    whether the verify report is clearly passing."""
    core_ready = _is_core_ready(artifacts, tasks)
    apply_state = _resolve_apply_state(core_ready, tasks)

    reasons = _core_blocked_reasons(artifacts, tasks)
    if (
        artifacts["verifyReport"] == ARTIFACT_DONE
        and not verify_passing
        and apply_state != APPLY_READY
    ):
        reasons.append("verify-report.md is not clearly passing.")

    dependencies = _resolve_dependencies(artifacts, tasks, apply_state, core_ready, verify_passing)
    next_recommended = _resolve_next_recommended(dependencies, apply_state)

    return StateMachine(
        apply_state=apply_state,
        dependencies=dependencies,
        next=next_recommended,
        reasons=reasons,
    )


def _is_core_ready(artifacts: dict[str, str], tasks: TaskProgress) -> bool:
    """The four core artifacts are done and tasks.md has at least one checkbox."""
    return (
        artifacts["proposal"] == ARTIFACT_DONE
        and artifacts["specs"] == ARTIFACT_DONE
        and artifacts["design"] == ARTIFACT_DONE
        and artifacts["tasks"] == ARTIFACT_DONE
        and tasks.total > 0
    )


def _resolve_apply_state(core_ready: bool, tasks: TaskProgress) -> str:
    if not core_ready:
        return APPLY_BLOCKED
    if tasks.all_complete:
        return APPLY_ALL_DONE
    return APPLY_READY


def _resolve_dependencies(
    artifacts: dict[str, str],
    tasks: TaskProgress,
    apply_state: str,
    core_ready: bool,
    verify_passing: bool,
) -> Dependencies:
    deps = Dependencies(
        proposal=_artifact_dependency(artifacts["proposal"]),
        specs=_artifact_dependency(artifacts["specs"]),
        design=_artifact_dependency(artifacts["design"]),
        tasks=_artifact_dependency(artifacts["tasks"]),
        apply=_apply_dependency(apply_state),
        verify=DEP_BLOCKED,
        archive=DEP_BLOCKED,
    )

    apply_report_done = artifacts["applyReport"] == ARTIFACT_DONE
    verify_report_done = artifacts["verifyReport"] == ARTIFACT_DONE

    if verify_report_done and core_ready and tasks.all_complete and verify_passing:
        deps.verify = DEP_ALL_DONE
    elif core_ready and (apply_state == APPLY_ALL_DONE or apply_report_done):
        deps.verify = DEP_READY

    if deps.verify == DEP_ALL_DONE and tasks.all_complete:
        deps.archive = DEP_READY
    return deps


def _artifact_dependency(state: str) -> str:
    return DEP_ALL_DONE if state == ARTIFACT_DONE else DEP_BLOCKED


def _apply_dependency(apply_state: str) -> str:
    if apply_state == APPLY_READY:
        return DEP_READY
    if apply_state == APPLY_ALL_DONE:
        return DEP_ALL_DONE
    return DEP_BLOCKED


def _resolve_next_recommended(deps: Dependencies, apply_state: str) -> str:
    """Choose the single next action: apply when ready, else verify when ready,
    else archive when verify is done and apply is done, else resolve-blockers."""
    if deps.apply == DEP_READY:
        return PHASE_APPLY
    if deps.verify == DEP_READY:
        return PHASE_VERIFY
    if deps.verify == DEP_ALL_DONE and apply_state == APPLY_ALL_DONE:
        return PHASE_ARCHIVE
    return NEXT_RESOLVE_BLOCKERS


def _core_blocked_reasons(artifacts: dict[str, str], tasks: TaskProgress) -> list[str]:
    """List the human reasons the core is not ready: one per missing-or-partial
    core artifact, plus a note when tasks.md is present but has no checkboxes."""
    reasons: list[str] = []
    if artifacts["proposal"] != ARTIFACT_DONE:
        reasons.append("proposal.md is missing or partial.")
    if artifacts["specs"] != ARTIFACT_DONE:
        reasons.append("specs/**/spec.md is missing or partial.")
    if artifacts["design"] != ARTIFACT_DONE:
        reasons.append("design.md is missing or partial.")
    if artifacts["tasks"] != ARTIFACT_DONE:
        reasons.append("tasks.md is missing or partial.")
    if artifacts["tasks"] == ARTIFACT_DONE and tasks.total == 0:
        reasons.append("tasks.md has no markdown task checkboxes.")
    return reasons
