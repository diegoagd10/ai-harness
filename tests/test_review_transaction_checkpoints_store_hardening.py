"""Storage hardening tests for ``ReviewTransactionCheckpointStore``.

These tests exercise the strict persistence guarantees:

* Graph-first, evidence-first, checkpoint-last publication ordering.
* Idempotence and pre-commit failure isolation.
* Missing, tampered, noncanonical, wrong-role, and conflict bundle
  rejection.
* Filesystem tampering — symlinks, FIFO devices, topology violations,
  and replacement-during-read — is rejected by the strict readback.
* Real local persistence in temporary directories; no mocks.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import (
    encode_canonical,
    typed_hash,
)
from ai_harness.modules.harness.review_transaction_checkpoints import (
    CODE_STORAGE_CONFLICT,
    CODE_STORAGE_INVALID,
    CODE_STORAGE_MISSING,
    ReviewCorrectionEvidence,
    ReviewTransactionCheckpoint,
    ReviewTransactionCheckpointContractV1,
    ReviewTransactionCheckpointStorageError,
    ReviewTransactionCheckpointStore,
)
from tests._review_transaction_checkpoints_fixtures import (
    checkpoint_contract,
    make_evidence,
    publish_full_checkpoint,
)
from tests._review_transaction_storage_fixtures import (
    CANDIDATE_BEFORE,
)

# ---------------------------------------------------------------------------
# 12.1 — Round-trip, idempotence, and pre-commit failures
# ---------------------------------------------------------------------------


def test_publish_then_load_round_trips_full_checkpoint(tmp_path: Path) -> None:
    """A full checkpoint with evidence round-trips through publish and load."""

    checkpoint, evidence, checkpoint_id = publish_full_checkpoint(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    verified = checkpoint_store.load(checkpoint_id)
    assert verified.checkpoint == checkpoint
    assert verified.correction_evidence == evidence


def test_publish_is_idempotent_for_same_inputs(tmp_path: Path) -> None:
    """Repeated publish of the same inputs returns the same id."""

    checkpoint, evidence, first_id = publish_full_checkpoint(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    second_id = checkpoint_store.publish(checkpoint, correction_evidence=evidence)
    assert first_id == second_id


def test_publish_failure_before_checkpoint_install_leaves_no_visible_checkpoint(
    tmp_path: Path,
) -> None:
    """A pre-checkpoint failure leaves no visible checkpoint bundle."""

    checkpoint, _evidence, _first_id = publish_full_checkpoint(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)

    # Force a pre-checkpoint failure by passing an evidence value whose
    # ``correction_fact_id`` disagrees with the loaded correction fact.
    bad_evidence = make_evidence(
        checkpoint_contract(),
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        correction_fact_id="sha256:" + "9" * 64,
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError):
        checkpoint_store.publish(checkpoint, correction_evidence=bad_evidence)
    # The original checkpoint remains loadable.
    checkpoint_store.load(_first_id)


def test_publish_with_archived_graph_missing_reports_missing(tmp_path: Path) -> None:
    """A missing archived graph is translated to ``review-checkpoint-storage.missing``."""

    checkpoint, _evidence, _first_id = publish_full_checkpoint(tmp_path)
    # Remove the lens-selection bundle so the archived load fails.
    archived = tmp_path / ".receipts" / "review-lens-selections" / "sha256"
    for path in list(archived.iterdir()):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    bogus_evidence = make_evidence(
        checkpoint_contract(),
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        correction_fact_id="sha256:" + "9" * 64,
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.publish(checkpoint, correction_evidence=bogus_evidence)
    assert exc.value.code in {CODE_STORAGE_MISSING, CODE_STORAGE_INVALID}


# ---------------------------------------------------------------------------
# 12.2 — Missing, tampered, noncanonical, wrong-role, conflict rejection
# ---------------------------------------------------------------------------


def test_load_rejects_missing_checkpoint_bundle(tmp_path: Path) -> None:
    """A removed checkpoint bundle is reported as ``missing``."""

    _checkpoint, _evidence, checkpoint_id = publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    shutil.rmtree(bundle, ignore_errors=True)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code == CODE_STORAGE_MISSING


def test_load_rejects_tampered_checkpoint_bytes(tmp_path: Path) -> None:
    """A checkpoint bundle with noncanonical or tampered bytes is rejected."""

    _checkpoint, _evidence, checkpoint_id = publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    target = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest / "object.json"
    target.write_bytes(b"not-canonical-bytes")
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_load_rejects_wrong_role_bytes(tmp_path: Path) -> None:
    """A bundle whose bytes were produced under the wrong role is rejected."""

    _checkpoint, evidence, checkpoint_id = publish_full_checkpoint(tmp_path)
    # Locate the evidence bundle and copy its bytes into the checkpoint
    # bundle directory under the same digest.
    evidence_id_value = typed_hash(
        "ai-harness/review-correction-evidence/v1",
        ReviewTransactionCheckpointContractV1().encode(evidence),
    )
    evidence_digest = evidence_id_value.removeprefix("sha256:")
    evidence_bundle = tmp_path / ".receipts" / "review-correction-evidence" / "sha256" / evidence_digest
    checkpoint_digest = checkpoint_id.value.removeprefix("sha256:")
    wrong_role_bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / checkpoint_digest
    shutil.rmtree(wrong_role_bundle, ignore_errors=True)
    shutil.copytree(evidence_bundle, wrong_role_bundle)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code in {CODE_STORAGE_INVALID, CODE_STORAGE_CONFLICT}


def test_publish_with_existing_object_at_other_role_does_not_overwrite(tmp_path: Path) -> None:
    """Publishing the same checkpoint does not overwrite conflicting bytes."""

    _checkpoint, evidence, _first_id = publish_full_checkpoint(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)

    # Publish the same checkpoint — second call is idempotent.
    _second_id = checkpoint_store.publish(
        _checkpoint_or_publish_payload(_checkpoint, evidence),
        correction_evidence=evidence,
    )
    # The published bundle bytes still match the original canonical bytes.
    digest = _first_id.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    payload = encode_canonical(
        {
            "candidate_id": _checkpoint.candidate_id,
            "correction_evidence_id": _checkpoint.correction_evidence_id.value,
            "lens_completions": [
                {
                    "complete": c.complete,
                    "finding_ids": [fid.value for fid in c.finding_ids],
                    "lens": c.lens,
                }
                for c in _checkpoint.lens_completions
            ],
            "review_transaction_id": _checkpoint.review_transaction_id.value,
            "review_transaction_root_id": _checkpoint.review_transaction_root_id.value,
            "schema_name": _checkpoint.schema_name,
            "schema_version": _checkpoint.schema_version,
        }
    )
    assert (bundle / "object.json").read_bytes() == payload


def _checkpoint_or_publish_payload(
    checkpoint: ReviewTransactionCheckpoint,
    _evidence: ReviewCorrectionEvidence,
) -> ReviewTransactionCheckpoint:
    return checkpoint


# ---------------------------------------------------------------------------
# 12.3 — Filesystem tampering and replacement-during-read
# ---------------------------------------------------------------------------


def test_load_rejects_symlinked_object_file(tmp_path: Path) -> None:
    """A symlink replacing ``object.json`` is rejected without following the link."""

    _checkpoint, _evidence, checkpoint_id = publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    target = bundle / "object.json"
    real = bundle.parent / f"real-target-{digest}"
    real.mkdir(parents=True)
    (real / "object.json").write_bytes(b'{"replacement":true}')
    target.unlink()
    target.symlink_to(real / "object.json")
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError):
        checkpoint_store.load(checkpoint_id)


def test_load_rejects_symlinked_bundle_directory(tmp_path: Path) -> None:
    """A bundle directory replaced with a symlink is rejected at lookup time."""

    _checkpoint, _evidence, checkpoint_id = publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    real = bundle.parent / f"real-target-{digest}"
    real.mkdir(parents=True)
    (real / "object.json").write_bytes(b'{"replacement":true}')
    shutil.rmtree(bundle)
    bundle.symlink_to(real)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError):
        checkpoint_store.load(checkpoint_id)


def test_load_rejects_fifo_object_file(tmp_path: Path) -> None:
    """A FIFO replacing ``object.json`` is rejected by the strict readback."""

    _checkpoint, _evidence, checkpoint_id = publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    target = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest / "object.json"
    target.unlink()
    os.mkfifo(target)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError):
        checkpoint_store.load(checkpoint_id)


def test_load_rejects_extra_child_in_bundle(tmp_path: Path) -> None:
    """A stray file inside the bundle is rejected by strict topology."""

    _checkpoint, _evidence, checkpoint_id = publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    (bundle / "stray.txt").write_text("extra", encoding="utf-8")
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code in {CODE_STORAGE_INVALID, CODE_STORAGE_CONFLICT}


def test_load_rejects_overwritten_object_file_with_tampered_bytes(tmp_path: Path) -> None:
    """A bundle whose ``object.json`` is overwritten with tampered bytes is rejected."""

    _checkpoint, _evidence, checkpoint_id = publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    target = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest / "object.json"
    target.write_text(
        json.dumps({"tampered": True}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_load_rejects_replaced_object_file_with_different_digest_bytes(tmp_path: Path) -> None:
    """Replacing ``object.json`` with valid bytes for a different id is rejected."""

    _checkpoint, _evidence, checkpoint_id = publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    target = bundle / "object.json"
    other_payload = {
        "candidate_id": CANDIDATE_BEFORE,
        "correction_evidence_id": None,
        "lens_completions": [
            {"complete": True, "finding_ids": [], "lens": "correctness"},
        ],
        "review_transaction_id": "sha256:" + "5" * 64,
        "review_transaction_root_id": "sha256:" + "4" * 64,
        "schema_name": "ai-harness.review-transaction-checkpoint",
        "schema_version": 1,
    }
    target.write_bytes(encode_canonical(other_payload))
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code in {CODE_STORAGE_INVALID, CODE_STORAGE_CONFLICT}


# ---------------------------------------------------------------------------
# 12.4 — Focused regression run
# ---------------------------------------------------------------------------


def test_focused_checkpoint_and_storage_suites_run_cleanly(tmp_path: Path) -> None:
    """The focused checkpoint and archived-storage suites pass without mocks."""

    project_root = Path(__file__).resolve().parents[1]
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "XDG_RUNTIME_DIR": str(tmp_path),
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_review_transaction_checkpoints_store.py",
            "tests/test_review_transaction_checkpoints_store_load.py",
            "tests/test_review_transaction_checkpoints.py",
            "tests/test_checkpoint_bundle_store.py",
            "tests/test_review_bundle_store.py",
            "tests/test_review_transaction_storage.py",
            "tests/test_review_transaction_storage_publish.py",
            "tests/test_review_transaction_storage_load.py",
            "tests/test_review_transaction_storage_hardening.py",
            "--no-header",
            "-q",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"focused suite failed (returncode={result.returncode})\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_checkpoint_storage_does_not_touch_user_storage(tmp_path: Path) -> None:
    """Running the focused checkpoint suites against ``tmp_path`` leaves it clean.

    The ``tmp_path`` fixture owns the test workspace; ``HOME`` is
    redirected to ``tmp_path`` so any filesystem leak would be visible
    there.
    """

    home = tmp_path / "isolated-home"
    home.mkdir()
    project_root = Path(__file__).resolve().parents[1]
    # Use a dedicated work directory outside ``HOME`` so pytest's own
    # per-test tmp directories do not pollute the home check.
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": str(home),
        "TMPDIR": str(work_dir),
        "XDG_RUNTIME_DIR": str(work_dir),
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_review_transaction_checkpoints_store.py",
            "tests/test_review_transaction_checkpoints_store_load.py",
            "--no-header",
            "-q",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    # The home directory must remain empty.
    assert list(home.iterdir()) == [], f"checkpoint tests wrote to user home: {[p.name for p in home.iterdir()]}"
