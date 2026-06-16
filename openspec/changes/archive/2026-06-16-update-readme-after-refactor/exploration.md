## Context

The root `README.md` was rewritten in `improve-readme-onboarding` to fix broken install paths, add a problem-first structure, and document the native `ai-harness` SDD subcommands. That change was archived, but `main` has since merged PR #10 (`refactor/commands-install-uninstall`), which extracted install/uninstall logic into per-CLI installers, introduced an `ArtifactManifest` data contract, and reorganized commands under `src/ai_harness/commands/`. The user needs to know whether those changes invalidate the README or require updates before the repo is renamed and the README is committed.

The previous proposal explicitly flagged a coordination risk: if the new `ArtifactManifest` enumerated `src/ai_harness/resources/agent-clis/opencode/README.md` (the sub-README deleted by `improve-readme-onboarding`), the refactor and the README change would conflict. That question must be answered concretely before any README can be considered final.

## Coordination risk — manifest check

`ArtifactManifest` is **not** a Python `enum`; it is an immutable dataclass declared in `src/ai_harness/artifacts/manifest.py` (lines 35–40) with two fields: `files: list[FileArtifact]` and `dirs: list[DirArtifact]`. It does not pre-enumerate resource files; per-CLI installers build a manifest at runtime from explicit `FileArtifact` and `DirArtifact` instances.

- Does `ArtifactManifest` list the deleted sub-README? **No.** `manifest.py` contains no literal paths at all; the class only defines the data contract (`source`, `target_relative`, etc.).
- Does `catalog.py` reference the deleted sub-README by name? **No.** `src/ai_harness/artifacts/catalog.py` line 19 references `agent-clis/opencode/opencode.json`, not a README: `OPENCODE_JSON_SRC = RESOURCES_DIR / "agent-clis" / "opencode" / "opencode.json"`.
- Does `installer.py` enumerate the resource directory by glob? **No.** `src/ai_harness/artifacts/installer.py` iterates only the explicit `manifest.files` list (line 43) and `manifest.dirs` list (line 64). `DirArtifact` install/uninstall enumerates the *source* directory of each declared `DirArtifact` (lines 69 and 109), but a directory is only in the manifest if an installer explicitly added it.
- Does `installers/opencode.py` reference the deleted sub-README? **No.** `src/ai_harness/artifacts/installers/opencode.py` references only `agent-clis/opencode/opencode.json` (lines 39 and 51), `prompts/sdd` (lines 42 and 54), `AGENTS.md` via `get_main_instructions()` (line 60), and the `skills/` directory (line 100).

A quick repository-wide grep for `agent-clis/opencode/README` in `*.py` files returns zero production-code matches; the only matches are in archived `openspec/changes/archive/` artifacts and in `tests/test_catalog.py`, where a `README.md` is created as test fixture data inside a temporary `skills/` directory (line 50) and is unrelated to the deleted sub-README.

**Verdict:** `Safe — manifest does not enumerate documentation files`. The deleted `agent-clis/opencode/README.md` is not referenced by the new artifact subsystem. The refactor's manifest is built explicitly by installers and is independent of the deleted file.

## README accuracy audit

| # | Section | Verdict | Notes |
|---|---------|---------|-------|
| 1 | `# ai-harness` | ACCURATE | H1 matches the intended project rename. |
| 2 | `## Why we built this` | ACCURATE | Problem statement is unchanged by the refactor. |
| 3 | `## What this tool does` | ACCURATE | The SDD pipeline and ASCII diagram describe prompt/configuration orchestration; the refactor changed install architecture, not the SDD flow. |
| 4 | `## Getting started` | ACCURATE | `uv tool install .`, `ai-harness install`, and `ai-harness uninstall` still resolve through `main.py` and the new command packages. |
| 5 | `## Driving the SDD pipeline` | OUTDATED (minor) | `sdd-status` currently **always** emits JSON (`src/ai_harness/commands/sdd/status.py:30` hard-codes `json_output=True`), so the parenthetical "(use `--json` for machine-readable output)" is misleading — `--json` exists as a Typer option but is effectively a no-op. |
| 6 | `### Prerequisite: Engram` | ACCURATE | No code change affects the Engram recommendation. |
| 7 | `## What's in here` | MISSING | The directory table omits the new `src/ai_harness/artifacts/` and `src/ai_harness/commands/` packages. The `src/ai_harness/` row is still broadly true but no longer the home of command implementations. |
| 8 | `## Running tests` | MISSING | The section only documents `uv run inv test` and `e2e/docker-test.sh`; it does not mention the unit-test command (`uv run pytest`) that the refactor added tests for. |
| 9 | `## Contributing` | ACCURATE | No change to contribution workflow. |

Summary: 6 accurate, 1 outdated, 2 missing.

## Command surface changes

| README claim | File that backs it | Verdict |
|---|---|---|
| `ai-harness install` | `src/ai_harness/main.py` + `src/ai_harness/commands/artifacts/install.py` | ACCURATE |
| `ai-harness uninstall` | `src/ai_harness/main.py` + `src/ai_harness/commands/artifacts/uninstall.py` | ACCURATE |
| `ai-harness sdd-status` | `src/ai_harness/main.py` + `src/ai_harness/commands/sdd/status.py` | ACCURATE |
| `ai-harness sdd-continue` | `src/ai_harness/main.py` + `src/ai_harness/commands/sdd/continue_cmd.py` | ACCURATE |
| `uv run inv test` | `tasks.py` + `e2e/tasks.py` | ACCURATE |

## New directories in the tree

- `src/ai_harness/artifacts/` — Contains the manifest dataclasses, generic installer I/O policy, resource catalog, and per-CLI installer modules. The `## What's in here` table should add a row for this directory.
- `src/ai_harness/commands/` — Contains the Typer command registration packages (`sdd/` and `artifacts/`). The table should add a row for this directory.
- `tests/` — Already existed, but now additionally holds `test_catalog.py` and `test_installer.py` covering the new artifact subsystem. A sentence noting unit tests for the new modules is sufficient; a separate table row may not be necessary.

## Recommended change scope

**Small — fix 1–3 specific inaccuracies:**

1. Correct the `sdd-status` `--json` description (it always emits JSON).
2. Add rows to `## What's in here` for `src/ai_harness/artifacts/` and `src/ai_harness/commands/`.
3. Add a one-line mention of `uv run pytest` for unit tests in `## Running tests`.

The classification is grounded in the audit count: six sections are accurate, only one is outdated, and two are missing minor additions. No structural rewrite is needed.

## Out of scope for this change

- Renaming the GitHub repo from `ai-harness-setup` to `ai-harness` (still out of band).
- Touching the `openspec/changes/archive/` content (archived changes are immutable).
- Touching the deleted sub-README — it is already gone and the new manifest does not reference it.
- Touching the SDD phase prompts or the OpenCode agent graph.

## Open questions

None.
