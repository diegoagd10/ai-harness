"""Verify canonical prompt sources contain no YAML frontmatter.

Spec scenario: "One body per agent, no provider glue"
  - GIVEN any logical agent body under resources/prompts/
  - WHEN its file is read
  - THEN it contains no YAML frontmatter, no tool names, no model keys
  - AND no byte-identical copy exists elsewhere under resources/
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Every canonical prompt body that must exist after this refactor.
# sdd/ remains unchanged; jd/, review/, orchestrator/ are new.
_CANONICAL_PROMPT_PATHS: list[str] = [
    # JD agents (extracted from claude/agents/ body past ---)
    "prompts/jd/jd-fix-agent.md",
    "prompts/jd/jd-judge-a.md",
    "prompts/jd/jd-judge-b.md",
    # Review agents (extracted from claude/agents/ body past ---)
    "prompts/review/review-risk.md",
    "prompts/review/review-readability.md",
    "prompts/review/review-reliability.md",
    "prompts/review/review-resilience.md",
    # Orchestrator Agent variant (extracted from claude/sdd-orchestrator/SKILL.md body)
    "prompts/orchestrator/sdd-orchestrator-agent.md",
    # SDD phases (preexisting, must also lack frontmatter)
    "prompts/sdd/sdd-explore.md",
    "prompts/sdd/sdd-propose.md",
    "prompts/sdd/sdd-spec.md",
    "prompts/sdd/sdd-design.md",
    "prompts/sdd/sdd-tasks.md",
    "prompts/sdd/sdd-apply.md",
    "prompts/sdd/sdd-verify.md",
    "prompts/sdd/sdd-archive.md",
    # SDD orchestrator task variant (preexisting)
    "prompts/sdd/sdd-orchestrator.md",
]

# The resources root relative to this test file's project.
_RESOURCES = Path(__file__).resolve().parent.parent / "src" / "ai_harness" / "resources"


def _prompt_path(relative: str) -> Path:
    return _RESOURCES / relative


# ── existence ────────────────────────────────────────────────────────────────


def test_all_canonical_prompt_files_exist() -> None:
    """Every path in the inventory must resolve to a real file."""
    missing: list[str] = []
    for rel in _CANONICAL_PROMPT_PATHS:
        p = _prompt_path(rel)
        if not p.is_file():
            missing.append(rel)
    assert not missing, (
        f"Missing canonical prompt files: {missing}"
    )


# ── no frontmatter ───────────────────────────────────────────────────────────


def test_canonical_prompt_files_have_no_yaml_frontmatter() -> None:
    """No canonical prompt body may start with YAML frontmatter (---).

    Canonical bodies are content-only: they carry no provider metadata.
    """
    violations: list[str] = []
    for rel in _CANONICAL_PROMPT_PATHS:
        p = _prompt_path(rel)
        if not p.is_file():
            continue  # caught by existence test
        text = p.read_text(encoding="utf-8")
        if text.startswith("---"):
            violations.append(rel)
    assert not violations, (
        f"Canonical prompt files with YAML frontmatter: {violations}"
    )


def test_canonical_prompt_files_contain_no_tool_names() -> None:
    """No canonical body may mention a tool-name key or model."""
    # Yaml-like lines we must NOT see inside a canonical body.
    forbidden_patterns = [
        "tools:", "model:",  # YAML keys
        "tools :", "model :",  # spaced variant
    ]
    violations: list[tuple[str, str]] = []
    for rel in _CANONICAL_PROMPT_PATHS:
        p = _prompt_path(rel)
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            for pattern in forbidden_patterns:
                if stripped.startswith(pattern):
                    violations.append((rel, stripped))
    assert not violations, (
        f"Canonical prompt files with tool/model metadata: {violations}"
    )


# ── agent-clis/ absence ─────────────────────────────────────────────────────


def test_agent_clis_directory_absent() -> None:
    """After building agent CLIs from prompts, agent-clis/ MUST NOT exist.

    Spec: "Source-Tree Absence"
      - GIVEN source tree
      - THEN agent-clis/ stat returns ENOENT
    """
    agent_clis_root = _RESOURCES / "agent-clis"
    assert not agent_clis_root.exists(), (
        f"agent-clis/ directory must not exist: {agent_clis_root}"
    )
