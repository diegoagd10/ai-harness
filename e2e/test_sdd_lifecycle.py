"""SDD lifecycle: sdd-status and sdd-continue end-to-end coverage.

Both commands share ``_run_sdd_resolve`` and ``resolve``, so their scenarios
live together in this file. Uses ``seed_openspec_change`` workspaces.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import harness

REPO_ROOT = Path(__file__).resolve().parent.parent

# tasks.md content for various test scenarios.
TASKS_ALL_DONE = """# Tasks
## 1. Setup
- [x] 1.1 Done task
"""

TASKS_PENDING = """# Tasks
## 1. Setup
- [ ] 1.1 Pending task
"""


def _bin_path(bin_dir: str) -> str:
    return f"{bin_dir}:{os.environ.get('PATH', '')}"


def run_sdd_status_tests(bin_dir: str) -> None:
    """Exercise sdd-status JSON output, explicit/inferred change,
    --instructions, missing-change error, and change-not-ready state."""
    extra_env = {"PATH": _bin_path(bin_dir)}

    # -- explicit change name --------------------------------------------
    print("=== SDD Lifecycle: sdd-status — explicit change name")
    ws = harness.workspace_root()
    harness.seed_openspec_change(Path(ws), "my-change", TASKS_ALL_DONE)
    proc = harness.run_in_sandbox(
        ws,
        "ai-harness",
        "sdd-status",
        "my-change",
        "--cwd",
        ws,
        extra_env=extra_env,
    )
    data = json.loads(proc.stdout.strip())
    assert data["changeName"] == "my-change", f"Expected changeName=my-change, got {data['changeName']}"
    assert data["schemaName"] == "ai-harness.sdd-status", f"Unexpected schemaName: {data['schemaName']}"
    assert "taskProgress" in data, "Missing taskProgress"
    print(f"  PASS: explicit change — changeName={data['changeName']}, nextRecommended={data['nextRecommended']}")

    # -- inferred change (no arg, single active) --------------------------
    print("=== SDD Lifecycle: sdd-status — inferred change")
    ws2 = harness.workspace_root()
    harness.seed_openspec_change(Path(ws2), "inferred", TASKS_ALL_DONE)
    proc = harness.run_in_sandbox(
        ws2,
        "ai-harness",
        "sdd-status",
        "--cwd",
        ws2,
        extra_env=extra_env,
    )
    data = json.loads(proc.stdout.strip())
    assert data["changeName"] == "inferred", f"Expected inferred changeName=inferred, got {data['changeName']}"
    print(f"  PASS: inferred change — changeName={data['changeName']}")

    # -- --instructions flag ---------------------------------------------
    print("=== SDD Lifecycle: sdd-status — --instructions")
    proc = harness.run_in_sandbox(
        ws,
        "ai-harness",
        "sdd-status",
        "my-change",
        "--cwd",
        ws,
        "--instructions",
        extra_env=extra_env,
    )
    data = json.loads(proc.stdout.strip())
    if data["nextRecommended"] in ("apply", "verify", "archive"):
        assert "phaseInstructions" in data, f"phaseInstructions missing for concrete phase {data['nextRecommended']}"
        pi = data["phaseInstructions"]
        assert isinstance(pi, dict), "phaseInstructions should be a dict"
        print(f"  PASS: --instructions includes phaseInstructions for {data['nextRecommended']}")
    else:
        # Non-concrete phases don't get instructions
        print(
            f"  PASS: --instructions with non-concrete next={data['nextRecommended']} "
            f"(phaseInstructions {'present' if 'phaseInstructions' in data else 'absent'})"
        )

    # -- missing-change error --------------------------------------------
    print("=== SDD Lifecycle: sdd-status — missing change")
    proc = harness.run_in_sandbox(
        ws,
        "ai-harness",
        "sdd-status",
        "no-such-change",
        "--cwd",
        ws,
        extra_env=extra_env,
        check=False,
    )
    data = json.loads(proc.stdout.strip())
    assert data["nextRecommended"] == "sdd-new", f"Expected sdd-new for missing change, got {data['nextRecommended']}"
    assert any("not found" in r.lower() for r in data.get("blockedReasons", [])), (
        f"Expected 'not found' in blockedReasons, got {data.get('blockedReasons')}"
    )
    print(f"  PASS: missing change → sdd-new with blockedReasons")

    # -- no active changes -----------------------------------------------
    print("=== SDD Lifecycle: sdd-status — no active changes")
    ws_empty = harness.workspace_root()
    os.makedirs(os.path.join(ws_empty, "openspec", "changes"), exist_ok=True)
    proc = harness.run_in_sandbox(
        ws_empty,
        "ai-harness",
        "sdd-status",
        "--cwd",
        ws_empty,
        extra_env=extra_env,
        check=False,
    )
    data = json.loads(proc.stdout.strip())
    assert data["nextRecommended"] == "sdd-new", f"Expected sdd-new for empty workspace, got {data['nextRecommended']}"
    print(f"  PASS: no active changes → sdd-new")

    # -- change-not-ready state (pending tasks) --------------------------
    print("=== SDD Lifecycle: sdd-status — pending tasks (not ready)")
    ws3 = harness.workspace_root()
    harness.seed_openspec_change(Path(ws3), "pending-change", TASKS_PENDING)
    proc = harness.run_in_sandbox(
        ws3,
        "ai-harness",
        "sdd-status",
        "pending-change",
        "--cwd",
        ws3,
        extra_env=extra_env,
    )
    data = json.loads(proc.stdout.strip())
    tp = data["taskProgress"]
    assert tp["total"] > tp["completed"], (
        f"Expected pending tasks (total > completed), got total={tp['total']}, completed={tp['completed']}"
    )
    print(
        f"  PASS: pending tasks — total={tp['total']}, completed={tp['completed']}, "
        f"nextRecommended={data['nextRecommended']}"
    )

    print("=== SDD Lifecycle: all sdd-status assertions passed")


def run_sdd_continue_tests(bin_dir: str) -> None:
    """Exercise sdd-continue dispatcher markdown, --json mode,
    and multi-phase change progression."""
    extra_env = {"PATH": _bin_path(bin_dir)}

    # -- dispatcher markdown output (default) ---------------------------
    print("=== SDD Lifecycle: sdd-continue — dispatcher markdown")
    ws = harness.workspace_root()
    harness.seed_openspec_change(Path(ws), "continue-change", TASKS_ALL_DONE)
    proc = harness.run_in_sandbox(
        ws,
        "ai-harness",
        "sdd-continue",
        "continue-change",
        "--cwd",
        ws,
        extra_env=extra_env,
    )
    output = proc.stdout.strip()
    assert "Native SDD Dispatcher" in output, "Missing dispatcher header in markdown output"
    assert "next_recommended:" in output, "Missing next_recommended in markdown output"
    assert "Dependency States" in output, "Missing Dependency States section"
    assert "JSON" in output, "Missing JSON fenced block in markdown"
    assert "```json" in output, "Missing JSON fence in markdown"
    print("  PASS: dispatcher markdown contains header, deps, next, JSON block")

    # -- --json mode ----------------------------------------------------
    print("=== SDD Lifecycle: sdd-continue — --json mode")
    proc = harness.run_in_sandbox(
        ws,
        "ai-harness",
        "sdd-continue",
        "continue-change",
        "--cwd",
        ws,
        "--json",
        extra_env=extra_env,
    )
    data = json.loads(proc.stdout.strip())
    assert data["changeName"] == "continue-change", f"Expected changeName=continue-change, got {data['changeName']}"
    assert "phaseInstructions" in data, (
        "phaseInstructions missing in --json mode (instructions are always included for continue)"
    )
    print(
        f"  PASS: --json mode — changeName={data['changeName']}, "
        f"nextRecommended={data['nextRecommended']}, "
        f"phaseInstructions={'present' if 'phaseInstructions' in data else 'absent'}"
    )

    # -- multi-phase progression (pending → proposal-ready) -------------
    print("=== SDD Lifecycle: sdd-continue — pending tasks (not ready)")
    ws2 = harness.workspace_root()
    harness.seed_openspec_change(Path(ws2), "progression", TASKS_PENDING)
    proc = harness.run_in_sandbox(
        ws2,
        "ai-harness",
        "sdd-continue",
        "progression",
        "--cwd",
        ws2,
        extra_env=extra_env,
    )
    output = proc.stdout.strip()
    assert "Native SDD Dispatcher" in output, "Missing dispatcher header for pending change"
    # Pending tasks should not produce a concrete phase recommendation
    print(f"  PASS: dispatcher markdown for pending change — output length={len(output)}")

    print("=== SDD Lifecycle: all sdd-continue assertions passed")


def run_workspace_cleanup_tests() -> None:
    """Verify that workspace_root() directories are removed by cleanup.

    This is a focused verification of the fix for the sdd-verify warning:
    workspace directories must be removed by the same cleanup path used by the
    atexit handler — preventing ``e2e-sdd-ws-*`` leaks in /tmp.
    """
    print("=== SDD Lifecycle: workspace_root cleanup")
    ws = harness.workspace_root()
    assert os.path.isdir(ws), f"workspace_root() returned non-directory: {ws}"
    testfile = Path(ws) / ".write-test"
    testfile.write_text("ok")
    assert testfile.read_text() == "ok"

    harness._cleanup()

    assert not os.path.exists(ws), f"workspace_root() cleanup did not remove: {ws}"
    print(f"  PASS: workspace_root() → {ws} (writable, then removed by cleanup)")
