"""Go-compatible JSON serialization and exit codes for the SDD commands.

This module is the single owner of the wire contract: it emits explicit camelCase
keys in the Go struct order, with the ``artifacts`` map in Go's sorted-key order,
non-null empty lists, ``null`` for unresolved change name/root, and an omitted
``phaseInstructions`` key when instructions are absent. JSON is produced with the
standard library only — Rich never participates.
"""

from __future__ import annotations

import json

from .sdd import (
    ArtifactPaths,
    Dependencies,
    PhaseInstructions,
    Status,
    TaskProgress,
)

# Exit codes mirror the Go CLI: success, resolution/serialization failure, and
# usage/parse error.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

# Go's encoding/json HTML-escapes these in string values by default (and escapes
# the U+2028/U+2029 line/paragraph separators). Reproduce it so paths, names, and
# reasons containing them stay byte-identical. Structural JSON never contains raw
# &, <, > so a flat replacement over the serialized text is safe.
_HTML_ESCAPES = {
    "&": "\\u0026",
    "<": "\\u003c",
    ">": "\\u003e",
    " ": "\\u2028",
    " ": "\\u2029",
}


def status_to_json(status: Status) -> str:
    """Serialize a Status to deterministic, Go-compatible 2-space-indented JSON."""
    payload = json.dumps(status_to_dict(status), indent=2, ensure_ascii=False)
    for raw, escaped in _HTML_ESCAPES.items():
        payload = payload.replace(raw, escaped)
    return payload


def status_to_dict(status: Status) -> dict:
    """Build the ordered camelCase payload for a Status."""
    payload: dict = {
        "schemaName": status.schema_name,
        "schemaVersion": status.schema_version,
        "changeName": status.change_name,
        "artifactStore": status.artifact_store,
        "planningHome": {
            "mode": status.planning_home.mode,
            "path": status.planning_home.path,
        },
        "changeRoot": status.change_root,
        "artifactPaths": _artifact_paths(status.artifact_paths),
        "contextFiles": _artifact_paths(status.context_files),
        "artifacts": _artifacts(status.artifacts),
        "taskProgress": _task_progress(status.task_progress),
        "dependencies": _dependencies(status.dependencies),
        "applyState": status.apply_state,
        "actionContext": {
            "mode": status.action_context.mode,
            "workspaceRoot": status.action_context.workspace_root,
            "allowedEditRoots": list(status.action_context.allowed_edit_roots),
        },
        "relationships": {
            "dependsOn": list(status.relationships.depends_on),
            "supersedes": list(status.relationships.supersedes),
            "amends": list(status.relationships.amends),
            "conflictsWith": list(status.relationships.conflicts_with),
            "sameDomainActiveChanges": list(status.relationships.same_domain_active_changes),
        },
    }
    # phaseInstructions precedes nextRecommended in the Go struct and is omitted
    # entirely when absent (omitempty).
    if status.phase_instructions is not None:
        payload["phaseInstructions"] = _phase_instructions(status.phase_instructions)
    payload["nextRecommended"] = status.next_recommended
    payload["blockedReasons"] = list(status.blocked_reasons)
    return payload


def _artifact_paths(paths: ArtifactPaths) -> dict:
    return {
        "proposal": list(paths.proposal),
        "specs": list(paths.specs),
        "design": list(paths.design),
        "tasks": list(paths.tasks),
        "applyProgress": list(paths.apply_progress),
        "verifyReport": list(paths.verify_report),
    }


def _artifacts(artifacts: dict[str, str]) -> dict:
    # Go marshals maps with keys sorted lexically; reproduce that ordering.
    return {key: artifacts[key] for key in sorted(artifacts)}


def _task_progress(progress: TaskProgress) -> dict:
    return {
        "total": progress.total,
        "completed": progress.completed,
        "pending": progress.pending,
        "allComplete": progress.all_complete,
    }


def _dependencies(deps: Dependencies) -> dict:
    return {
        "proposal": deps.proposal,
        "specs": deps.specs,
        "design": deps.design,
        "tasks": deps.tasks,
        "apply": deps.apply,
        "verify": deps.verify,
        "archive": deps.archive,
    }


def _phase_instructions(instructions: PhaseInstructions) -> dict:
    return {
        "apply": list(instructions.apply),
        "verify": list(instructions.verify),
        "archive": list(instructions.archive),
    }
