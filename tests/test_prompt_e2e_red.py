"""tests/test_prompt_e2e_red.py — live RED pytest surface for the
change-orchestrator prompt regression contract.

# Per-fixture routing contract (LOCKED — do not edit without a PRD)

| Fixture id             | Category         | bash change-* | task sub | Final assistant text                       |
| ---------------------- | ---------------- | ------------- | -------- | ----------------------------------------- |
| fibonacci-ES           | small/concrete   | must NOT fire | NOT fire | (any; orchestrator answers directly)      |
| mario-kart-3d-vague    | ambiguous/large  | NOT fire (new)| NOT fire | MUST contain "?"; NOT contain "change-new"|
| mario-kart-3d-complete | complete/large   | new MUST fire OR task MUST fire (OR-fence) | (any) | (any) |

The table is the spec. The asserts below enforce it.

# Gate

This file is the LIVE RED surface. Each test spawns a fresh
`opencode run --agent change-orchestrator …` subprocess against a
per-test `tmp_path`. The tests run ONLY when BOTH:
  - the env var `PROMPT_E2E_RED == "1"` is set
  - `opencode` is resolvable on `PATH` via `shutil.which`

The gate exists to keep CI cost flat until the follow-up change
that edits `src/ai_harness/resources/change-agent/change-orchestrator.md`
flips the env on at apply time. Without the gate, the live tests
would run on every PR and cost real model tokens.

# Per-test isolation

Each test invokes the orchestrator with `--dir <tmp_path>` (the
pytest tmp_path fixture) so any `.ai-harness/changes/<name>/` the
complete-fixture run might create dies with the test's temp dir.
No host mutation, no cross-test state.

# Failure-path dump

When an assertion fails, the captured JSON event list is dumped to
the pytest failure report so the regression is debuggable from the
report alone (mirrors `dump_failure_trace` in run.sh:222-235).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module-level skip gate — both conditions must hold for the suite to run.
# A read-only `shutil.which("opencode")` probe is allowed in the skipif
# decorator (spec trigger-gate.md: "skip MUST NOT spawn `opencode`
# subprocesses" — the probe is read-only).
# ---------------------------------------------------------------------------
_OPENCODE_AVAILABLE = shutil.which("opencode") is not None

pytestmark = pytest.mark.skipif(
    not (os.environ.get("PROMPT_E2E_RED") == "1" and _OPENCODE_AVAILABLE),
    reason=(
        "PROMPT_E2E_RED=1 env var is unset OR `opencode` is not on PATH. "
        "Live RED tests are off by default to keep CI cost flat. The "
        "follow-up change that edits change-orchestrator.md flips the "
        "gate on at apply time."
    ),
)


# ---------------------------------------------------------------------------
# Helpers — fixtures + per-test live invocation.
# ---------------------------------------------------------------------------

_PINNED_MODEL = "minimax/MiniMax-M3"  # mirrors run.sh:98 + test_prompt_tests_extractor.py:175
_AGENT_NAME = "change-orchestrator"

# Fixture prompts mirror tests-prompts/cases_e2e.csv. The orchestrator
# decides between answering directly (small), grilling (ambiguous), or
# starting the file-backed change-flow (complete).
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
    """Lazy-load _e2e_assertions + _extractor from tests-prompts/.

    Loaded here (not at module import) so the test file's collection
    succeeds even when the helpers' files don't exist on the test
    runner — collection is independent of the gate above.
    """
    import importlib.util

    helpers_dir = Path(__file__).resolve().parent.parent / "tests-prompts"
    loaded: dict = {}
    for name, file in (
        ("_e2e_assertions", "_e2e_assertions.py"),
        ("_extractor", "_extractor.py"),
    ):
        spec = importlib.util.spec_from_file_location(name, helpers_dir / file)
        assert spec and spec.loader, f"could not load {file}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    return loaded


def _run_orchestrator(prompt: str, work_dir: Path, timeout: int = 180) -> list[dict]:
    """Invoke `opencode run` against `--dir <work_dir>` and parse stdout.

    Returns the parsed list of opencode JSON events. Empty list on
    subprocess failure (the calling assertion decides whether the
    failure is fatal via the events list).
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
        f"prompt-e2e-red-{work_dir.name}",
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
    """Format the captured event list for the pytest failure report.

    Mirrors dump_failure_trace shape in run.sh:222-235. Truncates very
    long text payloads to keep the report readable; never elides
    events that contain `?` or `ai-harness` (the spec is explicit
    that those must survive any cap).
    """
    if not events:
        return f"<no events captured for fixture={fixture_id}>"
    formatted: list[str] = []
    for idx, event in enumerate(events):
        text = json.dumps(event, indent=2, sort_keys=True)
        # Never elide the diagnostic bits.
        keep = "?" in text or "ai-harness" in text
        if not keep and len(text) > 800:
            text = text[:800] + "... <truncated>"
        formatted.append(f"[event {idx}] {text}")
    return "\n".join(formatted)


# ---------------------------------------------------------------------------
# Tests — one per fixture, asserting the per-fixture contract table.
# ---------------------------------------------------------------------------


class TestFibonacciRoute:
    """fibonacci-ES: orchestrator must answer directly.

    No `bash ai-harness change-new`, no `bash ai-harness change-continue`,
    no `task` subagent. The model is free to think / emit text but the
    routing-shape events must be absent.
    """

    def test_fibonacci_es_routes_to_answer_directly(self, tmp_path: Path) -> None:
        helpers = _load_helpers()
        events = _run_orchestrator(_FIXTURE_FIBONACCI, tmp_path)

        # The three routing predicates MUST all be False on a successful run.
        assert helpers["_e2e_assertions"].has_bash_ai_harness_change(events, "change-new") is False, (
            f"fibonacci-ES must NOT fire `bash ai-harness change-new`; "
            f"got events:\n{_dump_failure_trace(events, 'fibonacci-ES')}"
        )
        assert helpers["_e2e_assertions"].has_bash_ai_harness_change(events, "change-continue") is False, (
            f"fibonacci-ES must NOT fire `bash ai-harness change-continue`; "
            f"got events:\n{_dump_failure_trace(events, 'fibonacci-ES')}"
        )
        assert helpers["_e2e_assertions"].has_task_subagent(events) is False, (
            f"fibonacci-ES must NOT spawn a task subagent; got events:\n{_dump_failure_trace(events, 'fibonacci-ES')}"
        )


class TestVagueRoute:
    """mario-kart-3d-vague: orchestrator must grill first.

    No `bash ai-harness change-new` AND no `task` subagent AND final
    assistant text contains `?` AND the final text does NOT contain
    the substring `change-new`. The conjunction is the regression fence.
    """

    def test_mario_kart_3d_vague_grills_first(self, tmp_path: Path) -> None:
        helpers = _load_helpers()
        events = _run_orchestrator(_FIXTURE_VAGUE, tmp_path)

        # No flow launched.
        assert helpers["_e2e_assertions"].has_bash_ai_harness_change(events, "change-new") is False, (
            f"vague must NOT fire `bash ai-harness change-new`; "
            f"got events:\n{_dump_failure_trace(events, 'mario-kart-3d-vague')}"
        )
        assert helpers["_e2e_assertions"].has_task_subagent(events) is False, (
            f"vague must NOT spawn a task subagent; got events:\n{_dump_failure_trace(events, 'mario-kart-3d-vague')}"
        )
        # Final text must contain a clarifying question.
        assert helpers["_e2e_assertions"].final_assistant_text_contains(events, "?") is True, (
            f"vague final text must contain `?` (grill question); "
            f"got events:\n{_dump_failure_trace(events, 'mario-kart-3d-vague')}"
        )
        # Final text must NOT mention the change-flow subcmd.
        last_text = _last_assistant_text(events)
        assert last_text is not None, (
            f"vague must produce at least one assistant text event; "
            f"got events:\n{_dump_failure_trace(events, 'mario-kart-3d-vague')}"
        )
        assert "change-new" not in last_text, (
            f"vague final text must NOT contain `change-new` (no flow "
            f"launched yet); got: {last_text!r}; full events:\n"
            f"{_dump_failure_trace(events, 'mario-kart-3d-vague')}"
        )


class TestCompleteRoute:
    """mario-kart-3d-complete: orchestrator must start the change-flow.

    Either `bash ai-harness change-new` OR a `task` subagent fires.
    The OR-fence is intentional: future impls may prefer either path.
    """

    def test_mario_kart_3d_complete_starts_change_flow(self, tmp_path: Path) -> None:
        helpers = _load_helpers()
        events = _run_orchestrator(_FIXTURE_COMPLETE, tmp_path)

        change_new_fired = helpers["_e2e_assertions"].has_bash_ai_harness_change(events, "change-new")
        task_fired = helpers["_e2e_assertions"].has_task_subagent(events)

        assert change_new_fired or task_fired, (
            f"complete must fire `bash ai-harness change-new` OR spawn a "
            f"`task` subagent; neither fired. Events:\n"
            f"{_dump_failure_trace(events, 'mario-kart-3d-complete')}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _last_assistant_text(events: list[dict]) -> str | None:
    """Return the LAST text-event payload; None if no text events."""
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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
