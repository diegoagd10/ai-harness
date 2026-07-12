"""Init command — thin typer adapter over ``ChangeConfigAdministrator``.

Routes ``ai-harness init`` to the change-config administrator seam so the
command owns no filesystem policy beyond invocation and reporting. No root
scaffold delegation: ``CLAUDE.md``, ``AGENTS.md``, and
``CODING_STANDARDS.md`` stay user-owned.
"""

from __future__ import annotations

import typer

from ai_harness.modules.change_config import ChangeConfigAdministrator


def init() -> None:
    """Initialize the change configuration at ``.ai-harness/config.yml``.

    Delegates to :meth:`ChangeConfigAdministrator.initialize_config`, which
    creates the file only when absent and leaves existing user-owned
    configuration untouched. The wording is valid for both creation and an
    idempotent no-op because the administrator returns no created-versus-
    existing status.
    """
    ChangeConfigAdministrator().initialize_config()
    typer.echo("Initialized change configuration at .ai-harness/config.yml")
