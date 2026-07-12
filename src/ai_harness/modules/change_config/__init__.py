"""Change-config administrator — owns ``.ai-harness/config.yml`` lifecycle.

This package owns the deep module the change orchestrator reads from
between phases: it scaffolds the initial empty config, resolves the
per-phase rule list the next sub-agent should be told, and validates
that user edits have not corrupted the schema. Commands are thin typer
adapters; all business logic lives here.

Public surface
--------------
ChangeConfigAdministrator  Holds the 3-method seam: initialize / read / validate.
ChangeConfigPromptContext  Per-phase rule bundle handed to the next sub-agent.
ChangeConfigValidationResults  Integrity verdict plus any non-halting warnings.
"""

from ai_harness.modules.change_config.models import (
    ChangeConfigPromptContext,
    ChangeConfigValidationResults,
)
from ai_harness.modules.change_config.module import ChangeConfigAdministrator, ChangeConfigError

__all__ = [
    "ChangeConfigAdministrator",
    "ChangeConfigError",
    "ChangeConfigPromptContext",
    "ChangeConfigValidationResults",
]
