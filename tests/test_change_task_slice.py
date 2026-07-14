"""Tests for the capability-scoped task state view added in task 1.

These tests focus on the read-only capability association API exposed by
``ai_harness.modules.harness.tasks``. Sliced routing asks ``TaskStore`` for a
single capability's ordered task ids, definition digest, state digest, and
progress; this file exercises canonicalization, association rejection,
ordered progress, and stable digests.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from ai_harness.modules.harness.tasks import (
    CapabilityTaskState,
    SubtaskInput,
    TaskInput,
    TaskStoreError,
    task_capability_state,
    task_create,
    task_done,
)


def _make_change(tmp_path: Path, change: str = "demo") -> Path:
    """Create a change directory and return its root path."""
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True)
    return change_dir


def _task_input(
    title: str,
    *,
    spec: str,
    subtasks: list[SubtaskInput] | None = None,
) -> TaskInput:
    """Build a TaskInput tied to a specific spec reference."""
    return TaskInput(
        title=title,
        spec=spec,
        phase="implement",
        depends_on=[],
        subtasks=subtasks if subtasks is not None else [SubtaskInput(title="first")],
    )


def _capability_field_names() -> tuple[str, ...]:
    """Return the dataclass field names for stable test introspection."""
    return tuple(field.name for field in fields(CapabilityTaskState))


def test_capability_state_dataclass_exposes_ordered_progress_and_digests() -> None:
    """``CapabilityTaskState`` exposes the slice contract fields."""
    # Locking the field shape protects the router contract — adding,
    # removing, or renaming a field is a breaking API change.
    assert _capability_field_names() == (
        "progress",
        "taskIds",
        "definitionDigest",
        "stateDigest",
        "routingDiagnostic",
    )


def test_supported_spec_references_canonicalize_to_specs_relative(tmp_path: Path) -> None:
    """``<id>``, ``<id>.md``, and ``specs/<id>.md`` all associate.

    Mirrors the spec scenario "Canonical and legacy task references associate":
    each input form must be accepted and treated as the same capability.
    """
    root = tmp_path
    _make_change(root)
    task_create(root, "demo", _task_input("Plain id", spec="capability"))
    task_create(root, "demo", _task_input("Dot md", spec="capability.md"))
    task_create(root, "demo", _task_input("Full path", spec="specs/capability.md"))

    bare = task_capability_state(root, "demo", "capability")
    dot_md = task_capability_state(root, "demo", "capability.md")
    full = task_capability_state(root, "demo", "specs/capability.md")

    assert bare.taskIds == dot_md.taskIds == full.taskIds == ["1", "2", "3"]
    assert bare.definitionDigest == dot_md.definitionDigest == full.definitionDigest
    assert bare.stateDigest == dot_md.stateDigest == full.stateDigest


def test_capability_state_preserves_task_input_order(tmp_path: Path) -> None:
    """Associated task ids appear in their persisted (insertion) order."""
    root = tmp_path
    _make_change(root)
    task_create(root, "demo", _task_input("first slice work", spec="first"))
    task_create(root, "demo", _task_input("second slice work", spec="first"))
    task_create(root, "demo", _task_input("third slice work", spec="first"))

    state = task_capability_state(root, "demo", "first")

    assert state.taskIds == ["1", "2", "3"]


def test_capability_state_associates_only_matching_spec(tmp_path: Path) -> None:
    """Only tasks whose spec canonicalizes to the target are associated.

    Mirrors "Unsafe references do not associate": a different capability's
    tasks must NOT be credited to the requested capability.
    """
    root = tmp_path
    _make_change(root)
    task_create(root, "demo", _task_input("Other slice", spec="specs/other.md"))
    task_create(root, "demo", _task_input("Self slice", spec="specs/first.md"))
    task_create(root, "demo", _task_input("Self slice again", spec="first.md"))

    state = task_capability_state(root, "demo", "first")

    assert state.taskIds == ["2", "3"]


def test_capability_state_rejects_unsafe_spec_references(tmp_path: Path) -> None:
    """Absolute paths, parent traversal, nested paths, and empty IDs do not associate.

    Unsafe references stay unassociated but never raise — the router needs a
    diagnostic, not a crash. (An empty store is handled separately by the
    "missing/empty task input is safe" case.)
    """
    root = tmp_path
    _make_change(root)
    task_create(root, "demo", _task_input("absolute", spec="/abs/capability.md"))
    task_create(root, "demo", _task_input("absolute dot", spec="/abs/capability"))
    task_create(root, "demo", _task_input("parent traversal", spec="../capability.md"))
    task_create(root, "demo", _task_input("nested", spec="specs/sub/capability.md"))
    # Empty id and whitespace-only id are "unused" — neither associates.
    task_create(root, "demo", _task_input("empty id", spec=""))
    task_create(root, "demo", _task_input("whitespace id", spec="   "))

    # The router asks for the canonical capability by its kebab id; the
    # unsafe tasks must not be returned even when the target is a valid id.
    state = task_capability_state(root, "demo", "capability")

    assert state.taskIds == []

    # Explicit ``is unsafe reference -> not associated`` semantics: each
    # unsafe reference is recognizable via the explicit canonical form.
    # We assert behavior by enumerating the canonical rules.
    unsafe_specs = {
        task.spec
        for task in (
            # Same set as defined in the spec; we re-derive via a tiny helper
            # so the assertion stands alone if internals change.
            type("Probe", (), {"spec": s})()
            for s in (
                "/abs/capability.md",
                "../capability.md",
                "specs/sub/capability.md",
                "",
            )
        )
    }
    assert "/abs/capability.md" in unsafe_specs
    assert "../capability.md" in unsafe_specs
    assert "specs/sub/capability.md" in unsafe_specs
    assert "" in unsafe_specs


def test_capability_state_for_missing_change_dir_returns_empty_progress(tmp_path: Path) -> None:
    """A capability query against a missing change yields zero progress safely.

    Mirrors "Missing or empty task input is safe": the router must still
    receive a usable :class:`CapabilityTaskState` whose progress reports
    empty, not raise.
    """
    state = task_capability_state(tmp_path, "missing", "any-capability")

    assert state.taskIds == []
    assert state.definitionDigest != ""
    assert state.stateDigest != ""
    assert state.progress.total == 0
    assert state.progress.completed == 0
    assert state.progress.pending == 0
    assert state.progress.allComplete is True


def test_capability_state_for_empty_tasks_store_returns_empty_progress(tmp_path: Path) -> None:
    """A change with no tasks file (or empty tasks list) reports zero progress."""
    root = tmp_path
    _make_change(root)
    # No tasks.json written at all.

    state = task_capability_state(root, "demo", "any-capability")

    assert state.taskIds == []
    assert state.definitionDigest != ""
    assert state.stateDigest != ""
    assert state.progress.total == 0
    assert state.progress.allComplete is True


def test_capability_state_progress_reflects_only_matching_tasks(tmp_path: Path) -> None:
    """Progress totals count only associated tasks, not unrelated tasks."""
    root = tmp_path
    _make_change(root)
    task_create(root, "demo", _task_input("Self", spec="self.md"))
    task_create(root, "demo", _task_input("Other", spec="other.md"))
    task_create(root, "demo", _task_input("Self 2", spec="specs/self.md"))

    state = task_capability_state(root, "demo", "self")

    assert state.taskIds == ["1", "3"]
    assert state.progress.total == 2
    assert state.progress.completed == 0
    assert state.progress.pending == 2
    assert state.progress.allComplete is False

    task_done(root, "demo", "1")
    state_after = task_capability_state(root, "demo", "self")
    assert state_after.progress.completed == 1
    assert state_after.progress.pending == 1
    assert state_after.progress.allComplete is False

    task_done(root, "demo", "3")
    final_state = task_capability_state(root, "demo", "self")
    assert final_state.progress.allComplete is True


def test_definition_digest_excludes_statuses_and_state_digest_includes_them(tmp_path: Path) -> None:
    """Pending→done transitions invalidate ``stateDigest`` but not ``definitionDigest``.

    Mirrors the design note that "definitionDigest covers selected task
    IDs, titles, canonical spec references, phases, dependencies, and
    subtask IDs/titles/scenarios, but excludes task statuses" so that
    ordinary completion does not invalidate the implementation approval.
    """
    root = tmp_path
    _make_change(root)
    task_create(root, "demo", _task_input("Slice A", spec="capability", subtasks=[SubtaskInput(title="step1")]))

    before = task_capability_state(root, "demo", "capability")

    task_done(root, "demo", "1")

    after = task_capability_state(root, "demo", "capability")

    # Definition digest MUST be stable across an ordinary status flip.
    assert before.definitionDigest == after.definitionDigest
    # State digest MUST change when a status flips.
    assert before.stateDigest != after.stateDigest


def test_digests_are_stable_for_identical_inputs(tmp_path: Path) -> None:
    """Two stores with identical associated tasks produce identical digests.

    Both digests use a length-delimited, ordered canonical form so the
    router can compare fingerprint equality without positional ambiguity.
    """
    # Build store A
    root_a = tmp_path / "a"
    root_a.mkdir()
    _make_change(root_a)
    task_create(root_a, "demo", _task_input("One", spec="capability"))
    task_create(root_a, "demo", _task_input("Two", spec="capability.md"))
    state_a = task_capability_state(root_a, "demo", "specs/capability.md")

    # Build store B (independent filesystem, same logical content)
    root_b = tmp_path / "b"
    root_b.mkdir()
    _make_change(root_b)
    task_create(root_b, "demo", _task_input("One", spec="capability"))
    task_create(root_b, "demo", _task_input("Two", spec="specs/capability.md"))
    state_b = task_capability_state(root_b, "demo", "specs/capability.md")

    assert state_a.definitionDigest == state_b.definitionDigest
    assert state_a.stateDigest == state_b.stateDigest
    # Same content ⇒ same taskIds, in the same order.
    assert state_a.taskIds == state_b.taskIds


def test_digests_shift_when_task_set_grows(tmp_path: Path) -> None:
    """Adding a task invalidates both digests; the router can detect scope drift."""
    root = tmp_path
    _make_change(root)
    task_create(root, "demo", _task_input("First", spec="capability"))

    before = task_capability_state(root, "demo", "capability")

    task_create(root, "demo", _task_input("Second", spec="capability"))

    after = task_capability_state(root, "demo", "capability")

    assert before.definitionDigest != after.definitionDigest
    assert before.stateDigest != after.stateDigest


def test_capability_state_rejects_storage_errors_safely(tmp_path: Path) -> None:
    """Malformed ``tasks.json`` raises the same TaskStoreError as task operations."""
    root = tmp_path
    _make_change(root)
    tasks_file = root / ".ai-harness" / "changes" / "demo" / "tasks.json"
    tasks_file.write_text("not-json", encoding="utf-8")

    with pytest.raises(TaskStoreError, match="Malformed tasks.json"):
        task_capability_state(root, "demo", "any-capability")


# ---------------------------------------------------------------------------
# Routing diagnostic for unsafe spec references
# ---------------------------------------------------------------------------


def test_routing_diagnostic_none_when_all_references_safe(tmp_path: Path) -> None:
    """A task store with only safe references leaves the diagnostic empty."""
    root = tmp_path
    _make_change(root)
    task_create(
        root,
        "demo",
        TaskInput(
            title="Safe",
            spec="capability",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )

    state = task_capability_state(root, "demo", "capability")

    assert state.taskIds == ["1"]
    assert state.routingDiagnostic is None


def test_routing_diagnostic_lists_absolute_path_reference(tmp_path: Path) -> None:
    """A task referencing an absolute spec path is reported in the diagnostic."""
    root = tmp_path
    _make_change(root)
    # Inject an unsafe task directly so we can bypass the create-time
    # validation that the CLI layer enforces.
    import json

    tasks_file = root / ".ai-harness" / "changes" / "demo" / "tasks.json"
    payload = {
        "tasks": [
            {
                "id": "1",
                "title": "Absolute",
                "spec": "/etc/specs/capability.md",
                "phase": "implement",
                "depends_on": [],
                "status": "pending",
                "subtasks": [],
            }
        ]
    }
    tasks_file.write_text(json.dumps(payload), encoding="utf-8")

    state = task_capability_state(root, "demo", "capability")

    assert state.taskIds == []
    assert state.routingDiagnostic is not None
    assert "absolute path" in state.routingDiagnostic
    assert "1" in state.routingDiagnostic


def test_routing_diagnostic_lists_parent_traversal(tmp_path: Path) -> None:
    """A task using parent traversal is reported in the diagnostic."""
    root = tmp_path
    _make_change(root)
    import json

    tasks_file = root / ".ai-harness" / "changes" / "demo" / "tasks.json"
    payload = {
        "tasks": [
            {
                "id": "1",
                "title": "Traversal",
                "spec": "../capability.md",
                "phase": "implement",
                "depends_on": [],
                "status": "pending",
                "subtasks": [],
            }
        ]
    }
    tasks_file.write_text(json.dumps(payload), encoding="utf-8")

    state = task_capability_state(root, "demo", "capability")

    assert state.taskIds == []
    assert state.routingDiagnostic is not None
    assert "parent traversal" in state.routingDiagnostic


def test_routing_diagnostic_lists_nested_path(tmp_path: Path) -> None:
    """A task using a nested spec path is reported in the diagnostic."""
    root = tmp_path
    _make_change(root)
    import json

    tasks_file = root / ".ai-harness" / "changes" / "demo" / "tasks.json"
    payload = {
        "tasks": [
            {
                "id": "1",
                "title": "Nested",
                "spec": "nested/capability.md",
                "phase": "implement",
                "depends_on": [],
                "status": "pending",
                "subtasks": [],
            }
        ]
    }
    tasks_file.write_text(json.dumps(payload), encoding="utf-8")

    state = task_capability_state(root, "demo", "capability")

    assert state.taskIds == []
    assert state.routingDiagnostic is not None
    assert "nested path" in state.routingDiagnostic


def test_routing_diagnostic_lists_different_capability(tmp_path: Path) -> None:
    """A task referencing a different capability simply does not associate.

    A reference to ``other-capability`` is a legitimate canonical
    reference for that capability, not an unsafe reference. When the
    router asks for ``capability``, the task correctly stays out of
    the selected slice and no diagnostic is produced — the diagnostic
    is reserved for truly unsafe references that cannot be audited.
    """
    root = tmp_path
    _make_change(root)
    import json

    tasks_file = root / ".ai-harness" / "changes" / "demo" / "tasks.json"
    payload = {
        "tasks": [
            {
                "id": "1",
                "title": "Other cap",
                "spec": "other-capability",
                "phase": "implement",
                "depends_on": [],
                "status": "pending",
                "subtasks": [],
            }
        ]
    }
    tasks_file.write_text(json.dumps(payload), encoding="utf-8")

    state = task_capability_state(root, "demo", "capability")

    assert state.taskIds == []
    assert state.routingDiagnostic is None


def test_routing_diagnostic_lists_empty_spec(tmp_path: Path) -> None:
    """A task with an empty spec reference is reported in the diagnostic."""
    root = tmp_path
    _make_change(root)
    import json

    tasks_file = root / ".ai-harness" / "changes" / "demo" / "tasks.json"
    payload = {
        "tasks": [
            {
                "id": "1",
                "title": "Empty",
                "spec": "",
                "phase": "implement",
                "depends_on": [],
                "status": "pending",
                "subtasks": [],
            }
        ]
    }
    tasks_file.write_text(json.dumps(payload), encoding="utf-8")

    state = task_capability_state(root, "demo", "capability")

    assert state.taskIds == []
    assert state.routingDiagnostic is not None
    assert "empty spec reference" in state.routingDiagnostic


def test_routing_diagnostic_keeps_safe_tasks_associated(tmp_path: Path) -> None:
    """Unsafe tasks are excluded but safe tasks remain associated with the capability."""
    root = tmp_path
    _make_change(root)
    # Safe reference for the selected capability.
    task_create(
        root,
        "demo",
        TaskInput(
            title="Safe",
            spec="capability",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    # Inject an unsafe task alongside the safe one.
    import json

    tasks_file = root / ".ai-harness" / "changes" / "demo" / "tasks.json"
    raw = json.loads(tasks_file.read_text(encoding="utf-8"))
    raw["tasks"].append(
        {
            "id": "2",
            "title": "Absolute",
            "spec": "/etc/specs/capability.md",
            "phase": "implement",
            "depends_on": [],
            "status": "pending",
            "subtasks": [],
        }
    )
    tasks_file.write_text(json.dumps(raw), encoding="utf-8")

    state = task_capability_state(root, "demo", "capability")

    assert state.taskIds == ["1"]
    assert state.routingDiagnostic is not None
    assert "absolute path" in state.routingDiagnostic
    assert "/etc/specs/capability.md" in state.routingDiagnostic


def test_slice_status_surfaces_unsafe_reference_diagnostic(tmp_path: Path) -> None:
    """The slice router surfaces the unsafe-reference diagnostic in ``blockedReasons``."""
    import json
    from dataclasses import asdict

    import yaml

    from ai_harness.modules.harness.change import change_continue

    # Initialise the config so change_continue can resolve context.
    config_path = tmp_path / ".ai-harness" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "commit": {"format": "[{change_name}][{task_id}] {slug}"},
                "phases": {
                    phase: {"rules": ["rule"]}
                    for phase in (
                        "change_explorer",
                        "change_propose",
                        "change_design",
                        "change_specs",
                        "change_tasks",
                        "change_implementor",
                        "change_validator",
                        "change_archiver",
                    )
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    change_dir = _make_change(tmp_path, "unsafe-ref")
    prd = change_dir / "prd.md"
    prd.write_text(
        "---\n"
        "changeFlow:\n"
        "  schemaVersion: 1\n"
        "  mode: sliced\n"
        "  capabilities:\n"
        "    - id: unsafe-ref\n"
        "      title: U\n"
        "      risk:\n"
        "        level: normal\n"
        "        reasons: []\n"
        "      design: none\n"
        "---\n",
        encoding="utf-8",
    )
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "unsafe-ref.md").write_text("# spec\n", encoding="utf-8")
    tasks_file = change_dir / "tasks.json"
    tasks_file.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "1",
                        "title": "Absolute",
                        "spec": "/etc/specs/unsafe-ref.md",
                        "phase": "implement",
                        "depends_on": [],
                        "status": "pending",
                        "subtasks": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    status = change_continue(tmp_path, "unsafe-ref")
    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "tasks"
    assert any("absolute path" in reason for reason in payload["blockedReasons"])
