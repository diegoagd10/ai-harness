# pylint: disable=duplicate-code
"""Tests for the package-internal checkpoint bundle storage helper.

The checkpoint bundle store is a closed-registry, package-internal helper
that owns the immutable-bundle primitives the new
:class:`ai_harness.modules.harness.review_transaction_checkpoints.ReviewTransactionCheckpointStore`
composes with. These tests pin:

1. The closed two-role registry of ``(kind, label)`` pairs.
2. Atomic sibling-rename publication and idempotent reuse.
3. Strict stable reads with symlink / FIFO / extra-child rejection.
4. Defense against malformed, missing, or path-traversing object IDs.
5. The archived ``_ReviewBundleStore`` six-role registry and public
   ``ReceiptObjectStore`` API are unchanged.

The tests use real temporary directories and the real filesystem
helpers; they do not mock the store or the receipts module.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import (
    ReceiptStoreError,
    _CheckpointBundleRole,
    _CheckpointBundleStore,
    _ImmutableBundleStore,
    _ReviewBundleRole,
    _ReviewBundleStore,
    typed_hash,
)

# ---------------------------------------------------------------------------
# Fixed role/label pairs the closed two-role registry must contain
# ---------------------------------------------------------------------------


_CHECKPOINT_ROLES: tuple[tuple[str, str, str], ...] = (
    (
        "checkpoint",
        "review-transaction-checkpoints",
        "ai-harness/review-transaction-checkpoint/v1",
    ),
    (
        "correction_evidence",
        "review-correction-evidence",
        "ai-harness/review-correction-evidence/v1",
    ),
)


CANONICAL_PAYLOAD: bytes = json.dumps(
    {"value": 1},
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def change_root(tmp_path: Path) -> Path:
    """Return a hermetic test-owned change root."""

    return tmp_path


@pytest.fixture
def checkpoint_store(change_root: Path) -> _CheckpointBundleStore:
    """A checkpoint bundle store scoped to a temporary change root."""

    return _CheckpointBundleStore(change_root / ".receipts")


# ---------------------------------------------------------------------------
# Closed two-role registry tests
# ---------------------------------------------------------------------------


def test_checkpoint_bundle_role_enum_has_exactly_two_members() -> None:
    """The role enum has exactly the two closed storage roles."""

    members = tuple(_CheckpointBundleRole)
    assert len(members) == 2
    assert {member.value for member in members} == {role for role, _, _ in _CHECKPOINT_ROLES}


def test_checkpoint_bundle_store_registry_pairs_match_spec() -> None:
    """The private registry pins the two (kind, label) pairs the spec requires."""

    pair_by_role = {role: (kind, label) for role, kind, label in _CHECKPOINT_ROLES}
    for role in _CheckpointBundleRole:
        kind, label = _CheckpointBundleStore._REGISTRY[role]
        assert kind == pair_by_role[role.value][0]
        assert label == pair_by_role[role.value][1]


def test_checkpoint_bundle_store_registry_is_disjoint_from_review_registry() -> None:
    """The checkpoint registry owns no review-graph role or label."""

    checkpoint_kinds = {kind for _, kind, _ in _CHECKPOINT_ROLES}
    checkpoint_labels = {label for _, _, label in _CHECKPOINT_ROLES}
    for role in _ReviewBundleRole:
        review_kind, review_label = _ReviewBundleStore._REGISTRY[role]
        assert review_kind not in checkpoint_kinds
        assert review_label not in checkpoint_labels


def test_checkpoint_bundle_store_rejects_unknown_role_publish(
    checkpoint_store: _CheckpointBundleStore,
) -> None:
    """Publishing with an unknown role raises a closed-registry error."""

    with pytest.raises(ReceiptStoreError):
        checkpoint_store.publish("not_a_role", CANONICAL_PAYLOAD)


def test_checkpoint_bundle_store_rejects_unknown_role_read(
    checkpoint_store: _CheckpointBundleStore,
) -> None:
    """Reading with an unknown role raises a closed-registry error."""

    with pytest.raises(ReceiptStoreError):
        checkpoint_store.read("not_a_role", "sha256:" + "0" * 64)


def test_checkpoint_bundle_store_rejects_non_bytes_publish(
    checkpoint_store: _CheckpointBundleStore,
) -> None:
    """Publishing non-bytes payloads raises a closed-registry error."""

    with pytest.raises(ReceiptStoreError):
        checkpoint_store.publish(_CheckpointBundleRole.CHECKPOINT, "not bytes")


# ---------------------------------------------------------------------------
# Atomic publication and idempotence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_name,kind,label", _CHECKPOINT_ROLES)
def test_publish_writes_bundle_under_role_kind_and_label(
    checkpoint_store: _CheckpointBundleStore,
    change_root: Path,
    role_name: str,
    kind: str,
    label: str,
) -> None:
    """Each role publishes under the fixed kind using a content-addressed bundle."""

    role = _CheckpointBundleRole(role_name)
    object_id = checkpoint_store.publish(role, CANONICAL_PAYLOAD)

    assert object_id.startswith("sha256:")
    digest = object_id.removeprefix("sha256:")
    bundle = change_root / ".receipts" / kind / "sha256" / digest / "object.json"
    assert bundle.is_file()
    # Bytes are the canonical payload byte-for-byte.
    assert bundle.read_bytes() == CANONICAL_PAYLOAD


def test_publish_returns_typed_hash_under_role_label(
    checkpoint_store: _CheckpointBundleStore,
) -> None:
    """The returned ID hashes the canonical bytes under the role's static label."""

    role = _CheckpointBundleRole.CHECKPOINT
    expected = typed_hash("ai-harness/review-transaction-checkpoint/v1", CANONICAL_PAYLOAD)
    assert checkpoint_store.publish(role, CANONICAL_PAYLOAD) == expected


def test_publish_is_idempotent_for_equal_bytes(
    checkpoint_store: _CheckpointBundleStore,
) -> None:
    """Two publishes of equal bytes return the same ID without replacing data."""

    role = _CheckpointBundleRole.CORRECTION_EVIDENCE
    first = checkpoint_store.publish(role, CANONICAL_PAYLOAD)
    second = checkpoint_store.publish(role, CANONICAL_PAYLOAD)
    assert first == second


def test_publish_rejects_conflicting_bytes_for_same_id(
    checkpoint_store: _CheckpointBundleStore,
    change_root: Path,
) -> None:
    """Different bytes at the same content address surface as immutable conflict."""

    role = _CheckpointBundleRole.CHECKPOINT
    expected_id = checkpoint_store.publish(role, CANONICAL_PAYLOAD)

    conflicting = json.dumps(
        {"value": 2},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = expected_id.removeprefix("sha256:")
    bundle = change_root / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    (bundle / "object.json").write_bytes(conflicting)

    with pytest.raises(ReceiptStoreError):
        checkpoint_store.publish(role, CANONICAL_PAYLOAD)


def test_publish_leaves_no_sibling_temporary_after_success(
    checkpoint_store: _CheckpointBundleStore,
    change_root: Path,
) -> None:
    """A successful publication leaves only the final bundle under its parent."""

    role = _CheckpointBundleRole.CHECKPOINT
    object_id = checkpoint_store.publish(role, CANONICAL_PAYLOAD)
    parent = change_root / ".receipts" / "review-transaction-checkpoints" / "sha256"
    entries = list(parent.iterdir())
    assert len(entries) == 1
    assert entries[0].name == object_id.removeprefix("sha256:")


# ---------------------------------------------------------------------------
# Strict stable readback
# ---------------------------------------------------------------------------


def test_read_returns_published_bytes(checkpoint_store: _CheckpointBundleStore) -> None:
    """A successful read returns the exact bytes that were published."""

    role = _CheckpointBundleRole.CHECKPOINT
    object_id = checkpoint_store.publish(role, CANONICAL_PAYLOAD)
    assert checkpoint_store.read(role, object_id) == CANONICAL_PAYLOAD


def test_read_rejects_malformed_object_id(checkpoint_store: _CheckpointBundleStore) -> None:
    """An object ID with the wrong shape fails closed before any read."""

    role = _CheckpointBundleRole.CHECKPOINT
    checkpoint_store.publish(role, CANONICAL_PAYLOAD)
    from ai_harness.modules.harness.receipts import CodecError

    with pytest.raises(CodecError):
        checkpoint_store.read(role, "sha256:UPPERCASE")
    with pytest.raises(CodecError):
        checkpoint_store.read(role, "sha256:" + "0" * 63)


def test_read_rejects_path_traversal_in_object_id(
    checkpoint_store: _CheckpointBundleStore,
) -> None:
    """An object ID with separators cannot escape the receipts directory."""

    role = _CheckpointBundleRole.CHECKPOINT
    checkpoint_store.publish(role, CANONICAL_PAYLOAD)
    traversal = "sha256:" + ("../" * 10) + "escape"
    from ai_harness.modules.harness.receipts import CodecError

    with pytest.raises(CodecError):
        checkpoint_store.read(role, traversal)


def test_read_rejects_missing_bundle(checkpoint_store: _CheckpointBundleStore) -> None:
    """Reading a never-published ID reports an absent bundle."""

    with pytest.raises(ReceiptStoreError):
        checkpoint_store.read(
            _CheckpointBundleRole.CHECKPOINT,
            "sha256:" + "0" * 64,
        )


def test_read_rejects_symlinked_object_file(
    checkpoint_store: _CheckpointBundleStore,
    change_root: Path,
) -> None:
    """A symlink replacing ``object.json`` is rejected without following the link."""

    import shutil

    role = _CheckpointBundleRole.CHECKPOINT
    object_id = checkpoint_store.publish(role, CANONICAL_PAYLOAD)
    digest = object_id.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    real = target.parent / "real-target"
    real.mkdir()
    (real / "object.json").write_text(
        json.dumps({"replacement": True}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(target)
    target.symlink_to(real)

    with pytest.raises(ReceiptStoreError):
        checkpoint_store.read(role, object_id)


def test_read_rejects_fifo_object(
    checkpoint_store: _CheckpointBundleStore,
    change_root: Path,
) -> None:
    """A FIFO replacing ``object.json`` is detected and rejected."""

    import os

    role = _CheckpointBundleRole.CHECKPOINT
    object_id = checkpoint_store.publish(role, CANONICAL_PAYLOAD)
    digest = object_id.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest / "object.json"
    target.unlink()
    os.mkfifo(target)

    with pytest.raises(ReceiptStoreError):
        checkpoint_store.read(role, object_id)


def test_read_rejects_extra_child_in_bundle(
    checkpoint_store: _CheckpointBundleStore,
    change_root: Path,
) -> None:
    """Adding a stray file under a bundle directory is rejected at topology check."""

    role = _CheckpointBundleRole.CHECKPOINT
    object_id = checkpoint_store.publish(role, CANONICAL_PAYLOAD)
    digest = object_id.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    (target / "stray.txt").write_text("extra content", encoding="utf-8")

    with pytest.raises(ReceiptStoreError):
        checkpoint_store.read(role, object_id)


def test_read_rejects_digest_mismatch(
    checkpoint_store: _CheckpointBundleStore,
    change_root: Path,
) -> None:
    """A bundle whose bytes are tampered surfaces as invalid."""

    role = _CheckpointBundleRole.CHECKPOINT
    object_id = checkpoint_store.publish(role, CANONICAL_PAYLOAD)
    digest = object_id.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest / "object.json"
    target.write_bytes(b'{"value":99}')

    with pytest.raises(ReceiptStoreError):
        checkpoint_store.read(role, object_id)


# ---------------------------------------------------------------------------
# Separation from the archived review-graph registry
# ---------------------------------------------------------------------------


def test_review_bundle_role_enum_still_has_exactly_six_members() -> None:
    """The archived review-graph role enum remains a closed six-role registry."""

    members = tuple(_ReviewBundleRole)
    assert len(members) == 6
    expected = frozenset(
        {
            "lens_selection",
            "review_transaction",
            "finding",
            "finding_transition",
            "correction_fact",
            "transaction_root",
        }
    )
    assert {member.value for member in members} == expected


def test_review_bundle_store_registry_pairs_unchanged() -> None:
    """The archived review-graph registry pins the six (kind, label) pairs unchanged."""

    expected_pairs = {
        "lens_selection": ("review-lens-selections", "ai-harness/review-lens-selection/v1"),
        "review_transaction": ("review-transactions", "ai-harness/review-transaction/v1"),
        "finding": ("review-findings", "ai-harness/review-finding/v1"),
        "finding_transition": (
            "review-finding-transitions",
            "ai-harness/review-finding-transition/v1",
        ),
        "correction_fact": ("review-correction-facts", "ai-harness/review-correction-fact/v1"),
        "transaction_root": (
            "review-transaction-roots",
            "ai-harness/review-transaction-root/v1",
        ),
    }
    for role in _ReviewBundleRole:
        kind, label = _ReviewBundleStore._REGISTRY[role]
        assert (kind, label) == expected_pairs[role.value]


def test_public_receipt_object_store_remains_closed_to_checkpoint_kinds() -> None:
    """The public ``ReceiptObjectStore`` has no checkpoint or evidence kind option.

    The public receipt dispatch exposes exactly ``runs`` and
    ``receipts`` as kind tokens. No checkpoint or evidence kind is
    added there.
    """

    from ai_harness.modules.harness.receipts import (
        RECEIPT_OBJECT_KIND_RECEIPTS,
        RECEIPT_OBJECT_KIND_RUNS,
    )

    public_kinds = {RECEIPT_OBJECT_KIND_RUNS, RECEIPT_OBJECT_KIND_RECEIPTS}
    checkpoint_kinds = {kind for _, kind, _ in _CHECKPOINT_ROLES}
    assert public_kinds.isdisjoint(checkpoint_kinds)


def test_checkpoint_store_composes_immutable_bundle_store_not_subclass(
    checkpoint_store: _CheckpointBundleStore,
) -> None:
    """The checkpoint store uses composition, not inheritance.

    Composition lets the checkpoint store share hardened bundle
    mechanics while keeping the closed two-role registry and public
    surface separate from the archived six-role registry.
    """

    assert isinstance(checkpoint_store.bundles, _ImmutableBundleStore)
    # Explicit type identity assertion — the checkpoint store does not
    # claim to be an ``_ImmutableBundleStore`` subclass.
    assert type(checkpoint_store) is not _ImmutableBundleStore
