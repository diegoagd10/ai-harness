# Exploration: address-architecture-audit

## Goal

Address the three architecture-audit findings from `.ai-harness/audit-report.md`: eliminate the six administrator by-pass methods cited at audit lines 71-85 and 167-170 by moving identical metadata/discovery defaults into `ArtifactsAdministrator`; create `src/ai_harness/utils/` and migrate the pure helpers from `wizard/pure.py` that have callers outside `wizard/`; and add at least three ASCII class-interaction diagrams for the administrator strategy dispatch, the change/task file-backed FSM, and the wizard phase loop.

## Affected files

- `src/ai_harness/modules/harness/administrators/base.py` — add non-abstract default `get_agent_metadata()` and `discover_agent_names()` implementations using `_resolve_agent_metadata()` and module-level `discover_agent_names()`; add administrator strategy ASCII diagram near the ABC; estimated `+35 / -2`.
- `src/ai_harness/modules/harness/administrators/claude.py` — remove imports only needed by the deleted wrappers and delete `get_agent_metadata()` / `discover_agent_names()` overrides; estimated `+0 / -22`.
- `src/ai_harness/modules/harness/administrators/copilot.py` — remove imports only needed by the deleted wrappers and delete `get_agent_metadata()` / `discover_agent_names()` overrides; estimated `+0 / -21`.
- `src/ai_harness/modules/harness/administrators/opencode.py` — remove imports only needed by the deleted wrappers and delete `get_agent_metadata()` / `discover_agent_names()` overrides; estimated `+0 / -21`.
- `src/ai_harness/modules/harness/administrators/__init__.py` — optionally add or reference the dispatch-table side of the administrator strategy diagram; estimated `+10 / -0` if the diagram is split from `base.py`.
- `src/ai_harness/modules/wizard/pure.py` — remove/move the helpers that have non-wizard callers, then import/re-export them for compatibility while keeping wizard-internal picker, catalog, label, and override-payload helpers local; estimated `+8 / -55`.
- `src/ai_harness/utils/__init__.py` — new package re-exporting migrated utility helpers under stable `ai_harness.utils` names; estimated `+15 / -0`.
- `src/ai_harness/utils/agent_sets.py` — new pure utility module for `AgentMode`, `parse_agent_mode()`, `claude_wizard_agents()`, and `opencode_change_agents()` because source/tests outside `wizard/` currently import or depend on them; estimated `+70 / -0`.
- `src/ai_harness/commands/set_models.py` — update `parse_agent_mode` import from `wizard.pure` to `ai_harness.utils`; estimated `+1 / -1`.
- `src/ai_harness/modules/wizard/tui.py` — update imports for migrated helpers while keeping wizard-internal helpers imported from `wizard.pure`; add the wizard phase-loop ASCII diagram near `_drive_phases()`; estimated `+35 / -4`.
- `src/ai_harness/modules/harness/change.py` — add change/task FSM ASCII diagram near `ChangeStatus` or `_derive_status()`; estimated `+35 / -0`.
- `src/ai_harness/modules/harness/tasks.py` — optionally reference the `change.py` FSM diagram from task dataclass docstrings; estimated `+5 / -0`.
- `tests/test_set_models.py` — update imports for migrated helpers/types while keeping wizard-internal helper tests pointed at `wizard.pure`; estimated `+4 / -4`.
- `tests/test_install.py` — update `opencode_change_agents` imports to `ai_harness.utils`; estimated `+2 / -2`.
- `tests/test_renderers.py` — update `claude_wizard_agents` / `opencode_change_agents` imports to `ai_harness.utils`; estimated `+2 / -2`.

## Plan

1. Preserve the `ArtifactsAdministrator` public contract by keeping the same method names and signatures, but make `get_agent_metadata()` and `discover_agent_names()` concrete defaults in `base.py`; only `render_artifacts()` remains abstract.
2. Delete the six cited by-pass methods from `ClaudeArtifactsAdministrator`, `CopilotArtifactsAdministrator`, and `OpenCodeArtifactsAdministrator`, and remove now-unused imports of `AgentMetadata`, `_resolve_agent_metadata`, and `discover_agent_names` from the subclass modules as applicable.
3. Migrate only the helpers with non-wizard callers out of `wizard/pure.py`: `AgentMode`, `parse_agent_mode()`, `claude_wizard_agents()`, and `opencode_change_agents()`. Keep wizard-internal UI/data-prep helpers such as `PickerRow`, `ModelSelection`, picker builders, OpenCode catalog joiners, label alignment, and override payload builders in `wizard/pure.py`.
4. Add `src/ai_harness/utils/__init__.py` and a focused `src/ai_harness/utils/agent_sets.py`; update production and test import sites to consume migrated helpers from `ai_harness.utils`. Keep backward-compatible imports/re-exports in `wizard/pure.py` unless the next phase explicitly chooses a breaking cleanup.
5. Add ASCII diagrams inside source docstrings near the load-bearing classes/functions instead of creating a new top-level docs/ADR tree: administrator strategy near `ArtifactsAdministrator`/`ADMINISTRATORS`, change/task FSM near `ChangeStatus` or `_derive_status()`, and wizard phase loop near `_drive_phases()`. This keeps diagrams next to the code they explain and avoids introducing a docs directory solely for three maintenance diagrams.
6. Verify with targeted gates in the next phases: administrator renderer tests, set-models pure/CLI tests, install tests that consume agent-set helpers, plus ruff format/check. No `pyproject.toml` change is expected because `src` is already on pytest's pythonpath and `ai_harness.utils` is inside the existing package.

## Risks

- ABC contract breaks: if `get_agent_metadata()` or `discover_agent_names()` signatures drift while becoming concrete defaults, existing callers through `ADMINISTRATORS[...]`, tests, or polymorphic `ArtifactsAdministrator` references can fail. Mitigation: copy exact subclass signatures and keep method names on the ABC.
- Import cycles from utils migration: `utils/agent_sets.py` must not import `wizard.tui` or administrator modules. It should depend only on stdlib types/enums so both `commands/set_models.py` and `wizard/pure.py` can import it safely.
- Callers of `wizard/pure.py` helpers: production currently imports `parse_agent_mode` from `src/ai_harness/commands/set_models.py`, while `src/ai_harness/modules/wizard/tui.py` imports many pure helpers; tests also import `claude_wizard_agents()` and `opencode_change_agents()` from `wizard.pure`. Mitigation: update known import sites and keep compatibility re-exports in `wizard/pure.py` during this change.
- Over-migrating wizard-internal helpers: moving `PickerRow`, `ModelSelection`, picker builders, catalog joiners, alignment, or override payload builders into `utils/` would turn a cohesive wizard seam into a junk drawer. Mitigation: move only helpers with outside-wizard callers.
- Diagram churn: large diagrams in broad module docstrings can become stale. Mitigation: place compact ASCII diagrams next to the owning class/function and describe stable interactions, not line-by-line implementation.

## Open questions

- None requiring user input for PRD/design. The only design choice to confirm is internal: keep compatibility re-exports in `wizard/pure.py` for one change to avoid a broad public import break while still updating repo import sites to `ai_harness.utils`.

## Budget

245
