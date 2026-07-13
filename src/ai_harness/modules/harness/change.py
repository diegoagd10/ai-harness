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
from datetime import UTC, datetime
from pathlib import Path

from ai_harness.modules.change_config import ChangeConfigAdministrator, ChangeConfigError
from ai_harness.modules.change_config.models import ChangeConfigPromptContext
from ai_harness.modules.harness.change_flow import (
    ApprovalRecord,
    ApprovalStore,
    ApprovalStoreError,
    Capability,
    PrdDelivery,
    RiskAssessment,
    compute_effective_risk,
    hash_scope_digest,
    read_prd_delivery,
)
from ai_harness.modules.harness.tasks import (
    TaskProgress,
    TaskStoreError,
    task_capability_state,
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

    # Read approvals first so malformed data surfaces as a blocked
    # route before any capability derivation proceeds.
    approvals, approval_error = _safe_read_approvals(change_dir)
    if approval_error is not None:
        return _blocked_slice_status(approval_error), [approval_error]

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
    spec_path, design_path, validation_path = _capability_artifact_paths(first_capability)

    if risk.changeWideDesignRequired and not _non_empty_file(change_dir / "design.md"):
        # Elevated risk requires a change-wide design first. The
        # implementation gate is *also* implied because change-wide
        # design is a high-risk prerequisite, but the immediate
        # actionable route is ``design``; we mark approval as the
        # eventual pending requirement.
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
                approval=_approval_status_for_gate(approvals, "implementation", first_capability.id, root, change),
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
                approval=_approval_status_for_gate(approvals, "implementation", first_capability.id, root, change),
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
                approval=_approval_status_for_gate(approvals, "implementation", first_capability.id, root, change),
            ),
            [],
        )

    # Effective high-risk capabilities require a fresh implementation
    # approval before any pending task is implemented. Without one the
    # route is ``approve-implementation`` (the human gate).
    if risk.effectiveLevel == "high":
        gate = _approval_status_for_gate(approvals, "implementation", first_capability.id, root, change)
        if gate.state != "valid":
            return (
                _build_slice_status(
                    mode="sliced",
                    route="approve-implementation",
                    current=current_ref,
                    next_capability=next_ref,
                    spec_path=spec_path,
                    design_path=design_path,
                    validation_path=validation_path,
                    progress=progress,
                    risk=risk,
                    approval=gate,
                ),
                [],
            )

    if not cap_state.progress.allComplete:
        # Once an implementation approval is valid for a high-risk
        # capability, the approval state persists through pending work
        # so the slice never silently forgets the human gate. For
        # normal-risk slices, the gate was never required.
        implement_approval = (
            _approval_status_for_gate(approvals, "implementation", first_capability.id, root, change)
            if risk.effectiveLevel == "high"
            else ApprovalStatus(gate=None, state="not-required")
        )
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
                approval=implement_approval,
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
                approval=ApprovalStatus(gate=None, state="not-required"),
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


def _safe_read_approvals(change_dir: Path) -> tuple[tuple[ApprovalRecord, ...], str | None]:
    """Return approval records and any parse error.

    The slice router needs the approval records to project state. If
    ``approvals.json`` is present but malformed, the caller MUST
    surface the failure as a blocked route — silently ignoring the
    data would let callers accept approvals that cannot be audited.
    """
    store = ApprovalStore(change_dir)
    try:
        return store.read(), None
    except ApprovalStoreError as exc:
        return (), str(exc)


def _approval_status_for_gate(
    approvals: tuple[ApprovalRecord, ...],
    gate: str,
    capability_id: str,
    root: Path,
    change: str,
) -> ApprovalStatus:
    """Return the current :class:`ApprovalStatus` for the given gate.

    Looks for the latest persisted record matching
    ``(capability_id, gate)`` and recomputes the scope digest from
    disk. When the digest matches the recorded digest, the approval is
    ``valid``; otherwise it is ``stale``. A missing record produces
    ``state="required"`` for ``implementation`` and
    ``state="required"`` for ``continuation`` is only ever consulted
    when the slice arrives at the review checkpoint.
    """
    matching = [record for record in approvals if record.gate == gate and record.capabilityId == capability_id]
    if not matching:
        return ApprovalStatus(gate=gate, state="required")

    latest = matching[-1]
    try:
        current_digest = _compute_scope_digest(root, change, gate=gate)
    except (ChangeStoreError, OSError):
        return ApprovalStatus(gate=gate, state="stale")

    if current_digest == latest.scopeDigest:
        return ApprovalStatus(gate=gate, state="valid")
    return ApprovalStatus(gate=gate, state="stale")


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
    the second stage fails, the first is rolled back so the source tree
    is restored unchanged.

    On failure, raises :class:`ChangeStoreError` whose ``errors`` attribute
    is the list of human-readable error strings and whose ``args[0]`` is
    the joined summary. Returns nothing on success.
    """
    errors = _archive_preflight(root, change)
    if errors:
        raise ChangeStoreError("\n".join(errors), errors=errors)

    _archive_move(root, change)


# ---------------------------------------------------------------------------
# Approval persistence — task 4
# ---------------------------------------------------------------------------


def change_approve(root: Path, change: str) -> ChangeStatus:
    """Approve the current pending gate and return freshly derived status.

    The operation refuses to act when the current route is not a human
    gate (``approve-implementation`` or ``review-slice``). It derives
    the gate-specific scope fingerprint from disk, atomically writes a
    new :class:`ApprovalRecord` to ``approvals.json``, and returns the
    resulting :class:`ChangeStatus` so the caller can confirm the new
    state without re-deriving it.

    Raises :class:`ChangeStoreError` for off-route approvals, malformed
    approvals data, missing change folders, or any disk write failure.
    """
    return ChangeLifecycle(root).approve_pending_gate(change)


class ChangeLifecycle:
    """Own creation, continuation, approval persistence, and archive moves.

    All four operations are side-effect free *except*:

    - :meth:`create` creates an empty change folder.
    - :meth:`approve_pending_gate` atomically writes
      ``approvals.json``.
    - :meth:`archive` performs the two-stage move.

    :meth:`continue_` is derived entirely from disk; its returned
    :class:`ChangeStatus` is the canonical source for any caller.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def create(self, change: str) -> ChangeStatus:
        """Wrap :func:`change_new` so the class is the only seam for callers."""
        return change_new(self._root, change)

    def continue_(self, change: str) -> ChangeStatus:
        """Wrap :func:`change_continue` so the class is the only seam for callers."""
        return change_continue(self._root, change)

    def approve_pending_gate(self, change: str) -> ChangeStatus:
        """Atomically approve the current gate and return the fresh status.

        Identifies the current route by deriving status (without
        persisting approval data), then computes the gate-specific
        scope fingerprint from disk. Refuses to write any approval
        when the route is neither ``approve-implementation`` nor
        ``review-slice``; the gate selection is fully driven by disk
        facts so callers cannot approve arbitrary scope.

        The recorded :class:`ApprovalRecord` includes a derived scope
        digest, so the next status derivation detects scope edits
        through fingerprint mismatch and reports the approval stale.
        """
        change_dir = _change_dir(self._root, change)
        if not change_dir.is_dir():
            raise ChangeStoreError(f"Change not found: {change}")

        current = _derive_status(self._root, change)
        if current.sliceStatus is None:
            raise ChangeStoreError("No slice status available; cannot approve without a sliced PRD.")

        gate = current.sliceStatus.approval.gate
        if gate not in {"implementation", "continuation"}:
            raise ChangeStoreError(
                f"Approval refused: current route is not a human gate (route={current.sliceStatus.route!r})."
            )

        scope_digest = _compute_scope_digest(self._root, change, gate=gate)
        store = ApprovalStore(change_dir)
        try:
            existing = store.read()
        except ApprovalStoreError as exc:
            raise ChangeStoreError(str(exc)) from exc

        record = ApprovalRecord(
            capabilityId=current.sliceStatus.currentCapability.id
            if current.sliceStatus.currentCapability is not None
            else change,
            gate=gate,
            scopeDigest=scope_digest,
            approvedAt=_now_iso8601(),
        )
        store.write(record, existing=existing)
        return _derive_status(self._root, change)

    def archive(self, change: str) -> None:
        """Wrap :func:`change_archive` so the class is the only seam for callers."""
        change_archive(self._root, change)


def _now_iso8601() -> str:
    """Return the current UTC timestamp in RFC 3339 / ISO 8601 form."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_scope_digest(root: Path, change: str, *, gate: str) -> str:
    """Return the gate-specific scope fingerprint, length-delimited and hashed.

    Implementation scope covers the complete PRD, applicable design,
    selected spec, effective risk, and the selected task *definition*
    digest. Continuation scope is the implementation scope plus the
    selected task *state* digest and the slice-validation bytes.

    The bytes are concatenated with length prefixes so a path/content
    boundary cannot collide and equality compares constant-time SHA-256
    hex strings.
    """
    change_dir = _change_dir(root, change)
    delivery = read_prd_delivery(change_dir / "prd.md")
    if delivery.mode != "sliced":
        raise ChangeStoreError("Scope fingerprinting requires a sliced PRD.")

    capability = _select_capability_for_gate(delivery, gate)
    spec_path = change_dir / f"specs/{capability.id}.md"

    parts: list[bytes] = []
    parts.append(_label_bytes("capability"))
    parts.append(capability.id.encode("utf-8"))
    parts.append(_label_bytes("gate"))
    parts.append(gate.encode("utf-8"))
    parts.append(_label_bytes("prd"))
    parts.append((change_dir / "prd.md").read_bytes() if (change_dir / "prd.md").is_file() else b"")
    parts.append(_label_bytes("risk"))
    parts.append(_risk_bytes(compute_effective_risk(capability)))

    design_bytes = _applicable_design_bytes(change_dir, capability)
    parts.append(_label_bytes("design"))
    parts.append(design_bytes)

    parts.append(_label_bytes("spec"))
    parts.append(spec_path.read_bytes() if spec_path.is_file() else b"")

    cap_state = task_capability_state(root, change, spec_path.relative_to(root).as_posix())
    parts.append(_label_bytes("task_definition_digest"))
    parts.append(cap_state.definitionDigest.encode("utf-8"))

    if gate == "continuation":
        parts.append(_label_bytes("task_state_digest"))
        parts.append(cap_state.stateDigest.encode("utf-8"))
        validation_path = change_dir / f"validations/{capability.id}.md"
        parts.append(_label_bytes("validation"))
        parts.append(validation_path.read_bytes() if validation_path.is_file() else b"")

    return hash_scope_digest(tuple(parts))


def _select_capability_for_gate(delivery: PrdDelivery, gate: str) -> Capability:
    """Return the capability the gate applies to.

    For task 4 the router always gates the first capability; task 5
    introduces continuation capability skipping. The shared invariant
    is that the approval scope covers exactly one capability, never
    arbitrary caller input.
    """
    if not delivery.capabilities:
        raise ChangeStoreError("Cannot approve without at least one capability.")
    return delivery.capabilities[0]


def _applicable_design_bytes(change_dir: Path, capability: Capability) -> bytes:
    """Read the change-wide or slice-scoped design bytes for the capability."""
    if capability.design == "change":
        design_file = change_dir / "design.md"
    elif capability.design == "slice":
        design_file = change_dir / "designs" / f"{capability.id}.md"
    else:
        return b""
    return design_file.read_bytes() if design_file.is_file() else b""


def _risk_bytes(risk: RiskAssessment) -> bytes:
    """Serialize a :class:`RiskAssessment` to bytes for the scope digest."""
    parts = [
        risk.declaredLevel.encode("utf-8"),
        risk.effectiveLevel.encode("utf-8"),
        risk.designScope.encode("utf-8"),
        b"\x00".join(reason.encode("utf-8") for reason in risk.reasons),
    ]
    return b"\x00".join(parts)


def _label_bytes(label: str) -> bytes:
    """Encode a digest segment label."""
    return label.encode("utf-8")


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
