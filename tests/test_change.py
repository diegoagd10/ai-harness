# pylint: disable=duplicate-code
"""Tests for the change module and its CLI adapter."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app
from ai_harness.modules.change_config import ChangeConfigAdministrator
from ai_harness.modules.change_config.models import ChangeConfigPromptContext
from ai_harness.modules.harness.change import (
    ChangeStatus,
    ChangeStoreError,
    change_archive,
    change_continue,
    change_new,
)
from ai_harness.modules.harness.tasks import (
    SubtaskInput,
    TaskInput,
    TaskProgress,
    task_create,
    task_done,
)

runner = CliRunner()


def test_change_new_scaffolds_fresh_change_status(tmp_path: Path) -> None:
    """Starting a change creates its folder and returns the first ready phase."""
    status = change_new(tmp_path, "demo")

    assert (tmp_path / ".ai-harness" / "changes" / "demo").is_dir()
    assert status.schemaName == "ai-harness.change-status"
    assert status.schemaVersion == 3
    assert status.changeName == "demo"
    assert status.artifacts == {
        "explore": "missing",
        "prd": "missing",
        "design": "missing",
        "specs": "missing",
        "tasks": "missing",
        "implement": "missing",
        "validate": "missing",
        "archive": "missing",
    }
    assert status.dependencies["explore"] == "ready"
    assert status.nextRecommended == "explore"
    # Version-2 shape: nullable configContext defaults to None for change_new
    # because new changes never consult repository configuration.
    assert status.configContext is None
    # Phase instructions remain the existing nullable string contract.
    assert status.phaseInstructions is None
    assert "budget" not in asdict(status)
    assert "verdict" not in asdict(status)


def test_change_status_serializes_populated_config_context_as_json_object() -> None:
    """A populated ChangeConfigPromptContext is serialized as a JSON object with phase_rules."""
    populated = ChangeConfigPromptContext(
        phase="change_propose",
        phase_rules=("First rule", "Second rule"),
        commit_format="[{change_name}][{task_id}] {slug}",
    )
    status = ChangeStatus(
        schemaName="ai-harness.change-status",
        schemaVersion=3,
        changeName="auth-rework",
        changeRoot=".ai-harness/changes/auth-rework",
        artifactPaths={"prd": [".ai-harness/changes/auth-rework/prd.md"]},
        artifacts={"prd": "missing"},
        taskProgress=TaskProgress(total=0, completed=0, pending=0, allComplete=True),
        dependencies={"prd": "ready"},
        relationships={"parent": None, "siblings": [], "children": []},
        phaseInstructions=None,
        nextRecommended="prd",
        blockedReasons=[],
        configContext=populated,
    )

    serialized = json.loads(json.dumps(asdict(status)))

    assert serialized["schemaVersion"] == 3
    assert serialized["nextRecommended"] == "prd"
    assert serialized["configContext"] == {
        "phase": "change_propose",
        "phase_rules": ["First rule", "Second rule"],
        "commit_format": "[{change_name}][{task_id}] {slug}",
    }
    # phaseInstructions remains the documented nullable string field with
    # its existing name and meaning; the additive change must not perturb it.
    assert serialized["phaseInstructions"] is None


def test_change_status_serializes_empty_rules_as_json_array() -> None:
    """An empty rules tuple serializes as a JSON array (not null and not omitted)."""
    populated = ChangeConfigPromptContext(
        phase="change_explorer", phase_rules=(), commit_format="[{change_name}][{task_id}] {slug}"
    )
    status = ChangeStatus(
        schemaName="ai-harness.change-status",
        schemaVersion=3,
        changeName="demo",
        changeRoot=".ai-harness/changes/demo",
        artifactPaths={"exploration": []},
        artifacts={"explore": "missing"},
        taskProgress=TaskProgress(total=0, completed=0, pending=0, allComplete=True),
        dependencies={"explore": "ready"},
        relationships={"parent": None, "siblings": [], "children": []},
        phaseInstructions=None,
        nextRecommended="explore",
        blockedReasons=[],
        configContext=populated,
    )

    serialized = json.loads(json.dumps(asdict(status)))

    assert serialized["configContext"]["phase"] == "change_explorer"
    assert serialized["configContext"]["phase_rules"] == []
    assert isinstance(serialized["configContext"]["phase_rules"], list)


def test_change_status_preserves_ordered_rules_in_source_order() -> None:
    """Rules appear in the response exactly as written, in source order."""
    populated = ChangeConfigPromptContext(
        phase="change_propose",
        phase_rules=("Observe", "Decide", "Report"),
        commit_format="[{change_name}][{task_id}] {slug}",
    )
    status = ChangeStatus(
        schemaName="ai-harness.change-status",
        schemaVersion=3,
        changeName="demo",
        changeRoot=".ai-harness/changes/demo",
        artifactPaths={"prd": []},
        artifacts={"prd": "missing"},
        taskProgress=TaskProgress(total=0, completed=0, pending=0, allComplete=True),
        dependencies={"prd": "ready"},
        relationships={"parent": None, "siblings": [], "children": []},
        phaseInstructions=None,
        nextRecommended="prd",
        blockedReasons=[],
        configContext=populated,
    )

    serialized = json.loads(json.dumps(asdict(status)))

    assert serialized["configContext"]["phase_rules"] == ["Observe", "Decide", "Report"]


def test_change_status_keeps_phase_instructions_alongside_config_context() -> None:
    """A non-null phaseInstructions survives the additive configContext field."""
    populated = ChangeConfigPromptContext(
        phase="change_propose", phase_rules=("Only rule",), commit_format="[{change_name}][{task_id}] {slug}"
    )
    status = ChangeStatus(
        schemaName="ai-harness.change-status",
        schemaVersion=3,
        changeName="demo",
        changeRoot=".ai-harness/changes/demo",
        artifactPaths={"prd": []},
        artifacts={"prd": "missing"},
        taskProgress=TaskProgress(total=0, completed=0, pending=0, allComplete=True),
        dependencies={"prd": "ready"},
        relationships={"parent": None, "siblings": [], "children": []},
        phaseInstructions="Draft the PRD.",
        nextRecommended="prd",
        blockedReasons=[],
        configContext=populated,
    )

    serialized = json.loads(json.dumps(asdict(status)))

    assert serialized["phaseInstructions"] == "Draft the PRD."
    assert serialized["configContext"]["phase_rules"] == ["Only rule"]


def test_cli_change_new_status_includes_null_config_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI version-3 status JSON for ``change-new`` exposes configContext as null."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-new", "demo"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schemaVersion"] == 3
    assert payload["configContext"] is None


# ---------------------------------------------------------------------------
# configContext enrichment — change_continue seam (task 2)
# ---------------------------------------------------------------------------


def _initialize_config_with_rules(tmp_path: Path, rules_by_phase: dict[str, list[str]]) -> None:
    """Write a valid ``.ai-harness/config.yml`` with per-phase rule lists.

    Used by routed-context tests to give ``change_continue`` a real
    configured file so the seam consults
    ``ChangeConfigAdministrator.get_context_by`` end-to-end. Keeps the
    helper narrow so each test stays a single specification.
    """
    config_path = tmp_path / ".ai-harness" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    phases = {
        "change_explorer": {"rules": rules_by_phase.get("change_explorer", [])},
        "change_propose": {"rules": rules_by_phase.get("change_propose", [])},
        "change_design": {"rules": rules_by_phase.get("change_design", [])},
        "change_specs": {"rules": rules_by_phase.get("change_specs", [])},
        "change_tasks": {"rules": rules_by_phase.get("change_tasks", [])},
        "change_implementor": {"rules": rules_by_phase.get("change_implementor", [])},
        "change_validator": {"rules": rules_by_phase.get("change_validator", [])},
        "change_archiver": {"rules": rules_by_phase.get("change_archiver", [])},
    }
    payload = {
        "commit": {"format": "[{change_name}][{task_id}] {slug}"},
        "phases": phases,
    }
    config_path.write_text(
        __import__("yaml").safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def _stage_change_for_route(tmp_path: Path, change: str, *, next_recommended: str) -> None:
    """Populate a change's artifact files so ``nextRecommended`` equals *next_recommended*.

    Each phase ``X`` only becomes ``nextRecommended`` when ``X``'s
    artifact is missing but every earlier-listed phase is present. So
    setting up state for one route sometimes requires *not* writing
    a later artifact. The ``prerequisites`` table is the minimum set
    of artifact states needed to land on each route, plus the
    ``must_be_present`` guard that keeps earlier phases from
    shortcutting the recommendation.

    Tests for non-obvious aliases (``prd``, ``implement``,
    ``archive``) use this helper to land on a specific route
    deterministically without leaking into archive.
    """
    change_new(tmp_path, change)
    change_dir = tmp_path / ".ai-harness" / "changes" / change

    # Prerequisite map: every artifact that MUST be present for the
    # requested route to surface as ``nextRecommended``. The target
    # phase itself is intentionally absent here.
    prerequisites = {
        "explore": [],
        "prd": ["exploration.md"],
        "design": ["exploration.md", "prd.md"],
        "specs": ["exploration.md", "prd.md", "design.md"],
        # tasks needs both design and specs done. Either is sufficient,
        # but the FSM lists tasks after specs — supply both so the test
        # is order-independent.
        "tasks": ["exploration.md", "prd.md", "design.md", "specs"],
        "implement": ["exploration.md", "prd.md", "design.md", "specs"],
        "validate": ["exploration.md", "prd.md", "design.md", "specs"],
        "archive": ["exploration.md", "prd.md", "design.md", "specs"],
    }
    present = prerequisites[next_recommended]
    if "exploration.md" in present:
        (change_dir / "exploration.md").write_text("x\n", encoding="utf-8")
    if "prd.md" in present:
        (change_dir / "prd.md").write_text("x\n", encoding="utf-8")
    if "design.md" in present:
        (change_dir / "design.md").write_text("x\n", encoding="utf-8")
    if "specs" in present:
        specs_dir = change_dir / "specs"
        specs_dir.mkdir()
        (specs_dir / "capability.md").write_text("x\n", encoding="utf-8")

    # For implement/validate/archive routes, the FSM requires a tasks
    # file with at least one task that is fully closed before implement
    # is ready. Use the existing tasks API so the test stays on the
    # public seam.
    needs_tasks = next_recommended in {"implement", "validate", "archive"}
    if needs_tasks:
        task = task_create(
            tmp_path,
            change,
            TaskInput(
                title="Finish work",
                spec="specs/capability.md",
                phase="implement",
                depends_on=[],
                subtasks=[SubtaskInput(title="Build")],
            ),
        )
        task_done(tmp_path, change, task.id)
        # The implementation.md, validation.md artifacts are still
        # intentionally absent for ``implement``/``validate`` routes —
        # only the matching lifecycle artifact must be missing so the
        # nextRecommended token equals the requested route.
        if next_recommended in {"validate", "archive"}:
            (change_dir / "implementation.md").write_text("x\n", encoding="utf-8")
        if next_recommended == "archive":
            (change_dir / "validation.md").write_text(
                "## Verdict\nverdict: pass\ncritical: 0\n",
                encoding="utf-8",
            )


def test_change_continue_attaches_canonical_explorer_context_for_explore_route(tmp_path: Path) -> None:
    """A fresh change's ``explore`` route resolves to ``change_explorer``."""
    _initialize_config_with_rules(
        tmp_path,
        {"change_explorer": ["Read the codebase", "Surface unknowns"]},
    )
    change_new(tmp_path, "demo")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "explore"
    assert status.configContext is not None
    assert status.configContext.phase == "change_explorer"
    assert status.configContext.phase_rules == ("Read the codebase", "Surface unknowns")
    assert status.configContext.commit_format == "[{change_name}][{task_id}] {slug}"


def test_change_continue_attaches_canonical_propose_context_for_prd_route(tmp_path: Path) -> None:
    """``prd`` resolves through the alias map to ``change_propose``."""
    _initialize_config_with_rules(
        tmp_path,
        {"change_propose": ["Anchor scope", "Outcome-first framing"]},
    )
    _stage_change_for_route(tmp_path, "demo", next_recommended="prd")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "prd"
    assert status.configContext is not None
    assert status.configContext.phase == "change_propose"
    assert status.configContext.phase_rules == ("Anchor scope", "Outcome-first framing")


def test_change_continue_attaches_canonical_design_context_for_design_route(tmp_path: Path) -> None:
    """``design`` resolves to ``change_design``."""
    _initialize_config_with_rules(
        tmp_path,
        {"change_design": ["Pick a seam", "Trade-offs table"]},
    )
    _stage_change_for_route(tmp_path, "demo", next_recommended="design")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "design"
    assert status.configContext is not None
    assert status.configContext.phase == "change_design"
    assert status.configContext.phase_rules == ("Pick a seam", "Trade-offs table")


def test_change_continue_attaches_canonical_specs_context_for_specs_route(tmp_path: Path) -> None:
    """``specs`` resolves to ``change_specs``."""
    _initialize_config_with_rules(
        tmp_path,
        {"change_specs": ["One capability per file", "Cover edge cases"]},
    )
    _stage_change_for_route(tmp_path, "demo", next_recommended="specs")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "specs"
    assert status.configContext is not None
    assert status.configContext.phase == "change_specs"
    assert status.configContext.phase_rules == ("One capability per file", "Cover edge cases")


def test_change_continue_attaches_canonical_tasks_context_for_tasks_route(tmp_path: Path) -> None:
    """``tasks`` resolves to ``change_tasks``."""
    _initialize_config_with_rules(
        tmp_path,
        {"change_tasks": ["Idiomatic tasks.json", "Sequenced dependencies"]},
    )
    _stage_change_for_route(tmp_path, "demo", next_recommended="tasks")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "tasks"
    assert status.configContext is not None
    assert status.configContext.phase == "change_tasks"
    assert status.configContext.phase_rules == ("Idiomatic tasks.json", "Sequenced dependencies")


def test_change_continue_attaches_canonical_implementor_context_for_implement_route(tmp_path: Path) -> None:
    """``implement`` resolves through the alias map to ``change_implementor``."""
    _initialize_config_with_rules(
        tmp_path,
        {"change_implementor": ["TDD red/green/refactor", "One commit per task"]},
    )
    _stage_change_for_route(tmp_path, "demo", next_recommended="implement")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "implement"
    assert status.configContext is not None
    assert status.configContext.phase == "change_implementor"
    assert status.configContext.phase_rules == ("TDD red/green/refactor", "One commit per task")
    # The orchestrator inlines this into the change-implementor delegation
    # block instead of reading CODING_STANDARDS.md.
    assert status.configContext.commit_format == "[{change_name}][{task_id}] {slug}"


def test_change_continue_attaches_canonical_validator_context_for_validate_route(tmp_path: Path) -> None:
    """``validate`` resolves to ``change_validator``."""
    _initialize_config_with_rules(
        tmp_path,
        {"change_validator": ["Verdict shape", "Re-run on warnings"]},
    )
    _stage_change_for_route(tmp_path, "demo", next_recommended="validate")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "validate"
    assert status.configContext is not None
    assert status.configContext.phase == "change_validator"
    assert status.configContext.phase_rules == ("Verdict shape", "Re-run on warnings")


def test_change_continue_attaches_canonical_archiver_context_for_archive_route(tmp_path: Path) -> None:
    """``archive`` resolves through the alias map to ``change_archiver``."""
    _initialize_config_with_rules(
        tmp_path,
        {"change_archiver": ["Move specs/ to .ai-harness/specs/", "Roll back partial moves"]},
    )
    _stage_change_for_route(tmp_path, "demo", next_recommended="archive")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "archive"
    assert status.configContext is not None
    assert status.configContext.phase == "change_archiver"
    assert status.configContext.phase_rules == (
        "Move specs/ to .ai-harness/specs/",
        "Roll back partial moves",
    )


def test_change_continue_preserves_lifecycle_status_when_enriching_config_context(tmp_path: Path) -> None:
    """Enrichment must NOT change artifacts/dependencies/taskProgress/nextRecommended."""
    _initialize_config_with_rules(
        tmp_path,
        {"change_explorer": ["Read the codebase"]},
    )
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "exploration.md").write_text("x\n", encoding="utf-8")

    status = change_continue(tmp_path, "demo")

    # Lifecycle-derived fields remain identical to a config-free derivation.
    assert status.nextRecommended == "prd"
    assert status.artifacts["explore"] == "done"
    assert status.dependencies["explore"] == "all_done"
    assert status.dependencies["prd"] == "ready"
    # The new field carries the routed phase context.
    assert status.configContext is not None
    assert status.configContext.phase == "change_propose"


def test_change_continue_bypasses_configuration_for_resolve_blockers(tmp_path: Path) -> None:
    """``resolve-blockers`` returns null context and never reads the configuration.

    Even if the configuration file is missing or malformed, a
    blocked-state continuation must still succeed because no sub-agent
    is routable in that state. The test deliberately pre-installs a
    broken config so any accidental ``validate_config`` call would
    raise; the only way to satisfy the assertion is to bypass the
    configuration administrator entirely.
    """
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    # Land on resolve-blockers: complete every required artifact so all
    # but ``archive`` read all_done, then keep tasks empty so
    # ``archive`` dependency stays blocked.
    for name in ("exploration.md", "prd.md", "design.md"):
        (change_dir / name).write_text("x\n", encoding="utf-8")
    specs_dir = change_dir / "specs"
    specs_dir.mkdir()
    (specs_dir / "capability.md").write_text("x\n", encoding="utf-8")
    (change_dir / "implementation.md").write_text("x\n", encoding="utf-8")
    (change_dir / "validation.md").write_text("x\n", encoding="utf-8")
    (change_dir / "tasks.json").write_text('{"tasks": []}', encoding="utf-8")
    # Intentionally broken configuration file. If the seam reads it,
    # validate_config() raises ChangeConfigError which fails the test.
    (tmp_path / ".ai-harness" / "config.yml").write_text("commit: [unclosed\n", encoding="utf-8")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "resolve-blockers"
    assert status.configContext is None
    # Other lifecycle fields are populated normally.
    assert status.artifacts["explore"] == "done"
    assert status.dependencies["archive"] == "blocked"


def test_change_continue_observes_config_rule_edit_on_next_invocation(tmp_path: Path) -> None:
    """Edits to ``.ai-harness/config.yml`` between invocations become visible immediately.

    Locks the freshness contract: the next invocation must reflect the
    edit, proving that no administrator, parsed config, or context is
    cached across calls.
    """
    _initialize_config_with_rules(tmp_path, {"change_explorer": ["Before edit"]})
    change_new(tmp_path, "demo")

    first_status = change_continue(tmp_path, "demo")
    assert first_status.configContext is not None
    assert first_status.configContext.phase_rules == ("Before edit",)

    # User edits ``.ai-harness/config.yml`` between calls.
    _initialize_config_with_rules(tmp_path, {"change_explorer": ["After edit", "Added later"]})

    second_status = change_continue(tmp_path, "demo")
    assert second_status.configContext is not None
    assert second_status.configContext.phase == "change_explorer"
    assert second_status.configContext.phase_rules == ("After edit", "Added later")


def test_change_continue_derives_artifacts_dependencies_and_next_phase(tmp_path: Path) -> None:
    """Continuing derives completed phases from artifact presence."""
    change_new(tmp_path, "demo")
    ChangeConfigAdministrator(repo_root=tmp_path).initialize_config()
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "exploration.md").write_text("explored\n", encoding="utf-8")

    status = change_continue(tmp_path, "demo")

    assert status.changeRoot == ".ai-harness/changes/demo"
    assert status.artifactPaths["exploration"] == [".ai-harness/changes/demo/exploration.md"]
    assert status.artifacts["explore"] == "done"
    assert status.dependencies["explore"] == "all_done"
    assert status.dependencies["prd"] == "ready"
    assert status.nextRecommended == "prd"


def test_tasks_dependency_is_ready_when_design_or_specs_exists(tmp_path: Path) -> None:
    """The tasks phase accepts either design or specs as its input dependency."""
    ChangeConfigAdministrator(repo_root=tmp_path).initialize_config()
    change_new(tmp_path, "by-design")
    design_dir = tmp_path / ".ai-harness" / "changes" / "by-design"
    (design_dir / "exploration.md").write_text("explored\n", encoding="utf-8")
    (design_dir / "prd.md").write_text("prd\n", encoding="utf-8")
    (design_dir / "design.md").write_text("design\n", encoding="utf-8")

    change_new(tmp_path, "by-specs")
    specs_dir = tmp_path / ".ai-harness" / "changes" / "by-specs"
    (specs_dir / "exploration.md").write_text("explored\n", encoding="utf-8")
    (specs_dir / "prd.md").write_text("prd\n", encoding="utf-8")
    (specs_dir / "specs").mkdir()
    (specs_dir / "specs" / "capability.md").write_text("spec\n", encoding="utf-8")

    assert change_continue(tmp_path, "by-design").dependencies["tasks"] == "ready"
    assert change_continue(tmp_path, "by-specs").dependencies["tasks"] == "ready"


def test_archive_requires_validation_and_non_empty_complete_tasks(tmp_path: Path) -> None:
    """Archive stays blocked for zero or pending tasks even when validation passes."""
    ChangeConfigAdministrator(repo_root=tmp_path).initialize_config()
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "exploration.md").write_text("explored\n", encoding="utf-8")
    (change_dir / "prd.md").write_text("prd\n", encoding="utf-8")
    (change_dir / "design.md").write_text("design\n", encoding="utf-8")
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "capability.md").write_text("spec\n", encoding="utf-8")
    (change_dir / "tasks.json").write_text('{"tasks": []}\n', encoding="utf-8")
    (change_dir / "implementation.md").write_text("implemented\n", encoding="utf-8")
    (change_dir / "validation.md").write_text(
        "## Verdict\nverdict: pass\ncritical: 0\n",
        encoding="utf-8",
    )

    assert change_continue(tmp_path, "demo").dependencies["archive"] == "blocked"

    (change_dir / "tasks.json").unlink()
    task = task_create(
        tmp_path,
        "demo",
        TaskInput(
            title="Finish work",
            spec="specs/capability.md",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    assert change_continue(tmp_path, "demo").dependencies["archive"] == "blocked"

    task_done(tmp_path, "demo", task.id)
    ready_status = change_continue(tmp_path, "demo")

    assert ready_status.taskProgress.total == 1
    assert ready_status.dependencies["archive"] == "ready"
    assert ready_status.nextRecommended == "archive"


def test_change_errors_on_collision_and_absent_change(tmp_path: Path) -> None:
    """Start collisions and resume typos are explicit store errors."""
    change_new(tmp_path, "demo")

    with pytest.raises(ChangeStoreError, match="already exists"):
        change_new(tmp_path, "demo")

    with pytest.raises(ChangeStoreError, match="not found"):
        change_continue(tmp_path, "missing")


def test_cli_change_new_and_continue_output_status_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI exposes change-new and change-continue as top-level JSON commands."""
    monkeypatch.chdir(tmp_path)
    ChangeConfigAdministrator(repo_root=tmp_path).initialize_config()

    new_result = runner.invoke(app, ["change-new", "demo"])
    continue_result = runner.invoke(app, ["change-continue", "demo"])

    assert new_result.exit_code == 0, new_result.stderr
    assert continue_result.exit_code == 0, continue_result.stderr
    new_status = json.loads(new_result.stdout)
    continue_status = json.loads(continue_result.stdout)
    assert new_status["schemaName"] == "ai-harness.change-status"
    assert new_status["nextRecommended"] == "explore"
    assert continue_status["changeName"] == "demo"
    assert "budget" not in new_status
    assert "verdict" not in new_status


def test_cli_change_errors_are_non_zero_and_not_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Change CLI errors go to stderr instead of being folded into status JSON."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["change-new", "demo"])

    collision = runner.invoke(app, ["change-new", "demo"])
    absent = runner.invoke(app, ["change-continue", "missing"])

    assert collision.exit_code == 1
    assert "already exists" in collision.stderr
    assert collision.stdout == ""
    assert absent.exit_code == 1
    assert "not found" in absent.stderr
    assert absent.stdout == ""


# ---------------------------------------------------------------------------
# deterministic configuration failure — CLI contract coverage
# ---------------------------------------------------------------------------


def test_change_continue_raises_changestoreerror_when_config_missing(tmp_path: Path) -> None:
    """Missing ``.ai-harness/config.yml`` halts continuation as ChangeStoreError."""
    change_new(tmp_path, "demo")

    with pytest.raises(ChangeStoreError, match="configuration"):
        change_continue(tmp_path, "demo")


def test_change_continue_raises_changestoreerror_when_config_malformed(tmp_path: Path) -> None:
    """Malformed YAML is normalized to ChangeStoreError at the seam."""
    change_new(tmp_path, "demo")
    (tmp_path / ".ai-harness" / "config.yml").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".ai-harness" / "config.yml").write_text("commit: [unclosed\n", encoding="utf-8")

    with pytest.raises(ChangeStoreError, match="configuration"):
        change_continue(tmp_path, "demo")


def test_change_continue_raises_changestoreerror_when_config_schema_invalid(tmp_path: Path) -> None:
    """Schema-invalid configuration halts continuation as ChangeStoreError."""
    change_new(tmp_path, "demo")
    (tmp_path / ".ai-harness" / "config.yml").parent.mkdir(parents=True, exist_ok=True)
    # Missing ``commit`` and ``phases`` keys → validation rejects.
    (tmp_path / ".ai-harness" / "config.yml").write_text("notes: this is not the schema\n", encoding="utf-8")

    with pytest.raises(ChangeStoreError, match="invalid"):
        change_continue(tmp_path, "demo")


def test_cli_change_continue_fails_when_config_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing config produces a non-zero exit, useful stderr, and no stdout JSON."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["change-new", "demo"])

    result = runner.invoke(app, ["change-continue", "demo"])

    assert result.exit_code == 1
    assert "configuration" in result.stderr.lower()
    assert result.stdout == ""


def test_cli_change_continue_fails_when_config_malformed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed YAML produces a non-zero exit, useful stderr, and no stdout JSON."""
    monkeypatch.chdir(tmp_path)
    ChangeConfigAdministrator(repo_root=tmp_path).initialize_config()
    runner.invoke(app, ["change-new", "demo"])
    (tmp_path / ".ai-harness" / "config.yml").write_text("commit: [unclosed\n", encoding="utf-8")

    result = runner.invoke(app, ["change-continue", "demo"])

    assert result.exit_code == 1
    assert "configuration" in result.stderr.lower()
    assert result.stdout == ""


def test_cli_change_continue_fails_when_config_schema_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Schema-invalid YAML produces a non-zero exit, useful stderr, and no stdout JSON."""
    monkeypatch.chdir(tmp_path)
    ChangeConfigAdministrator(repo_root=tmp_path).initialize_config()
    runner.invoke(app, ["change-new", "demo"])
    (tmp_path / ".ai-harness" / "config.yml").write_text("wrong_section: []\n", encoding="utf-8")

    result = runner.invoke(app, ["change-continue", "demo"])

    assert result.exit_code == 1
    assert "invalid" in result.stderr.lower()
    assert result.stdout == ""


def test_change_continue_succeeds_with_only_warnings(tmp_path: Path) -> None:
    """Validation warnings (unknown phase key) must NOT halt context delivery."""
    ChangeConfigAdministrator(repo_root=tmp_path).initialize_config()
    change_new(tmp_path, "demo")
    config_path = tmp_path / ".ai-harness" / "config.yml"
    data = __import__("yaml").safe_load(config_path.read_text(encoding="utf-8"))
    # Add a non-halting warning by introducing an unknown phase key.
    data["phases"]["change_extra"] = {"rules": ["preserved"]}
    config_path.write_text(__import__("yaml").safe_dump(data, sort_keys=False), encoding="utf-8")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "explore"
    # Warnings alone never produce a null configContext.
    assert status.configContext is not None
    assert status.configContext.phase == "change_explorer"


def test_cli_change_continue_succeeds_with_only_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI surfaces success and a populated configContext even when warnings exist."""
    monkeypatch.chdir(tmp_path)
    ChangeConfigAdministrator(repo_root=tmp_path).initialize_config()
    runner.invoke(app, ["change-new", "demo"])
    config_path = tmp_path / ".ai-harness" / "config.yml"
    data = __import__("yaml").safe_load(config_path.read_text(encoding="utf-8"))
    data["phases"]["change_extra"] = {"rules": ["preserved"]}
    config_path.write_text(__import__("yaml").safe_dump(data, sort_keys=False), encoding="utf-8")

    result = runner.invoke(app, ["change-continue", "demo"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schemaVersion"] == 3
    assert payload["configContext"] is not None
    assert payload["configContext"]["phase"] == "change_explorer"


# ---------------------------------------------------------------------------
# Helpers — build a Change folder that passes every archive preflight
# ---------------------------------------------------------------------------


def _build_archiveable_change(tmp_path: Path, name: str) -> Path:
    """Create a Change folder that satisfies every archive preflight check.

    Returns the change directory path. The fixture has a complete task
    plus a validation artifact, so the only preflight that could fire
    in a positive test is the destination-collision check.
    """
    change_new(tmp_path, name)
    change_dir = tmp_path / ".ai-harness" / "changes" / name
    (change_dir / "exploration.md").write_text("explored\n", encoding="utf-8")
    (change_dir / "prd.md").write_text("prd\n", encoding="utf-8")
    (change_dir / "design.md").write_text("design\n", encoding="utf-8")
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "capability.md").write_text("spec\n", encoding="utf-8")
    task = task_create(
        tmp_path,
        name,
        TaskInput(
            title="Finish work",
            spec="specs/capability.md",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    task_done(tmp_path, name, task.id)
    (change_dir / "implementation.md").write_text("implemented\n", encoding="utf-8")
    (change_dir / "validation.md").write_text(
        "## Verdict\nverdict: pass\ncritical: 0\n",
        encoding="utf-8",
    )
    return change_dir


# ---------------------------------------------------------------------------
# change_archive — preflight rejection paths
# ---------------------------------------------------------------------------


def test_change_archive_preflight_rejects_missing_change_folder(tmp_path: Path) -> None:
    """Archive rejects an absent Change folder before touching the filesystem."""
    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "ghost")

    assert excinfo.value.errors
    assert any("not found" in err for err in excinfo.value.errors)
    assert not (tmp_path / ".ai-harness" / "archive").exists()


def test_change_archive_preflight_rejects_incomplete_tasks(tmp_path: Path) -> None:
    """Archive rejects a Change whose tasks are not all complete."""
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "validation.md").write_text("verdict: pass\n", encoding="utf-8")
    task_create(
        tmp_path,
        "demo",
        TaskInput(
            title="Work",
            spec="x",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("incomplete" in err for err in excinfo.value.errors)
    # Preflight refused — no archive move happened.
    assert not (tmp_path / ".ai-harness" / "archive" / "demo").exists()


def test_change_archive_preflight_rejects_missing_validation_artifact(tmp_path: Path) -> None:
    """Archive rejects a Change whose validation.md is absent."""
    change_new(tmp_path, "demo")
    task = task_create(
        tmp_path,
        "demo",
        TaskInput(
            title="Work",
            spec="x",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    task_done(tmp_path, "demo", task.id)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("validation" in err.lower() for err in excinfo.value.errors)


def test_change_archive_preflight_rejects_existing_specs_destination(tmp_path: Path) -> None:
    """Archive refuses when the top-level specs destination already exists."""
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "validation.md").write_text("verdict: pass\n", encoding="utf-8")
    # Pre-create the specs destination collision.
    (tmp_path / ".ai-harness" / "specs" / "demo").mkdir(parents=True)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("specs destination" in err.lower() for err in excinfo.value.errors)
    # Source untouched — change folder still in place.
    assert change_dir.is_dir()


def test_change_archive_preflight_rejects_existing_archive_destination(tmp_path: Path) -> None:
    """Archive refuses when the top-level archive destination already exists."""
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "validation.md").write_text("verdict: pass\n", encoding="utf-8")
    (tmp_path / ".ai-harness" / "archive" / "demo").mkdir(parents=True)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("archive destination" in err.lower() for err in excinfo.value.errors)
    assert change_dir.is_dir()


def test_change_archive_preflight_collects_multiple_errors(tmp_path: Path) -> None:
    """Multiple unsafe conditions surface together in a single error list."""
    change_new(tmp_path, "demo")
    # Add a pending task so "tasks incomplete" actually fires (empty
    # task list is reported as all-complete by task_progress).
    task_create(
        tmp_path,
        "demo",
        TaskInput(
            title="Work",
            spec="x",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    # No validation.md + colliding archive dest.
    (tmp_path / ".ai-harness" / "archive" / "demo").mkdir(parents=True)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    errors = excinfo.value.errors
    assert any("incomplete" in err for err in errors)
    assert any("validation" in err.lower() for err in errors)
    assert any("archive destination" in err.lower() for err in errors)


def test_change_archive_preflight_does_not_mutate_on_failure(tmp_path: Path) -> None:
    """A failed preflight leaves the change folder, specs, and archive untouched."""
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "x.md").write_text("spec\n", encoding="utf-8")
    # No validation.md → preflight fails.
    assert (tmp_path / ".ai-harness" / "specs" / "demo").exists() is False

    with pytest.raises(ChangeStoreError):
        change_archive(tmp_path, "demo")

    # Source specs subtree is still in place.
    assert (change_dir / "specs" / "x.md").is_file()
    assert change_dir.is_dir()
    # No archive destination created.
    assert not (tmp_path / ".ai-harness" / "archive" / "demo").exists()
    # No specs destination created.
    assert not (tmp_path / ".ai-harness" / "specs" / "demo").exists()


# ---------------------------------------------------------------------------
# change_archive — successful transactional move
# ---------------------------------------------------------------------------


def test_change_archive_promotes_specs_and_moves_change_folder(tmp_path: Path) -> None:
    """Successful archive promotes specs and relocates the remaining change folder."""
    _build_archiveable_change(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"

    change_archive(tmp_path, "demo")

    # Specs subtree landed at the top-level specs destination.
    specs_dest = tmp_path / ".ai-harness" / "specs" / "demo"
    assert specs_dest.is_dir()
    assert (specs_dest / "capability.md").is_file()
    # Remaining change folder landed at the top-level archive destination.
    archive_dest = tmp_path / ".ai-harness" / "archive" / "demo"
    assert archive_dest.is_dir()
    assert (archive_dest / "prd.md").is_file()
    assert (archive_dest / "design.md").is_file()
    # Source change folder is gone.
    assert not change_dir.exists()


def test_change_archive_excludes_specs_subtree_from_archived_change(tmp_path: Path) -> None:
    """Archived change folder MUST NOT carry a duplicate specs/ subtree."""
    _build_archiveable_change(tmp_path, "demo")
    change_archive(tmp_path, "demo")

    archive_dest = tmp_path / ".ai-harness" / "archive" / "demo"
    assert not (archive_dest / "specs").exists()
    # Specs live at the top-level specs destination instead.
    assert (tmp_path / ".ai-harness" / "specs" / "demo" / "capability.md").is_file()


def test_change_archive_uses_canonical_top_level_layout(tmp_path: Path) -> None:
    """Archive lands at .ai-harness/archive/{change}, never .ai-harness/changes/archive/{change}."""
    _build_archiveable_change(tmp_path, "demo")
    change_archive(tmp_path, "demo")

    assert (tmp_path / ".ai-harness" / "archive" / "demo").is_dir()
    # The stale `changes/archive/{name}` layout is NOT created.
    assert not (tmp_path / ".ai-harness" / "changes" / "archive").exists()


def test_change_archive_rolls_back_when_change_folder_move_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure during the change-folder move restores the source tree intact."""
    _build_archiveable_change(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    specs_src = change_dir / "specs"

    # First shutil.move (specs promotion) succeeds; the second one (change
    # folder) is forced to fail. Preflight already passed, so the rollback
    # contract is what we're testing.
    real_move = __import__("shutil").move
    call_count = {"n": 0}

    def failing_move(src: str, dst: str) -> str:
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("simulated move failure")
        return real_move(src, dst)

    monkeypatch.setattr("ai_harness.modules.harness.change.shutil.move", failing_move)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("simulated move failure" in err for err in excinfo.value.errors)
    # Source change folder and its specs subtree are restored.
    assert change_dir.is_dir()
    assert specs_src.is_dir()
    assert (specs_src / "capability.md").is_file()
    # No partial destination was left behind.
    assert not (tmp_path / ".ai-harness" / "archive" / "demo").exists()


def test_change_archive_leaves_source_intact_when_specs_move_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure during the specs move leaves the change folder and archive untouched."""
    _build_archiveable_change(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    specs_src = change_dir / "specs"

    def failing_move(src: str, dst: str) -> str:
        if src.endswith("/specs") or src.endswith("\\specs"):
            raise OSError("simulated specs move failure")
        return __import__("shutil").move(src, dst)

    monkeypatch.setattr("ai_harness.modules.harness.change.shutil.move", failing_move)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("specs" in err for err in excinfo.value.errors)
    # Change folder + specs subtree still in place.
    assert change_dir.is_dir()
    assert specs_src.is_dir()
    # No destination created.
    assert not (tmp_path / ".ai-harness" / "archive" / "demo").exists()
    assert not (tmp_path / ".ai-harness" / "specs" / "demo").exists()


# ---------------------------------------------------------------------------
# CLI adapter — output contract
# ---------------------------------------------------------------------------


def test_cli_change_archive_success_prints_done_and_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful archive prints exactly 'done' on stdout and exits zero."""
    _build_archiveable_change(tmp_path, "demo")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-archive", "demo"])

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "done\n"
    # Side effects of success are visible on disk.
    assert (tmp_path / ".ai-harness" / "archive" / "demo").is_dir()
    assert (tmp_path / ".ai-harness" / "specs" / "demo").is_dir()


def test_cli_change_archive_failure_prints_json_errors_and_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed archive prints JSON {errors: [...]} on stdout and exits non-zero."""
    change_new(tmp_path, "demo")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-archive", "demo"])

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert "errors" in payload
    assert isinstance(payload["errors"], list)
    assert payload["errors"]
    # Failure is silent on stderr — the JSON shape is the contract.
    assert result.stderr == ""


def test_cli_change_archive_failure_does_not_emit_done(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed archive never prints the success token 'done'."""
    change_new(tmp_path, "demo")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-archive", "demo"])

    assert "done" not in result.stdout
    assert "done" not in result.stderr


def test_cli_change_archive_success_does_not_emit_change_status_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful archive output is 'done', not a ChangeStatus JSON object."""
    _build_archiveable_change(tmp_path, "demo")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-archive", "demo"])

    # Plain terminal token — no JSON braces, no schemaName field.
    assert result.stdout == "done\n"
    assert "schemaName" not in result.stdout
    assert "{" not in result.stdout


def test_cli_change_archive_allows_prose_outside_verdict_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Archive approval reads only the strict Verdict section."""
    _build_archiveable_change(tmp_path, "demo")
    validation_path = tmp_path / ".ai-harness" / "changes" / "demo" / "validation.md"
    body = validation_path.read_text(encoding="utf-8")
    validation_path.write_text(body + "## Ad-hoc\nReview prose.\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-archive", "demo"])

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "done\n"
