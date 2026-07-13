"""Change-config value objects — typed shapes for the administrator's public surface.

No behaviour lives here. This module holds only the two dataclasses the
:class:`ChangeConfigAdministrator` returns to callers — the per-phase
prompt bundle and the validation verdict. Field sets are part of the
value contract: the orchestrator reads them by name, so adding or
renaming a field is a public-surface change.

Public surface
--------------
ChangeConfigPromptContext      Phase name, rule list, and commit format to inject.
ChangeConfigValidationResults  Verdict and non-halting diagnostic list.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ChangeConfigPromptContext", "ChangeConfigValidationResults"]


@dataclass(frozen=True, slots=True)
class ChangeConfigPromptContext:
    """Phase rules to inject into the next change-orchestrator sub-agent prompt.

    *phase* is the canonical snake_case phase key the orchestrator asked
    for (post-normalization). *phase_rules* is the ordered rule list
    from ``config.yml`` — empty when the phase is absent or unknown.
    *commit_format* is the repo-wide ``commit.format`` string from
    ``config.yml`` — the orchestrator inlines it verbatim into the
    ``change-implementor`` delegation block instead of reading
    ``CODING_STANDARDS.md``.
    """

    phase: str
    phase_rules: tuple[str, ...]
    commit_format: str


@dataclass(frozen=True, slots=True)
class ChangeConfigValidationResults:
    """Integrity verdict of ``.ai-harness/config.yml`` plus non-halting diagnostics.

    *is_valid* is ``True`` when the file parses and conforms to the
    strict schema. *warnings* are deterministic messages about
    preserved-but-suspect state (e.g. unknown phase keys). The validator
    raises on halting errors; warnings never halt the read.
    """

    is_valid: bool
    warnings: tuple[str, ...]
