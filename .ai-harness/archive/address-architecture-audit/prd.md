# PRD — address-architecture-audit

## Title & TL;DR

Address the three agreed architecture-audit findings from `.ai-harness/audit-report.md` by removing six administrator by-pass methods, standing up `src/ai_harness/utils/` with the selected cross-module pure helpers from `wizard/pure.py`, and adding compact ASCII class-interaction diagrams beside the seams they explain. This change is intentionally surgical: preserve runtime behavior and public contracts while making the codebase comply with the audit evidence and the repo's architecture rules.

## Context

The source of truth for this change is `.ai-harness/audit-report.md`, with implementation discovery captured in `.ai-harness/changes/address-architecture-audit/exploration.md`.

The audit identified three hard findings that this change addresses:

- Six by-pass methods in the administrator subclasses, listed in `.ai-harness/audit-report.md:71-85` and ranked as an actionable finding in `.ai-harness/audit-report.md:167-170`.
- No ASCII class-interaction diagrams anywhere in source or docs, identified in `.ai-harness/audit-report.md:46-55` and ranked in `.ai-harness/audit-report.md:167`.
- Missing `src/ai_harness/utils/`, identified in `.ai-harness/audit-report.md:122-134` and ranked in `.ai-harness/audit-report.md:171`.

The AGENTS.md path-drift doc fix for `src/ai_harness/` was already landed separately and is not part of this change. The exploration confirms the implementation scope, affected files, migration boundary, risks, and verification expectations in `.ai-harness/changes/address-architecture-audit/exploration.md:3-44`.

## Goals

- Eliminate the six administrator by-pass methods cited by the audit by moving `get_agent_metadata()` and `discover_agent_names()` to concrete defaults on `ArtifactsAdministrator`, while preserving the existing public method names and signatures.
- Create `src/ai_harness/utils/` and migrate exactly the selected cross-module pure helpers from `src/ai_harness/modules/wizard/pure.py`: `AgentMode`, `parse_agent_mode()`, `claude_wizard_agents()`, and `opencode_change_agents()`.
- Add at least three compact ASCII class-interaction diagrams near the owning source seams: administrator Strategy dispatch, change/task FSM, and wizard phase loop.

## Non-goals

- Do not modify README path references or `CODING_STANDARDS.md` path references; no drift was identified there for this change.
- Do not change `e2e/`, `test-harness/`, or `expected/`.
- Do not modify `pyproject.toml` unless the utils migration unexpectedly requires Python path configuration; exploration confirmed no change is expected because `src` is already on pytest's pythonpath.
- Do not modify AGENTS.md path lines; the path-drift fix already landed separately.
- Do not migrate wizard-internal picker, catalog, label, or override-payload helpers; these stay in `src/ai_harness/modules/wizard/pure.py`.
- Do not broaden this change into a Protocol rewrite, administrator strategy redesign, docs/ADR tree, or behavior change.

## Capabilities

### Administrator default metadata and discovery

User-visible behavior: no behavior change. The same administrator objects continue to expose `get_agent_metadata()` and `discover_agent_names()` through the existing public contract, but identical one-line subclass wrappers are removed.

Acceptance criteria:

- `ArtifactsAdministrator` in `src/ai_harness/modules/harness/administrators/base.py` provides concrete defaults for `get_agent_metadata()` and `discover_agent_names()`.
- `render_artifacts()` remains the provider-specific abstract method on `ArtifactsAdministrator`.
- The six audit-cited wrappers are deleted from `src/ai_harness/modules/harness/administrators/claude.py`, `copilot.py`, and `opencode.py`.
- After the change, `grep -n 'def discover_agent_names' src/ai_harness/modules/harness/administrators/claude.py src/ai_harness/modules/harness/administrators/copilot.py src/ai_harness/modules/harness/administrators/opencode.py` returns zero matches.
- After the change, `grep -n 'def get_agent_metadata' src/ai_harness/modules/harness/administrators/claude.py src/ai_harness/modules/harness/administrators/copilot.py src/ai_harness/modules/harness/administrators/opencode.py` returns zero matches.
- Existing callers through `ADMINISTRATORS[...]` and polymorphic `ArtifactsAdministrator` references continue to work without import or call-site changes.

Risks:

- ABC contract break if signatures drift while moving the methods to the base class.
- Unused imports can remain in subclass modules if `_resolve_agent_metadata`, `AgentMetadata`, or module-level `discover_agent_names` imports are not cleaned up.
- The solution must not remove the public methods from the base contract; it only changes where the default implementation lives.

### Shared agent-set utilities package

User-visible behavior: no behavior change. Internal and test import sites move to `ai_harness.utils`, while `wizard/pure.py` keeps compatibility re-exports for one change to avoid a broad public import break.

Acceptance criteria:

- `src/ai_harness/utils/__init__.py` exists and re-exports the migrated helper API under stable `ai_harness.utils` names.
- `src/ai_harness/utils/agent_sets.py` owns `AgentMode`, `parse_agent_mode()`, `claude_wizard_agents()`, and `opencode_change_agents()`.
- `src/ai_harness/modules/wizard/pure.py` no longer owns the implementation of those four helpers, but imports and re-exports them for compatibility during this change.
- Production import sites identified by exploration, including `src/ai_harness/commands/set_models.py` and `src/ai_harness/modules/wizard/tui.py`, import migrated helpers from `ai_harness.utils` where appropriate.
- Test import sites identified by exploration, including `tests/test_set_models.py`, `tests/test_install.py`, and `tests/test_renderers.py`, are updated to import migrated helpers from `ai_harness.utils` where appropriate.
- Wizard-internal helpers such as `PickerRow`, `ModelSelection`, picker builders, catalog joiners, label alignment, and override payload builders remain in `wizard/pure.py`.
- No `pyproject.toml` change is required for this migration.

Risks:

- Import cycles if `utils/agent_sets.py` imports wizard TUI code, administrator modules, or other deep-module runtime dependencies.
- Public import break if existing `wizard.pure` consumers lose access before compatibility re-exports are provided.
- Over-migration could turn `utils/` into a junk drawer and weaken the wizard seam.

### Source-adjacent ASCII interaction diagrams

User-visible behavior: no runtime behavior change. Maintainers get source-adjacent diagrams that explain the three load-bearing interactions cited by the audit.

Acceptance criteria:

- Add an ASCII diagram for administrator Strategy dispatch near `ArtifactsAdministrator` and/or `ADMINISTRATORS`, covering the relationship between callers, the dispatch table, and concrete administrator implementations.
- Add an ASCII diagram for the change/task FSM near `ChangeStatus` or `_derive_status()` in `src/ai_harness/modules/harness/change.py`.
- Add an ASCII diagram for the wizard phase loop near `_drive_phases()` in `src/ai_harness/modules/wizard/tui.py`.
- Diagrams are plain ASCII, compact, and describe stable interactions rather than line-by-line implementation details.
- Diagrams live inside source docstrings or adjacent comments near the owning seams, as recommended by `.ai-harness/changes/address-architecture-audit/exploration.md:31`, instead of creating a new docs/ADR tree solely for this cleanup.

Risks:

- Diagrams can become stale if they are too broad or placed far from the code they describe.
- Large diagrams in top-level module docstrings can add noise; placing compact diagrams near the owning seam mitigates this.

## Open questions

- Confirm whether the compatibility re-exports in `wizard/pure.py` should be explicitly timeboxed to this one change and removed in a later cleanup, or retained indefinitely as supported public compatibility.

## Success metrics

- `ruff check` is clean.
- `pytest tests/` is green.
- An audit re-run shows zero violations for the three addressed findings: administrator by-pass methods, missing `src/ai_harness/utils/`, and missing ASCII class-interaction diagrams.
