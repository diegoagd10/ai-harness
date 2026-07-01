"""Init command — thin typer adapter over ``init_repo``.

No business logic here; the command delegates to ``init_repo`` and echoes
the result. This is a repo-local scaffold (distinct from the global ``install``).
"""

from __future__ import annotations

import typer

from ai_harness.modules.harness import init_repo


def init() -> None:
    """Scaffold CODING_STANDARDS.md and the agent-doc init block at the repo root.

    Idempotent — if an artifact already exists with the new init markers it is
    left unchanged; an existing legacy ``ai-harness:start/end`` block is
    migrated in place. No GitHub label side effects.
    """
    result = init_repo()

    if result.wrote_standards:
        typer.echo("Created CODING_STANDARDS.md (titles-only skeleton — fill in the bodies).")
    else:
        typer.echo("CODING_STANDARDS.md already exists — unchanged.")

    if result.wrote_init_block:
        typer.echo(f"Managed init block on {', '.join(result.init_block_targets)}.")
    else:
        typer.echo(f"Managed init block already present on {', '.join(result.init_block_targets)} — unchanged.")
