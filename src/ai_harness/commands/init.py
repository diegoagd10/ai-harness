"""Init command — thin typer adapter over ``init_repo``.

No business logic here; the command delegates to ``init_repo`` and echoes
the result. This is a repo-local scaffold (distinct from the global ``install``).
"""

from __future__ import annotations

import typer

from ai_harness.modules.harness import init_repo


def init() -> None:
    """Scaffold CODING_STANDARDS.md and CLAUDE.md labels policy at the repo root.

    Idempotent — if an artifact already exists it is left unchanged.
    """
    result = init_repo()

    if result.wrote_standards:
        typer.echo("Created CODING_STANDARDS.md (titles-only skeleton — fill in the bodies).")
    else:
        typer.echo("CODING_STANDARDS.md already exists — unchanged.")

    if result.wrote_labels_policy:
        typer.echo("Appended labels-policy block to CLAUDE.md.")
    elif result.claude_md_missing:
        typer.echo("No CLAUDE.md found — skipping labels-policy block.")
    else:
        typer.echo("CLAUDE.md labels-policy block already present — unchanged.")
