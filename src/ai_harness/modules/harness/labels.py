"""GitHub label creation wrapper for the loop workflow.

Only the loop's two fixed labels are created: ``ready-for-agent`` and ``loop``.
The other four canonical triage labels belong to ``setup-matt-pocock-skills``
and are not touched here (see ADR 0005).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

_LOOP_LABELS = [
    ("ready-for-agent", "7057ff", "Fully specified, ready for an AFK agent"),
    ("loop", "1D76DB", "The issue-draining loop multi-agent workflow"),
]


@dataclass(frozen=True, slots=True)
class LabelResult:
    """Outcome of ``ensure_labels``.

    *created* lists label names successfully created (absent before, now present).
    *warnings* are human-readable messages for labels that could not be created
    (gh missing, no remote, authentication failure, etc.).
    """

    created: list[str]
    warnings: list[str]


def ensure_labels(repo_root: Path, *, _run: _Runner = None) -> LabelResult:
    """Create ``ready-for-agent`` and ``loop`` GitHub labels via ``gh label create``.

    Only missing labels are created; existing labels are left untouched (gh
    reports "already exists" on stderr, which is treated as a skip). The
    label step runs on every invocation so a previously-failed attempt
    self-heals on re-run.

    On failure (no GitHub remote, gh not authenticated, non-GitHub remote),
    emits warnings with the exact manual commands and returns — local
    scaffolding still completes.

    ``_run`` is the subprocess boundary for test injection; callers should
    not supply it.
    """
    run = _run if _run is not None else subprocess.run
    created: list[str] = []
    warnings: list[str] = []

    for name, color, description in _LOOP_LABELS:
        args = ["gh", "label", "create", name, "--color", color, "--description", description]
        try:
            completed = run(args, capture_output=True, text=True, cwd=str(repo_root))
        except FileNotFoundError:
            warnings.append(_format_manual_command(name, color, description, reason="gh CLI not found"))
            continue
        except OSError:
            warnings.append(_format_manual_command(name, color, description, reason="failed to invoke gh"))
            continue

        if completed.returncode == 0:
            created.append(name)
        elif "already exists" in (completed.stderr or "").lower():
            # Idempotent skip — label present, leave untouched
            continue
        else:
            warnings.append(
                _format_manual_command(
                    name,
                    color,
                    description,
                    reason=f"gh exited {completed.returncode}: {completed.stderr.strip()}",
                )
            )

    return LabelResult(created=created, warnings=warnings)


def _format_manual_command(name: str, color: str, description: str, *, reason: str) -> str:
    return (
        f"Could not create GitHub label {name!r} ({reason}). "
        f"Run manually:\n"
        f'  gh label create {name} --color {color} --description "{description}"'
    )


# --- seams for testing ------------------------------------------------------

_Runner = object  # Structural type: callable like subprocess.run
