# Design — address-architecture-audit

## Context

This managed change addresses the three agreed audit findings without broadening the product or runtime contract: six administrator by-pass methods, a missing `src/ai_harness/utils/` package for selected cross-module pure helpers, and missing ASCII class-interaction diagrams. The PRD anchors those findings to `.ai-harness/audit-report.md:71-85`, `.ai-harness/audit-report.md:122-134`, and `.ai-harness/audit-report.md:46-55`; the ranked audit summary repeats the same three targets at `.ai-harness/audit-report.md:167-171`. The exploration narrows the implementation plan to concrete administrator defaults, a focused `utils/agent_sets.py`, compatibility re-exports in `wizard/pure.py`, and source-adjacent diagrams near the owning seams (`.ai-harness/changes/address-architecture-audit/exploration.md:25-32`).

The design constraint is surgical preservation: public method names and signatures stay available, existing `ADMINISTRATORS[...]` dispatch remains the composition seam, wizard-internal helpers stay in the wizard, and diagrams document stable interactions rather than creating a separate docs or ADR tree.

## Deep modules

### ArtifactsAdministrator base class

- Seam: `src/ai_harness/modules/harness/administrators/base.py`, through the existing `ArtifactsAdministrator` contract and the `ADMINISTRATORS` strategy dispatch table described in the audit at `.ai-harness/audit-report.md:35-38`.
- Interface: callers continue to use the same administrator object methods: `render_artifacts(...)`, `get_agent_metadata(name, overrides=None, *, home=None)`, and `discover_agent_names()`. `get_agent_metadata()` and `discover_agent_names()` become concrete defaults on the base class and delegate to the existing module-level helper behavior; subclasses inherit them unless a future provider has real provider-specific behavior. `render_artifacts(...)` remains abstract because artifact rendering is the provider-specific operation that differs across Claude, Copilot, and OpenCode.
- Hides: the ABC no longer leaks the repeated requirement that every provider hand-write identical metadata and discovery wrappers. The base class absorbs the common helper delegation while leaving provider render helpers, private render details, and dispatch-table selection untouched.
- Depth note: deleting the base defaults would reintroduce six shallow by-pass methods cited by `.ai-harness/audit-report.md:73-84`; keeping them concentrates common behavior behind one small public seam instead of moving names around.

### `ai_harness.utils` package

- Seam: `src/ai_harness/utils/__init__.py` and `src/ai_harness/utils/agent_sets.py`, introduced as the stable import location for cross-module pure agent-set helpers selected in the PRD at `.ai-harness/changes/address-architecture-audit/prd.md:55-67`.
- Interface: the public utility surface for this change is exactly `AgentMode`, `parse_agent_mode()`, `claude_wizard_agents()`, and `opencode_change_agents()`. `__init__.py` re-exports those names so callers can import from `ai_harness.utils`; `agent_sets.py` owns the implementation. `src/ai_harness/modules/wizard/pure.py` imports and re-exports the same four names for compatibility during this change.
- Hides: parsing of agent-mode strings and construction/filtering of the shared Claude/OpenCode agent-name sets become independent from wizard UI code. The utility module must depend only on the standard library and local constants/types it owns; it must not import `wizard.tui`, administrator modules, command modules, or rendering code.
- Depth note: the seam is deep because it removes cross-module callers from `wizard/pure.py` while keeping wizard-only picker rows, model selections, catalog joins, label alignment, and override payload helpers inside the wizard as required by `.ai-harness/changes/address-architecture-audit/exploration.md:29-30`. It rejects turning `utils/` into a junk drawer.

### Source-adjacent diagrams

- Seam: source docstrings or immediately adjacent comments placed beside the owning class/function seams, not a new docs tree. The required placements are near `ArtifactsAdministrator` or `ADMINISTRATORS`, near `ChangeStatus` or `_derive_status()` in `src/ai_harness/modules/harness/change.py`, and near `_drive_phases()` in `src/ai_harness/modules/wizard/tui.py`, matching `.ai-harness/changes/address-architecture-audit/prd.md:75-90`.
- Interface: each diagram is compact plain ASCII that explains a stable interaction: administrator Strategy dispatch from caller to `ADMINISTRATORS` to provider implementation; change/task status derivation as a file-backed FSM; and the wizard phase loop from phase selection through phase execution and navigation. The diagrams are documentation contracts, not executable APIs.
- Hides: diagrams deliberately omit line-by-line control flow, local variables, and transient implementation details. Their job is to preserve the mental model at the seam where maintainers need it, not to duplicate code.
- Depth note: source-adjacent diagrams pass the deletion test because removing them would leave the exact audit violation unchanged (`.ai-harness/audit-report.md:46-55`) and force maintainers to reconstruct stable interactions from scattered code.

## Internal collaborators

- Existing module-level administrator helpers remain internal collaborators behind `ArtifactsAdministrator`: metadata resolution and agent-name discovery are reused by the base defaults, not promoted into new public seams. They should be tested transitively through administrator behavior.
- Provider render helpers in `claude.py`, `copilot.py`, and `opencode.py` remain private implementation detail behind `render_artifacts(...)`; this change must not create new wrapper classes or methods around them.
- `wizard/pure.py` remains the home for wizard-internal pure helpers. Its compatibility re-exports for the four migrated names are temporary compatibility shims for this change, while repo production/test imports move toward `ai_harness.utils` as listed in `.ai-harness/changes/address-architecture-audit/exploration.md:17-23`.
- The three ASCII diagrams are internal documentation collaborators. They are owned by nearby source seams and should evolve with those seams instead of being treated as detached architecture docs.

## Seam map

```text
Administrator dispatch:
  operations/callers
        |
        v
  ADMINISTRATORS[AgentCli]  --->  ArtifactsAdministrator
                                      | render_artifacts(...) abstract
                                      | get_agent_metadata(...) default
                                      | discover_agent_names() default
                                      v
                         Claude / Copilot / OpenCode render behavior

Agent-set utilities:
  commands/set_models.py ----\
  wizard/tui.py -------------+--> ai_harness.utils.{AgentMode, parse_agent_mode,
  tests ---------------------/        claude_wizard_agents, opencode_change_agents}
                                      ^
                                      |
                         wizard/pure.py compatibility re-exports

Source-adjacent diagrams:
  base.py seam diagram       -> administrator Strategy dispatch
  change.py seam diagram     -> change/task status FSM
  wizard/tui.py seam diagram -> wizard phase loop
```

## Rejected alternatives

- Keep the six subclass methods and only rename imports: rejected because it preserves the by-pass-method violation identified at `.ai-harness/audit-report.md:71-85` and does not deepen the base seam.
- Replace `ArtifactsAdministrator` with a `Protocol` or callable strategy in this change: rejected as scope creep. The audit notes the composition dispatch is already good and the ABC inheritance is only borderline (`.ai-harness/audit-report.md:31-39`); this change only removes the shallow duplicated methods while preserving dispatch.
- Move all of `wizard/pure.py` into `utils/`: rejected because picker rows, model selections, catalog joins, label alignment, and override-payload builders are wizard-internal helpers, not cross-module utilities (`.ai-harness/changes/address-architecture-audit/prd.md:31` and `.ai-harness/changes/address-architecture-audit/exploration.md:39`).
- Remove `wizard/pure.py` compatibility imports immediately: rejected because the PRD requires compatibility re-exports during this change to avoid a broad public import break (`.ai-harness/changes/address-architecture-audit/prd.md:57-64`).
- Put diagrams in a new `docs/` or ADR directory: rejected because the exploration chose source-adjacent docstrings to avoid stale detached diagrams and avoid introducing a docs tree solely for this cleanup (`.ai-harness/changes/address-architecture-audit/exploration.md:31`).
