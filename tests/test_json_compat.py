"""JSON contract: applyReport sorted lexically, applyProgress absent, camelCase order,
HTML escapes, 2-space indent, non-null empty lists per spec R7.

Ported from cli.bak/tests/test_json_compat.py, stripped of Go parity tests,
sdd-continue tests, and --instructions tests (all out of scope).
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_harness import compat
from ai_harness.sdd import resolve
from conftest import seed_ready_change, write_file

# Top-level JSON keys in Go struct order. phaseInstructions is omitted in this
# slice (--instructions deferred), so it is excluded from the golden order.
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

# Artifact map keys sorted lexically (Go map key order). applyReport replaces applyProgress.
ARTIFACT_KEY_ORDER = ["applyReport", "design", "proposal", "specs", "tasks", "verifyReport"]


def _payload(tmp_path: Path, change: str = "thin") -> dict:
    status = resolve(str(tmp_path), "", change)
    return json.loads(compat.status_to_json(status))


def test_top_level_key_order_matches_go_struct(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    assert list(_payload(tmp_path).keys()) == EXPECTED_KEY_ORDER


def test_artifacts_map_uses_go_sorted_key_order(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    assert list(_payload(tmp_path)["artifacts"].keys()) == ARTIFACT_KEY_ORDER


def test_empty_collections_are_arrays_not_null(tmp_path: Path):
    write_file(tmp_path / "openspec" / "changes" / "thin" / "tasks.md", "- [ ] 1.1 Work\n")
    payload = _payload(tmp_path)
    assert payload["artifactPaths"]["specs"] == []
    assert isinstance(payload["blockedReasons"], list)
    assert payload["relationships"]["dependsOn"] == []


def test_unresolved_change_name_and_root_are_null(tmp_path: Path):
    payload = _payload(tmp_path, change="")  # no changes -> blocked
    assert payload["changeName"] is None
    assert payload["changeRoot"] is None


def test_apply_report_appears_in_artifact_paths(tmp_path: Path):
    """applyReport key must exist in artifactPaths; applyProgress must be absent."""
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    payload = _payload(tmp_path)
    assert "applyReport" in payload["artifactPaths"]
    assert "applyProgress" not in payload["artifactPaths"]


def test_apply_report_appears_in_artifacts_map(tmp_path: Path):
    """applyReport key must exist in artifacts map; applyProgress must be absent."""
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    payload = _payload(tmp_path)
    assert "applyReport" in payload["artifacts"]
    assert "applyProgress" not in payload["artifacts"]


def test_html_escape_in_change_name(tmp_path: Path):
    """&, <, > in change name must be HTML-escaped in JSON output."""
    seed_ready_change(tmp_path, "a&b<c>d", "- [ ] 1.1 Work\n")
    payload = _payload(tmp_path, change="a&b<c>d")
    assert payload["changeName"] == "a&b<c>d"
    # The raw JSON string must contain escaped forms
    raw = compat.status_to_json(resolve(str(tmp_path), "", "a&b<c>d"))
    assert "\\u0026" in raw
    assert "\\u003c" in raw
    assert "\\u003e" in raw


# --- phaseInstructions serialization ----------------------------------------


def test_phase_instructions_present_when_populated(tmp_path: Path):
    from ai_harness.sdd.models import PhaseInstructions as PI

    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    status = resolve(str(tmp_path), "", "thin")
    status.phase_instructions = PI(
        apply=["Change: thin", "State: ready", "hint1", "hint2"],
        verify=["Change: thin", "State: blocked", "hint3", "hint4"],
        archive=["Change: thin", "State: blocked", "hint5"],
    )
    raw = compat.status_to_json(status)
    payload = json.loads(raw)

    assert "phaseInstructions" in payload
    # Must appear before nextRecommended in the JSON output
    assert raw.index('"phaseInstructions"') < raw.index('"nextRecommended"')
    assert payload["phaseInstructions"]["apply"] == [
        "Change: thin",
        "State: ready",
        "hint1",
        "hint2",
    ]
    assert payload["phaseInstructions"]["verify"] == [
        "Change: thin",
        "State: blocked",
        "hint3",
        "hint4",
    ]
    assert payload["phaseInstructions"]["archive"] == ["Change: thin", "State: blocked", "hint5"]


def test_phase_instructions_absent_when_none(tmp_path: Path):
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    status = resolve(str(tmp_path), "", "thin")
    assert status.phase_instructions is None
    raw = compat.status_to_json(status)
    payload = json.loads(raw)

    assert "phaseInstructions" not in payload


def test_phase_instructions_absent_from_key_order_when_none(tmp_path: Path):
    """When phase_instructions is None, the key must not appear in the expected
    key order (first-slice behavior is preserved)."""
    seed_ready_change(tmp_path, "thin", "- [ ] 1.1 Work\n")
    payload = _payload(tmp_path)
    assert "phaseInstructions" not in payload
    assert list(payload.keys()) == EXPECTED_KEY_ORDER
