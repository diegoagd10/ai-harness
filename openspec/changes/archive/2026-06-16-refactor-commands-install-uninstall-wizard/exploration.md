# Exploration: refactor-commands-install-uninstall

## Context

`ai-harness install` and `ai-harness uninstall` currently run all three CLI installers unconditionally. The user wants an interactive wizard that lets them pick which agents to install or uninstall, and a simple state file so the tool knows what is already installed.

## Current State

- `src/ai_harness/commands/artifacts/install.py` (lines 17–28) and `src/ai_harness/commands/artifacts/uninstall.py` (lines 17–28) are thin orchestrators. Each instantiates `ArtifactCatalog`, then loops over `OpencodeInstaller`, `ClaudeInstaller`, and `CopilotInstaller` in that fixed order, calling `install(home, console)` or `uninstall(home, console)` unconditionally.
- `src/ai_harness/commands/artifacts/__init__.py` (lines 12–18) registers `install` and `uninstall` on the Typer app from `main.py`.
- `src/ai_harness/main.py` (lines 16–17) calls `register_artifact_commands(app)`.
- `pyproject.toml` (lines 9–13) lists only `pyyaml`, `rich`, and `typer` as runtime dependencies. `questionary` is not present, and `uv.lock` contains no `questionary`/`prompt-toolkit` entries.
- `src/ai_harness/artifacts/installer.py` is the deep module for file I/O. It handles backup/restore and conflict rotation, but returns `None` and does not report success/failure per installer.

## Established Design Decisions

From the grill session, the following are fixed and should not be re-opened:

- **Library**: `questionary` for the interactive checkbox UI.
- **State file**: `~/.ai-harness/state.json` with shape `{"installed": ["opencode", "claude", "copilot"]}`.
- **Missing state file**: treated as an empty list; no auto-recovery.
- **Agent order in all lists**: OpenCode, Claude Code, Copilot CLI.
- **Install wizard**: always shows all three agents; pre-selects the ones not already in `installed`.
- **Uninstall wizard**: shows only agents present in `installed`; nothing pre-selected.
- **State write semantics**: all-or-nothing per session — write the file only if every selected agent succeeds.
- **Visual**: header + footer with key hints (`↑↓/j k move · space toggle · enter confirm · esc cancel`).
- **Terminal states**:
  - Escape → exit 1 with a cancellation message.
  - Enter with zero selected → exit 0 with a "No agents were …" message.
  - Enter with N>0 selected → execute; exit 0 on full success, non-zero on any failure.

## Codebase Findings

### What each installer writes today

These are the target paths that the wizard will eventually track. The state file is the source of truth, but the targets explain what "installed" means physically.

- **OpencodeInstaller** (`src/ai_harness/artifacts/installers/opencode.py`, lines 64–107):
  - `~/.config/opencode/AGENTS.md`
  - `~/.agents/AGENTS.md`
  - `~/.config/opencode/opencode.json` (with `{{HOME}}` substitution)
  - `~/.config/opencode/prompts/sdd/*.md`
  - `~/.agents/skills/*`

- **ClaudeInstaller** (`src/ai_harness/artifacts/installers/claude.py`, lines 95–139):
  - `~/.claude/CLAUDE.md`
  - `~/.claude/agents/<phase>.md` for 8 SDD phases (composed)
  - `~/.claude/agents/<inline>.md` for 7 inline agents
  - `~/.claude/skills/*`
  - `~/.claude/skills/sdd-orchestrator/SKILL.md`

- **CopilotInstaller** (`src/ai_harness/artifacts/installers/copilot.py`, lines 104–150):
  - `~/.copilot/copilot-instructions.md`
  - `~/.copilot/agents/<phase>.md` for 9 composed agents (SDD phases + orchestrator)
  - `~/.copilot/agents/<inline>.md` for 7 inline agents
  - `~/.copilot/hooks/sdd-pre-tool-use.json`
  - `~/.copilot/skills/*`

### Catalog

`src/ai_harness/artifacts/catalog.py` (lines 48–93) is CLI-agnostic. It exposes resource discovery methods (`get_root`, `get_main_instructions`, `get_resource_dir`, `get_skills`). The wizard does not need to consume the catalog directly; it only needs a mapping from agent names to installer classes.

### No existing state file or detection logic

There is no `~/.ai-harness/state.json`, no `.ai-harness` directory, and no `is_installed` method on any installer class. `README.md` lines 81–82 mentions a "central harness manifest", but no such manifest exists in code; `state.json` will be the first persistent runtime state.

### No existing interactive prompt infrastructure

The project already uses `rich` for console output, but there are no reusable prompt/select/checkbox helpers. `questionary` will be the first interactive input dependency.

### Test/e2e impact

- `tests/test_install.py` and `tests/test_uninstall.py` invoke `runner.invoke(app, ["install"])` and assert that all three installers ran. These tests will need to be rewritten to drive the wizard (or to use a non-interactive bypass) and to assert state file updates.
- `tests/test_installer.py` exercises the generic installer and can be reused, but the command-layer tests need new coverage for selection, cancellation, and zero-selection paths.
- `e2e/test_harness_lifecycle.py` calls `ai-harness install` and `ai-harness uninstall` in a subprocess with no TTY. Adding an interactive default will break these tests unless the design provides a non-interactive mode (e.g., a `--all` flag) or feeds stdin.

## Risks & Open Questions

1. **All-or-nothing semantics vs. current installer behavior**
   The generic installer writes files and creates backups as it goes. If the second or third selected installer fails, files written by earlier installers are already on disk, but the state file must not be updated. This can leave the user’s home in a partially installed state. The design phase should decide whether to attempt rollback or simply document that a failure leaves partial filesystem changes.

2. **Generic installer does not return success/failure**
   `installer.install()` and `installer.uninstall()` return `None`. The wizard will need a way to detect failure (catch exceptions, or add return values). This is a design-phase decision.

3. **Interactive default breaks non-TTY tests and e2e**
   The existing unit tests and the e2e harness lifecycle assume `install`/`uninstall` run without interaction. The design phase should decide whether to add a `--yes`/`-y` or `--all` non-interactive flag, or to refactor tests to send wizard input via stdin.

4. **Backup/conflict rotation is unchanged**
   Backup/restore behavior inside each installer is unaffected by the wizard, but the state file must remain consistent with whichever agents were selected. If an agent is uninstalled, its entry is removed only after the uninstall succeeds.

5. **README divergence**
   `README.md` describes a "central harness manifest" that does not exist. The design should clarify whether `state.json` replaces that concept and whether README updates are in scope.

## Scope Estimate

Keep total production + test code under the C2 review budget of ~800 LOC.

| Area | Files | Approx. LOC | Notes |
|------|-------|-------------|-------|
| Production | `src/ai_harness/state.py` | 40 | Read/write `~/.ai-harness/state.json`, shape validation. |
| Production | `src/ai_harness/wizard.py` | 80 | `questionary` checkbox UI, header/footer, key hints. |
| Production | `src/ai_harness/commands/artifacts/install.py` | +25 | Select agents, call installer, update state. |
| Production | `src/ai_harness/commands/artifacts/uninstall.py` | +25 | Filter to installed, call uninstaller, update state. |
| Production | `pyproject.toml` / `uv.lock` | — | Add `questionary` dependency. |
| Tests | `tests/test_state.py` | 60 | Load/save state, missing file, bad JSON. |
| Tests | `tests/test_wizard.py` | 80 | Checkbox defaults, selection, escape, zero-selected. |
| Tests | Rewrite `tests/test_install.py` | 120 | Drive wizard or use bypass; assert state and filesystem. |
| Tests | Rewrite `tests/test_uninstall.py` | 120 | Same as above for uninstall. |
| Tests | `e2e/test_harness_lifecycle.py` | +40 | Use non-interactive flag or stdin. |
| **Total** | | **~570** | Well under 800 LOC. |

If a full rollback mechanism or a non-TTY bypass is added, the estimate could approach 700 LOC but should still fit within the budget.
