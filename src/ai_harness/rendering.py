"""Human-readable dispatcher markdown for sdd-continue.

This is the presentation layer: it renders a resolved Status as structured
markdown targeting LLM consumption. A single public function hides the section
ordering, conditional blocks, and fenced JSON formatting. No Rich, no ANSI.
"""

from __future__ import annotations

from . import compat
from .sdd import Status
from .sdd.instructions import build_phase_instructions
from .sdd.models import PHASE_APPLY, PHASE_ARCHIVE, PHASE_VERIFY

UNRESOLVED_CHANGE = "unresolved"

# Concrete phase identifiers that have renderable next-phase instructions.
_PHASES_WITH_INSTRUCTIONS = (PHASE_APPLY, PHASE_VERIFY, PHASE_ARCHIVE)


def render_dispatcher(status: Status) -> str:
    """Render the routing-oriented dispatcher markdown for sdd-continue.

    Produces plain markdown (no Rich, no ANSI) targeting LLM consumption.
    The output contains seven sections in fixed order: header, advisory,
    next recommendation, dependency states, blocked reasons (conditional),
    next-phase instructions (conditional), and a fenced JSON block.
    """
    change = status.change_name if status.change_name is not None else UNRESOLVED_CHANGE
    deps = status.dependencies
    progress = status.task_progress

    # Section 1: header + advisory + next_recommended + dependency states
    lines: list[str] = [
        f"## Native SDD Dispatcher: {change}",
        "",
        "Native status is authoritative. Route by next_recommended and "
        "dependency state, not by prompt inference.",
        "",
        f"next_recommended: {status.next_recommended}",
        "",
        "### Dependency States",
        f"- proposal: {deps.proposal}",
        f"- specs: {deps.specs}",
        f"- design: {deps.design}",
        f"- tasks: {deps.tasks}",
        f"- apply: {deps.apply}",
        f"- verify: {deps.verify}",
        f"- archive: {deps.archive}",
        f"- task_progress: {progress.completed}/{progress.total} complete",
    ]

    # Section 2: blocked reasons (conditional)
    if status.blocked_reasons:
        lines.append("")
        lines.append("### Blocked Reasons")
        for reason in status.blocked_reasons:
            lines.append(f"- {reason}")

    # Section 3: next-phase instructions (conditional, concrete phases only)
    phase = _phase_with_instructions(status.next_recommended)
    if phase is not None:
        lines.append("")
        lines.append(f"### Next Phase Instructions: {phase}")
        for instruction in _instructions_for_phase(status, phase):
            lines.append(f"- {instruction}")

    # Section 4: fenced JSON block
    lines.append("")
    lines.append("### JSON")
    lines.append("```json")
    lines.append(compat.status_to_json(status))
    lines.append("```")
    return "\n".join(lines)


def _phase_with_instructions(next_recommended: str) -> str | None:
    """Return the phase name when next_recommended has renderable instructions.

    Only the three concrete phases qualify; sentinels return None.
    """
    if next_recommended in _PHASES_WITH_INSTRUCTIONS:
        return next_recommended
    return None


def _instructions_for_phase(status: Status, phase: str) -> list[str]:
    """Return the per-phase instruction lines, building them on demand when the
    status does not carry them."""
    instructions = status.phase_instructions
    if instructions is None:
        instructions = build_phase_instructions(status)
    if phase == PHASE_APPLY:
        return list(instructions.apply)
    if phase == PHASE_VERIFY:
        return list(instructions.verify)
    if phase == PHASE_ARCHIVE:
        return list(instructions.archive)
    return []
