# Design: Handoff Deepening — Rename `Target.GENERIC` → `Target.AGENTS` & Absorb Agents-on-Top

## Technical Approach

Move the "agents always installed" invariant from the caller (three locations: `_with_generic` helper, docstring preconditions, e2e comments) *into* `install_targets` as an inline prepend. Rename `Target.GENERIC` → `Target.AGENTS` so the enum matches the `.agents/AGENTS.md` filesystem the user sees. Add `parse_targets(raw, *, allowed=None)` — one parser, two policies — avoiding parser duplication.

## Architecture Decisions

### Decision 1: Deepen `install_targets` — absorb the agents-on-top invariant

| Option | Trade-off | Decision |
|--------|-----------|----------|
| Status quo: `_with_generic` helper in `install.py` | Caller must remember the rule; repeated in docstrings at 3 locations | Reject |
| Private `_ensure_agents` helper inside operations | Indirection that saves no interface complexity (locked decision #10) | Reject |
| Inline: `targets = [Target.AGENTS] + [t for t in targets if t is not Target.AGENTS]` | Absorbs the invariant; deletes the helper; one expression | **Accept** |

**Deep-modules rationale**: the **interface** loses a precondition and gains a guarantee — fewer things for N callers to remember (**leverage**). The invariant disappears from 3 locations (docstring, helper, module docstring) and concentrates in one implementation line (**locality**). Deleting `_with_generic` after deepening produces zero complexity reappearance.

**Trade-off**: `install_targets([Target.OPENCODE])` now writes `.agents/` too. Accepted: the user-facing concept is "agents" (the `.agents/` directory), and running agents alongside a tool is the sane default.

### Decision 2: Rename `Target.GENERIC` → `Target.AGENTS`

| Option | Trade-off | Decision |
|--------|-----------|----------|
| Keep `GENERIC` | Users see `.agents/AGENTS.md` on disk, not "generic" — jargon gap | Reject |
| Rename member only, keep value `"generic"` | Manifest keys stay stale | Reject |
| Rename member `AGENTS` + value `"agents"` | Hard break on old manifests; aligns code with filesystem | **Accept** |

**Rationale**: The enum is the **interface** vocabulary. `uninstall -o agents` should not require knowing the internal name was "generic." The **seam** between code and filesystem is now consistent. Old manifest breakage is dev-only (locked decision #8).

### Decision 3: `parse_targets` gains `allowed` kwarg

| Option | Trade-off | Decision |
|--------|-----------|----------|
| Two parsers (`parse_install_targets`, `parse_uninstall_targets`) | Duplicates validation | Reject |
| One parser, `allowed` kwarg | Small interface expansion; install passes `{CLAUDE, COPILOT, OPENCODE}`, uninstall passes default `set(Target)` | **Accept** |

**Rationale**: A small **interface** expansion prevents **implementation** duplication. The CLI **adapter** sets the policy; the parser enforces it. `typer.BadParameter` → non-zero exit (locked decision #4). All target-name validation lives in one function (**locality**).

## Module Map (after change)

| Module | Role | Public surface |
|--------|------|----------------|
| `models` | Type vocabulary | `Target(StrEnum)`, `InstallManifest` |
| `operations` | Deep implementation | `install_targets`, `uninstall_targets` |
| `commands` | Trust boundary adapter | `parse_targets(raw, *, allowed=None)` |
| `commands.install` | Thin typer adapter | Calls `parse_targets(…, allowed={CLAUDE, COPILOT, OPENCODE})`, then `install_targets(…)` |
| `commands.uninstall` | Thin typer adapter | Calls `parse_targets(…)` with default `allowed=None`, then `uninstall_targets(…)` |

## Key Sequences

| Scenario | parse_targets input | allowed | Result |
|----------|--------------------|---------|--------|
| `install -o claude,copilot` | `"claude,copilot"` | `{CLAUDE, COPILOT, OPENCODE}` | `[CLAUDE, COPILOT]` → `install_targets` prepends `AGENTS` |
| `install -o agents` (rejected) | `"agents"` | `{CLAUDE, COPILOT, OPENCODE}` | `BadParameter` → exit ≠ 0, no files written |
| `install` (no args) | `""` | `{CLAUDE, COPILOT, OPENCODE}` | `[]` → `install_targets` → manifest with `["agents"]` only |
| `uninstall -o agents` | `"agents"` | `None` (= `set(Target)`) | `[AGENTS]` → removes `.agents/` files |

## File Changes

| File | Action | What changes |
|------|--------|-------------|
| `models.py` | Modify | `GENERIC = "generic"` → `AGENTS = "agents"` |
| `operations.py` | Modify | Rename `Target.GENERIC` → `Target.AGENTS`; inline agents prepend; drop caller-precondition docstring |
| `commands/__init__.py` | Modify | `parse_targets` gains `*, allowed: set[Target] \| None = None` with filter logic |
| `commands/install.py` | Modify | Delete `_with_generic`; call `parse_targets(to, allowed={CLAUDE, COPILOT, OPENCODE})`; update docstrings + help |
| `commands/uninstall.py` | Modify | Update docstrings s/generic/agents/ |
| `tests/test_install.py` | Modify | 17× rename `Target.GENERIC`; 6× rename `"generic"` string; add `-o agents` rejection CLI test |
| `e2e/install_lifecycle.py` | Modify | Rename `_assert_generic_exists` → `_assert_agents_exists`; update assertion labels |
| `e2e/uninstall_lifecycle.py` | Modify | Same rename; fix `_test_uninstall_only_generic` |
| `README.md` | Modify | L4: "generic .agents consumers" → "agents directory" |

## Test Seams

- **`install_targets`**: `home=tmp_path` — the function's own **interface** is the seam.
- **`parse_targets`**: pure function, string in → list out or raise. `pytest.raises(typer.BadParameter)`.
- **CLI**: `typer.testing.CliRunner` — existing seam; add `-o agents` rejection.

## Risks / Accepted Breaks

- Old manifests with `"generic"` fail `Target(t)` on uninstall — dev-only break (locked #8).
- `install_targets([Target.OPENCODE])` now writes `.agents/` — existing opencode-only test must be updated to *assert* agents presence.
- No production users, no shipped manifests. Single PR revert.

## Open Questions

None — all decisions locked by proposal.
