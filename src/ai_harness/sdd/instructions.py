"""Build PhaseInstructions from a resolved Status.

This module is a deep-module extension: one public function hides the per-phase
message tables that would otherwise be duplicated across consumers. Callers
express intent ("build me the instructions"), not mechanics.
"""

from __future__ import annotations

from .models import PhaseInstructions, Status

UNRESOLVED_CHANGE = "unresolved"


def build_phase_instructions(status: Status) -> PhaseInstructions:
    """Compose the per-phase guidance from the resolved status.

    Returns a fully-populated PhaseInstructions with all three phases
    (apply, verify, archive). The change name defaults to "unresolved"
    when status.change_name is None. Each phase carries 3–4 instruction
    lines matching Go's buildPhaseInstructions (render.go:124-148).
    """
    change = status.change_name if status.change_name is not None else UNRESOLVED_CHANGE
    return PhaseInstructions(
        apply=[
            f"Change: {change}",
            f"State: {status.dependencies.apply}",
            "Read proposal, specs, design, and tasks before editing.",
            "Implement only unchecked tasks and update tasks.md checkboxes as work completes.",
        ],
        verify=[
            f"Change: {change}",
            f"State: {status.dependencies.verify}",
            "Verify implementation against proposal, specs, design, and task completion.",
            "Incomplete tasks remain archive blockers even when apply-progress.md exists.",
        ],
        archive=[
            f"Change: {change}",
            f"State: {status.dependencies.archive}",
            "Archive only when verify-report.md exists and every task checkbox is complete.",
        ],
    )
