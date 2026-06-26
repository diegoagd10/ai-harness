"""Init command — thin typer adapter over ``init_repo``.

No business logic here; the command delegates to ``init_repo`` and echoes
the result. This is a repo-local scaffold (distinct from the global ``install``).
"""

from __future__ import annotations

import typer

from ai_harness.modules.harness import init_repo


def init() -> None:
    """Scaffold CODING_STANDARDS.md, the agent-doc labels policy, and GitHub labels at the repo root.

    Idempotent — if an artifact already exists it is left unchanged.
    """
    result = init_repo()

    if result.wrote_standards:
        typer.echo("Created CODING_STANDARDS.md (titles-only skeleton — fill in the bodies).")
    else:
        typer.echo("CODING_STANDARDS.md already exists — unchanged.")

    if result.labels_policy_targets:
        typer.echo(f"Appended labels-policy block to {', '.join(result.labels_policy_targets)}.")
    elif result.no_agent_doc:
        typer.echo("No CLAUDE.md or AGENTS.md found — skipping labels-policy block.")
    else:
        typer.echo("Labels-policy block already present — unchanged.")

    if result.created_labels:
        typer.echo(f"Created GitHub labels: {', '.join(result.created_labels)}.")
    if result.label_warnings:
        for warning in result.label_warnings:
            typer.echo(f"Warning: {warning}", err=True)
