"""Unit tests for the dispatcher markdown renderer.

Targets ``render_dispatcher`` directly. The function is pure: a Status in, a
plain ``str`` out. We construct Status fixtures by hand to exercise the
conditional sections (blocked reasons, next-phase instructions) without
depending on a real workspace.
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_harness import compat
from ai_harness.rendering import render_dispatcher
from ai_harness.sdd.models import (
    ARTIFACT_STORE_OPENSPEC,
    DEP_BLOCKED,
    DEP_READY,
    PHASE_APPLY,
    PHASE_ARCHIVE,
    PHASE_VERIFY,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    ActionContext,
    ArtifactPaths,
    Dependencies,
    PlanningHome,
    Relationships,
    Status,
    TaskProgress,
)


def _build_status(
    change_name: str | None = "thin",
    next_recommended: str = PHASE_APPLY,
    blocked_reasons: list[str] | None = None,
    deps: Dependencies | None = None,
    task_progress: TaskProgress | None = None,
) -> Status:
    root = "/tmp/workspace"
    return Status(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        change_name=change_name,
        artifact_store=ARTIFACT_STORE_OPENSPEC,
        planning_home=PlanningHome(mode="repo-local", path=f"{root}/openspec"),
        change_root=f"{root}/openspec/changes/{change_name}" if change_name else None,
        artifact_paths=ArtifactPaths(),
        context_files=ArtifactPaths(),
        artifacts={},
        task_progress=task_progress
        or TaskProgress(total=2, completed=0, pending=2, all_complete=False),
        dependencies=deps or Dependencies(apply=DEP_READY),
        apply_state="ready",
        action_context=ActionContext(
            mode="repo-local",
            workspace_root=root,
            allowed_edit_roots=[root],
        ),
        relationships=Relationships(),
        next_recommended=next_recommended,
        blocked_reasons=list(blocked_reasons or []),
        phase_instructions=None,
    )


def test_render_dispatcher_returns_plain_str_with_required_sections():
    status = _build_status(change_name="add-auth", next_recommended=PHASE_APPLY)
    out = render_dispatcher(status)

    assert isinstance(out, str)
    assert "## Native SDD Dispatcher: add-auth" in out
    assert "next_recommended: apply" in out
    assert "### Dependency States" in out
    # All seven dependency fields must surface, with task_progress last.
    for label in (
        "proposal:",
        "specs:",
        "design:",
        "tasks:",
        "apply:",
        "verify:",
        "archive:",
        "task_progress:",
    ):
        assert label in out
    # Fenced JSON block with the deterministic compat payload.
    assert "### JSON" in out
    assert "```json" in out
    assert out.rstrip().endswith("```")
    # Dispatcher markdown targets LLM consumption — never Rich or ANSI.
    assert "\x1b" not in out


def test_render_dispatcher_fenced_json_matches_compat_serializer():
    status = _build_status(change_name="thin", next_recommended=PHASE_APPLY)
    out = render_dispatcher(status)

    fence_open = "```json\n"
    fence_close = "\n```"
    start = out.index(fence_open) + len(fence_open)
    end = out.index(fence_close, start)
    fenced = out[start:end]

    assert fenced == compat.status_to_json(status)
    json.loads(fenced)  # parses cleanly


def test_render_dispatcher_emits_blocked_reasons_section_when_present():
    status = _build_status(
        next_recommended="resolve-blockers",
        blocked_reasons=["proposal.md is missing or partial."],
        deps=Dependencies(),
    )
    out = render_dispatcher(status)

    assert "### Blocked Reasons" in out
    assert "- proposal.md is missing or partial." in out
    # No next-phase instructions when next is not a concrete phase.
    assert "### Next Phase Instructions" not in out


def test_render_dispatcher_omits_blocked_reasons_when_empty():
    status = _build_status(
        next_recommended=PHASE_VERIFY,
        blocked_reasons=[],
    )
    out = render_dispatcher(status)

    assert "### Blocked Reasons" not in out


def test_render_dispatcher_emits_next_phase_instructions_for_each_concrete_phase():
    for phase in (PHASE_APPLY, PHASE_VERIFY, PHASE_ARCHIVE):
        status = _build_status(next_recommended=phase)
        out = render_dispatcher(status)
        assert f"### Next Phase Instructions: {phase}" in out
        # Each line begins with "- ".
        section = out.split(f"### Next Phase Instructions: {phase}", 1)[1]
        section = section.split("### JSON", 1)[0]
        for line in section.strip().splitlines():
            assert line.startswith("- "), line


def test_render_dispatcher_omits_next_phase_instructions_for_non_phase_nexts():
    for non_phase in ("resolve-blockers", "sdd-new", "select-change"):
        status = _build_status(
            next_recommended=non_phase,
            blocked_reasons=["some blocker."],
        )
        out = render_dispatcher(status)
        assert "### Next Phase Instructions" not in out


def test_render_dispatcher_change_name_unresolved_uses_literal():
    status = _build_status(change_name=None, next_recommended="sdd-new")
    out = render_dispatcher(status)
    assert "## Native SDD Dispatcher: unresolved" in out


def test_render_dispatcher_uses_plain_newlines_only(tmp_path: Path):
    """Reject any Rich/ANSI/terminal escape noise from the human path."""
    status = _build_status(change_name="thin", next_recommended=PHASE_APPLY)
    out = render_dispatcher(status)
    assert "\r" not in out
    assert "\x1b" not in out


def test_render_dispatcher_advisory_line_present():
    status = _build_status(next_recommended=PHASE_APPLY)
    out = render_dispatcher(status)
    assert "Native status is authoritative." in out


def test_render_dispatcher_task_progress_line_present():
    status = _build_status(task_progress=TaskProgress(total=5, completed=3, pending=2, all_complete=False))
    out = render_dispatcher(status)
    assert "task_progress: 3/5 complete" in out


def test_render_dispatcher_all_seven_dependencies_listed():
    status = _build_status(
        deps=Dependencies(
            proposal=DEP_READY, specs=DEP_BLOCKED, design=DEP_BLOCKED,
            tasks=DEP_READY, apply=DEP_BLOCKED, verify=DEP_BLOCKED, archive=DEP_BLOCKED,
        )
    )
    out = render_dispatcher(status)
    assert "proposal: ready" in out
    assert "specs: blocked" in out
    assert "design: blocked" in out
    assert "tasks: ready" in out
    assert "apply: blocked" in out
    assert "verify: blocked" in out
    assert "archive: blocked" in out


def test_render_dispatcher_json_fenced_block_is_last_section():
    status = _build_status(next_recommended=PHASE_ARCHIVE)
    out = render_dispatcher(status)
    # Fenced JSON block is last, ends with ```
    assert "### JSON" in out
    json_pos = out.rindex("### JSON")
    assert out.rstrip().endswith("```")
    # Nothing of substance after the JSON block
    assert out.rindex("```") > json_pos
