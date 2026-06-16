"""Unit tests for build_phase_instructions: per-phase hint lines.

Targets build_phase_instructions directly. The function is pure:
a Status in, a PhaseInstructions out. We construct Status fixtures
by hand to exercise all three phases, the "unresolved" fallback,
and the dependency-state reflection.
"""

from __future__ import annotations

from ai_harness.sdd.instructions import build_phase_instructions
from ai_harness.sdd.models import (
    ARTIFACT_STORE_OPENSPEC,
    DEP_BLOCKED,
    DEP_READY,
    PHASE_APPLY,
    PHASE_VERIFY,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    ActionContext,
    ArtifactPaths,
    Dependencies,
    PhaseInstructions,
    PlanningHome,
    Relationships,
    Status,
    TaskProgress,
)


def _build_status(
    change_name: str | None = "fix-auth",
    deps: Dependencies | None = None,
) -> Status:
    root = "/tmp/workspace"
    return Status(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        change_name=change_name,
        artifact_store=ARTIFACT_STORE_OPENSPEC,
        planning_home=PlanningHome(mode="repo-local", path=f"{root}/openspec"),
        change_root=f"{root}/openspec/changes/{change_name}" if change_name else None,
        artifact_paths=ArtifactPaths(),
        context_files=ArtifactPaths(),
        artifacts={},
        task_progress=TaskProgress(total=2, completed=0, pending=2, all_complete=False),
        dependencies=deps or Dependencies(apply=DEP_READY),
        apply_state="ready",
        action_context=ActionContext(
            mode="repo-local",
            workspace_root=root,
            allowed_edit_roots=[root],
        ),
        relationships=Relationships(),
        next_recommended=PHASE_APPLY,
        blocked_reasons=[],
        phase_instructions=None,
    )


def test_apply_phase_returns_four_hint_lines():
    status = _build_status("fix-auth")
    result = build_phase_instructions(status)
    assert isinstance(result, PhaseInstructions)
    assert len(result.apply) == 4
    assert result.apply[0] == "Change: fix-auth"
    assert result.apply[1] == "State: ready"
    assert "Read proposal" in result.apply[2]
    assert "update tasks.md checkboxes" in result.apply[3]


def test_verify_phase_returns_four_hint_lines():
    status = _build_status("feat-x")
    result = build_phase_instructions(status)
    assert len(result.verify) == 4
    assert result.verify[0] == "Change: feat-x"
    assert result.verify[1] == f"State: {status.dependencies.verify}"
    assert "Verify implementation" in result.verify[2]
    assert "apply-progress.md exists" in result.verify[3]


def test_archive_phase_returns_three_hint_lines():
    status = _build_status("old-change")
    result = build_phase_instructions(status)
    assert len(result.archive) == 3
    assert result.archive[0] == "Change: old-change"
    assert result.archive[1] == f"State: {status.dependencies.archive}"
    assert "verify-report.md exists" in result.archive[2]


def test_change_name_none_uses_unresolved():
    status = _build_status(None)
    result = build_phase_instructions(status)
    assert result.apply[0] == "Change: unresolved"
    assert result.verify[0] == "Change: unresolved"
    assert result.archive[0] == "Change: unresolved"


def test_change_name_reflected_across_all_phases():
    status = _build_status("specific-name")
    result = build_phase_instructions(status)
    assert result.apply[0] == "Change: specific-name"
    assert result.verify[0] == "Change: specific-name"
    assert result.archive[0] == "Change: specific-name"


def test_dependency_state_reflected_in_instructions():
    deps = Dependencies(apply=DEP_READY, verify=DEP_BLOCKED, archive=DEP_READY)
    status = _build_status("feat-y", deps=deps)
    result = build_phase_instructions(status)
    assert result.apply[1] == "State: ready"
    assert result.verify[1] == "State: blocked"
    assert result.archive[1] == "State: ready"
