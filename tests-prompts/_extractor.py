#!/usr/bin/env python3
"""_extractor.py — schema-aware tool-call counter for the prompt-test runner.

This is the ONLY module in the prompt-test suite that knows about
opencode's JSON event schema. A future schema rename (tool name field,
event type marker, etc.) is a one-line fix here.

Bucket rules (per disjoint-count-assertion spec):
    - "skill" tool calls  -> skills bucket
    - "task"  tool calls  -> sub_agents bucket
    - any other tool name -> tools bucket
    - text/thinking/step events are ignored

The helper tolerates non-JSON lines (warnings, debug chatter) silently
so opencode quirks don't break the count.

CLI usage from run.sh:
    printf '%s' "$trace_text" | python3 /tests-prompts/_extractor.py

Stdout: "<tools> <skills> <sub_agents>" (space-separated, three ints).
"""

from __future__ import annotations

import json
import sys
from typing import Iterable, Tuple


# ---------------------------------------------------------------------------
# Event-shape constants — single source of truth for the opencode schema.
# Update here only; the rest of the runner consumes the returned triple.
# ---------------------------------------------------------------------------
_TOOL_USE_TOP_TYPE = "tool_use"
_TOOL_PART_TYPE = "tool"

_TOOL_NAME_SKILL = "skill"
_TOOL_NAME_TASK = "task"


def extract_counts(trace_text: str) -> Tuple[int, int, int]:
    """Return (tools, skills, sub_agents) from raw opencode --format json stdout.

    Lines that fail JSON parsing are skipped silently. Lines that parse but
    don't carry a tool_use event contribute nothing. Tool calls are
    classified into exactly one bucket by tool name.
    """
    tools = skills = sub_agents = 0
    for line in _iter_lines(trace_text):
        event = _safe_parse(line)
        if event is None:
            continue
        if event.get("type") != _TOOL_USE_TOP_TYPE:
            continue
        part = event.get("part") or {}
        if part.get("type") != _TOOL_PART_TYPE:
            continue
        tool_name = part.get("tool")
        if not isinstance(tool_name, str):
            continue
        if tool_name == _TOOL_NAME_SKILL:
            skills += 1
        elif tool_name == _TOOL_NAME_TASK:
            sub_agents += 1
        else:
            tools += 1
    return tools, skills, sub_agents


def _iter_lines(trace_text: str) -> Iterable[str]:
    """Yield non-empty lines from the trace text."""
    for raw in trace_text.splitlines():
        if raw.strip():
            yield raw


def _safe_parse(line: str) -> dict | None:
    """Parse one line as JSON; return None on failure (silent skip)."""
    try:
        return json.loads(line)
    except (ValueError, TypeError):
        return None


def _main() -> int:
    trace_text = sys.stdin.read()
    tools, skills, sub_agents = extract_counts(trace_text)
    print(f"{tools} {skills} {sub_agents}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
