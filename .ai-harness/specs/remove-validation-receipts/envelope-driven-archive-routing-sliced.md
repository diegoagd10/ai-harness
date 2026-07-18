# Spec — Envelope-driven archive routing (sliced)

## Purpose

Complete the sliced `final-validate` to `archive` transition from fresh root and capability validation artifacts, without receipt authorization.

## Requirements

### Requirement: Approved sliced validation reaches archive
The system MUST route a sliced change from `final-validate` to `archive` when every capability is complete, required capability validation files exist, and the fresh root validation envelope declares an approved zero-critical verdict.

#### Scenario: Sliced pass archives without receipt
GIVEN a sliced change in an isolated temporary change root with all capabilities complete, every required `validations/<cap>.md` artifact present, and a fresh root `validation.md` declaring `verdict: pass` and `critical: 0`
WHEN `change_continue` finalizes the terminal route
THEN `nextRecommended` is `archive` even though no receipt exists

#### Scenario: Sliced pass with warnings archives without receipt
GIVEN the same completed sliced state with a fresh root envelope declaring `verdict: pass-with-warnings` and `critical: 0`
WHEN `change_continue` finalizes the terminal route
THEN `nextRecommended` is `archive` without a gate-run or sealed receipt

### Requirement: Capability validation artifacts remain mandatory
The system MUST preserve the sliced requirement for per-capability validation artifacts.

#### Scenario: Missing capability validation
GIVEN all sliced capabilities are otherwise complete and root `validation.md` is an approved zero-critical pass but one required `validations/<cap>.md` is missing
WHEN `change_continue` derives the terminal route
THEN archive is not recommended and the existing capability-validation route is preserved

### Requirement: Root validation freshness remains mandatory
The system MUST preserve the existing mtime-based freshness check for sliced root validation.

#### Scenario: Stale root validation
GIVEN all sliced capabilities and validation artifacts are complete but root `validation.md` predates the latest continuation approval
WHEN `change_continue` finalizes the terminal route
THEN it routes to `final-validate` rather than `archive` and reports the existing freshness diagnostic

### Requirement: Sliced tests are isolated
Tests for sliced archive routing MUST create all PRD, capability, continuation, and validation artifacts under pytest-managed temporary paths and MUST NOT alter the user's system.

#### Scenario: Sliced regression execution
GIVEN the sliced routing tests run under Python 3.12 or newer via `uv run pytest`
WHEN the tests exercise the file-backed transition
THEN they use real temporary file persistence, do not mock routing internals, and leave user and repository state unchanged
