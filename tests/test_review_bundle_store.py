"""Tests for the package-internal review bundle store.

The review bundle store is a closed-registry, package-internal helper
that owns the immutable-bundle primitives the new ``ReviewTransactionStore``
composes with. These tests pin:

1. The closed six-role registry of (kind, label) pairs.
2. Atomic sibling-rename publication and idempotent reuse.
3. Strict stable reads with symlink / FIFO / extra-child rejection.
4. Defense against malformed, missing, or path-traversing object IDs.
5. Public receipt dispatch remains closed to review kinds.

The tests use real temporary directories and the real filesystem
helpers; they do not mock the store, the records, or the receipts module.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import (
    CodecError,
    ReceiptStoreError,
    _ImmutableBundleStore,
    _ReviewBundleRole,
    _ReviewBundleStore,
)

# ---------------------------------------------------------------------------
# Fixed role/label pairs the closed registry must contain
# ---------------------------------------------------------------------------


_REVIEW_ROLES: tuple[tuple[str, str, str], ...] = (
    (
        "lens_selection",
        "review-lens-selections",
        "ai-harness/review-lens-selection/v1",
    ),
    (
        "review_transaction",
        "review-transactions",
        "ai-harness/review-transaction/v1",
    ),
    (
        "finding",
        "review-findings",
        "ai-harness/review-finding/v1",
    ),
    (
        "finding_transition",
        "review-finding-transitions",
        "ai-harness/review-finding-transition/v1",
    ),
    (
        "correction_fact",
        "review-correction-facts",
        "ai-harness/review-correction-fact/v1",
    ),
    (
        "transaction_root",
        "review-transaction-roots",
        "ai-harness/review-transaction-root/v1",
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
def bundle_store(change_root: Path) -> _ReviewBundleStore:
    """A review bundle store scoped to a temporary change root."""

    return _ReviewBundleStore(change_root / ".receipts")


@pytest.fixture
def plain_store(change_root: Path) -> _ImmutableBundleStore:
    """A raw immutable bundle store used to seed adversarial state."""

    return _ImmutableBundleStore(change_root / ".receipts")


# ---------------------------------------------------------------------------
# Closed registry tests
# ---------------------------------------------------------------------------


def test_review_bundle_role_enum_has_exactly_six_members() -> None:
    """The role enum has exactly the six closed storage roles."""

    members = tuple(_ReviewBundleRole)
    assert len(members) == 6
    assert {member.value for member in members} == {role for role, _, _ in _REVIEW_ROLES}


def test_review_bundle_store_registry_pairs_match_spec() -> None:
    """The private registry pins the six (kind, label) pairs the spec requires."""

    pair_by_role = {role: (kind, label) for role, kind, label in _REVIEW_ROLES}
    for role in _ReviewBundleRole:
        kind, label = _ReviewBundleStore._REGISTRY[role]
        assert kind == pair_by_role[role.value][0]
        assert label == pair_by_role[role.value][1]


def test_review_bundle_store_rejects_unknown_role_publish(
    bundle_store: _ReviewBundleStore,
) -> None:
    """Publishing with an unknown role raises a closed-registry error."""

    with pytest.raises(ReceiptStoreError):
        bundle_store.publish("not_a_role", CANONICAL_PAYLOAD)


def test_review_bundle_store_rejects_unknown_role_read(
    bundle_store: _ReviewBundleStore,
) -> None:
    """Reading with an unknown role raises a closed-registry error."""

    with pytest.raises(ReceiptStoreError):
        bundle_store.read("not_a_role", "sha256:" + "0" * 64)


def test_review_bundle_store_rejects_non_bytes_publish(
    bundle_store: _ReviewBundleStore,
) -> None:
    """Publishing non-bytes payloads raises a closed-registry error."""

    with pytest.raises(ReceiptStoreError):
        bundle_store.publish(_ReviewBundleRole.LENS_SELECTION, "not bytes")


# ---------------------------------------------------------------------------
# Atomic publication and idempotence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_name,kind,label", _REVIEW_ROLES)
def test_publish_writes_bundle_under_role_kind_and_label(
    bundle_store: _ReviewBundleStore,
    change_root: Path,
    role_name: str,
    kind: str,
    label: str,
) -> None:
    """Each role publishes under the fixed kind using a content-addressed bundle."""

    role = _ReviewBundleRole(role_name)
    object_id = bundle_store.publish(role, CANONICAL_PAYLOAD)

    assert object_id.startswith("sha256:")
    digest = object_id.removeprefix("sha256:")
    bundle = change_root / ".receipts" / kind / "sha256" / digest / "object.json"
    assert bundle.is_file()
    # Bytes are the canonical payload byte-for-byte.
    assert bundle.read_bytes() == CANONICAL_PAYLOAD


def test_publish_returns_typed_hash_under_role_label(
    bundle_store: _ReviewBundleStore,
) -> None:
    """The returned ID hashes the canonical bytes under the role's static label."""

    from ai_harness.modules.harness.receipts import typed_hash

    role = _ReviewBundleRole.FINDING
    expected = typed_hash("ai-harness/review-finding/v1", CANONICAL_PAYLOAD)
    assert bundle_store.publish(role, CANONICAL_PAYLOAD) == expected


def test_publish_is_idempotent_for_equal_bytes(
    bundle_store: _ReviewBundleStore,
) -> None:
    """Two publishes of equal bytes return the same ID without replacing data."""

    role = _ReviewBundleRole.FINDING
    first = bundle_store.publish(role, CANONICAL_PAYLOAD)
    second = bundle_store.publish(role, CANONICAL_PAYLOAD)
    assert first == second


def test_publish_rejects_conflicting_bytes_for_same_id(
    bundle_store: _ReviewBundleStore,
    change_root: Path,
) -> None:
    """Different bytes at the same content address surface as immutable conflict.

    A manually-injected final bundle whose bytes do not match the
    planned canonical payload must surface as a strict conflict during
    a publication that hits the same path. The same-id publish
    therefore refuses to overwrite the existing bytes.
    """

    role = _ReviewBundleRole.FINDING
    expected_id = bundle_store.publish(role, CANONICAL_PAYLOAD)

    conflicting = json.dumps(
        {"value": 2},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = expected_id.removeprefix("sha256:")
    bundle = change_root / ".receipts" / "review-findings" / "sha256" / digest
    (bundle / "object.json").write_bytes(conflicting)

    with pytest.raises(ReceiptStoreError):
        bundle_store.publish(role, CANONICAL_PAYLOAD)


def test_publish_leaves_no_sibling_temporary_after_success(
    bundle_store: _ReviewBundleStore,
    change_root: Path,
) -> None:
    """A successful publication leaves only the final bundle under its parent."""

    role = _ReviewBundleRole.LENS_SELECTION
    object_id = bundle_store.publish(role, CANONICAL_PAYLOAD)
    parent = change_root / ".receipts" / "review-lens-selections" / "sha256"
    entries = list(parent.iterdir())
    assert len(entries) == 1
    assert entries[0].name == object_id.removeprefix("sha256:")


# ---------------------------------------------------------------------------
# Strict stable readback
# ---------------------------------------------------------------------------


def test_read_returns_published_bytes(bundle_store: _ReviewBundleStore) -> None:
    """A successful read returns the exact bytes that were published."""

    role = _ReviewBundleRole.REVIEW_TRANSACTION
    object_id = bundle_store.publish(role, CANONICAL_PAYLOAD)
    assert bundle_store.read(role, object_id) == CANONICAL_PAYLOAD


def test_read_rejects_malformed_object_id(bundle_store: _ReviewBundleStore) -> None:
    """An object ID with the wrong shape fails closed before any read.

    The bundle primitive reuses the receipt codec's typed-id check,
    which raises a :class:`CodecError` for malformed wire shapes. The
    downstream public review seam translates this error into a
    ``review-storage.invalid`` failure; at the bundle primitive
    boundary, the codec-level failure is the documented interface.
    """

    role = _ReviewBundleRole.FINDING
    bundle_store.publish(role, CANONICAL_PAYLOAD)
    with pytest.raises(CodecError):
        bundle_store.read(role, "sha256:UPPERCASE")
    with pytest.raises(CodecError):
        bundle_store.read(role, "sha256:" + "0" * 63)


def test_read_rejects_path_traversal_in_object_id(
    bundle_store: _ReviewBundleStore,
) -> None:
    """An object ID with separators cannot escape the receipts directory.

    The traversal shape fails the wire-format check at the primitive
    boundary; the shape check is what guarantees no path component
    traversal could reach the filesystem even if the format check were
    weakened in the future.
    """

    role = _ReviewBundleRole.FINDING
    bundle_store.publish(role, CANONICAL_PAYLOAD)
    traversal = "sha256:" + ("../" * 10) + "escape"
    with pytest.raises(CodecError):
        bundle_store.read(role, traversal)


def test_read_rejects_missing_bundle(bundle_store: _ReviewBundleStore) -> None:
    """Reading a never-published ID reports an absent bundle."""

    with pytest.raises(ReceiptStoreError):
        bundle_store.read(
            _ReviewBundleRole.FINDING,
            "sha256:" + "0" * 64,
        )


def test_read_rejects_symlinked_object_file(
    bundle_store: _ReviewBundleStore,
    change_root: Path,
) -> None:
    """A symlinked ``object.json`` is detected and rejected without a follow read."""

    role = _ReviewBundleRole.LENS_SELECTION
    object_id = bundle_store.publish(role, CANONICAL_PAYLOAD)
    digest = object_id.removeprefix("sha256:")
    bundle = change_root / ".receipts" / "review-lens-selections" / "sha256" / digest
    real = bundle.parent / "real-target"
    real.mkdir()
    (real / "object.json").write_text(
        json.dumps({"value": 1}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    target = bundle / "object.json"
    target.unlink()
    target.symlink_to(real / "object.json")

    with pytest.raises(ReceiptStoreError):
        bundle_store.read(role, object_id)


def test_read_rejects_fifo_object(
    bundle_store: _ReviewBundleStore,
    change_root: Path,
) -> None:
    """A FIFO replacement of ``object.json`` is detected and rejected."""

    role = _ReviewBundleRole.LENS_SELECTION
    object_id = bundle_store.publish(role, CANONICAL_PAYLOAD)
    digest = object_id.removeprefix("sha256:")
    bundle = change_root / ".receipts" / "review-lens-selections" / "sha256" / digest
    (bundle / "object.json").unlink()
    os.mkfifo(bundle / "object.json")

    with pytest.raises(ReceiptStoreError):
        bundle_store.read(role, object_id)


def test_read_rejects_extra_child_in_bundle(
    bundle_store: _ReviewBundleStore,
    change_root: Path,
) -> None:
    """An additional file under the bundle directory fails the topology check."""

    role = _ReviewBundleRole.LENS_SELECTION
    object_id = bundle_store.publish(role, CANONICAL_PAYLOAD)
    digest = object_id.removeprefix("sha256:")
    bundle = change_root / ".receipts" / "review-lens-selections" / "sha256" / digest
    (bundle / "stray.txt").write_text("extra", encoding="utf-8")

    with pytest.raises(ReceiptStoreError):
        bundle_store.read(role, object_id)


def test_read_rejects_digest_mismatch(
    bundle_store: _ReviewBundleStore,
    change_root: Path,
) -> None:
    """Bundle bytes whose recomputed digest differs are rejected as invalid."""

    role = _ReviewBundleRole.LENS_SELECTION
    object_id = bundle_store.publish(role, CANONICAL_PAYLOAD)
    digest = object_id.removeprefix("sha256:")
    bundle = change_root / ".receipts" / "review-lens-selections" / "sha256" / digest
    (bundle / "object.json").write_text(
        json.dumps({"value": 99}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ReceiptStoreError):
        bundle_store.read(role, object_id)


def test_publish_recovers_after_manual_idempotent_install(
    plain_store: _ImmutableBundleStore,
    bundle_store: _ReviewBundleStore,
    change_root: Path,
) -> None:
    """A pre-existing final bundle with identical bytes is treated as idempotent success.

    The primitive bypasses graph publication, which is exactly the test:
    the bundle helper alone does not validate a graph. Aggregate graph
    validation is the responsibility of the public ``ReviewTransactionStore``.
    """

    role = _ReviewBundleRole.LENS_SELECTION
    label = "ai-harness/review-lens-selection/v1"
    kind = "review-lens-selections"
    expected_id = plain_store.publish(kind=kind, label=label, canonical_bytes=CANONICAL_PAYLOAD)
    digest = expected_id.removeprefix("sha256:")
    bundle = change_root / ".receipts" / kind / "sha256" / digest
    assert bundle.is_dir()

    # The review store sees the existing bundle and treats the publish
    # as idempotent, returning the same ID.
    actual_id = bundle_store.publish(role, CANONICAL_PAYLOAD)
    assert actual_id == expected_id
