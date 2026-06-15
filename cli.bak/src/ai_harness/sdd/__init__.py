"""Deterministic Spec-Driven Development dispatcher (deep module).

Callers depend only on :func:`resolve` plus the :class:`Status` model. How
artifacts are discovered, how task progress is counted, and how the verify-report
heuristic works are all hidden behind that small surface.
"""

from __future__ import annotations

from .models import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    ActionContext,
    ArtifactPaths,
    Dependencies,
    PhaseInstructions,
    PlanningHome,
    Relationships,
    SddError,
    Status,
    TaskProgress,
)
from .resolve import resolve

__all__ = [
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "ActionContext",
    "ArtifactPaths",
    "Dependencies",
    "PhaseInstructions",
    "PlanningHome",
    "Relationships",
    "SddError",
    "Status",
    "TaskProgress",
    "resolve",
]
