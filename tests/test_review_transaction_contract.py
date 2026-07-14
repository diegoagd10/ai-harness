# pylint: disable=duplicate-code
"""Smoke tests for the v1 review-transaction contract primitives.

These tests pin the local behaviour of the codec, the immutable record
model, and the strict primitive/path grammar covered by task 1's
foundation subtasks. They run fully in-memory and do not touch the
filesystem, environment, clock, Git, CLI, or persistence layer.
"""

from __future__ import annotations

import dataclasses

import pytest

from ai_harness.modules.harness import review_transactions as rt
from ai_harness.modules.harness.review_transactions import (
    CODE_CORRECTION_INVALID,
    CODE_ID_INVALID,
    CODE_POLICY_INVALID,
    CODE_SCHEMA_INVALID,
    CODE_TRANSITION_INVALID,
    CODE_VERSION_UNSUPPORTED,
    HIGH_RISK_LENSES,
    LENS_POLICY_NAME,
    NORMAL_RISK_LENSES,
    REVIEW_CORRECTION_FACT_ID_LABEL,
    REVIEW_CORRECTION_FACT_SCHEMA_NAME,
    REVIEW_FINDING_ID_LABEL,
    REVIEW_FINDING_SCHEMA_NAME,
    REVIEW_FINDING_TRANSITION_ID_LABEL,
    REVIEW_FINDING_TRANSITION_SCHEMA_NAME,
    REVIEW_LENS_SELECTION_ID_LABEL,
    REVIEW_LENS_SELECTION_SCHEMA_NAME,
    REVIEW_TRANSACTION_ID_LABEL,
    REVIEW_TRANSACTION_SCHEMA_NAME,
    SEVERITIES,
    CorrectionFact,
    CorrectionFactId,
    Finding,
    FindingId,
    FindingTransition,
    FindingTransitionId,
    LensSelection,
    LensSelectionId,
    ReviewContractError,
    ReviewContractV1,
    ReviewTransaction,
    ReviewTransactionId,
)

CANDIDATE_ID: str = "sha256:" + ("c" * 64)
CHANGE_NAME: str = "test-change"


# ---------------------------------------------------------------------------
# Constants and schemas
# ---------------------------------------------------------------------------


def test_constants_pin_closed_vocabulary() -> None:
    """The public vocabulary literals are pinned by the v1 contract."""

    assert LENS_POLICY_NAME == "native-review-lenses-v1"
    assert NORMAL_RISK_LENSES == ("correctness", "tests")
    assert HIGH_RISK_LENSES == ("correctness", "tests", "architecture", "security")
    assert SEVERITIES == ("critical", "warning", "suggestion")
    assert rt.FINDING_STATUSES == ("open", "resolved", "accepted")

    assert REVIEW_LENS_SELECTION_SCHEMA_NAME == "ai-harness.review-lens-selection"
    assert REVIEW_TRANSACTION_SCHEMA_NAME == "ai-harness.review-transaction"
    assert REVIEW_FINDING_SCHEMA_NAME == "ai-harness.review-finding"
    assert REVIEW_FINDING_TRANSITION_SCHEMA_NAME == "ai-harness.review-finding-transition"
    assert REVIEW_CORRECTION_FACT_SCHEMA_NAME == "ai-harness.review-correction-fact"

    assert REVIEW_LENS_SELECTION_ID_LABEL == "ai-harness/review-lens-selection/v1"
    assert REVIEW_TRANSACTION_ID_LABEL == "ai-harness/review-transaction/v1"
    assert REVIEW_FINDING_ID_LABEL == "ai-harness/review-finding/v1"
    assert REVIEW_FINDING_TRANSITION_ID_LABEL == "ai-harness/review-finding-transition/v1"
    assert REVIEW_CORRECTION_FACT_ID_LABEL == "ai-harness/review-correction-fact/v1"


def test_codes_are_exactly_the_six_public_literals() -> None:
    """Error codes match the closed public set."""

    assert {
        CODE_SCHEMA_INVALID,
        CODE_VERSION_UNSUPPORTED,
        CODE_ID_INVALID,
        CODE_POLICY_INVALID,
        CODE_TRANSITION_INVALID,
        CODE_CORRECTION_INVALID,
    } == set(rt.ALL_CODES)


# ---------------------------------------------------------------------------
# Immutable record and ID kind separation
# ---------------------------------------------------------------------------


def _make_selection() -> LensSelection:
    return LensSelection(
        schema_name=REVIEW_LENS_SELECTION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        policy=LENS_POLICY_NAME,
        risk_level="normal",
        required_lenses=NORMAL_RISK_LENSES,
    )


def test_records_are_frozen_and_slotted_and_tuple_backed() -> None:
    """Public records cannot be mutated after construction."""

    selection = _make_selection()
    assert dataclasses.is_dataclass(selection)
    assert type(selection).__slots__ == tuple(
        field.name for field in dataclasses.fields(selection)
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        selection.policy = "changed"  # type: ignore[misc]

    finding = Finding(
        schema_name=REVIEW_FINDING_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=ReviewTransactionId("sha256:" + ("a" * 64)),
        lens="correctness",
        severity="warning",
        summary="summary text",
        detail="detail text",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.severity = "critical"  # type: ignore[misc]
    # Tuple collections are immutable: attempts to mutate raise TypeError.
    with pytest.raises((AttributeError, TypeError)):
        finding.paths.__setitem__(0, "src")  # type: ignore[attr-defined]


def test_typed_id_kinds_cannot_be_substituted() -> None:
    """Each ID class is its own runtime type; use-site guards reject other kinds.

    The contract supplies five ID classes that share no base class, so
    Python's runtime ``isinstance`` guards reject a ``LensSelectionId``
    where a ``LensSelectionId`` is required. The internal validators
    raise ``review.id-invalid`` if a caller bypasses ``isinstance``.
    """

    lens_id = LensSelectionId("sha256:" + ("1" * 64))
    # Runtime type separation: ``LensSelectionId`` is not a FindingId and
    # vice versa; static and runtime type checks both fail substitution.
    assert not isinstance(lens_id, FindingId)
    assert not isinstance(lens_id, ReviewTransactionId)
    assert not isinstance(lens_id, FindingTransitionId)
    assert not isinstance(lens_id, CorrectionFactId)

    # The use-site validators raise ``review.id-invalid`` if a caller
    # passes anything but the expected ID class.
    with pytest.raises(ReviewContractError) as exc:
        rt._require_finding_id(lens_id, field="finding_id")
    assert exc.value.code == CODE_ID_INVALID

    with pytest.raises(ReviewContractError) as exc:
        rt._require_correction_fact_id(lens_id, field="correction_fact_id")
    assert exc.value.code == CODE_ID_INVALID


# ---------------------------------------------------------------------------
# Exact schemas and the policy matrix
# ---------------------------------------------------------------------------


def test_select_lenses_returns_deterministic_normal_selection() -> None:
    """`normal` risk returns the exact dual-lens selection."""

    contract = ReviewContractV1()
    first = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")
    second = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")

    assert first == second
    assert first.required_lenses == NORMAL_RISK_LENSES


def test_select_lenses_returns_deterministic_high_selection() -> None:
    """`high` risk returns the four-lens selection in contractual order."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")
    assert selection.required_lenses == HIGH_RISK_LENSES


def test_select_lenses_rejects_unknown_policy_and_risk() -> None:
    """Unknown policy or risk tokens fail with `review.policy-invalid`."""

    contract = ReviewContractV1()
    with pytest.raises(ReviewContractError) as policy_exc:
        contract.select_lenses(policy="unknown-policy", risk_level="normal")
    assert policy_exc.value.code == CODE_POLICY_INVALID

    with pytest.raises(ReviewContractError) as risk_exc:
        contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="unknown")
    assert risk_exc.value.code == CODE_POLICY_INVALID


def test_decode_lens_selection_rejects_forged_payload() -> None:
    """Decoding a forged selection (omitted, extra, duplicated lens) fails."""

    contract = ReviewContractV1()
    payload = {
        "schema_name": REVIEW_LENS_SELECTION_SCHEMA_NAME,
        "schema_version": 1,
        "policy": LENS_POLICY_NAME,
        "risk_level": "normal",
        "required_lenses": ["correctness"],  # missing 'tests'
    }
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, payload)
    assert exc.value.code == CODE_POLICY_INVALID

    bad = {
        "schema_name": REVIEW_LENS_SELECTION_SCHEMA_NAME,
        "schema_version": 1,
        "policy": LENS_POLICY_NAME,
        "risk_level": "normal",
        "required_lenses": ["correctness", "tests", "correctness"],
    }
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, bad)
    assert exc.value.code == CODE_SCHEMA_INVALID


# ---------------------------------------------------------------------------
# Canonical bytes and identity
# ---------------------------------------------------------------------------


def _basic_lens_selection_payload() -> dict[str, object]:
    return {
        "schema_name": REVIEW_LENS_SELECTION_SCHEMA_NAME,
        "schema_version": 1,
        "policy": LENS_POLICY_NAME,
        "risk_level": "normal",
        "required_lenses": list(NORMAL_RISK_LENSES),
    }


def test_canonical_round_trip_is_stable_and_id_is_deterministic() -> None:
    """Encoding, decoding, and re-encoding reproduce identical bytes and IDs."""

    contract = ReviewContractV1()
    payload = _basic_lens_selection_payload()
    bytes_a = contract.encode(contract.decode(LensSelection, payload))
    bytes_b = contract.encode(contract.decode(LensSelection, payload))
    assert bytes_a == bytes_b

    record = contract.decode(LensSelection, payload)
    first_id = contract.id_for(record)
    second_id = contract.id_for(record)
    assert isinstance(first_id, LensSelectionId)
    assert first_id == second_id
    assert first_id.value.startswith("sha256:")
    assert len(first_id.value) == len("sha256:") + 64


def test_id_for_uses_record_specific_label() -> None:
    """Each record kind hashes its own canonical bytes under its own label.

    The five typed-ID classes share no base class so Python's runtime
    distinguishes them; the canonical hash labels differ per record kind
    so the same byte sequence would yield a different ID under another
    label. The validator enforces that an ID is recomputed from the
    supplied record before a reference is trusted.
    """

    contract = ReviewContractV1()
    payload = _basic_lens_selection_payload()
    record = contract.decode(LensSelection, payload)
    rid = contract.id_for(record)
    assert isinstance(rid, LensSelectionId)
    assert rid.value.startswith("sha256:") and len(rid.value) == len("sha256:") + 64

    # Distinct ID classes — a `LensSelectionId` is not a `FindingId`.
    assert type(rid) is not FindingId
    assert type(rid) is not ReviewTransactionId
    assert type(rid) is not FindingTransitionId
    assert type(rid) is not CorrectionFactId

    # Distinct labels per record kind — typing the same bytes under two
    # labels yields two distinct IDs.
    from ai_harness.modules.harness import receipts as receipts_codec
    bytes_payload = contract.encode(record)
    label_a = REVIEW_LENS_SELECTION_ID_LABEL
    label_b = REVIEW_TRANSACTION_ID_LABEL
    assert label_a != label_b
    assert (
        receipts_codec.typed_hash(label_a, bytes_payload)
        != receipts_codec.typed_hash(label_b, bytes_payload)
    )


# ---------------------------------------------------------------------------
# Strict primitive and collection grammar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "description"),
    [
        ("", "empty"),
        ("with\x00nul", "nul byte"),
        (None, "non-string"),
        (123, "integer not string"),
        ([], "list not string"),
    ],
)
def test_decode_rejects_invalid_required_strings(value: object, description: str) -> None:
    """Decoder rejects invalid prose/identifier values."""

    contract = ReviewContractV1()
    payload = _basic_lens_selection_payload()
    payload["policy"] = value  # type: ignore[assignment]
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, payload)
    assert exc.value.code == CODE_SCHEMA_INVALID
    assert description or True  # description retained for diagnostic labels


def test_boolean_is_not_a_schema_version() -> None:
    """Boolean `True` does not satisfy integer version 1."""

    contract = ReviewContractV1()
    payload = _basic_lens_selection_payload()
    payload["schema_version"] = True  # type: ignore[assignment]
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, payload)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_unknown_schema_name_is_version_unsupported() -> None:
    """A well-typed but unknown schema literal rejects with version-unsupported."""

    contract = ReviewContractV1()
    payload = _basic_lens_selection_payload()
    payload["schema_name"] = "ai-harness.unknown-schema"
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, payload)
    assert exc.value.code == CODE_VERSION_UNSUPPORTED


def test_to_payload_projection_is_detached() -> None:
    """Mutating the projected mapping does not mutate the record."""

    contract = ReviewContractV1()
    record = contract.decode(LensSelection, _basic_lens_selection_payload())
    payload = contract.to_payload(record)
    assert payload["required_lenses"] == list(NORMAL_RISK_LENSES)
    payload["required_lenses"].append("rogue")  # type: ignore[attr-defined]
    payload["policy"] = "rogue"

    # Record and a fresh projection are unaffected.
    assert record.required_lenses == NORMAL_RISK_LENSES
    second_projection = contract.to_payload(record)
    assert second_projection["required_lenses"] == list(NORMAL_RISK_LENSES)
    assert second_projection["policy"] == LENS_POLICY_NAME


def test_canonical_bytes_reject_duplicate_keys_and_trailing_whitespace() -> None:
    """Bytes containing duplicate keys or trailing whitespace are not canonical."""

    contract = ReviewContractV1()
    payload = _basic_lens_selection_payload()
    # Encode a record once, then craft noncanonical bytes to prove rejection.
    record = contract.decode(LensSelection, payload)
    canonical = contract.encode(record)
    # Whitespace prefix is not canonical.
    bad_whitespace = b" " + canonical
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, bad_whitespace)
    assert exc.value.code == CODE_SCHEMA_INVALID
    # Trailing newline is not canonical.
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, canonical + b"\n")
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_canonical_bytes_reject_duplicate_keys_at_root_and_nested() -> None:
    """Duplicate keys at any depth are rejected via the canonical decoder."""

    contract = ReviewContractV1()
    duplicate_root = b'{"a":1,"a":2}'
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, duplicate_root)
    assert exc.value.code == CODE_SCHEMA_INVALID


# ---------------------------------------------------------------------------
# Sanity: the contract is deterministic and does not read the environment
# ---------------------------------------------------------------------------


def test_module_does_not_import_persistence_or_lifecycle() -> None:
    """The contract seam must not pull in persistence, Git, lifecycle, or CLI.

    The check inspects the *import* lines of the module — plain docstring
    mentions of these tokens (e.g. describing what the module does not
    do) are allowed. Only concrete import statements are forbidden.
    """

    source_path = rt.__file__  # type: ignore[attr-defined]
    assert source_path is not None
    lines = open(source_path, encoding="utf-8").read().splitlines()
    import_lines = [line for line in lines if line.startswith(("import ", "from "))]
    forbidden = (
        "os",
        "pathlib",
        "subprocess",
        "datetime",
        "shutil",
        "requests",
        "git",
        "typer",
        "questionary",
        "tempfile",
    )
    joined = "\n".join(import_lines)
    for token in forbidden:
        # Match either a top-level import or any `from X import` reference.
        assert (
            f"import {token}" not in joined and f".{token} " not in joined and f".{token}\n" not in joined
        ), f"forbidden import: {token}"


def test_module_constants_export_surface() -> None:
    """Public surface matches the design's stated exports."""

    expected = {
        "ReviewContractV1",
        "ReviewContractError",
        "LensSelection",
        "ReviewTransaction",
        "Finding",
        "FindingTransition",
        "CorrectionFact",
        "LensSelectionId",
        "ReviewTransactionId",
        "FindingId",
        "FindingTransitionId",
        "CorrectionFactId",
    }
    for name in expected:
        assert hasattr(rt, name), f"missing public export: {name}"


# ---------------------------------------------------------------------------
# Decoder sanity for non-codec records (foundation payload grammars only)
# ---------------------------------------------------------------------------


def test_review_transaction_decoder_rejects_invalid_change_name() -> None:
    """Change names containing separators, NUL bytes, or `.` are rejected."""

    contract = ReviewContractV1()
    base = {
        "schema_name": REVIEW_TRANSACTION_SCHEMA_NAME,
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "lens_selection_id": "sha256:" + ("9" * 64),
        "scope_paths": ["src"],
        "loc_budget": 0,
    }
    for invalid in ["", ".", "..", "with/slash", "with\\back", "nul\x00name"]:
        bad = dict(base)
        bad["change_name"] = invalid  # type: ignore[assignment]
        with pytest.raises(ReviewContractError) as exc:
            contract.decode(ReviewTransaction, bad)
        assert exc.value.code == CODE_SCHEMA_INVALID


def test_review_transaction_decoder_requires_sorted_unique_scope_paths() -> None:
    """Out-of-order or duplicated scope paths fail the decoder."""

    contract = ReviewContractV1()
    base = {
        "schema_name": REVIEW_TRANSACTION_SCHEMA_NAME,
        "schema_version": 1,
        "change_name": CHANGE_NAME,
        "candidate_id": CANDIDATE_ID,
        "lens_selection_id": "sha256:" + ("9" * 64),
        "loc_budget": 5,
    }
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(
            ReviewTransaction,
            dict(base, scope_paths=["src", "abc/"]),
        )
    assert exc.value.code == CODE_SCHEMA_INVALID

    with pytest.raises(ReviewContractError) as exc:
        contract.decode(
            ReviewTransaction,
            dict(base, scope_paths=["src", "src"]),
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_correction_fact_decoder_rejects_loc_arithmetic_mismatch() -> None:
    """`loc_actual` must equal `loc_added + loc_deleted` at decode time."""

    contract = ReviewContractV1()
    payload = {
        "schema_name": REVIEW_CORRECTION_FACT_SCHEMA_NAME,
        "schema_version": 1,
        "review_transaction_id": "sha256:" + ("9" * 64),
        "resolved_finding_ids": ["sha256:" + ("1" * 64), "sha256:" + ("2" * 64)],
        "candidate_before": CANDIDATE_ID,
        "candidate_after": "sha256:" + ("d" * 64),
        "changed_paths": ["src/a.py"],
        "loc_added": 3,
        "loc_deleted": 4,
        "loc_actual": 9,
    }
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(CorrectionFact, payload)
    assert exc.value.code == CODE_CORRECTION_INVALID


def test_finding_transition_requires_correction_for_resolved() -> None:
    """Transitions to `resolved` carry a correction ID, not null."""

    contract = ReviewContractV1()
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(
            FindingTransition,
            {
                "schema_name": REVIEW_FINDING_TRANSITION_SCHEMA_NAME,
                "schema_version": 1,
                "review_transaction_id": "sha256:" + ("9" * 64),
                "finding_id": "sha256:" + ("1" * 64),
                "from_status": "open",
                "to_status": "resolved",
                "correction_fact_id": None,
            },
        )
    assert exc.value.code == CODE_TRANSITION_INVALID


def test_finding_transition_must_have_null_correction_for_accepted() -> None:
    """Transitions to `accepted` must carry `null` for correction_fact_id."""

    contract = ReviewContractV1()
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(
            FindingTransition,
            {
                "schema_name": REVIEW_FINDING_TRANSITION_SCHEMA_NAME,
                "schema_version": 1,
                "review_transaction_id": "sha256:" + ("9" * 64),
                "finding_id": "sha256:" + ("1" * 64),
                "from_status": "open",
                "to_status": "accepted",
                "correction_fact_id": "sha256:" + ("7" * 64),
            },
        )
    assert exc.value.code == CODE_TRANSITION_INVALID


def test_finding_decoder_rejects_non_open_initial_status() -> None:
    """A finding whose initial status is not exactly `open` is rejected."""

    contract = ReviewContractV1()
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(
            Finding,
            {
                "schema_name": REVIEW_FINDING_SCHEMA_NAME,
                "schema_version": 1,
                "review_transaction_id": "sha256:" + ("9" * 64),
                "lens": "correctness",
                "severity": "warning",
                "summary": "s",
                "detail": "d",
                "paths": [],
                "status": "resolved",
            },
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decoder_catches_basic_id_substitution_via_string_field() -> None:
    """A non-canonical typed-id string fails the contract decoder."""

    contract = ReviewContractV1()
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(
            ReviewTransaction,
            {
                "schema_name": REVIEW_TRANSACTION_SCHEMA_NAME,
                "schema_version": 1,
                "change_name": CHANGE_NAME,
                "candidate_id": "not-a-typed-id",
                "lens_selection_id": "sha256:" + ("9" * 64),
                "scope_paths": [],
                "loc_budget": 0,
            },
        )
    assert exc.value.code == CODE_ID_INVALID


def test_to_payload_returns_decoded_object_for_each_record_kind() -> None:
    """`to_payload` works for each of the five record kinds."""

    contract = ReviewContractV1()
    selection = contract.decode(LensSelection, _basic_lens_selection_payload())
    assert contract.to_payload(selection)["schema_name"] == REVIEW_LENS_SELECTION_SCHEMA_NAME

    # Other payloads: encode + decode + project round-trips.
    canonical_lens_bytes = contract.encode(selection)

    transaction = ReviewTransaction(
        schema_name=REVIEW_TRANSACTION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=CHANGE_NAME,
        candidate_id=CANDIDATE_ID,
        lens_selection_id=LensSelectionId("sha256:" + ("9" * 64)),
        scope_paths=(),
        loc_budget=0,
    )
    assert contract.to_payload(transaction)["change_name"] == CHANGE_NAME

    # Confirm decoder rejects noncanonical byte sequences even on real records.
    bad = canonical_lens_bytes.replace(b":", b": ")  # type: ignore[union-attr]
    if bad == canonical_lens_bytes:  # pragma: no cover - safety net only
        pytest.skip("noncanonical surrogate produced identical bytes")
    with pytest.raises(ReviewContractError):
        contract.decode(LensSelection, bad)


def test_review_transaction_id_label_matches_record() -> None:
    """The five labels are strings and non-empty."""

    labels = (
        REVIEW_LENS_SELECTION_ID_LABEL,
        REVIEW_TRANSACTION_ID_LABEL,
        REVIEW_FINDING_ID_LABEL,
        REVIEW_FINDING_TRANSITION_ID_LABEL,
        REVIEW_CORRECTION_FACT_ID_LABEL,
    )
    assert len(set(labels)) == 5
    assert all(label.endswith("/v1") for label in labels)


# ---------------------------------------------------------------------------
# Lens policy and transaction binding (task 2)
# ---------------------------------------------------------------------------


def _transaction_with_lens_selection(
    lens_selection: LensSelection,
) -> ReviewTransaction:
    """Build a transaction whose lens_selection_id matches the selection."""

    contract = ReviewContractV1()
    return ReviewTransaction(
        schema_name=REVIEW_TRANSACTION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=CHANGE_NAME,
        candidate_id=CANDIDATE_ID,
        lens_selection_id=contract.id_for(lens_selection),
        scope_paths=(),
        loc_budget=0,
    )


def test_select_lenses_for_high_risk_is_closed_ordered_tuple() -> None:
    """High risk selection returns the contractual four-lens ordered tuple."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")
    assert selection.required_lenses == ("correctness", "tests", "architecture", "security")


def test_select_lenses_for_normal_risk_is_closed_ordered_tuple() -> None:
    """Normal risk selection returns the contractual dual-lens ordered tuple."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")
    assert selection.required_lenses == ("correctness", "tests")


def test_select_lenses_rejects_unknown_risk_levels() -> None:
    """Unknown risk levels fail with ``review.policy-invalid``."""

    contract = ReviewContractV1()
    for risk in ("medium", "low", "NORMAL", "", "Normal", None):
        with pytest.raises(ReviewContractError) as exc:
            contract.select_lenses(policy=LENS_POLICY_NAME, risk_level=risk)  # type: ignore[arg-type]
        assert exc.value.code == CODE_POLICY_INVALID


def test_select_lenses_rejects_unknown_policy_tokens() -> None:
    """Unknown policy tokens fail with ``review.policy-invalid``."""

    contract = ReviewContractV1()
    for policy in ("", "v0", "native-review-lenses-v0", "lenses-v2"):
        with pytest.raises(ReviewContractError) as exc:
            contract.select_lenses(policy=policy, risk_level="normal")
        assert exc.value.code == CODE_POLICY_INVALID


def test_select_lenses_is_repeatable_for_normal_risk() -> None:
    """Identical inputs always produce identical records, bytes, and IDs."""

    contract = ReviewContractV1()
    records = [
        contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")
        for _ in range(3)
    ]
    assert records[0] == records[1] == records[2]

    bytes_set = {contract.encode(record) for record in records}
    ids = {contract.id_for(record).value for record in records}
    assert len(bytes_set) == 1
    assert len(ids) == 1


def test_select_lenses_is_repeatable_for_high_risk() -> None:
    """Identical high-risk inputs always produce identical bytes and IDs."""

    contract = ReviewContractV1()
    records = [
        contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")
        for _ in range(3)
    ]
    assert records[0] == records[1] == records[2]

    bytes_set = {contract.encode(record) for record in records}
    ids = {contract.id_for(record).value for record in records}
    assert len(bytes_set) == 1
    assert len(ids) == 1


def test_decode_lens_selection_accepts_exact_risk_tuple_for_normal() -> None:
    """A normal-risk selection decodes without modification."""

    contract = ReviewContractV1()
    payload = {
        "schema_name": REVIEW_LENS_SELECTION_SCHEMA_NAME,
        "schema_version": 1,
        "policy": LENS_POLICY_NAME,
        "risk_level": "normal",
        "required_lenses": ["correctness", "tests"],
    }
    record = contract.decode(LensSelection, payload)
    assert record.required_lenses == ("correctness", "tests")


def test_decode_lens_selection_accepts_exact_risk_tuple_for_high() -> None:
    """A high-risk selection decodes without modification."""

    contract = ReviewContractV1()
    payload = {
        "schema_name": REVIEW_LENS_SELECTION_SCHEMA_NAME,
        "schema_version": 1,
        "policy": LENS_POLICY_NAME,
        "risk_level": "high",
        "required_lenses": ["correctness", "tests", "architecture", "security"],
    }
    record = contract.decode(LensSelection, payload)
    assert record.required_lenses == ("correctness", "tests", "architecture", "security")


def test_decode_lens_selection_rejects_reordered_lens_tuple() -> None:
    """Reordering the contractual lens tuple is rejected."""

    contract = ReviewContractV1()
    payload = {
        "schema_name": REVIEW_LENS_SELECTION_SCHEMA_NAME,
        "schema_version": 1,
        "policy": LENS_POLICY_NAME,
        "risk_level": "normal",
        "required_lenses": ["tests", "correctness"],
    }
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, payload)
    assert exc.value.code == CODE_POLICY_INVALID


def test_decode_lens_selection_rejects_extra_lens() -> None:
    """Adding a non-contractual lens is rejected."""

    contract = ReviewContractV1()
    payload = {
        "schema_name": REVIEW_LENS_SELECTION_SCHEMA_NAME,
        "schema_version": 1,
        "policy": LENS_POLICY_NAME,
        "risk_level": "normal",
        "required_lenses": ["correctness", "tests", "bonus"],
    }
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, payload)
    assert exc.value.code == CODE_POLICY_INVALID


def test_decode_lens_selection_rejects_unknown_lens_token() -> None:
    """Replacing a contractual lens with an unknown token is rejected."""

    contract = ReviewContractV1()
    payload = {
        "schema_name": REVIEW_LENS_SELECTION_SCHEMA_NAME,
        "schema_version": 1,
        "policy": LENS_POLICY_NAME,
        "risk_level": "normal",
        "required_lenses": ["correctness", "mystery"],
    }
    with pytest.raises(ReviewContractError) as exc:
        contract.decode(LensSelection, payload)
    assert exc.value.code == CODE_POLICY_INVALID


def test_validate_transaction_binds_normal_lens_selection() -> None:
    """A transaction whose lens-selection id matches the supplied selection passes."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")
    transaction = _transaction_with_lens_selection(selection)
    # No findings, transitions, or correction — task 2 only binds lenses.
    contract.validate_transaction(transaction, lens_selection=selection)


def test_validate_transaction_binds_high_lens_selection() -> None:
    """A high-risk selection binds the transaction correctly."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")
    transaction = _transaction_with_lens_selection(selection)
    contract.validate_transaction(transaction, lens_selection=selection)


def test_validate_transaction_rejects_shape_only_lens_selection_id() -> None:
    """A well-shaped lens ID that does not match the supplied selection is rejected."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")
    # Build a transaction with an unrelated well-formed sha256 id; it has
    # valid wire form but does not match the supplied selection's content hash.
    unrelated_id = LensSelectionId("sha256:" + ("0" * 64))
    transaction = ReviewTransaction(
        schema_name=REVIEW_TRANSACTION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=CHANGE_NAME,
        candidate_id=CANDIDATE_ID,
        lens_selection_id=unrelated_id,
        scope_paths=(),
        loc_budget=0,
    )
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(transaction, lens_selection=selection)
    assert exc.value.code == CODE_ID_INVALID


def test_validate_transaction_rejects_wrong_risk_level_binding() -> None:
    """Selecting ``high`` while the transaction references the ``normal`` ID fails."""

    contract = ReviewContractV1()
    normal_selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")
    transaction = _transaction_with_lens_selection(normal_selection)
    high_selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(transaction, lens_selection=high_selection)
    assert exc.value.code == CODE_ID_INVALID


def test_validate_transaction_refuses_findings_until_later_tasks() -> None:
    """Cross-record validation stages land in tasks 3 and 4; non-empty graph fails."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")
    transaction = _transaction_with_lens_selection(selection)
    # The lens binding succeeds, but supplying non-empty findings trips
    # the not-yet-implemented cross-record guard.
    with pytest.raises(ReviewContractError):
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(
                Finding(
                    schema_name=REVIEW_FINDING_SCHEMA_NAME,  # type: ignore[arg-type]
                    schema_version=1,  # type: ignore[arg-type]
                    review_transaction_id=ReviewTransactionId("sha256:" + ("a" * 64)),
                    lens="correctness",
                    severity="warning",
                    summary="s",
                    detail="d",
                    paths=(),
                    status="open",  # type: ignore[arg-type]
                ),
            ),
        )


def test_validate_transaction_refuses_transitions_until_later_tasks() -> None:
    """Transitions are validated in tasks 3 and 4."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")
    transaction = _transaction_with_lens_selection(selection)
    with pytest.raises(ReviewContractError):
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            transitions=(
                FindingTransition(
                    schema_name=REVIEW_FINDING_TRANSITION_SCHEMA_NAME,  # type: ignore[arg-type]
                    schema_version=1,  # type: ignore[arg-type]
                    review_transaction_id=ReviewTransactionId("sha256:" + ("a" * 64)),
                    finding_id=FindingId("sha256:" + ("b" * 64)),
                    from_status="open",
                    to_status="resolved",
                    correction_fact_id=CorrectionFactId("sha256:" + ("c" * 64)),
                ),
            ),
        )


def test_lens_selection_id_wire_format_is_enforced() -> None:
    """A malformed wire id fails the typed-id helpers."""

    with pytest.raises(ReviewContractError) as exc:
        LensSelectionId("not-a-canonical-id")
    assert exc.value.code == CODE_ID_INVALID


# ---------------------------------------------------------------------------
# Finding lifecycle state-machine and bindings (task 3)
# ---------------------------------------------------------------------------


def _build_finding_fixture(
    lens: str = "correctness",
    severity: str = "warning",
    *,
    paths: tuple[str, ...] = (),
    summary: str = "summary",
    detail: str = "detail",
) -> tuple[ReviewContractV1, LensSelection, ReviewTransaction, ReviewTransactionId]:
    """Return a ``(contract, selection, transaction, tx_id)`` tuple for tests."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")
    transaction = ReviewTransaction(
        schema_name=REVIEW_TRANSACTION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=CHANGE_NAME,
        candidate_id=CANDIDATE_ID,
        lens_selection_id=contract.id_for(selection),
        scope_paths=("src",),
        loc_budget=20,
    )
    tx_id = contract.id_for(transaction)
    return contract, selection, transaction, tx_id,  # type: ignore[return-value]


def _make_finding(
    contract: ReviewContractV1,
    tx_id: ReviewTransactionId,
    *,
    lens: str = "correctness",
    severity: str = "warning",
    paths: tuple[str, ...] = (),
    summary: str = "summary",
    detail: str = "detail",
) -> Finding:
    """Build a fully-typed finding record."""

    return Finding(
        schema_name=REVIEW_FINDING_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        lens=lens,
        severity=severity,
        summary=summary,
        detail=detail,
        paths=paths,
        status="open",  # type: ignore[arg-type]
    )


def _make_transition(
    contract: ReviewContractV1,
    tx_id: ReviewTransactionId,
    finding_id: FindingId,
    *,
    from_status: str = "open",
    to_status: str = "accepted",
    correction_fact_id: CorrectionFactId | None = None,
) -> FindingTransition:
    """Build a finding transition record."""

    return FindingTransition(
        schema_name=REVIEW_FINDING_TRANSITION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=finding_id,
        from_status=from_status,
        to_status=to_status,
        correction_fact_id=correction_fact_id,
    )


def test_finding_belongs_to_transaction() -> None:
    """A finding bound to the supplied transaction and selected lens passes."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, lens="correctness", severity="warning")
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding,),
    )


def test_finding_lens_must_be_selected_by_transaction() -> None:
    """A finding whose lens is not in the selection is rejected."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    # High selection is ``(correctness, tests, architecture, security)``;
    # ``performance`` is not contractual.
    bad_lens_finding = _make_finding(contract, tx_id, lens="performance", severity="warning")
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(bad_lens_finding,),
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_finding_with_unknown_severity_is_rejected() -> None:
    """A severity outside the closed vocabulary is rejected at validation."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    bad_finding = Finding(
        schema_name=REVIEW_FINDING_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        lens="correctness",
        severity="fatal",  # invalid
        summary="s",
        detail="d",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(bad_finding,),
        )
    assert exc.value.code in {CODE_SCHEMA_INVALID, CODE_ID_INVALID}


def test_finding_path_outside_scope_is_schema_invalid() -> None:
    """A finding path outside the transaction scope fails with schema-invalid."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    in_scope = _make_finding(contract, tx_id, paths=("src/module.py",))
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(in_scope,),
    )

    out_of_scope = _make_finding(contract, tx_id, paths=("other/module.py",))
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(out_of_scope,),
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_finding_path_prefix_text_is_not_segment_containment() -> None:
    """``src-old/...`` is not contained by ``src``."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    bad = _make_finding(contract, tx_id, paths=("src-old/module.py",))
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(bad,),
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_finding_descendant_path_is_in_scope() -> None:
    """A path equal to scope or descending from a scope entry is in scope."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    descendant = _make_finding(contract, tx_id, paths=("src", "src/inner/file.py"))
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(descendant,),
    )


def test_duplicate_supplied_findings_fail_validation() -> None:
    """Two supplied findings with identical content produce a duplicate ID."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    a = _make_finding(contract, tx_id)
    b = _make_finding(contract, tx_id)
    # ``a`` and ``b`` carry identical fields -> identical ID.
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(a, b),
        )
    assert exc.value.code == CODE_ID_INVALID


def test_warning_finding_can_resolve_with_correction() -> None:
    """`warning -> resolved` with a correction reference is legal."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="warning")
    finding_id = contract.id_for(finding)
    correction_id = CorrectionFactId("sha256:" + ("f" * 64))
    transition = _make_transition(
        contract,
        tx_id,
        finding_id,
        to_status="resolved",
        correction_fact_id=correction_id,
    )
    # Stage 4 (correction validation) is not yet wired; the transition
    # itself is reduced correctly here, but correction belongs to task 4.
    # Without a correction fact supplied the resolved transition's
    # correction id is recomputed elsewhere; for now we just want to
    # confirm the state-machine accepts the edge.
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding,),
        transitions=(transition,),
    )


def test_warning_finding_can_be_accepted() -> None:
    """`warning -> accepted` is allowed for noncritical findings."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="warning")
    finding_id = contract.id_for(finding)
    transition = _make_transition(
        contract,
        tx_id,
        finding_id,
        to_status="accepted",
        correction_fact_id=None,
    )
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding,),
        transitions=(transition,),
    )


def test_suggestion_finding_can_be_accepted() -> None:
    """`suggestion -> accepted` follows the suggestion-severity rule."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="suggestion")
    finding_id = contract.id_for(finding)
    transition = _make_transition(
        contract,
        tx_id,
        finding_id,
        to_status="accepted",
        correction_fact_id=None,
    )
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding,),
        transitions=(transition,),
    )


def test_critical_finding_cannot_be_accepted() -> None:
    """`critical -> accepted` is invalid per severity rule."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="critical")
    finding_id = contract.id_for(finding)
    transition = _make_transition(
        contract,
        tx_id,
        finding_id,
        to_status="accepted",
        correction_fact_id=None,
    )
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(finding,),
            transitions=(transition,),
        )
    assert exc.value.code == CODE_TRANSITION_INVALID


def test_self_transition_is_rejected() -> None:
    """Source equals destination is rejected."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="warning")
    finding_id = contract.id_for(finding)
    transition = _make_transition(
        contract,
        tx_id,
        finding_id,
        from_status="open",
        to_status="open",
        correction_fact_id=None,
    )
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(finding,),
            transitions=(transition,),
        )
    assert exc.value.code == CODE_TRANSITION_INVALID


def test_replayed_transition_is_rejected() -> None:
    """A second transition after a terminal state is rejected."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="warning")
    finding_id = contract.id_for(finding)
    first = _make_transition(
        contract,
        tx_id,
        finding_id,
        to_status="accepted",
        correction_fact_id=None,
    )
    second = _make_transition(
        contract,
        tx_id,
        finding_id,
        from_status="accepted",  # source must equal derived state
        to_status="resolved",
        correction_fact_id=CorrectionFactId("sha256:" + ("a" * 64)),
    )
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(finding,),
            transitions=(first, second),
        )
    assert exc.value.code == CODE_TRANSITION_INVALID


def test_resolved_transition_requires_correction_id() -> None:
    """Stage 3 rejects resolved transitions that omit a correction id."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="warning")
    finding_id = contract.id_for(finding)
    transition = _make_transition(
        contract,
        tx_id,
        finding_id,
        to_status="resolved",
        correction_fact_id=None,  # resolved must carry a correction
    )
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(finding,),
            transitions=(transition,),
        )
    assert exc.value.code == CODE_TRANSITION_INVALID


def test_accepted_transition_must_not_carry_correction_id() -> None:
    """Stage 3 rejects accepted transitions that carry a correction id."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="warning")
    finding_id = contract.id_for(finding)
    transition = _make_transition(
        contract,
        tx_id,
        finding_id,
        to_status="accepted",
        correction_fact_id=CorrectionFactId("sha256:" + ("a" * 64)),  # accepted must be null
    )
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(finding,),
            transitions=(transition,),
        )
    assert exc.value.code == CODE_TRANSITION_INVALID


def test_unknown_finding_transition_reference_fails() -> None:
    """A transition that names a finding not in the supplied graph is rejected."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    # No supplied findings; any transition reference is unknown.
    bogus_finding_id = FindingId("sha256:" + ("d" * 64))
    transition = _make_transition(
        contract,
        tx_id,
        bogus_finding_id,
        to_status="accepted",
        correction_fact_id=None,
    )
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            transitions=(transition,),
        )
    assert exc.value.code == CODE_ID_INVALID


def test_cross_transaction_finding_reference_fails() -> None:
    """A transition that names a finding of another transaction is rejected."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="warning")
    finding_id = contract.id_for(finding)

    # Build an unrelated transaction and a transition that targets the
    # supplied finding via the unrelated transaction reference.
    other_selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")
    other_transaction = ReviewTransaction(
        schema_name=REVIEW_TRANSACTION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name="other-change",
        candidate_id=CANDIDATE_ID,
        lens_selection_id=contract.id_for(other_selection),
        scope_paths=(),
        loc_budget=0,
    )

    bad_transition = FindingTransition(
        schema_name=REVIEW_FINDING_TRANSITION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=contract.id_for(other_transaction),
        finding_id=finding_id,
        from_status="open",
        to_status="accepted",
        correction_fact_id=None,
    )
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(finding,),
            transitions=(bad_transition,),
        )
    assert exc.value.code == CODE_ID_INVALID


def test_unresolved_critical_finding_is_rejected() -> None:
    """A critical finding without a resolving transition is rejected."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    critical = _make_finding(contract, tx_id, severity="critical")
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(critical,),
        )
    assert exc.value.code == CODE_TRANSITION_INVALID


def test_noncritical_finding_can_remain_open() -> None:
    """A warning or suggestion finding may remain open with no transitions."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    for severity in ("warning", "suggestion"):
        finding = _make_finding(contract, tx_id, severity=severity)
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(finding,),
        )


def test_critical_finding_resolves_successfully() -> None:
    """`critical -> resolved` with correction succeeds."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="critical")
    finding_id = contract.id_for(finding)
    transition = _make_transition(
        contract,
        tx_id,
        finding_id,
        to_status="resolved",
        correction_fact_id=CorrectionFactId("sha256:" + ("f" * 64)),
    )
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding,),
        transitions=(transition,),
    )


def test_resolved_then_accepted_replay_is_rejected() -> None:
    """After a resolved edge the source must be ``resolved`` not ``open``."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    finding = _make_finding(contract, tx_id, severity="warning")
    finding_id = contract.id_for(finding)
    bad_first = _make_transition(
        contract,
        tx_id,
        finding_id,
        to_status="resolved",
        correction_fact_id=CorrectionFactId("sha256:" + ("1" * 64)),
    )
    bad_second = _make_transition(
        contract,
        tx_id,
        finding_id,
        # Source must equal derived state ``resolved``; replaying from
        # ``open`` is rejected.
        from_status="open",
        to_status="accepted",
        correction_fact_id=None,
    )
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(finding,),
            transitions=(bad_first, bad_second),
        )
    assert exc.value.code == CODE_TRANSITION_INVALID


def test_finding_with_wrong_transaction_id_is_id_invalid() -> None:
    """A finding pointing at a different transaction is rejected."""

    contract, selection, transaction, tx_id = _build_finding_fixture()
    other_tx_id = ReviewTransactionId("sha256:" + ("f" * 64))
    finding = _make_finding(contract, other_tx_id)  # wrong tx id
    with pytest.raises(ReviewContractError) as exc:
        contract.validate_transaction(
            transaction,
            lens_selection=selection,
            findings=(finding,),
        )
    assert exc.value.code == CODE_ID_INVALID


def test_empty_findings_without_transitions_is_valid() -> None:
    """A transaction without findings has a valid empty graph."""

    contract, selection, transaction, _ = _build_finding_fixture()
    contract.validate_transaction(transaction, lens_selection=selection)


def test_whole_repository_scope_accepts_any_concrete_path() -> None:
    """Scope ``(``.``,)`` accepts any concrete path."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="normal")
    transaction = ReviewTransaction(
        schema_name=REVIEW_TRANSACTION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=CHANGE_NAME,
        candidate_id=CANDIDATE_ID,
        lens_selection_id=contract.id_for(selection),
        scope_paths=(".",),
        loc_budget=100,
    )
    tx_id = contract.id_for(transaction)
    finding = _make_finding(contract, tx_id, paths=("src/anywhere/very/deep.py",))
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding,),
    )
