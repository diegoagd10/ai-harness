# Spec — Validation-blocked routing preserved

## Purpose

Keep archive unavailable when the authoritative validation envelope is absent, invalid, contradictory, or disapproving, while returning actionable routing diagnostics instead of storage exceptions.

## Requirements

### Requirement: Failed validation routes back
The system MUST reject archive approval when the envelope verdict is `fail`.

#### Scenario: Legacy fail verdict
GIVEN a structurally archive-ready legacy change whose well-formed envelope declares `verdict: fail`
WHEN `change_continue` derives the route
THEN archive is blocked, `nextRecommended` is `validate`, and `blockedReasons` explains the validation rejection

#### Scenario: Sliced fail verdict
GIVEN a structurally complete sliced change whose fresh root envelope declares `verdict: fail`
WHEN the terminal route is finalized
THEN archive is blocked, `nextRecommended` is `final-validate`, and a validation diagnostic is returned

### Requirement: Critical findings block archive
The system MUST reject archive approval whenever the validation envelope reports a critical count greater than `0`.

#### Scenario: Nonzero critical count
GIVEN an otherwise archive-ready change whose validation content reports one or more critical findings
WHEN routing or direct archive preflight evaluates validation
THEN archive is denied and a validation diagnostic is surfaced

### Requirement: Missing validation blocks archive
The system MUST treat a missing `validation.md` as a blocked validation condition rather than as archive approval.

#### Scenario: Legacy validation file absent
GIVEN a legacy change with complete tasks but no `validation.md`
WHEN `change_continue` derives the route
THEN `nextRecommended` is `validate` and `blockedReasons` identifies the missing validation artifact

#### Scenario: Direct archive validation file absent
GIVEN an otherwise complete change with no `validation.md`
WHEN direct archive preflight runs
THEN preflight rejects archive with a missing-validation error

### Requirement: Malformed and contradictory envelopes produce diagnostics
The system MUST convert validation parsing failures into blocked routing diagnostics and MUST NOT expose them as `ChangeStoreError`.

#### Scenario: Malformed Verdict section
GIVEN an otherwise archive-ready change whose `validation.md` has duplicate fields, unknown fields, malformed counts, or no valid `## Verdict` section
WHEN `change_continue` evaluates archive readiness
THEN it routes to `validate` or `final-validate` as appropriate and includes the parser-derived reason in `blockedReasons`

#### Scenario: Contradictory approved verdict
GIVEN `validation.md` declares `verdict: pass` or `pass-with-warnings` together with a nonzero critical count
WHEN archive readiness is evaluated
THEN the envelope is rejected as contradictory, archive remains blocked, and no `ChangeStoreError` is raised

#### Scenario: Unreadable validation artifact
GIVEN `validation.md` exists but file persistence reports an `OSError` while it is read
WHEN archive readiness is evaluated
THEN the operation returns a blocked diagnostic rather than propagating the read exception

### Requirement: Envelope grammar matches the validator contract
The parser MUST accept exactly one `verdict` and one `critical` field in the unfenced `## Verdict` section and MUST reject the removed `gate-run` field as unknown.

#### Scenario: Two-field envelope
GIVEN valid UTF-8 validation text with exactly `verdict: pass` and `critical: 0` in its sole unfenced `## Verdict` section
WHEN `parse_validation_envelope` parses the text
THEN it returns an approved envelope without requiring `gate-run`

#### Scenario: Legacy gate-run field
GIVEN otherwise valid validation text that also contains `gate-run:` in the Verdict section
WHEN `parse_validation_envelope` parses the text
THEN it raises `ReceiptError` for an unknown field

### Requirement: Negative tests avoid the user system
Validation-routing tests MUST use isolated temporary files; mocks MAY be used only to induce a file-persistence read failure and MUST NOT replace the parser or routing logic.

#### Scenario: Isolated negative suite
GIVEN the negative tests execute via `uv run pytest` on Python 3.12 or newer
WHEN missing, malformed, contradictory, and unreadable artifacts are exercised
THEN no test touches user-owned paths and any mock is limited to file persistence
