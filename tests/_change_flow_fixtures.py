"""Shared fixtures for change-flow regression tests.

These helpers back the table-driven tests in ``test_change_*`` and
``test_renderers``. Centralizing them keeps the per-file test modules
focused on assertions and eliminates the duplicate-code findings the
pylint gate raises across the change-flow suite.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from ai_harness.modules.change_config import PHASE_ORDER as _PHASE_ORDER
from ai_harness.modules.harness.tasks import SubtaskInput, TaskInput, task_create, task_done

# Re-export the canonical phase-order tuple from the change_config
# seam so tests reference one source of truth instead of duplicating
# the phase list (which previously tripped pylint's duplicate-code
# gate).
ROUTED_PHASES: tuple[str, ...] = _PHASE_ORDER

DEFAULT_COMMIT_FORMAT = "[{change_name}][{task_id}] {slug}"


def make_change(root: Path, change: str = "demo") -> Path:
    """Create a fresh change directory and return its absolute path."""
    change_dir = root / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True)
    return change_dir


def stage(change_dir: Path, relative: str, content: str = "x\n") -> None:
    """Write *content* to ``<change_dir>/<relative>`` creating parents."""
    target = change_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def init_config(root: Path, *phases: str) -> None:
    """Initialize ``.ai-harness/config.yml`` with the supplied routed phases."""
    config_path = root / ".ai-harness" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "commit": {"format": DEFAULT_COMMIT_FORMAT},
        "phases": {phase: {"rules": ["rule"]} for phase in phases},
    }
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def autouse_config(*phases: str) -> Callable[[Path], None]:
    """Return an autouse fixture that initialises the config with *phases*."""

    def _fixture(tmp_path: Path) -> None:
        init_config(tmp_path, *phases)

    return _fixture


def render_capability(capability: dict[str, Any]) -> str:
    """Render one capability block in the YAML front matter."""
    reasons = capability.get("reasons", [])
    reasons_yaml = "        reasons: []\n"
    if reasons:
        rendered = "\n".join(f"          - {reason}" for reason in reasons)
        reasons_yaml = f"        reasons:\n{rendered}\n"
    return (
        f"    - id: {capability['id']}\n"
        f"      title: {capability['title']}\n"
        f"      risk:\n"
        f"        level: {capability['level']}\n"
        f"{reasons_yaml}"
        f"      design: {capability['design']}"
    )


def write_sliced_prd(change_dir: Path, *, capabilities: list[dict[str, Any]]) -> Path:
    """Write a sliced ``prd.md`` with the supplied capabilities."""
    yaml_capabilities = "\n".join(render_capability(cap) for cap in capabilities)
    body = f"---\nchangeFlow:\n  schemaVersion: 1\n  mode: sliced\n  capabilities:\n{yaml_capabilities}\n---\n"
    prd = change_dir / "prd.md"
    prd.write_text(body, encoding="utf-8")
    return prd


def complete_capability(tmp_path: Path, change: str, capability_id: str) -> None:
    """Stage spec, validation, and one completed associated task.

    The slice validation is written after the associated task is
    completed so its mtime is strictly newer than the tasks.json
    store; this mirrors the natural workflow and prevents the
    initial-validation freshness check from falsely flagging the
    validation as stale.
    """
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    stage(change_dir, f"specs/{capability_id}.md")
    task = task_create(
        tmp_path,
        change,
        TaskInput(
            title=f"Wrap {capability_id}",
            spec=capability_id,
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    task_done(tmp_path, change, task.id)
    stage(change_dir, f"validations/{capability_id}.md", content="verdict: pass\n")


def create_other_capability_task(
    tmp_path: Path,
    change: str,
    *,
    title: str = "Other",
    spec: str = "other-capability",
    subtask_title: str = "step",
) -> str:
    """Create a pending task referencing an unrelated capability.

    Used by tests that need an "other" task alongside the selected
    capability to verify that unrelated task completion does not
    advance the slice.
    """
    task = task_create(
        tmp_path,
        change,
        TaskInput(
            title=title,
            spec=spec,
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title=subtask_title)],
        ),
    )
    return task.id
