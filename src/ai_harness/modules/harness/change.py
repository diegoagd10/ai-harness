"""Derive file-backed change state from disk artifacts.

Change/task FSM (file-backed)
-----------------------------
A change has no mutable status field — status is *derived* each call
from the artifact files on disk under ``.ai-harness/changes/<name>/``.
The phases and their gating artifact filenames are the source of truth;
add or remove an artifact file and the FSM transitions automatically.

Legacy / global FSM (no ``changeFlow`` front matter):

::

    explore (exploration.md)
        |
        v
    prd (prd.md)
        |
        v
    design (design.md)
        |
        v
    specs (specs/*.md)
        |
        v
    tasks (tasks.json) ---> TaskProgress derived from tasks.json:
        |                       pending / in_progress / done / blocked
        v                       (file-backed, no separate state column)
    implement (implementation.md — populated as tasks close)
        |
        v
    validate (validation.md)
        |
        v
    archive (move change folder into .ai-harness/archive/)

Sliced FSM (PRD declares ``changeFlow`` with ordered capabilities):

::

    sliced design<capability>.md -> specs/<capability>.md
            -> tasks.json (filtered by canonical spec)
            -> implement -> validations/<capability>.md
            -> review-slice (approval gate)
            -> next capability or final validation -> archive

Rich slice routes are projected onto the existing ``nextRecommended``
phase tokens at the serializer boundary so older consumers see a
schema-v2-compatible surface; the additive ``sliceStatus`` field
carries the slice-aware truth for new consumers.

Each transition is gated by the artifact for the *next* phase being
present and unblocked — ``_derive_status`` walks the phase order,
aggregates ``TaskProgress`` from ``tasks.json``, and emits
``next_recommended`` + ``blocked_reasons`` so callers can render
the FSM without re-implementing the rules.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from pathlib import Path

from ai_harness.modules.change_config import ChangeConfigAdministrator, ChangeConfigError
from ai_harness.modules.change_config.models import ChangeConfigPromptContext
from ai_harness.modules.harness.change_flow import (
    Capability,
    RiskAssessment,
    compute_effective_risk,
    read_prd_delivery,
)
from ai_harness.modules.harness.tasks import (
    TaskProgress,
    TaskStoreError,
    task_progress,
)

_PHASES = ("explore", "prd", "design", "specs", "tasks", "implement", "validate", "archive")
_SCHEMA_NAME = "ai-harness.change-status"
# Schema version 3 introduces the additive nullable ``sliceStatus`` field
# carrying slice-aware routing and selected/next capability refs. Version 2
# added the nullable ``configContext`` field; version 1 omitted both.
# Consumers rely on the numeric version to detect the additive shape
# rather than silently receiving a changed schema.
_SCHEMA_VERSION = 3
_ARTIFACT_FILENAMES = {
    "exploration": "exploration.md",
    "prd": "prd.md",
    "design": "design.md",
    "tasks": "tasks.json",
    "implementation": "implementation.md",
    "validation": "validation.md",
}


class ChangeStoreError(RuntimeError):
    """Raised when a change operation cannot be satisfied.

    Carries an optional ``errors`` list — the human-readable error
    messages that produced the failure. Single-message callers
    (``ChangeStoreError("text")``) default ``errors`` to ``["text"]`` so
    archive/CLI callers can emit a uniform ``{ "errors": [...] }`` shape
    without branching on construction style.
    """

    def __init__(self, message: str = "", *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = list(errors) if errors is not None else ([message] if message else [])


@dataclass(frozen=True, slots=True)
class CapabilityRef:
    """A capability pointer in ``sliceStatus``.

    ``ordinal`` is the one-based PRD order, so consumers can render
    "Capability 1 of 3" without re-parsing the PRD.
    """

    id: str
    ordinal: int
    title: str


@dataclass(frozen=True, slots=True)
class ApprovalStatus:
    """The currently-pending human gate and its state.

    ``gate`` is ``"implementation"`` (effective high-risk capabilities)
    or ``"continuation"`` (capability-bound review). ``state`` reports
    whether the gate is required, present, or stale. ``null`` gates
    mean no human decision is needed.
    """

    gate: str | None  # "implementation" | "continuation" | null
    state: str  # "not-required" | "required" | "valid" | "stale"


@dataclass(frozen=True, slots=True)
class SliceStatus:
    """The additive slice-aware status (schema v3).

    ``mode`` discriminates legacy (no sliced front matter) from sliced
    or blocked. ``route`` is the rich slice token; ``nextRecommended``
    on :class:`ChangeStatus` is its safe projection for legacy
    consumers. ``currentCapability`` and ``nextCapability`` are
    non-null whenever a sliced or blocked delivery can identify the
    work in scope; both are null in legacy mode and for one-capability
    changes that have no successor.

    ``taskProgress`` mirrors the global ``taskProgress``; this duplicate
    is intentional so a route caller never needs to re-derive progress.
    ``completedCapabilities`` is the ordered list of capability IDs the
    router has accepted as complete in this derivation pass — it is
    never persisted across invocations.
    """

    mode: str  # "sliced" | "legacy" | "blocked"
    route: str
    currentCapability: CapabilityRef | None
    nextCapability: CapabilityRef | None
    completedCapabilities: tuple[str, ...]
    specPath: str | None
    designPath: str | None
    validationPath: str | None
    taskProgress: TaskProgress
    risk: RiskAssessment | None
    approval: ApprovalStatus


@dataclass(frozen=True, slots=True)
class ChangeStatus:
    """Represent the derived file-backed state for one change.

    Schema version 3 appends the additive nullable ``sliceStatus``
    field while every v2 field (including ``configContext``) retains
    its order, name, type, and meaning. Legacy consumers can ignore
    ``sliceStatus``; sliced-aware consumers read slice status directly
    and rely on ``nextRecommended`` for the projected legacy token.
    """

    schemaName: str
    schemaVersion: int
    changeName: str
    changeRoot: str
    artifactPaths: dict[str, list[str]]
    artifacts: dict[str, str]
    taskProgress: TaskProgress
    dependencies: dict[str, str]
    relationships: dict[str, object]
    phaseInstructions: str | None
    nextRecommended: str
    blockedReasons: list[str]
    configContext: ChangeConfigPromptContext | None
    sliceStatus: SliceStatus | None = None


def change_new(root: Path, change: str) -> ChangeStatus:
    """Create a new change folder and return its fresh status."""
    change_dir = _change_dir(root, change)
    if change_dir.exists():
        raise ChangeStoreError(f"Change already exists: {change}")

    change_dir.mkdir(parents=True)
    return _derive_status(root, change)


def change_continue(root: Path, change: str) -> ChangeStatus:
    """Return status for an existing change folder.

    Derives the file-backed status first, then enriches the response
    with the routed phase's :class:`ChangeConfigPromptContext` (or
    ``None`` for ``resolve-blockers``) using
    :class:`ChangeConfigAdministrator`. The reusable
    :func:`_derive_status` remains side-effect free; enrichment is the
    behaviour-specific seam owned by ``change-continue``.

    Sequence is fixed: derive → classify route → validate config →
    read context → immutable replace. Reusing a cached administrator
    or parsed configuration is forbidden so file edits between calls
    become visible immediately.
    """
    change_dir = _change_dir(root, change)
    if not change_dir.is_dir():
        raise ChangeStoreError(f"Change not found: {change}")

    status = _derive_status(root, change)
    context = _resolve_config_context(root, status.nextRecommended)
    if context is not None:
        return replace(status, configContext=context)
    return status


def _resolve_config_context(root: Path, next_recommended: str) -> ChangeConfigPromptContext | None:
    """Return the routed phase's prompt context or ``None`` for blockers.

    ``resolve-blockers`` is the synthetic non-routable token — no
    sub-agent dispatches, so the configuration administrator is never
    consulted and no canonical phase is invented. Actionable routes
    instantiate a fresh administrator, validate
    ``.ai-harness/config.yml``, and read context through the
    administrator's ``get_context_by``. Validation warnings are
    non-halting and never block context delivery.

    Every halted outcome (missing file, malformed YAML, schema-invalid
    config, read failure) is normalized to :class:`ChangeStoreError`
    here so callers see one failure type across the derivation seam.
    """
    if next_recommended == "resolve-blockers":
        return None

    admin = ChangeConfigAdministrator(repo_root=root)
    try:
        validation = admin.validate_config()
    except (ChangeConfigError, OSError) as exc:
        raise ChangeStoreError(f"Change configuration is unavailable: {exc}") from exc
    if not validation.is_valid:
        raise ChangeStoreError("Change configuration is invalid; fix .ai-harness/config.yml before continuing.")
    try:
        return admin.get_context_by(next_recommended)
    except (ChangeConfigError, OSError) as exc:
        raise ChangeStoreError(f"Could not load change configuration context: {exc}") from exc


def _derive_status(root: Path, change: str) -> ChangeStatus:
    """Derive a ChangeStatus from artifact presence on disk."""
    try:
        progress = task_progress(root, change)
    except TaskStoreError as exc:
        raise ChangeStoreError(str(exc)) from exc

    change_dir = _change_dir(root, change)
    artifact_paths = _artifact_paths(change_dir, change)
    artifacts = _artifact_statuses(artifact_paths)
    dependencies = _dependencies(artifacts, progress)

    # Slice-aware derivation. Legacy mode (no sliced front matter) falls
    # back to a ``legacy`` slice status whose ``route`` mirrors the
    # projected ``nextRecommended`` token. Sliced or blocked deliveries
    # produce rich routes that the projector below maps back to the
    # existing phase tokens so older consumers see no change.
    slice_status, blocked_reasons = _derive_slice_status(root, change, change_dir, progress)
    next_recommended = _project_slice_route_to_next_recommended(
        slice_status.route,
        fallback=_next_recommended(artifacts, dependencies),
    )

    return ChangeStatus(
        schemaName=_SCHEMA_NAME,
        schemaVersion=_SCHEMA_VERSION,
        changeName=change,
        changeRoot=str(_change_relative_dir(change)),
        artifactPaths=artifact_paths,
        artifacts=artifacts,
        taskProgress=progress,
        dependencies=dependencies,
        relationships={"parent": None, "siblings": [], "children": []},
        phaseInstructions=None,
        nextRecommended=next_recommended,
        blockedReasons=blocked_reasons,
        configContext=None,
        sliceStatus=slice_status,
    )


def _change_dir(root: Path, change: str) -> Path:
    """Return the directory for a change."""
    return root / _change_relative_dir(change)


def _change_relative_dir(change: str) -> Path:
    """Return the repository-relative directory for a change."""
    return Path(".ai-harness") / "changes" / change


def _artifact_paths(change_dir: Path, change: str) -> dict[str, list[str]]:
    """Return existing artifact paths using filename-keyed contract keys."""
    relative_dir = _change_relative_dir(change)
    paths = {
        key: [str(relative_dir / filename)] if (change_dir / filename).is_file() else []
        for key, filename in _ARTIFACT_FILENAMES.items()
    }
    specs_dir = change_dir / "specs"
    paths["specs"] = [
        str(relative_dir / "specs" / path.name) for path in sorted(specs_dir.glob("*.md")) if path.is_file()
    ]
    return paths


def _artifact_statuses(artifact_paths: dict[str, list[str]]) -> dict[str, str]:
    """Return phase-keyed done/missing states from artifact paths."""
    return {
        "explore": _done_if_present(artifact_paths["exploration"]),
        "prd": _done_if_present(artifact_paths["prd"]),
        "design": _done_if_present(artifact_paths["design"]),
        "specs": _done_if_present(artifact_paths["specs"]),
        "tasks": _done_if_present(artifact_paths["tasks"]),
        "implement": _done_if_present(artifact_paths["implementation"]),
        "validate": _done_if_present(artifact_paths["validation"]),
        "archive": "missing",
    }


def _done_if_present(paths: list[str]) -> str:
    """Return done when one or more paths are present."""
    return "done" if paths else "missing"


def _dependencies(artifacts: dict[str, str], progress: TaskProgress) -> dict[str, str]:
    """Compute phase dependency states from the forward DAG."""
    return {
        "explore": _done_or_ready(artifacts, "explore", True),
        "prd": _done_or_ready(artifacts, "prd", _is_done(artifacts, "explore")),
        "design": _done_or_ready(artifacts, "design", _is_done(artifacts, "prd")),
        "specs": _done_or_ready(artifacts, "specs", _is_done(artifacts, "prd")),
        "tasks": _done_or_ready(artifacts, "tasks", _is_done(artifacts, "design") or _is_done(artifacts, "specs")),
        "implement": _done_or_ready(artifacts, "implement", _is_done(artifacts, "tasks")),
        "validate": _done_or_ready(artifacts, "validate", _is_done(artifacts, "implement")),
        "archive": _archive_dependency(artifacts, progress),
    }


def _done_or_ready(artifacts: dict[str, str], phase: str, dependencies_done: bool) -> str:
    """Return all_done, ready, or blocked for a file-producing phase."""
    if _is_done(artifacts, phase):
        return "all_done"
    if dependencies_done:
        return "ready"
    return "blocked"


def _archive_dependency(artifacts: dict[str, str], progress: TaskProgress) -> str:
    """Return archive readiness with a non-empty task-progress guard."""
    if _is_done(artifacts, "validate") and progress.allComplete and progress.total > 0:
        return "ready"
    return "blocked"


def _is_done(artifacts: dict[str, str], phase: str) -> bool:
    """Return whether a phase artifact is present."""
    return artifacts[phase] == "done"


def _next_recommended(artifacts: dict[str, str], dependencies: dict[str, str]) -> str:
    """Return the first missing phase whose dependencies are ready."""
    for phase in _PHASES:
        if artifacts[phase] == "missing" and dependencies[phase] == "ready":
            return phase
    return "resolve-blockers"


# ---------------------------------------------------------------------------
# Slice-aware status derivation (schema v3, additive only)
# ---------------------------------------------------------------------------


_LEGACY_BLOCKED_REASONS: tuple[str, ...] = ()
# Slice routes that DO NOT have a legacy equivalent and therefore
# project to ``resolve-blockers`` so older consumers always receive a
# known token. Every other rich route maps verbatim onto a legacy phase
# token (see ``_project_slice_route_to_next_recommended``).
_HUMAN_GATE_SLICE_ROUTES = frozenset({"review-slice", "approve-implementation"})
_VALIDATION_SLICE_ROUTES = frozenset({"validate-slice", "final-validate"})


def _derive_slice_status(
    root: Path,
    change: str,
    change_dir: Path,
    progress: TaskProgress,
) -> tuple[SliceStatus, list[str]]:
    """Compute the additive ``SliceStatus`` for a change.

    Returns a tuple of the slice status and any human-readable
    ``blockedReasons`` callers should carry through. ``blockedReasons``
    is populated only for malformed metadata or required human gates;
    valid routes leave it empty so existing callers see no behavioral
    change.
    """
    prd_path = change_dir / "prd.md"
    delivery = read_prd_delivery(prd_path)

    if delivery.mode == "blocked":
        return _blocked_slice_status(delivery.error or "Sliced PRD metadata is invalid."), (
            [delivery.error] if delivery.error else ["Sliced PRD metadata is invalid."]
        )

    if delivery.mode == "legacy":
        return _legacy_slice_status(), []

    # Sliced delivery: walk the first capability without a valid
    # continuation approval. For task 3 we always select the first
    # capability; task 5 adds continuation approval filtering.
    first_capability = delivery.capabilities[0]
    next_capability = delivery.capabilities[1] if len(delivery.capabilities) > 1 else None
    current_ref = _capability_ref_from(first_capability)
    next_ref = _capability_ref_from(next_capability) if next_capability else None

    risk = compute_effective_risk(first_capability)
    # The first-capability check is intentionally limited to basic
    # review; deeper continuation selection belongs to task 5.
    approval = _approval_for_first_slice()
    spec_path, design_path, validation_path = _capability_artifact_paths(first_capability)

    if risk.changeWideDesignRequired and not _non_empty_file(change_dir / "design.md"):
        # Elevated risk requires a change-wide design first.
        return (
            _build_slice_status(
                mode="sliced",
                route="design",
                current=current_ref,
                next_capability=next_ref,
                spec_path=spec_path,
                design_path="design.md",
                validation_path=validation_path,
                progress=progress,
                risk=risk,
                approval=ApprovalStatus(gate="implementation", state="required"),
            ),
            ["Change-wide design is required before planning can proceed."],
        )

    if first_capability.design == "slice" and not _non_empty_file(change_dir / design_path):
        return (
            _build_slice_status(
                mode="sliced",
                route="design",
                current=current_ref,
                next_capability=next_ref,
                spec_path=spec_path,
                design_path=design_path,
                validation_path=validation_path,
                progress=progress,
                risk=risk,
                approval=approval,
            ),
            [],
        )

    if not _non_empty_file(change_dir / spec_path):
        return (
            _build_slice_status(
                mode="sliced",
                route="specs",
                current=current_ref,
                next_capability=next_ref,
                spec_path=spec_path,
                design_path=design_path,
                validation_path=validation_path,
                progress=progress,
                risk=risk,
                approval=approval,
            ),
            [],
        )

    # Tasks gating: zero associated tasks (per spec reference) routes
    # to ``tasks``.
    cap_state = _read_capability_state(root, change_dir, first_capability)
    if not cap_state.taskIds:
        return (
            _build_slice_status(
                mode="sliced",
                route="tasks",
                current=current_ref,
                next_capability=next_ref,
                spec_path=spec_path,
                design_path=design_path,
                validation_path=validation_path,
                progress=progress,
                risk=risk,
                approval=approval,
            ),
            [],
        )

    if not cap_state.progress.allComplete:
        return (
            _build_slice_status(
                mode="sliced",
                route="implement",
                current=current_ref,
                next_capability=next_ref,
                spec_path=spec_path,
                design_path=design_path,
                validation_path=validation_path,
                progress=progress,
                risk=risk,
                approval=approval,
            ),
            [],
        )

    if not _non_empty_file(change_dir / validation_path):
        return (
            _build_slice_status(
                mode="sliced",
                route="validate-slice",
                current=current_ref,
                next_capability=next_ref,
                spec_path=spec_path,
                design_path=design_path,
                validation_path=validation_path,
                progress=progress,
                risk=risk,
                approval=approval,
            ),
            [],
        )

    return (
        _build_slice_status(
            mode="sliced",
            route="review-slice",
            current=current_ref,
            next_capability=next_ref,
            spec_path=spec_path,
            design_path=design_path,
            validation_path=validation_path,
            progress=progress,
            risk=risk,
            approval=ApprovalStatus(gate="continuation", state="required"),
        ),
        [],
    )


def _legacy_slice_status() -> SliceStatus:
    """Return a legacy-mode slice status.

    Legacy mode intentionally carries no current/next capability and
    routes to the ``legacy`` token; the projector turns that into the
    existing global ``nextRecommended`` token.
    """
    return SliceStatus(
        mode="legacy",
        route="legacy",
        currentCapability=None,
        nextCapability=None,
        completedCapabilities=(),
        specPath=None,
        designPath=None,
        validationPath=None,
        taskProgress=TaskProgress(total=0, completed=0, pending=0, allComplete=True),
        risk=None,
        approval=ApprovalStatus(gate=None, state="not-required"),
    )


def _blocked_slice_status(error: str) -> SliceStatus:
    """Return a blocked-mode slice status carrying no capability pointer."""
    return SliceStatus(
        mode="blocked",
        route="resolve-blockers",
        currentCapability=None,
        nextCapability=None,
        completedCapabilities=(),
        specPath=None,
        designPath=None,
        validationPath=None,
        taskProgress=TaskProgress(total=0, completed=0, pending=0, allComplete=True),
        risk=None,
        approval=ApprovalStatus(gate=None, state="required"),
    )


def _build_slice_status(
    *,
    mode: str,
    route: str,
    current: CapabilityRef | None,
    next_capability: CapabilityRef | None,
    spec_path: str | None,
    design_path: str | None,
    validation_path: str | None,
    progress: TaskProgress,
    risk: RiskAssessment | None,
    approval: ApprovalStatus,
) -> SliceStatus:
    """Construct a slice status with a stable field order."""
    return SliceStatus(
        mode=mode,
        route=route,
        currentCapability=current,
        nextCapability=next_capability,
        completedCapabilities=(),
        specPath=spec_path,
        designPath=design_path,
        validationPath=validation_path,
        taskProgress=progress,
        risk=risk,
        approval=approval,
    )


def _capability_ref_from(capability: Capability | None) -> CapabilityRef | None:
    """Convert a parsed capability into a :class:`CapabilityRef`."""
    if capability is None:
        return None
    return CapabilityRef(id=capability.id, ordinal=capability.ordinal, title=capability.title)


def _capability_artifact_paths(capability: Capability) -> tuple[str, str, str]:
    """Return ``(specPath, designPath, validationPath)`` for a capability."""
    spec_path = f"specs/{capability.id}.md"
    design_path = f"designs/{capability.id}.md"
    validation_path = f"validations/{capability.id}.md"
    return spec_path, design_path, validation_path


def _non_empty_file(path: Path) -> bool:
    """Return whether *path* is a regular file with at least one byte."""
    if not path.is_file():
        return False
    try:
        return path.stat().st_size > 0
    except OSError:
        return False


def _approval_for_first_slice() -> ApprovalStatus:
    """Default approval state for a never-approved first slice."""
    return ApprovalStatus(gate=None, state="not-required")


def _read_capability_state(root: Path, change_dir: Path, capability: Capability):
    """Return the capability task state without leaking the seam to the router."""
    # Lazy import keeps the slice module surface small at load time and
    # avoids a circular dependency between ``change`` and ``tasks``.
    from ai_harness.modules.harness.tasks import task_capability_state

    spec_path = f"specs/{capability.id}.md"
    return task_capability_state(root, change_dir.name, spec_path)


def _project_slice_route_to_next_recommended(route: str, *, fallback: str) -> str:
    """Project a rich slice route onto a legacy ``nextRecommended`` token.

    Validation routes project to ``validate``. Human gates and the
    blocked resolution token project to ``resolve-blockers`` so legacy
    consumers never see a new token. All other actionable slice
    routes map verbatim onto the legacy phase vocabulary. The
    ``legacy`` slice route passes through ``fallback`` unchanged so a
    legacy change keeps its existing recommendation logic.
    """
    if route == "legacy":
        return fallback
    if route in _HUMAN_GATE_SLICE_ROUTES:
        return "resolve-blockers"
    if route in _VALIDATION_SLICE_ROUTES:
        return "validate"
    if route in _PHASES:
        return route
    return "resolve-blockers"


def _write_phase_artifact_atomic(artifact_path: Path, content: str) -> None:
    """Write a phase artifact with a sibling temp file then rename."""
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = artifact_path.with_name(f".{artifact_path.name}.tmp")
    temp_file.write_text(content, encoding="utf-8")
    temp_file.replace(artifact_path)


def change_archive(root: Path, change: str) -> None:
    """Archive a structurally valid Change.

    Validates every structural precondition BEFORE touching the filesystem.
    On success, moves ``.ai-harness/changes/{change}/specs/`` to
    ``.ai-harness/specs/{change}/`` and the remaining
    ``.ai-harness/changes/{change}/`` folder to
    ``.ai-harness/archive/{change}/``. The moves are all-or-nothing: if
    the second move fails, the first is rolled back so the source tree
    is restored unchanged.

    On failure, raises :class:`ChangeStoreError` whose ``errors`` attribute
    is the list of human-readable error strings and whose ``args[0]`` is
    the joined summary. Returns nothing on success.
    """
    errors = _archive_preflight(root, change)
    if errors:
        raise ChangeStoreError("\n".join(errors), errors=errors)

    _archive_move(root, change)


def _archive_preflight(root: Path, change: str) -> list[str]:
    """Collect every structural archive error without mutating the filesystem.

    Returns an empty list when every precondition holds. Multiple errors
    are collected so the CLI can surface them all at once instead of
    forcing the user to retry one failure at a time.
    """
    errors: list[str] = []
    change_dir = _change_dir(root, change)

    if not change_dir.is_dir():
        errors.append(f"Change folder not found: {change_dir}")
        # No point checking the rest — every subsequent precondition
        # depends on the change folder existing.
        return errors

    try:
        progress = task_progress(root, change)
        if not progress.allComplete:
            errors.append(f"Cannot archive: tasks are incomplete ({progress.completed}/{progress.total} done)")
    except TaskStoreError as exc:
        errors.append(f"Cannot read task progress: {exc}")

    validation = change_dir / "validation.md"
    if not validation.is_file():
        errors.append(f"Validation artifact missing: {validation}")

    specs_dest = _specs_archive_dir(root, change)
    if specs_dest.exists():
        errors.append(f"Specs destination already exists: {specs_dest}")

    archive_dest = _archive_dir(root, change)
    if archive_dest.exists():
        errors.append(f"Archive destination already exists: {archive_dest}")

    return errors


def _archive_move(root: Path, change: str) -> None:
    """Promote specs and move the remaining Change folder.

    Performs the moves in two stages with rollback if the second stage
    fails. The first stage is atomic from the caller's perspective — if
    it raises, the filesystem is unchanged. The second stage rolls back
    the first on failure so the source tree survives intact.
    """
    change_dir = _change_dir(root, change)
    specs_src = change_dir / "specs"
    specs_dest = _specs_archive_dir(root, change)
    archive_dest = _archive_dir(root, change)

    # Stage 1: promote specs subtree to top-level specs destination.
    # Skip when the source has no specs subtree — archive can still
    # succeed and produce an archive folder without specs duplication.
    if specs_src.is_dir():
        specs_dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(specs_src), str(specs_dest))
        except OSError as exc:
            raise ChangeStoreError(
                f"Failed to promote specs: {exc}",
                errors=[f"Failed to promote specs to {specs_dest}: {exc}"],
            ) from exc

    # Stage 2: move the remaining change folder to the top-level
    # archive destination. On failure, roll back stage 1 so the source
    # tree is restored unchanged.
    archive_dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(change_dir), str(archive_dest))
    except OSError as exc:
        rollback_errors = _rollback_specs_promotion(specs_src, specs_dest)
        if rollback_errors:
            raise ChangeStoreError(
                "Archive move failed and rollback failed",
                errors=[
                    f"Failed to move change folder to {archive_dest}: {exc}",
                    *rollback_errors,
                ],
            ) from exc
        raise ChangeStoreError(
            f"Failed to move change folder: {exc}",
            errors=[f"Failed to move change folder to {archive_dest}: {exc}"],
        ) from exc


def _rollback_specs_promotion(specs_src: Path, specs_dest: Path) -> list[str]:
    """Restore ``specs_dest`` back to ``specs_src``; return errors on rollback failure.

    Called only when the change-folder move fails after the specs move
    already succeeded. Returns a list of rollback error strings so the
    caller can surface both the original failure and any rollback problem
    to the user.
    """
    if not specs_dest.is_dir():
        return []
    try:
        shutil.move(str(specs_dest), str(specs_src))
    except OSError as exc:
        return [f"Rollback of specs promotion failed: {exc}"]
    return []


def _specs_archive_dir(root: Path, change: str) -> Path:
    """Return the top-level specs destination for an archived Change."""
    return root / ".ai-harness" / "specs" / change


def _archive_dir(root: Path, change: str) -> Path:
    """Return the top-level archive destination for an archived Change.

    Stale ``changes/archive/{name}`` assumptions are intentionally not
    supported — archive always lands at the top-level destination so
    callers do not need to learn two layouts.
    """
    return root / ".ai-harness" / "archive" / change
