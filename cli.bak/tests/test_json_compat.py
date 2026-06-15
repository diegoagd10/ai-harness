"""JSON schema/order golden tests and byte-for-byte parity with the Go binary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness import compat
from ai_harness.sdd import resolve
from conftest import run_go_continue, run_go_status, seed_ready_change, write_file

# Top-level JSON keys in Go struct order. phaseInstructions is omitted unless
# --instructions is set, so it is excluded from the no-instructions golden order.
EXPECTED_KEY_ORDER = [
    "schemaName",
    "schemaVersion",
    "changeName",
    "artifactStore",
    "planningHome",
    "changeRoot",
    "artifactPaths",
    "contextFiles",
    "artifacts",
    "taskProgress",
    "dependencies",
    "applyState",
    "actionContext",
    "relationships",
    "nextRecommended",
    "blockedReasons",
]

ARTIFACT_KEY_ORDER = ["applyProgress", "design", "proposal", "specs", "tasks", "verifyReport"]


def _payload(tmp_path: Path, change: str = "thin", instructions: bool = False) -> dict:
    status = resolve(str(tmp_path), "", change, instructions)
    return json.loads(compat.status_to_json(status))


def test_top_level_key_order_matches_go_struct(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    assert list(_payload(tmp_path).keys()) == EXPECTED_KEY_ORDER


def test_artifacts_map_uses_go_sorted_key_order(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    assert list(_payload(tmp_path)["artifacts"].keys()) == ARTIFACT_KEY_ORDER


def test_phase_instructions_inserted_before_next_recommended(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    keys = list(_payload(tmp_path, instructions=True).keys())
    assert keys.index("phaseInstructions") == keys.index("nextRecommended") - 1


def test_empty_collections_are_arrays_not_null(tmp_path: Path):
    write_file(tmp_path / "openspec" / "changes" / "thin" / "tasks.md", "- [ ] 1.1 Work\n")
    payload = _payload(tmp_path)
    assert payload["artifactPaths"]["specs"] == []
    assert payload["blockedReasons"] != []  # has reasons here, but is a list
    assert payload["relationships"]["dependsOn"] == []


def test_unresolved_change_name_and_root_are_null(tmp_path: Path):
    payload = _payload(tmp_path, change="")  # no changes -> blocked
    assert payload["changeName"] is None
    assert payload["changeRoot"] is None


# --- byte-for-byte parity against the reference Go binary ----------------------


def _seed_html_chars_in_name(r: Path) -> None:
    # &, <, > in the change name flow into changeName/changeRoot/paths; Go
    # HTML-escapes them in JSON and the Python serializer must match.
    seed_ready_change(r, "a&b<c>d", "- [ ] 1.1 Work\n")


def _seed_unicode_adjacent_keyword(r: Path) -> None:
    # "TODOé": a fail/pending keyword adjacent to a non-ASCII letter. Go's RE2
    # \b is ASCII so it blocks; Python must too (re.ASCII), keeping next=verify.
    change_root = seed_ready_change(r, "thin", "- [x] 1.1 Work\n")
    write_file(change_root / "verify-report.md", "# Verify\nPASS\nTODOé marker\n")


def _seed_non_utf8_tasks(r: Path) -> None:
    # Invalid UTF-8 bytes must not crash (Go reads lossily and exits 0).
    change_root = seed_ready_change(r, "thin", "- [x] 1.1 Work\n")
    (change_root / "tasks.md").write_bytes(b"\xff\xfe\n- [x] 1.1 Work\n")
    write_file(change_root / "verify-report.md", "# Verify\nPASS\n")


PARITY_FIXTURES = {
    "complete-archive-ready": lambda r: write_file(
        seed_ready_change(r, "thin", "- [x] 1.1 Work\n") / "verify-report.md",
        "# Verify\nPASS\n",
    ),
    "partial-apply-ready": lambda r: seed_ready_change(r, "thin", "- [ ] 1.1 Work\n"),
    "invalid-no-changes-dir": lambda r: None,
    "blocked-core-missing": lambda r: write_file(
        r / "openspec" / "changes" / "thin" / "tasks.md", "- [ ] 1.1 Work\n"
    ),
    "html-chars-in-change-name": _seed_html_chars_in_name,
    "unicode-adjacent-keyword": _seed_unicode_adjacent_keyword,
    "non-utf8-tasks-file": _seed_non_utf8_tasks,
}


@pytest.mark.parametrize("fixture", list(PARITY_FIXTURES), ids=list(PARITY_FIXTURES))
@pytest.mark.parametrize(
    "command,instructions",
    [
        ("sdd-status", False),
        ("sdd-status", True),
        ("sdd-continue", False),
        ("sdd-continue", True),
    ],
    ids=[
        "sdd-status-plain",
        "sdd-status-instructions",
        "sdd-continue-plain",
        "sdd-continue-instructions",
    ],
)
def test_json_matches_go_binary(
    go_cli, tmp_path: Path, fixture: str, command: str, instructions: bool
):
    PARITY_FIXTURES[fixture](tmp_path)

    # Go's sdd-continue always includes instructions (--instructions is accepted
    # and ignored); the Python resolver must mirror that, regardless of the flag.
    if command == "sdd-continue":
        go = run_go_continue(go_cli, tmp_path, "--json", "--cwd", str(tmp_path))
        include_instructions = True
    else:
        go_args = ["--json", "--cwd", str(tmp_path)]
        if instructions:
            go_args.append("--instructions")
        go = run_go_status(go_cli, tmp_path, *go_args)
        include_instructions = instructions
    assert go.returncode == 0, go.stderr

    status = resolve(str(tmp_path), "", "", include_instructions)
    py_json = compat.status_to_json(status)

    assert py_json == go.stdout.rstrip("\n")
