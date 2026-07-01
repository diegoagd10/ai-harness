#!/usr/bin/env python3
"""_e2e_runner.py — per-fixture orchestrator routing decision for the
CASES_CSV_E2E second loop in tests-prompts/run.sh.

Composes the three flat predicates in `_e2e_assertions.py` against
the per-fixture contract table from `tests/test_prompt_e2e_red.py`.
The bash loop in run.sh cannot easily express the conjunctive
routing rules ("no bash change-* AND final text contains ?"), so it
spawns this helper once per row and reads the verdict from its exit
code (0 = pass, non-zero = fail). The reason lines on stderr let the
bash loop surface WHICH clause tripped.

Per-fixture contracts (locked in design.md + tests/test_prompt_e2e_red.py):
    fibonacci-ES          (small/concrete)
        no bash change-new, no bash change-continue, no task subagent
    mario-kart-3d-vague   (ambiguous/large)
        no bash change-new, no task, final text contains ?, no change-new
        substring in final text
    mario-kart-3d-complete (complete/large)
        bash change-new OR task fired

The fixture slug is matched via slug-prefix containment, not exact
equality, so the slug survives slugify()'s 32-char cap and any future
slug-collision rules. Unknown fixtures FAIL with a labeled reason so
a typo or regression surfaces immediately.

CLI:
    python3 _e2e_runner.py <slug> <trace_file>
        exit 0 on pass, non-zero on fail
        stdout: "PASS" or "FAIL"
        stderr: one labeled REASON line per failed clause (on FAIL)

Schema awareness here is intentionally minimal — the predicates live
in `_e2e_assertions.py` per the locked interface. This module is
purely the per-fixture composition; `_e2e_assertions` is the
single source of truth for "what counts as a routing decision".
"""

from __future__ import annotations

import json
import sys

from _e2e_assertions import (
    final_assistant_text_contains,
    has_bash_ai_harness_change,
    has_task_subagent,
)


def _parse_events(trace_text: str) -> list[dict]:
    """Parse opencode --format json stream into a list of event dicts.

    Lines that fail JSON parsing are skipped silently (mirroring
    `_extractor._safe_parse`). Empty/whitespace input yields [].
    """
    events: list[dict] = []
    for line in trace_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            events.append(json.loads(stripped))
        except (ValueError, TypeError):
            continue
    return events


def route_orchestrator_decision(slug: str, events: list[dict]) -> tuple[bool, list[str]]:
    """Return (passed, reasons) for the given fixture slug + events.

    `passed` is True iff every clause of the fixture's contract holds.
    `reasons` lists the violated clauses (empty when passed).
    """
    reasons: list[str] = []
    slug_lower = slug.lower()

    # fibonacci-ES (small/concrete) — orchestrator answers directly.
    # No CLI invocation, no subagent delegation.
    if "fibonacci" in slug_lower or "fibonnaci" in slug_lower:
        if has_bash_ai_harness_change(events, "change-new"):
            reasons.append("bash ai-harness change-new fired (expected direct answer)")
        if has_bash_ai_harness_change(events, "change-continue"):
            reasons.append("bash ai-harness change-continue fired (expected direct answer)")
        if has_task_subagent(events):
            reasons.append("task subagent spawned (expected direct answer)")
        return (len(reasons) == 0, reasons)

    # mario-kart-3d-vague (ambiguous/large) — orchestrator grills first.
    # No change flow yet, but final text must contain a clarifying ?.
    if (
        "mario" in slug_lower
        and ("vague" in slug_lower or "karn" in slug_lower or "3d" in slug_lower)
        and "complete" not in slug_lower
    ):
        if has_bash_ai_harness_change(events, "change-new"):
            reasons.append("bash ai-harness change-new fired (expected grill first)")
        if has_task_subagent(events):
            reasons.append("task subagent spawned (expected grill first)")
        if not final_assistant_text_contains(events, "?"):
            reasons.append("final assistant text does not contain ? (expected grill question)")
        # Also assert no `change-new` substring in the final text — the
        # orchestrator must not have already started writing the change
        # folder. We approximate "final text" via the same LAST-text
        # rule used elsewhere.
        last_text = _last_text(events)
        if last_text is not None and "change-new" in last_text:
            reasons.append("final assistant text contains 'change-new' (expected no flow launch yet)")
        return (len(reasons) == 0, reasons)

    # mario-kart-3d-complete (complete/large) — orchestrator starts
    # the file-backed change-flow. Either `bash change-new` or a
    # `task` delegation satisfies the OR-fence.
    if "mario" in slug_lower and "complete" in slug_lower:
        change_new_fired = has_bash_ai_harness_change(events, "change-new")
        task_fired = has_task_subagent(events)
        if not change_new_fired and not task_fired:
            reasons.append("neither bash ai-harness change-new nor task subagent fired (expected change-flow start)")
        return (len(reasons) == 0, reasons)

    # Unknown fixture — fail loud to surface a typo or regression.
    reasons.append(f"unknown fixture slug: {slug!r}")
    return (False, reasons)


def _last_text(events: list[dict]) -> str | None:
    """Return the LAST text event payload (mirrors _e2e_assertions logic)."""
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


def _cli_main(slug: str, trace_path: str) -> int:
    """CLI driver — read trace file, run routing decision, emit verdict."""
    try:
        with open(trace_path, encoding="utf-8") as fh:
            trace_text = fh.read()
    except FileNotFoundError:
        print(f"REASON: trace file not found: {trace_path}", file=sys.stderr)
        print("FAIL")
        return 1
    except OSError as exc:
        print(f"REASON: cannot read trace: {exc}", file=sys.stderr)
        print("FAIL")
        return 1

    events = _parse_events(trace_text)
    passed, reasons = route_orchestrator_decision(slug, events)
    for reason in reasons:
        print(f"REASON: {reason}", file=sys.stderr)
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        sys.stderr.write("usage: _e2e_runner.py <slug> <trace_file>\n")
        return 2
    slug, trace_path = argv[0], argv[1]
    return _cli_main(slug, trace_path)


if __name__ == "__main__":
    sys.exit(main())
