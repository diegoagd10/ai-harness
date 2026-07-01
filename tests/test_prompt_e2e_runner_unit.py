"""Unit tests for tests-prompts/_e2e_runner.py — per-fixture orchestrator
routing decision helper used by the CASES_CSV_E2E second loop in run.sh.

The runner composes the three flat predicates in _e2e_assertions.py
against the per-fixture contract table from design.md +
tests/test_prompt_e2e_red.py:

  - fibonacci-ES         (small/concrete)    -> answer directly
  - mario-kart-3d-vague  (ambiguous/large)   -> grill first
  - mario-kart-3d-complete (complete/large)  -> start change-flow

The runner's verdict is exposed via the CLI exit code (0 = pass,
non-zero = fail) so bash can branch on it. This test covers the
verdict logic directly via the imported `route_orchestrator_decision`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HELPERS_DIR = Path(__file__).resolve().parent.parent / "tests-prompts"


def _load(module_name: str, file_name: str):
    path = _HELPERS_DIR / file_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader, f"could not load {file_name} from {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# _e2e_runner.py does `from _e2e_assertions import ...`. We must register
# `_e2e_assertions` in sys.modules BEFORE loading _e2e_runner so the
# import resolves. In production the runner is invoked via
# `python3 /tests-prompts/_e2e_runner.py` and Python's script-dir sys.path
# makes this work automatically; the test goes through importlib so we
# have to set up the dependency order explicitly.
_load("_e2e_assertions", "_e2e_assertions.py")
_runner = _load("_e2e_runner", "_e2e_runner.py")
route_orchestrator_decision = _runner.route_orchestrator_decision


def _tool_event(tool: str, command: str | None = None) -> dict:
    part: dict = {"type": "tool", "tool": tool}
    if command is not None:
        part["state"] = {"status": "completed", "input": {"command": command}}
    else:
        part["state"] = {"status": "completed"}
    return {"type": "tool_use", "part": part}


def _text_event(text: str) -> dict:
    return {
        "type": "text",
        "part": {"type": "text", "text": text},
    }


class TestFibonacciRoute:
    """fibonacci-ES must pass when no change flow is started."""

    def test_passes_when_orchestrator_answers_directly(self) -> None:
        events = [
            _text_event("Sure, here's the fibonacci implementation in JS..."),
        ]
        passed, reasons = route_orchestrator_decision("fibonacci-ES", events)
        assert passed is True
        assert reasons == []

    def test_fails_when_change_new_fires(self) -> None:
        events = [
            _tool_event("bash", command="ai-harness change-new fibonacci-ES"),
        ]
        passed, reasons = route_orchestrator_decision("fibonacci-ES", events)
        assert passed is False
        assert any("change-new fired" in r for r in reasons)

    def test_fails_when_change_continue_fires(self) -> None:
        events = [
            _tool_event("bash", command="ai-harness change-continue fibonacci-ES"),
        ]
        passed, reasons = route_orchestrator_decision("fibonacci-ES", events)
        assert passed is False
        assert any("change-continue fired" in r for r in reasons)

    def test_fails_when_task_spawned(self) -> None:
        events = [_tool_event("task")]
        passed, reasons = route_orchestrator_decision("fibonacci-ES", events)
        assert passed is False
        assert any("task subagent spawned" in r for r in reasons)


class TestVagueRoute:
    """mario-kart-3d-vague must grill — no flow, final text contains ?."""

    def test_passes_when_grills_with_question(self) -> None:
        events = [
            _text_event("Sure, I can help — what engine do you prefer?"),
        ]
        passed, reasons = route_orchestrator_decision("mario-kart-3d-vague", events)
        assert passed is True, f"expected pass, got reasons={reasons!r}"

    def test_fails_when_change_new_fires_on_vague(self) -> None:
        events = [
            _tool_event("bash", command="ai-harness change-new mario-kart-3d"),
        ]
        passed, reasons = route_orchestrator_decision("mario-kart-3d-vague", events)
        assert passed is False
        assert any("change-new fired" in r for r in reasons)

    def test_fails_when_no_question_in_final_text(self) -> None:
        events = [
            _text_event("Sure, I'll start a file-backed change."),
        ]
        passed, reasons = route_orchestrator_decision("mario-kart-3d-vague", events)
        assert passed is False
        assert any("does not contain ?" in r for r in reasons)

    def test_passes_with_karn_slug_variant(self) -> None:
        # The vague fixture uses "karn" in the prompt; the slug survives
        # slugify() but the matcher must still recognize it.
        events = [
            _text_event("What engine — Unity or Unreal?"),
        ]
        passed, reasons = route_orchestrator_decision("mario-kart-3d-karn", events)
        assert passed is True, f"expected pass, got reasons={reasons!r}"


class TestCompleteRoute:
    """mario-kart-3d-complete must start the change-flow (change-new OR task)."""

    def test_passes_when_change_new_fires(self) -> None:
        events = [
            _tool_event("bash", command="ai-harness change-new mario-kart-3d"),
        ]
        passed, reasons = route_orchestrator_decision("mario-kart-3d-complete", events)
        assert passed is True, f"expected pass, got reasons={reasons!r}"

    def test_passes_when_task_fires(self) -> None:
        events = [_tool_event("task")]
        passed, reasons = route_orchestrator_decision("mario-kart-3d-complete", events)
        assert passed is True, f"expected pass, got reasons={reasons!r}"

    def test_passes_when_both_change_new_and_task_fire(self) -> None:
        events = [
            _tool_event("bash", command="ai-harness change-new mario-kart-3d"),
            _tool_event("task"),
        ]
        passed, reasons = route_orchestrator_decision("mario-kart-3d-complete", events)
        assert passed is True

    def test_fails_when_neither_fires(self) -> None:
        events = [
            _text_event("Sure, here's the design for Mario Kart 3D..."),
        ]
        passed, reasons = route_orchestrator_decision("mario-kart-3d-complete", events)
        assert passed is False
        assert any("neither" in r.lower() for r in reasons)


class TestUnknownFixture:
    """Unknown slug must FAIL loud with a labeled reason."""

    def test_unknown_slug_fails(self) -> None:
        passed, reasons = route_orchestrator_decision("totally-unknown", [])
        assert passed is False
        assert any("unknown fixture slug" in r for r in reasons)

    def test_empty_slug_fails(self) -> None:
        passed, reasons = route_orchestrator_decision("", [])
        assert passed is False
        assert reasons
