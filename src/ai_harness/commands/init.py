"""Init command — thin typer adapter over ``init_repo``.

No business logic here; the command delegates to ``init_repo`` and echoes
the result. This is a repo-local scaffold (distinct from the global ``install``).
"""

from __future__ import annotations

import typer

from ai_harness.modules.harness import init_repo


def init() -> None:
    """Scaffold CODING_STANDARDS.md at the repo root (titles-only, human-filled).

    Idempotent — if the file already exists it is left unchanged.
    """
    wrote = init_repo()
    if wrote:
        typer.echo("Created CODING_STANDARDS.md (titles-only skeleton — fill in the bodies).")
    else:
        typer.echo("CODING_STANDARDS.md already exists — unchanged.")
