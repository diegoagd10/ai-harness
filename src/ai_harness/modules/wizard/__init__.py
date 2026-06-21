"""Set-models wizard — pure data-prep (testable) + thin TUI adapter (untested).

Public surface
--------------
``pure``    Decision logic: fixed Claude sets, picker rows, confirmation
           rows. Unit-tested.
``tui``     Thin questionary/rich shell that drives the wizard prompts.
           Left untested (interactive code with no business logic).
"""

from ai_harness.modules.wizard import pure, tui

__all__ = ["pure", "tui"]
