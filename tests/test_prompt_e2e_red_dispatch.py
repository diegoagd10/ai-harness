"""tests/test_prompt_e2e_red_dispatch.py — host-side RED dispatch driver.

# Per-fixture routing contract (LOCKED — must mirror test_prompt_e2e_red.py)

| Fixture id             | Category         | bash change-* | task sub | Final assistant text                       |
| ---------------------- | ---------------- | ------------- | -------- | ----------------------------------------- |
| fibonacci-ES           | small/concrete   | must NOT fire | NOT fire | (any; orchestrator answers directly)      |
| mario-kart-3d-vague    | ambiguous/large  | NOT fire (new)| NOT fire | MUST contain "?"; NOT contain "change-new"|
| mario-kart-3d-complete | complete/large   | new MUST fire OR task MUST fire (OR-fence) | (any) | (any) |

If the contract changes, BOTH this file AND tests/test_prompt_e2e_red.py
MUST change together — the shared semantics are enforced by both files
calling the same `_e2e_assertions` helpers.

# Why this file exists alongside tests/test_prompt_e2e_red.py

The Docker-side RED suite (tests/test_prompt_e2e_red.py) runs inside
the tests-prompts container harness. This dispatch driver runs the
SAME per-fixture contract directly on the host as a `subprocess.run`
call, mirroring the pattern at
`tests/test_prompt_tests_extractor.py::test_hello_prompt_live_with_minimax_m3`.

Use cases:
  - Worktree where Docker isn't available
  - Local development without rebuilding the test image
  - Debugging a single fixture in isolation

# Gate

Same gate as tests/test_prompt_e2e_red.py:
  - env var `PROMPT_E2E_RED == "1"` AND
  - `shutil.which("opencode")` is non-None

# Docker-free

This file MUST NOT import docker, the tests-prompts Dockerfile, or
the in-container run.sh. It is purely subprocess + the helpers in
`tests-prompts/_e2e_assertions.py`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_OPENCODE_AVAILABLE = shutil.which("opencode") is not None

pytestmark = pytest.mark.skipif(
    not (os.environ.get("PROMPT_E2E_RED") == "1" and _OPENCODE_AVAILABLE),
    reason=(
        "PROMPT_E2E_RED=1 env var is unset OR `opencode` is not on PATH. "
        "Live RED dispatch driver is off by default to keep CI cost flat."
    ),
)


_PINNED_MODEL = "minimax/MiniMax-M3"
_AGENT_NAME = "change-orchestrator"

_FIXTURE_FIBONACCI = (
    "Crea fibonnaci en javascript en este directorio para aprender el algoritmo y ver el codigo de manera recursiva"
)
_FIXTURE_VAGUE = "Crea juego de mario karn en 3d"
_FIXTURE_COMPLETE = (
    "Build a 3D Mario Kart-style racing game using Three.js. "
    "Requirements: at least 3 race tracks, a character select screen "
    "with 4 drivers, power-ups, AI opponents, and split-screen "
    "multiplayer controls. Add a main menu, lap counter, and "
    "minimap. Include physics for drifting and item boxes."
)


def _load_helpers():
    """Lazy-load _e2e_assertions from tests-prompts/."""
    import importlib.util

    helpers_dir = Path(__file__).resolve().parent.parent / "tests-prompts"
    spec = importlib.util.spec_from_file_location("_e2e_assertions", helpers_dir / "_e2e_assertions.py")
    assert spec and spec.loader, "could not load _e2e_assertions.py"
    module = importlib.util.module_from_spec(spec)
    sys.modules["_e2e_assertions"] = module
    spec.loader.exec_module(module)
    return module


def _run_opencode(prompt: str, work_dir: Path, timeout: int = 180) -> list[dict]:
    """Invoke `opencode run` as a host subprocess and parse stdout.

    Mirrors tests/test_prompt_tests_extractor.py:165-178
    (test_hello_prompt_live_with_minimax_m3) so the host worktree
    driver inherits the lessons learned there.
    """
    cmd = [
        "opencode",
        "run",
        "--agent",
        _AGENT_NAME,
        "--auto",
        "--format",
        "json",
        "--model",
        _PINNED_MODEL,
        "--dir",
        str(work_dir),
        "--title",
        f"prompt-e2e-red-dispatch-{work_dir.name}",
        prompt,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    events: list[dict] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            events.append(json.loads(stripped))
        except (ValueError, TypeError):
            continue
    return events


def _dump_failure_trace(events: list[dict], fixture_id: str) -> str:
    """Format the captured event list for the pytest failure report."""
    if not events:
        return f"<no events captured for fixture={fixture_id}>"
    formatted: list[str] = []
    for idx, event in enumerate(events):
        text = json.dumps(event, indent=2, sort_keys=True)
        keep = "?" in text or "ai-harness" in text
        if not keep and len(text) > 800:
            text = text[:800] + "... <truncated>"
        formatted.append(f"[event {idx}] {text}")
    return "\n".join(formatted)


def _last_assistant_text(events: list[dict]) -> str | None:
    """Return the LAST text event payload; None if no text events."""
    last: str | None = None
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") not in ("text", "assistant_message"):
            continue
        part = event.get("part") or {}
        if not isinstance(part, dict):
            continue
        if part.get("type") != "text":
            continue
        text = part.get("text")
        if isinstance(text, str):
            last = text
    return last


# ---------------------------------------------------------------------------
# Tests — one per fixture, mirroring tests/test_prompt_e2e_red.py
# ---------------------------------------------------------------------------


class TestFibonacciRouteDispatch:
    """fibonacci-ES via host subprocess: orchestrator must answer directly."""

    def test_fibonacci_es_routes_to_answer_directly(self, tmp_path: Path) -> None:
        e2e = _load_helpers()
        events = _run_opencode(_FIXTURE_FIBONACCI, tmp_path)
        assert e2e.has_bash_ai_harness_change(events, "change-new") is False, (
            f"fibonacci-ES must NOT fire `bash ai-harness change-new`; "
            f"got events:\n{_dump_failure_trace(events, 'fibonacci-ES')}"
        )
        assert e2e.has_bash_ai_harness_change(events, "change-continue") is False, (
            f"fibonacci-ES must NOT fire `bash ai-harness change-continue`; "
            f"got events:\n{_dump_failure_trace(events, 'fibonacci-ES')}"
        )
        assert e2e.has_task_subagent(events) is False, (
            f"fibonacci-ES must NOT spawn a task subagent; got events:\n{_dump_failure_trace(events, 'fibonacci-ES')}"
        )


class TestVagueRouteDispatch:
    """mario-kart-3d-vague via host subprocess: orchestrator must grill first."""

    def test_mario_kart_3d_vague_grills_first(self, tmp_path: Path) -> None:
        e2e = _load_helpers()
        events = _run_opencode(_FIXTURE_VAGUE, tmp_path)
        assert e2e.has_bash_ai_harness_change(events, "change-new") is False, (
            f"vague must NOT fire `bash ai-harness change-new`; "
            f"got events:\n{_dump_failure_trace(events, 'mario-kart-3d-vague')}"
        )
        assert e2e.has_task_subagent(events) is False, (
            f"vague must NOT spawn a task subagent; got events:\n{_dump_failure_trace(events, 'mario-kart-3d-vague')}"
        )
        assert e2e.final_assistant_text_contains(events, "?") is True, (
            f"vague final text must contain `?`; got events:\n{_dump_failure_trace(events, 'mario-kart-3d-vague')}"
        )
        last_text = _last_assistant_text(events)
        assert last_text is not None, (
            f"vague must produce at least one assistant text event; "
            f"got events:\n{_dump_failure_trace(events, 'mario-kart-3d-vague')}"
        )
        assert "change-new" not in last_text, (
            f"vague final text must NOT contain `change-new`; "
            f"got: {last_text!r}; full events:\n"
            f"{_dump_failure_trace(events, 'mario-kart-3d-vague')}"
        )


class TestCompleteRouteDispatch:
    """mario-kart-3d-complete via host subprocess: change-new OR task fires."""

    def test_mario_kart_3d_complete_starts_change_flow(self, tmp_path: Path) -> None:
        e2e = _load_helpers()
        events = _run_opencode(_FIXTURE_COMPLETE, tmp_path)
        change_new_fired = e2e.has_bash_ai_harness_change(events, "change-new")
        task_fired = e2e.has_task_subagent(events)
        assert change_new_fired or task_fired, (
            f"complete must fire `bash ai-harness change-new` OR spawn a "
            f"`task` subagent; neither fired. Events:\n"
            f"{_dump_failure_trace(events, 'mario-kart-3d-complete')}"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
