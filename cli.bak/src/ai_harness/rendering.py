"""Human-readable rendering for the SDD commands.

Rich lives only here: it formats the terminal display and never participates in
the deterministic ``--json`` path (see :mod:`ai_harness.compat`). Rendering reads
an already-resolved Status and computes no SDD state.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from . import compat
from .sdd import Status
from .sdd.instructions import build_phase_instructions
from .sdd.models import PHASE_APPLY, PHASE_ARCHIVE, PHASE_VERIFY

UNRESOLVED_CHANGE = "unresolved"


def render_status(status: Status, console: Console | None = None) -> None:
    """Render a status summary for sdd-status to the terminal using Rich."""
    console = console or Console()
    change = status.change_name if status.change_name is not None else UNRESOLVED_CHANGE

    console.print(f"[bold]SDD Status:[/bold] {change}")
    console.print(f"schema: {status.schema_name}@{status.schema_version}")
    console.print(f"store: {status.artifact_store}")
    console.print(f"planning_home: {status.planning_home.path}")
    console.print(f"next: {status.next_recommended}")

    table = Table(title="Summary", show_header=True, header_style="bold")
    table.add_column("phase")
    table.add_column("state")
    table.add_row("apply", status.dependencies.apply)
    table.add_row("verify", status.dependencies.verify)
    table.add_row("archive", status.dependencies.archive)
    table.add_row(
        "tasks",
        f"{status.task_progress.completed}/{status.task_progress.total} complete",
    )
    console.print(table)

    if status.blocked_reasons:
        console.print("[bold]Blocked Reasons[/bold]")
        for reason in status.blocked_reasons:
            console.print(f"- {reason}")


# Concrete phase identifiers that have renderable next-phase instructions. Mirrors
# Go's ``recommendedPhase`` switch.
_PHASES_WITH_INSTRUCTIONS = (PHASE_APPLY, PHASE_VERIFY, PHASE_ARCHIVE)


def render_dispatcher(status: Status) -> str:
    """Render the routing-oriented dispatcher markdown for sdd-continue.

    Produces plain markdown (no Rich, no ANSI) targeting LLM consumption:
    dispatcher header, the next recommended action, every dependency state,
    blocked reasons (when present), the next phase's instructions (when next
    is a concrete phase), and a fenced JSON block with the full Status.
    """
    change = status.change_name if status.change_name is not None else UNRESOLVED_CHANGE
    deps = status.dependencies
    progress = status.task_progress

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

    if status.blocked_reasons:
        lines.append("")
        lines.append("### Blocked Reasons")
        for reason in status.blocked_reasons:
            lines.append(f"- {reason}")

    phase = _phase_with_instructions(status.next_recommended)
    if phase is not None:
        lines.append("")
        lines.append(f"### Next Phase Instructions: {phase}")
        for instruction in _instructions_for_phase(status, phase):
            lines.append(f"- {instruction}")

    lines.append("")
    lines.append("### JSON")
    lines.append("```json")
    lines.append(compat.status_to_json(status))
    lines.append("```")
    return "\n".join(lines)


def _phase_with_instructions(next_recommended: str) -> str | None:
    """Return the phase name when next_recommended has renderable instructions.

    Mirrors Go's ``recommendedPhase``: only the three concrete phases qualify;
    sentinels like ``resolve-blockers`` / ``sdd-new`` / ``select-change`` return
    None.
    """
    if next_recommended in _PHASES_WITH_INSTRUCTIONS:
        return next_recommended
    return None


def _instructions_for_phase(status: Status, phase: str) -> list[str]:
    """Return the per-phase instruction lines, building them on demand when the
    status did not carry them. Mirrors Go's ``instructionsForPhase``."""
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
