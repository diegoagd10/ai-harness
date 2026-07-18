"""Behavior tests for the strict validation verdict envelope."""

from __future__ import annotations

import pytest

from ai_harness.modules.harness.receipts import (
    ReceiptError,
    ValidationEnvelope,
    parse_validation_envelope,
)


@pytest.mark.parametrize("verdict", ["pass", "pass-with-warnings"])
def test_parse_validation_approves_zero_critical_pass_verdicts(verdict: str) -> None:
    envelope = parse_validation_envelope(f"# Validation\n\n## Verdict\nverdict: {verdict}\ncritical: 0\n")

    assert envelope == ValidationEnvelope(verdict=verdict, critical=0, approved=True)


def test_parse_validation_preserves_well_formed_denial() -> None:
    envelope = parse_validation_envelope("## Verdict\nverdict: fail\ncritical: 3\n")

    assert envelope == ValidationEnvelope(verdict="fail", critical=3, approved=False)


@pytest.mark.parametrize(
    "body",
    [
        "verdict: pass\ncritical: 0\n",
        "## Verdict\nverdict: pass\n",
        "## Verdict\nverdict: pass\ncritical: 0\nextra: noise\n",
        "## Verdict\nverdict: pass\nverdict: pass\ncritical: 0\n",
        "## Verdict\nverdict: maybe\ncritical: 0\n",
        "\ufeff## Verdict\nverdict: pass\ncritical: 0\n",
    ],
)
def test_parse_validation_rejects_malformed_envelopes(body: str) -> None:
    with pytest.raises(ReceiptError) as exc_info:
        parse_validation_envelope(body)

    assert exc_info.value.code == "validation.malformed"


def test_parse_validation_rejects_legacy_gate_run_field() -> None:
    body = f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: sha256:{'a' * 64}\n"

    with pytest.raises(ReceiptError) as exc_info:
        parse_validation_envelope(body)

    assert exc_info.value.code == "validation.malformed"


@pytest.mark.parametrize(
    "body",
    [
        "## Verdict\nverdict: pass\ncritical: 1\n",
        "## Verdict\nverdict: pass-with-warnings\ncritical: 2\n",
        "## Verdict\nverdict: fail\ncritical: 0\n",
    ],
)
def test_parse_validation_rejects_contradictory_verdicts(body: str) -> None:
    with pytest.raises(ReceiptError) as exc_info:
        parse_validation_envelope(body)

    assert exc_info.value.code == "validation.contradictory"


def test_parse_validation_rejects_leading_zero_critical() -> None:
    with pytest.raises(ReceiptError) as exc_info:
        parse_validation_envelope("## Verdict\nverdict: fail\ncritical: 01\n")

    assert exc_info.value.code == "validation.malformed"


def test_parse_validation_rejects_invalid_utf8() -> None:
    with pytest.raises(ReceiptError) as exc_info:
        parse_validation_envelope(b"## Verdict\nverdict: pass\ncritical: 0\n\xff")

    assert exc_info.value.code == "validation.malformed"
