"""Change-config administrator — owns the ``.ai-harness/config.yml`` lifecycle.

This module is the deep seam for the change orchestrator: every
orchestrator sub-agent reads its phase rules through
:meth:`ChangeConfigAdministrator.get_context_by`, the user mutates the
file between phases, and the next phase validates integrity through
:meth:`ChangeConfigAdministrator.validate_config` before reading. The
admin hides YAML parsing, the strict schema, phase-key normalization,
and the immutable typed conversion behind three public methods.

The contract dictating this surface is fixed at three methods — no
more, no fewer. Paths are injected via the constructor so tests can
drive the seam against ``tmp_path`` without touching the host repo.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ai_harness.modules.change_config.models import (
    ChangeConfigPromptContext,
    ChangeConfigValidationResults,
)

__all__ = ["ChangeConfigAdministrator", "ChangeConfigError"]

_MANIFEST_DIR = ".ai-harness"
_CONFIG_FILENAME = "config.yml"

_DEFAULT_COMMIT_FORMAT: str = "[{change_name}][{task_id}] {slug}"

_PHASE_ORDER: tuple[str, ...] = (
    "change_explorer",
    "change_propose",
    "change_design",
    "change_specs",
    "change_tasks",
    "change_implementor",
    "change_validator",
    "change_archiver",
)

# Public alias of the canonical phase-order tuple. The seam exposes it so
# callers (notably the ``ai-harness init`` CLI tests) can verify the
# generated config against a single source of truth instead of duplicating
# the list — which previously tripped pylint's duplicate-code gate.
PHASE_ORDER: tuple[str, ...] = _PHASE_ORDER

# Canonical phase keys map to themselves; short aliases map to their owner.
# Consulted *after* kebab-to-snake normalization so callers can pass either
# "explore" or "change-explorer" interchangeably and land on the same node.
_PHASE_ALIASES: dict[str, str] = {
    "change_explorer": "change_explorer",
    "explore": "change_explorer",
    "explorer": "change_explorer",
    "change_propose": "change_propose",
    "prd": "change_propose",
    "propose": "change_propose",
    "change_design": "change_design",
    "design": "change_design",
    "change_specs": "change_specs",
    "specs": "change_specs",
    "change_tasks": "change_tasks",
    "tasks": "change_tasks",
    "change_implementor": "change_implementor",
    "implement": "change_implementor",
    "implementor": "change_implementor",
    "change_validator": "change_validator",
    "validate": "change_validator",
    "validator": "change_validator",
    "change_archiver": "change_archiver",
    "archive": "change_archiver",
    "archiver": "change_archiver",
}


class ChangeConfigError(ValueError):
    """Raised when ``.ai-harness/config.yml`` cannot be parsed into the strict schema.

    Covers every halting failure mode the orchestrator must surface
    verbatim: file missing, YAML unparseable, top-level wrong shape,
    missing required keys, and wrong-typed values. Non-halting issues
    (unknown phase keys) come back through
    :class:`ChangeConfigValidationResults.warnings` instead.
    """


def _empty_template() -> dict:
    """Return the starter schema: ``commit`` rule + one entry per orchestrator phase.

    Each phase starts with an empty ``rules`` list — the template is the
    shape the user fills in, never invented default rule text.
    """
    return {
        "commit": {"format": _DEFAULT_COMMIT_FORMAT},
        "phases": {phase_key: {"rules": []} for phase_key in _PHASE_ORDER},
    }


class ChangeConfigAdministrator:
    def __init__(self, repo_root: Path | None = None) -> None:
        """Pin the seam to ``repo_root`` so methods take no path argument.

        Resolves to ``<repo_root>/.ai-harness/``; defaults to
        ``Path.cwd()`` when *repo_root* is ``None`` — matches the
        project-wide ``init_repo`` and ``create_worktree`` seams.
        """
        self._config_dir = (repo_root if repo_root is not None else Path.cwd()) / _MANIFEST_DIR

    def initialize_config(self):
        """Creates an empty config.yml under .ai-harness directory
        containing an empty template with commit rules and the properties
        representing the rules for each phase of change-orchestrator"""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        path = self._config_dir / _CONFIG_FILENAME
        if path.is_file():
            return
        path.write_text(
            yaml.safe_dump(_empty_template(), sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    def get_context_by(self, change_phase: str) -> ChangeConfigPromptContext:
        """Read the phase rules and returns an object representing rules that needs to be
        injected by the next phase"""
        canonical = self._normalize_phase_key(change_phase)
        data = yaml.safe_load((self._config_dir / _CONFIG_FILENAME).read_text(encoding="utf-8")) or {}
        phases = data.get("phases", {}) if isinstance(data, dict) else {}
        phase = phases.get(canonical, {}) if isinstance(phases, dict) else {}
        rules = phase.get("rules", []) if isinstance(phase, dict) else []
        commit = data.get("commit", {}) if isinstance(data, dict) else {}
        commit_format = commit.get("format") if isinstance(commit, dict) else None
        return ChangeConfigPromptContext(
            phase=canonical,
            phase_rules=tuple(rules) if isinstance(rules, list) else (),
            commit_format=commit_format if isinstance(commit_format, str) else _DEFAULT_COMMIT_FORMAT,
        )

    def _normalize_phase_key(self, raw: str) -> str:
        """Map a caller-supplied phase key to its canonical snake_case owner.

        Trims whitespace, converts kebab-case to snake_case, then looks
        the result up in :data:`_PHASE_ALIASES` so short aliases land on
        their canonical phase. Unknown values pass through the
        kebab-conversion unchanged so callers asking for an absent phase
        still get a deterministic ``ChangeConfigPromptContext`` with
        empty rules.
        """
        normalized = raw.strip().replace("-", "_")
        return _PHASE_ALIASES.get(normalized, normalized)

    def validate_config(self) -> ChangeConfigValidationResults:
        """Validates that integratety of the config.yml after the user
        updated the rules"""
        config_path = self._config_dir / _CONFIG_FILENAME
        if not config_path.is_file():
            raise ChangeConfigError(f"Config file not found: {config_path}")
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ChangeConfigError(f"Could not parse YAML at {config_path}: {exc}") from exc
        is_valid = self._schema_is_valid(raw)
        warnings = self._collect_warnings(raw)
        return ChangeConfigValidationResults(is_valid=is_valid, warnings=warnings)

    def _collect_warnings(self, raw: object) -> tuple[str, ...]:
        """Return deterministic warnings for preserved-but-suspect config state.

        Currently flags phase keys outside the canonical eight so a typo
        like ``change_explorerr`` does not silently load but the
        validator never halts either. The schema check has already run,
        so ``raw`` is well-shaped when we get here.
        """
        if not isinstance(raw, dict):
            return ()
        phases = raw.get("phases")
        if not isinstance(phases, dict):
            return ()
        messages: list[str] = []
        for phase_key in phases:
            if phase_key not in _PHASE_ORDER:
                messages.append(
                    f"Unknown phase key at phases.{phase_key}; value preserved but no known phase will use it."
                )
        return tuple(messages)

    def _schema_is_valid(self, raw: object) -> bool:
        """Return True iff *raw* parses into the strict config schema.

        Top-level must be a mapping with a string ``commit.format`` and a
        ``phases`` mapping whose values each carry a list ``rules``.
        Anything else — wrong shape, missing keys, wrong types — short-
        circuits to ``False``. ``yaml.safe_load`` already returned the
        parsed structure; this walks it without re-reading the file.
        """
        if not isinstance(raw, dict):
            return False
        commit = raw.get("commit")
        if not isinstance(commit, dict):
            return False
        if not isinstance(commit.get("format"), str):
            return False
        phases = raw.get("phases")
        if not isinstance(phases, dict):
            return False
        for phase_value in phases.values():
            if not isinstance(phase_value, dict):
                return False
            if not isinstance(phase_value.get("rules"), list):
                return False
        return True
