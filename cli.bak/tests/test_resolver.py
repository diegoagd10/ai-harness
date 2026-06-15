"""Resolver parity: change selection, artifact classification, state-machine gates.

Ported from the Go sdd_test.go and gates_test.go tables.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_harness.sdd import resolve
from conftest import mkdir, seed_ready_change, write_file


def _resolve(root: Path, change: str = "thin"):
    return resolve(str(root), "", change, False)


# --- change selection ---------------------------------------------------------


def test_no_active_change_blocks_with_sdd_new(tmp_path: Path):
    mkdir(tmp_path / "openspec" / "changes")
    status = resolve(str(tmp_path), "", "", False)
    assert status.change_name is None
    assert status.next_recommended == "sdd-new"
    assert "No active OpenSpec changes" in "\n".join(status.blocked_reasons)


def test_ambiguous_changes_block_with_select_change(tmp_path: Path):
    mkdir(tmp_path / "openspec" / "changes" / "first")
    mkdir(tmp_path / "openspec" / "changes" / "second")
    status = resolve(str(tmp_path), "", "", False)
    assert status.next_recommended == "select-change"
    assert "ambiguous: first, second" in "\n".join(status.blocked_reasons)


def test_explicit_missing_change_blocks_with_sdd_new(tmp_path: Path):
    mkdir(tmp_path / "openspec" / "changes" / "real")
    status = resolve(str(tmp_path), "", "missing", False)
    assert status.change_name == "missing"
    assert status.next_recommended == "sdd-new"
    assert "not found: missing" in "\n".join(status.blocked_reasons)


def test_single_active_change_is_inferred(tmp_path: Path):
    seed_ready_change(tmp_path, "add-auth", "- [ ] 1.1 Wire routes\n")
    status = resolve(str(tmp_path), "", "", False)
    assert status.change_name == "add-auth"
    assert status.next_recommended == "apply"


def test_archive_directory_is_excluded(tmp_path: Path):
    mkdir(tmp_path / "openspec" / "changes" / "archive" / "2026-01-01-old")
    seed_ready_change(tmp_path, "only", "- [ ] 1.1 Work\n")
    status = resolve(str(tmp_path), "", "", False)
    assert status.change_name == "only"
    assert status.next_recommended == "apply"


# --- artifact states + task progress ------------------------------------------


def test_artifact_states_and_task_progress(tmp_path: Path):
    change_root = seed_ready_change(
        tmp_path,
        "add-auth",
        "\n".join(
            [
                "# Tasks",
                "",
                "- [x] 1.1 Build foundation",
                "- [X] 1.2 Add API",
                "- [ ] 1.3 Wire routes",
                "plain [ ] note is ignored",
                "",
            ]
        ),
    )
    write_file(change_root / "apply-progress.md", "# Apply\n")

    status = resolve(str(tmp_path), "", "add-auth", False)
    assert status.artifacts["proposal"] == "done"
    assert status.artifacts["specs"] == "done"
    assert status.artifacts["design"] == "done"
    assert status.artifacts["tasks"] == "done"
    assert status.artifacts["applyProgress"] == "done"
    assert status.artifacts["verifyReport"] == "missing"

    tp = status.task_progress
    assert (tp.total, tp.completed, tp.pending, tp.all_complete) == (3, 2, 1, False)
    assert status.dependencies.verify == "ready"  # apply-progress present


def test_partial_and_missing_states(tmp_path: Path):
    change_root = tmp_path / "openspec" / "changes" / "thin"
    write_file(change_root / "proposal.md", "   \n")  # blank -> partial
    write_file(change_root / "tasks.md", "- [ ] 1.1 Work\n")
    write_file(change_root / "specs" / "auth" / "notes.md", "notes\n")  # no spec.md -> partial

    status = _resolve(tmp_path)
    assert status.artifacts["proposal"] == "partial"
    assert status.artifacts["design"] == "missing"
    assert status.artifacts["specs"] == "partial"
    assert status.artifacts["tasks"] == "done"
    assert status.apply_state == "blocked"


def test_blank_spec_file_is_partial(tmp_path: Path):
    change_root = seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    write_file(change_root / "specs" / "auth" / "spec.md", "  \n")
    status = _resolve(tmp_path)
    assert status.artifacts["specs"] == "partial"


def test_missing_specs_dir_is_not_an_error(tmp_path: Path):
    # No specs/ at all -> empty/missing, resolves cleanly (Go: WalkDir not-exist
    # is swallowed). Guards that error propagation did not break the happy path.
    write_file(tmp_path / "openspec" / "changes" / "thin" / "tasks.md", "- [ ] 1.1 Work\n")
    status = _resolve(tmp_path)
    assert status.artifacts["specs"] == "missing"


def test_specs_as_file_is_missing_not_error(tmp_path: Path):
    # specs is a regular file, not a directory -> empty/missing, no error (Go parity).
    change_root = tmp_path / "openspec" / "changes" / "thin"
    write_file(change_root / "tasks.md", "- [ ] 1.1 Work\n")
    write_file(change_root / "specs", "not a directory\n")
    status = _resolve(tmp_path)
    assert status.artifacts["specs"] == "missing"


@pytest.mark.parametrize("locked_subpath", ["specs", "specs/locked"], ids=["root", "subdir"])
def test_unreadable_specs_propagates_as_error(tmp_path: Path, locked_subpath: str):
    # A permission-denied specs root OR subdir must surface as a resolution error
    # (exit 1 in the CLI), matching Go's filepath.WalkDir which propagates the read
    # error (only os.IsNotExist is swallowed).
    change_root = seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    locked = change_root / locked_subpath
    locked.mkdir(parents=True, exist_ok=True)
    locked.chmod(0o000)
    try:
        if os.access(locked, os.R_OK):  # running as root ignores perms
            pytest.skip("cannot revoke read permission as this user")
        with pytest.raises(PermissionError):
            _resolve(tmp_path)
    finally:
        locked.chmod(0o755)


def test_tasks_done_but_no_checkboxes_blocks(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "# Tasks\n\nProse only, no checkboxes.\n")
    status = _resolve(tmp_path)
    assert status.task_progress.total == 0
    assert "tasks.md has no markdown task checkboxes." in "\n".join(status.blocked_reasons)
    assert status.apply_state == "blocked"


def test_next_recommended_is_stable_token_not_prose(tmp_path: Path):
    write_file(tmp_path / "openspec" / "changes" / "thin" / "tasks.md", "- [ ] 1.1 Work\n")
    status = _resolve(tmp_path)
    assert status.next_recommended == "resolve-blockers"
    assert "proposal.md is missing or partial." in "\n".join(status.blocked_reasons)


# --- apply/verify/archive gates -----------------------------------------------

_PASS_MATRIX = "\n".join(
    [
        "## Verification Report",
        "### Build & Tests Execution",
        "**Tests**: ✅ 12 passed / ❌ 0 failed / ⚠️ 0 skipped",
        "failed: 0",
        "### Issues Found",
        "**CRITICAL**: None",
        "No blockers",
        "### Verdict",
        "Verdict: PASS",
        "",
    ]
)

_PASS_WARN = "\n".join(
    [
        "## Verification Report",
        "**Tests**: ✅ 12 passed / ❌ 0 failed / ⚠️ 1 skipped",
        "**CRITICAL**: None",
        "**WARNING**: flaky integration was skipped",
        "### Verdict",
        "PASS WITH WARNINGS",
        "",
    ]
)

_UNTESTED_MATRIX = "\n".join(
    [
        "## Verification Report",
        "### Spec Compliance Matrix",
        "| Requirement | Scenario | Test | Result |",
        "|-------------|----------|------|--------|",
        "| REQ-01 | Covers auth | (none found) | ❌ UNTESTED |",
        "### Verdict",
        "Verdict: PASS",
        "",
    ]
)

_FAILING_MATRIX = "\n".join(
    [
        "## Verification Report",
        "### Spec Compliance Matrix",
        "| Requirement | Scenario | Test | Result |",
        "|-------------|----------|------|--------|",
        "| REQ-01 | Covers auth | `auth_test.go > TestAuth` | ❌ FAILING |",
        "### Verdict",
        "Verdict: PASS",
        "",
    ]
)


def _seed_core_missing(root: Path) -> None:
    write_file(root / "openspec" / "changes" / "thin" / "tasks.md", "- [ ] 1.1 Work\n")


def _seed_apply_progress(root: Path) -> None:
    change_root = seed_ready_change(root, "thin", "- [x] 1.1 Done\n- [ ] 1.2 Remaining\n")
    write_file(change_root / "apply-progress.md", "# Apply\n")


def _seed_stale_bad_report(root: Path) -> None:
    change_root = seed_ready_change(root, "thin", "- [x] 1.1 Done\n- [ ] 1.2 Remaining\n")
    write_file(change_root / "verify-report.md", "# Verify\nVerdict: PASS\nfailed: 1\n")


def _seed_with_report(content: str):
    def seed(root: Path) -> None:
        change_root = seed_ready_change(root, "thin", "- [x] 1.1 Work\n")
        write_file(change_root / "verify-report.md", content)

    return seed


# name, seed, apply, applyDep, verify, archive, next, blocked-substr, blocked-absent
GATES = [
    (
        "core missing",
        _seed_core_missing,
        "blocked",
        "blocked",
        "blocked",
        "blocked",
        "resolve-blockers",
        "proposal.md is missing or partial.",
        None,
    ),
    (
        "apply ready",
        lambda r: seed_ready_change(r, "thin", "- [ ] 1.1 Work\n"),
        "ready",
        "ready",
        "blocked",
        "blocked",
        "apply",
        None,
        None,
    ),
    (
        "apply all done verify ready",
        lambda r: seed_ready_change(r, "thin", "- [x] 1.1 Work\n"),
        "all_done",
        "all_done",
        "ready",
        "blocked",
        "verify",
        None,
        None,
    ),
    (
        "apply progress verify ready",
        _seed_apply_progress,
        "ready",
        "ready",
        "ready",
        "blocked",
        "apply",
        None,
        None,
    ),
    (
        "apply ready ignores stale report",
        _seed_stale_bad_report,
        "ready",
        "ready",
        "blocked",
        "blocked",
        "apply",
        None,
        "verify-report.md is not clearly passing.",
    ),
    (
        "archive ready bare pass",
        _seed_with_report("# Verify\nPASS\n"),
        "all_done",
        "all_done",
        "all_done",
        "ready",
        "archive",
        None,
        None,
    ),
    (
        "archive ready canonical matrix",
        _seed_with_report(_PASS_MATRIX),
        "all_done",
        "all_done",
        "all_done",
        "ready",
        "archive",
        None,
        None,
    ),
    (
        "archive ready pass with warnings",
        _seed_with_report(_PASS_WARN),
        "all_done",
        "all_done",
        "all_done",
        "ready",
        "archive",
        None,
        None,
    ),
    (
        "archive blocked critical",
        _seed_with_report("# Verify\ncritical: archive blocker\n"),
        "all_done",
        "all_done",
        "ready",
        "blocked",
        "verify",
        "verify-report.md is not clearly passing.",
        None,
    ),
    (
        "archive blocked failed count",
        _seed_with_report("# Verify\nVerdict: PASS\nfailed: 1\n"),
        "all_done",
        "all_done",
        "ready",
        "blocked",
        "verify",
        "verify-report.md is not clearly passing.",
        None,
    ),
    (
        "archive blocked untested matrix",
        _seed_with_report(_UNTESTED_MATRIX),
        "all_done",
        "all_done",
        "ready",
        "blocked",
        "verify",
        "verify-report.md is not clearly passing.",
        None,
    ),
    (
        "archive blocked failing matrix",
        _seed_with_report(_FAILING_MATRIX),
        "all_done",
        "all_done",
        "ready",
        "blocked",
        "verify",
        "verify-report.md is not clearly passing.",
        None,
    ),
    (
        "archive blocked blockers present",
        _seed_with_report("# Verify\nVerdict: PASS\nBlockers: missing evidence\n"),
        "all_done",
        "all_done",
        "ready",
        "blocked",
        "verify",
        "verify-report.md is not clearly passing.",
        None,
    ),
    (
        "archive blocked todo pending",
        _seed_with_report(
            "# Verify\nPASS\nTODO: finish audit\nPENDING: test run\n"
            "Verification blocker: missing evidence\n"
        ),
        "all_done",
        "all_done",
        "ready",
        "blocked",
        "verify",
        "verify-report.md is not clearly passing.",
        None,
    ),
    (
        "archive blocked status not passed",
        _seed_with_report("# Verify\nStatus: not passed\n"),
        "all_done",
        "all_done",
        "ready",
        "blocked",
        "verify",
        "verify-report.md is not clearly passing.",
        None,
    ),
    (
        "archive blocked pass no",
        _seed_with_report("# Verify\nPASS: no\n"),
        "all_done",
        "all_done",
        "ready",
        "blocked",
        "verify",
        "verify-report.md is not clearly passing.",
        None,
    ),
    (
        "archive blocked success and failure",
        _seed_with_report("# Verify\nStatus: SUCCESS\nFailure: build broke\n"),
        "all_done",
        "all_done",
        "ready",
        "blocked",
        "verify",
        "verify-report.md is not clearly passing.",
        None,
    ),
    (
        "archive ready status pass",
        _seed_with_report("# Verify\nStatus: PASS\n"),
        "all_done",
        "all_done",
        "all_done",
        "ready",
        "archive",
        None,
        None,
    ),
]


@pytest.mark.parametrize(
    "name, seed, apply, apply_dep, verify, archive, nxt, blocked, blocked_absent",
    GATES,
    ids=[g[0] for g in GATES],
)
def test_apply_verify_archive_gates(
    tmp_path, name, seed, apply, apply_dep, verify, archive, nxt, blocked, blocked_absent
):
    seed(tmp_path)
    status = _resolve(tmp_path)
    assert status.apply_state == apply
    assert status.dependencies.apply == apply_dep
    assert status.dependencies.verify == verify
    assert status.dependencies.archive == archive
    assert status.next_recommended == nxt
    joined = "\n".join(status.blocked_reasons)
    if blocked is not None:
        assert blocked in joined
    if blocked_absent is not None:
        assert blocked_absent not in joined
