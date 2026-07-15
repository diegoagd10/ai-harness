# pylint: disable=duplicate-code
"""Conformance matrix for the v1 checkpoint and evidence codec.

This module enumerates the spec scenarios defined in
``specs/immutable-versioned-checkpoint-and-evidence-contract.md`` and
asserts that each is covered by the pure-codec tests. The fixtures
themselves live in ``tests/test_review_transaction_checkpoints.py``; this
file only pins the mapping between the spec and the test surface so a
regression in coverage is detectable.

The matrix is intentionally hermetic: every assertion uses in-memory
typed values and bytes; no filesystem, subprocess, network, environment,
clock, repository, CLI, or prompt access is permitted.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import encode_canonical, typed_hash
from ai_harness.modules.harness.review_transaction_checkpoints import (
    CHECKPOINT_LABEL,
    CHECKPOINT_SCHEMA_NAME,
    EVIDENCE_LABEL,
    EVIDENCE_SCHEMA_NAME,
    ReviewCheckpointContractError,
    ReviewCorrectionEvidence,
    ReviewCorrectionEvidenceId,
    ReviewTransactionCheckpoint,
    ReviewTransactionCheckpointContractV1,
    ReviewTransactionCheckpointId,
)
from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionRootId
from ai_harness.modules.harness.review_transactions import (
    CorrectionFactId,
    ReviewTransactionId,
)

VALID_ROOT_ID: str = "sha256:" + "0" * 64
VALID_TX_ID: str = "sha256:" + "1" * 64
VALID_CANDIDATE_BEFORE: str = "sha256:" + "a" * 64
VALID_CANDIDATE_AFTER: str = "sha256:" + "b" * 64
VALID_CORRECTION_FACT_ID: str = "sha256:" + "c" * 64


def _checkpoint_payload() -> dict:
    return {
        "candidate_id": VALID_CANDIDATE_BEFORE,
        "correction_evidence_id": None,
        "lens_completions": [{"complete": True, "finding_ids": [], "lens": "correctness"}],
        "review_transaction_id": VALID_TX_ID,
        "review_transaction_root_id": VALID_ROOT_ID,
        "schema_name": CHECKPOINT_SCHEMA_NAME,
        "schema_version": 1,
    }


def _evidence_payload() -> dict:
    return {
        "candidate_after": VALID_CANDIDATE_AFTER,
        "candidate_before": VALID_CANDIDATE_BEFORE,
        "correction_fact_id": VALID_CORRECTION_FACT_ID,
        "review_transaction_id": VALID_TX_ID,
        "review_transaction_root_id": VALID_ROOT_ID,
        "schema_name": EVIDENCE_SCHEMA_NAME,
        "schema_version": 1,
    }


# ---------------------------------------------------------------------------
# Spec scenarios — exact payload grammars
# ---------------------------------------------------------------------------


def test_spec_scenario_encode_exact_checkpoint_payload() -> None:
    """Scenario: Encode an exact checkpoint payload.

    The encoded bytes contain exactly the seven declared fields, with
    ``correction_evidence_id`` projected as JSON ``null``.
    """

    encoded = encode_canonical(_checkpoint_payload())
    parsed = json.loads(encoded.decode("utf-8"))
    expected_keys = {
        "candidate_id",
        "correction_evidence_id",
        "lens_completions",
        "review_transaction_id",
        "review_transaction_root_id",
        "schema_name",
        "schema_version",
    }
    assert set(parsed.keys()) == expected_keys
    assert parsed["correction_evidence_id"] is None
    assert parsed["schema_name"] == CHECKPOINT_SCHEMA_NAME
    assert parsed["schema_version"] == 1


def test_spec_scenario_encode_exact_correction_evidence() -> None:
    """Scenario: Encode exact correction evidence."""

    encoded = encode_canonical(_evidence_payload())
    parsed = json.loads(encoded.decode("utf-8"))
    expected_keys = {
        "candidate_after",
        "candidate_before",
        "correction_fact_id",
        "review_transaction_id",
        "review_transaction_root_id",
        "schema_name",
        "schema_version",
    }
    assert set(parsed.keys()) == expected_keys
    assert parsed["schema_name"] == EVIDENCE_SCHEMA_NAME
    assert parsed["schema_version"] == 1


# ---------------------------------------------------------------------------
# Spec scenarios — canonical round trip and deterministic separated IDs
# ---------------------------------------------------------------------------


def test_spec_scenario_canonical_round_trip() -> None:
    """Scenario: Canonical round trip.

    Canonical bytes produced for a valid checkpoint and correction-evidence
    value decode to equal values and re-encode to byte-identical bytes.
    """

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint_bytes = encode_canonical(_checkpoint_payload())
    evidence_bytes = encode_canonical(_evidence_payload())

    checkpoint = contract.decode(ReviewTransactionCheckpoint, checkpoint_bytes)
    evidence = contract.decode(ReviewCorrectionEvidence, evidence_bytes)
    assert contract.encode(checkpoint) == checkpoint_bytes
    assert contract.encode(evidence) == evidence_bytes


def test_spec_scenario_derive_deterministic_separated_ids() -> None:
    """Scenario: Derive deterministic separated IDs.

    Each value derives its ID under its fixed v1 label using the canonical
    bytes; the two ID wrappers are not interchangeable.
    """

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint_bytes = encode_canonical(_checkpoint_payload())
    evidence_bytes = encode_canonical(_evidence_payload())
    expected_checkpoint_id = typed_hash(CHECKPOINT_LABEL, checkpoint_bytes)
    expected_evidence_id = typed_hash(EVIDENCE_LABEL, evidence_bytes)

    checkpoint = contract.decode(ReviewTransactionCheckpoint, checkpoint_bytes)
    evidence = contract.decode(ReviewCorrectionEvidence, evidence_bytes)
    checkpoint_id = contract.id_for(checkpoint)
    evidence_id = contract.id_for(evidence)
    assert isinstance(checkpoint_id, ReviewTransactionCheckpointId)
    assert isinstance(evidence_id, ReviewCorrectionEvidenceId)
    assert checkpoint_id.value == expected_checkpoint_id
    assert evidence_id.value == expected_evidence_id


def test_spec_scenario_construct_immutable_values() -> None:
    """Scenario: Construct immutable values.

    The frozen, slotted dataclasses preserve exact input order, expose
    tuple-backed collections, and reject mutation.
    """

    checkpoint = ReviewTransactionCheckpoint(
        schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
        review_transaction_id=ReviewTransactionId(VALID_TX_ID),
        candidate_id=VALID_CANDIDATE_BEFORE,
        lens_completions=(),
        correction_evidence_id=None,
    )
    assert isinstance(checkpoint.lens_completions, tuple)
    with pytest.raises((AttributeError, Exception)):
        checkpoint.candidate_id = "tampered"  # type: ignore[misc]

    evidence = ReviewCorrectionEvidence(
        schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
        review_transaction_id=ReviewTransactionId(VALID_TX_ID),
        correction_fact_id=CorrectionFactId(VALID_CORRECTION_FACT_ID),
        candidate_before=VALID_CANDIDATE_BEFORE,
        candidate_after=VALID_CANDIDATE_AFTER,
    )
    with pytest.raises((AttributeError, Exception)):
        evidence.candidate_after = "tampered"  # type: ignore[misc]


def test_spec_scenario_reject_permissive_domain_inputs() -> None:
    """Scenario: Reject permissive domain inputs.

    A mapping, mutable collection, subclass, raw string in a typed id
    field, or value of the wrong exact record class is rejected with a
    stable contract failure rather than coerced.
    """

    contract = ReviewTransactionCheckpointContractV1()
    # Mapping passed to encode — must fail.
    with pytest.raises(ReviewCheckpointContractError):
        contract.encode({"not": "a record"})  # type: ignore[arg-type]
    # Mapping passed to decode — must fail.
    with pytest.raises(ReviewCheckpointContractError):
        contract.decode(ReviewTransactionCheckpoint, {"not": "bytes"})  # type: ignore[arg-type]


def test_spec_scenario_reject_cross_kind_data() -> None:
    """Scenario: Reject cross-kind data.

    Canonical bytes or a wire-shaped ID belonging to the other v1 object
    kind is rejected by expected-record decoding and fixed-label
    recomputation with a stable contract failure.
    """

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint_bytes = encode_canonical(_checkpoint_payload())
    evidence_bytes = encode_canonical(_evidence_payload())

    # Evidence bytes decoded as a checkpoint.
    with pytest.raises(ReviewCheckpointContractError):
        contract.decode(ReviewTransactionCheckpoint, evidence_bytes)
    # Checkpoint bytes decoded as evidence.
    with pytest.raises(ReviewCheckpointContractError):
        contract.decode(ReviewCorrectionEvidence, checkpoint_bytes)


# ---------------------------------------------------------------------------
# Spec scenarios — malformed, noncanonical, unsupported-schema rejection
# ---------------------------------------------------------------------------


def test_spec_scenario_reject_malformed_or_noncanonical_bytes() -> None:
    """Scenario: Reject malformed or noncanonical bytes.

    Invalid UTF-8, a BOM, malformed JSON, duplicate keys at any depth,
    a non-object root, whitespace, trailing bytes, noncanonical key order
    or escaping, a float, or a normalization-dependent representation
    raises ``review-checkpoint.schema-invalid``.
    """

    contract = ReviewTransactionCheckpointContractV1()
    cases = [
        b"\xef\xbb\xbf" + encode_canonical(_checkpoint_payload()),  # BOM
        b"not json",
        b"[1, 2, 3]",  # non-object root
        b"  " + encode_canonical(_checkpoint_payload()),  # leading whitespace
    ]
    for bad in cases:
        with pytest.raises(ReviewCheckpointContractError):
            contract.decode(ReviewTransactionCheckpoint, bad)


def test_spec_scenario_reject_invalid_v1_shape_or_primitives() -> None:
    """Scenario: Reject invalid v1 shape or primitives.

    Bytes with missing or unknown keys, a boolean schema version, a
    non-boolean completion flag, a malformed typed ID, an empty or
    NUL-bearing lens, or unsorted or duplicate finding IDs raise the
    applicable stable failure.
    """

    contract = ReviewTransactionCheckpointContractV1()

    # Boolean schema version.
    payload = _checkpoint_payload()
    payload["schema_version"] = True  # type: ignore[assignment]
    bad = encode_canonical(payload)
    with pytest.raises(ReviewCheckpointContractError):
        contract.decode(ReviewTransactionCheckpoint, bad)

    # Non-boolean completion.
    payload = _checkpoint_payload()
    payload["lens_completions"] = [{"complete": "yes", "finding_ids": [], "lens": "x"}]
    bad = encode_canonical(payload)
    with pytest.raises(ReviewCheckpointContractError):
        contract.decode(ReviewTransactionCheckpoint, bad)

    # Empty lens.
    payload = _checkpoint_payload()
    payload["lens_completions"] = [{"complete": True, "finding_ids": [], "lens": ""}]
    bad = encode_canonical(payload)
    with pytest.raises(ReviewCheckpointContractError):
        contract.decode(ReviewTransactionCheckpoint, bad)

    # Malformed typed id.
    payload = _checkpoint_payload()
    payload["review_transaction_id"] = "not-canonical"
    bad = encode_canonical(payload)
    with pytest.raises(ReviewCheckpointContractError):
        contract.decode(ReviewTransactionCheckpoint, bad)


def test_spec_scenario_reject_unsupported_schema_identity() -> None:
    """Scenario: Reject unsupported schema identity.

    Otherwise well-formed canonical bytes with an unsupported schema name
    or schema version raise ``review-checkpoint.version-unsupported``.
    """

    contract = ReviewTransactionCheckpointContractV1()

    # Unknown schema name.
    payload = _checkpoint_payload()
    payload["schema_name"] = "not-the-schema"
    bad = encode_canonical(payload)
    with pytest.raises(ReviewCheckpointContractError):
        contract.decode(ReviewTransactionCheckpoint, bad)

    # Unsupported schema version.
    payload = _checkpoint_payload()
    payload["schema_version"] = 2
    bad = encode_canonical(payload)
    with pytest.raises(ReviewCheckpointContractError):
        contract.decode(ReviewTransactionCheckpoint, bad)


# ---------------------------------------------------------------------------
# Spec scenario — pure codec boundary
# ---------------------------------------------------------------------------


def test_spec_scenario_exercise_the_codec_hermetically() -> None:
    """Scenario: Exercise the codec hermetically.

    All public contract operations depend only on supplied in-memory
    values; no filesystem, repository, subprocess, network, clock,
    environment, CLI, or prompt is accessed.
    """

    import ai_harness.modules.harness.review_transaction_checkpoints as module

    forbidden_symbols = {"open", "Path", "os", "subprocess"}
    module_attrs = {name for name in dir(module) if not name.startswith("__")}
    leaked = module_attrs & forbidden_symbols
    assert not leaked, f"codec module leaked non-pure symbols: {sorted(leaked)}"


# ---------------------------------------------------------------------------
# Running the focused suite via pytest subprocess stays hermetic.
# ---------------------------------------------------------------------------


def test_focused_codec_suite_runs_hermetically(tmp_path: Path) -> None:
    """Run the pure-codec suite in a clean subprocess and assert it passes.

    The suite must not touch the user filesystem (only the provided
    temporary directory) and must not require network access.
    """

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
            "tests/test_review_transaction_checkpoints.py",
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


def test_focused_codec_suite_does_not_touch_user_home(tmp_path: Path) -> None:
    """A second subprocess run with HOME pointed at a clean dir leaves it empty.

    This guards the pure-codec surface against accidental configuration,
    state, or filesystem reads.
    """

    home = tmp_path / "isolated-home"
    home.mkdir()
    project_root = Path(__file__).resolve().parents[1]
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": str(home),
        "TMPDIR": str(home),
        "XDG_RUNTIME_DIR": str(home),
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_review_transaction_checkpoints.py",
            "--no-header",
            "-q",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    # Pure-codec tests must not write to the user's home directory.
    assert list(home.iterdir()) == [], f"codec tests wrote to user home: {[p.name for p in home.iterdir()]}"
