"""Negative routing tests for validation-envelope archive approval."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.modules.harness.change import (
    ChangeStoreError,
    change_approve,
    change_archive,
    change_continue,
)
from tests._change_flow_fixtures import ROUTED_PHASES, complete_capability, init_config, make_change, write_sliced_prd


@pytest.fixture(autouse=True)
def _config(tmp_path: Path) -> None:
    init_config(tmp_path, *ROUTED_PHASES)


def _legacy_terminal(root: Path, *, validation: str | None) -> Path:
    change_dir = root / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True)
    for filename in ("exploration.md", "prd.md", "design.md", "implementation.md"):
        (change_dir / filename).write_text(f"# {filename}\n", encoding="utf-8")
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "demo.md").write_text("# spec\n", encoding="utf-8")
    (change_dir / "tasks.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "1",
                        "title": "done",
                        "spec": "demo",
                        "phase": "implement",
                        "depends_on": [],
                        "status": "done",
                        "subtasks": [{"id": "1.1", "title": "done", "scenario": None, "status": "done"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    if validation is not None:
        (change_dir / "validation.md").write_text(validation, encoding="utf-8")
    return change_dir


def test_legacy_missing_validation_routes_to_validate_with_diagnostic(tmp_path: Path) -> None:
    _legacy_terminal(tmp_path, validation=None)

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "validate"
    assert any("validation.md is missing" in reason for reason in status.blockedReasons)


def test_sliced_missing_validation_routes_to_final_validate_with_diagnostic(tmp_path: Path) -> None:
    change_dir = make_change(tmp_path, "sliced")
    write_sliced_prd(
        change_dir,
        capabilities=[{"id": "only", "title": "Only", "level": "normal", "design": "none"}],
    )
    complete_capability(tmp_path, "sliced", "only")
    change_approve(tmp_path, "sliced")

    status = change_continue(tmp_path, "sliced")

    assert status.nextRecommended == "validate"
    assert status.sliceStatus is not None
    assert status.sliceStatus.route == "final-validate"
    assert any("validation.md is missing" in reason for reason in status.blockedReasons)


def test_unreadable_validation_routes_to_validate_with_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    change_dir = _legacy_terminal(
        tmp_path,
        validation="## Verdict\nverdict: pass\ncritical: 0\n",
    )
    validation_path = change_dir / "validation.md"
    original_read_bytes = Path.read_bytes

    def fail_validation_read(path: Path) -> bytes:
        if path == validation_path:
            raise OSError("simulated read failure")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_validation_read)

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "validate"
    assert any("unreadable" in reason and "simulated read failure" in reason for reason in status.blockedReasons)


@pytest.mark.parametrize(
    ("body", "diagnostic"),
    [
        ("verdict: pass\ncritical: 0\n", "validation.malformed"),
        ("## Verdict\nverdict: pass\ncritical: 1\n", "validation.contradictory"),
        ("## Verdict\nverdict: pass\ncritical: 0\nextra: value\n", "validation.malformed"),
    ],
)
def test_invalid_envelopes_route_to_validate_with_parser_diagnostic(
    tmp_path: Path,
    body: str,
    diagnostic: str,
) -> None:
    _legacy_terminal(tmp_path, validation=body)

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "validate"
    assert any(diagnostic in reason for reason in status.blockedReasons)


def test_direct_archive_rejects_nonzero_critical_verdict(tmp_path: Path) -> None:
    change_dir = _legacy_terminal(
        tmp_path,
        validation="## Verdict\nverdict: fail\ncritical: 3\n",
    )

    with pytest.raises(ChangeStoreError) as exc_info:
        change_archive(tmp_path, "demo")

    assert any("critical=3" in error for error in exc_info.value.errors)
    assert change_dir.is_dir()


def test_direct_archive_rejects_contradictory_envelope(tmp_path: Path) -> None:
    change_dir = _legacy_terminal(
        tmp_path,
        validation="## Verdict\nverdict: pass-with-warnings\ncritical: 2\n",
    )

    with pytest.raises(ChangeStoreError) as exc_info:
        change_archive(tmp_path, "demo")

    assert any("validation.contradictory" in error for error in exc_info.value.errors)
    assert change_dir.is_dir()
