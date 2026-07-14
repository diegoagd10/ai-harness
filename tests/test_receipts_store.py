"""Tests for the immutable receipt object store.

These tests exercise ``publish_object`` and ``read_object`` against
real temporary directories. They verify atomic sibling publication,
strict regular-file reads, immutable reuse, symlink rejection, and
the failure modes the design requires to fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import (
    ReceiptStoreError,
    typed_hash,
    encode_canonical,
    ReceiptObjectStore,
)


@pytest.fixture
def store(tmp_path: Path) -> ReceiptObjectStore:
    return ReceiptObjectStore(tmp_path / ".receipts")


def test_publish_object_writes_canonical_json_and_returns_id(store: ReceiptObjectStore, tmp_path: Path) -> None:
    """A well-formed payload lands in the bundle directory as canonical JSON."""
    payload = {"schema_name": "ai-harness.example", "schema_version": 1, "value": 7}

    object_id = store.publish_object("runs", payload)

    assert object_id.startswith("sha256:")
    base = tmp_path / ".receipts" / "runs" / "sha256" / object_id.removeprefix("sha256:")
    bundle = base / "object.json"
    assert bundle.is_file()
    written = json.loads(bundle.read_text(encoding="utf-8"))
    # Canonical encoding: keys sorted, no insignificant whitespace.
    assert json.dumps(written, sort_keys=True, separators=(",", ":")) == bundle.read_text(encoding="utf-8").rstrip("\n")


def test_publish_object_is_atomic_via_sibling_rename(store: ReceiptObjectStore, tmp_path: Path) -> None:
    """Publication leaves either the final bundle or only an orphan temp directory."""
    payload = {"schema_name": "ai-harness.example", "schema_version": 1, "value": 1}
    object_id = store.publish_object("runs", payload)
    base = tmp_path / ".receipts" / "runs" / "sha256" / object_id.removeprefix("sha256:")

    # Final bundle exists, no tmp child left behind.
    assert (base / "object.json").is_file()
    assert not (base / "tmp").exists()
    # No sibling temp file leaked to the parent.
    parent = tmp_path / ".receipts" / "runs" / "sha256"
    leftover = [entry for entry in parent.iterdir() if entry.name != object_id.removeprefix("sha256:")]
    assert not leftover


def test_publish_object_reuses_existing_object_when_idempotent(store: ReceiptObjectStore) -> None:
    """A second publish of the same payload reuses the same bundle."""
    payload = {"schema_name": "ai-harness.example", "schema_version": 1, "value": 1}
    first = store.publish_object("runs", payload)
    second = store.publish_object("runs", payload)

    assert first == second


def test_publish_object_rejects_conflicting_payload_for_existing_id(store: ReceiptObjectStore) -> None:
    """Two different payloads at the same ID surface a stored corruption."""
    # The ID is deterministic; a colliding payload is corruption.
    payload_a = {"schema_name": "ai-harness.example", "schema_version": 1, "value": 1}
    object_id = store.publish_object("runs", payload_a)

    # Forcibly rewrite the bundle to a *different* canonical encoding.
    base = store.bundle_path("runs", object_id)
    base.mkdir(parents=True, exist_ok=True)
    (base / "object.json").write_text(
        json.dumps({"schema_name": "ai-harness.example", "schema_version": 1, "value": 2}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ReceiptStoreError):
        store.publish_object("runs", payload_a)


def test_read_object_rejects_missing_bundle(store: ReceiptObjectStore) -> None:
    with pytest.raises(ReceiptStoreError):
        store.read_object("runs", "sha256:" + "0" * 64)


def test_read_object_rejects_symlinked_bundle(store: ReceiptObjectStore, tmp_path: Path) -> None:
    object_id = store.publish_object("runs", {"schema_name": "ai-harness.example", "schema_version": 1, "value": 1})

    base = tmp_path / ".receipts" / "runs" / "sha256" / object_id.removeprefix("sha256:")
    real_path = base.parent / "real-target"
    real_path.mkdir()
    (real_path / "object.json").write_text(
        json.dumps({"value": 1}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    target = base / "object.json"
    target.unlink()
    target.symlink_to(real_path / "object.json")

    with pytest.raises(ReceiptStoreError):
        store.read_object("runs", object_id)


def test_read_object_rejects_non_regular_files(store: ReceiptObjectStore, tmp_path: Path) -> None:
    object_id = store.publish_object("runs", {"schema_name": "ai-harness.example", "schema_version": 1, "value": 1})
    base = tmp_path / ".receipts" / "runs" / "sha256" / object_id.removeprefix("sha256:")
    (base / "object.json").unlink()
    fifo_path = base / "object.json"
    import os

    os.mkfifo(fifo_path)

    with pytest.raises(ReceiptStoreError):
        store.read_object("runs", object_id)


def test_read_object_rejects_digest_mismatch(store: ReceiptObjectStore, tmp_path: Path) -> None:
    object_id = store.publish_object("runs", {"schema_name": "ai-harness.example", "schema_version": 1, "value": 1})
    base = tmp_path / ".receipts" / "runs" / "sha256" / object_id.removeprefix("sha256:")
    # Replace the bytes with a payload whose typed hash would be different.
    (base / "object.json").write_text(
        json.dumps({"value": 99}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ReceiptStoreError):
        store.read_object("runs", object_id)


def test_read_object_rejects_duplicate_extra_files_in_bundle(store: ReceiptObjectStore, tmp_path: Path) -> None:
    object_id = store.publish_object("runs", {"schema_name": "ai-harness.example", "schema_version": 1, "value": 1})
    base = tmp_path / ".receipts" / "runs" / "sha256" / object_id.removeprefix("sha256:")
    # Add an extra unrelated file inside the bundle directory.
    (base / "stray.txt").write_text("extra", encoding="utf-8")

    with pytest.raises(ReceiptStoreError):
        store.read_object("runs", object_id)


def test_publish_receipt_pointer_replaces_atomically(store: ReceiptObjectStore) -> None:
    object_id = store.publish_object("receipts", {"value": "first"})
    object_id_2 = store.publish_object("receipts", {"value": "second"})

    store.replace_current_pointer(object_id)
    pointer_path = store.receipts_dir / "current"
    data = json.loads(pointer_path.read_text(encoding="utf-8"))
    assert data["receipt_id"] == object_id
    assert data["schema_name"] == "ai-harness.receipt-pointer"

    store.replace_current_pointer(object_id_2)
    data = json.loads(pointer_path.read_text(encoding="utf-8"))
    assert data["receipt_id"] == object_id_2


def test_publish_receipt_pointer_rejects_malformed_pointer_read(store: ReceiptObjectStore, tmp_path: Path) -> None:
    (tmp_path / ".receipts").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".receipts" / "current").write_text("not json\n", encoding="utf-8")
    with pytest.raises(ReceiptStoreError):
        store.read_current_pointer()


def test_publish_receipt_pointer_rejects_unknown_schema(store: ReceiptObjectStore, tmp_path: Path) -> None:
    (tmp_path / ".receipts").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".receipts" / "current").write_text(
        json.dumps({"receipt_id": "sha256:" + "0" * 64, "schema_name": "wrong", "schema_version": 1}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ReceiptStoreError):
        store.read_current_pointer()


def test_bundled_evidence_round_trip(store: ReceiptObjectStore) -> None:
    """Run bundle: run.json + named evidence files with matching digests."""

    object_id = store.publish_run_bundle(
        run_payload={"schema_name": "ai-harness.gate-run", "schema_version": 1, "value": 1},
        evidence={
            "0000.stdout": (b"hello\n", "sha256:placeholder"),
            "0000.stderr": (b"", "sha256:placeholder"),
        },
    )

    raw = store.read_run_payload(object_id)
    assert raw["value"] == 1

    evidence = store.read_run_evidence(object_id, "0000.stdout")
    assert evidence == b"hello\n"

    empty = store.read_run_evidence(object_id, "0000.stderr")
    assert empty == b""
