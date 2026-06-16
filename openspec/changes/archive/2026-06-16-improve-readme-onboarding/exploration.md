# Exploration: improve-readme-onboarding

## Context

The user wants to rewrite the top-level `README.md` so an engineer evaluating or adopting the tool immediately understands why it exists, how to install it, what workflow it enables, and how to contribute. The change boundary is strictly the root `README.md`; sub-readmes and the source tree stay as-is. The rewrite must be grounded in the actual files in the worktree, not in an older or imagined repository layout.

## Current README audit

| Required section | Where it lives now | What it currently says | Gap |
|---|---|---|---|
| **Getting started** | Two places: `## CLI` (lines 19–55) and `## Install` (lines 57–75). | `## CLI` tells the reader to `cd cli` then `uv run ai-harness install`, then shows `uv tool install .` under `cli/`. `## Install` tells the reader to clone, `cd .../cli`, run `make install`, then `ai-harness install`. | Both sections assume a `cli/` subdirectory and a `Makefile` that no longer exist in the worktree, so the copy-paste path is broken. |
| **Why we built this** | Not present. | The one-line opening tagline ("Personal, version-controlled configuration for AI coding harnesses…") describes the repo contents, not the pain of generic LLM output and fix-it cycles. | No explicit problem statement for the target audience. |
| **The solution this tool provides** | Implicitly under `## Install` and `## Using the OpenSpec template in a new project`. | Mentions `ai-harness install` copies/configures harness artifacts and references OpenSpec config. | Does not explain the SDD planning-first workflow or how bounded tasks lead to cleaner implementation. |
| **Contributors** | Not present. | End-to-end test commands are listed under `## CLI`, but there is no "Contributing" section with tests, issues, or PR guidance. | No contributor entry point; `.github/` is absent so no templates exist to link to. |

## Install path inventory

Commands currently appearing in the README, grouped by audience:

### Get the binary on PATH

- `cd cli && uv tool install .` (lines 33–35) — assumes `cli/` exists.
- `cd cli && make install` (line 64) — assumes both `cli/` and a `Makefile` exist.

### Run without installing (development / e2e harness setup)

- `cd cli && uv run ai-harness install` (line 27) — assumes `cli/` exists.
- `uv run inv test` / `uv run inv install` / `uv run inv uninstall` / `uv run inv sdd-status` / `uv run inv sdd-continue` / `uv run inv tool-lifecycle` (lines 44–51).
- `e2e/docker-test.sh` (line 54).

### Recommended canonical sequence

```bash
git clone git@github.com:diegoagd10/ai-harness-setup.git ~/Projects/ai-harness-setup
cd ~/Projects/ai-harness-setup
uv tool install .          # puts ai-harness on PATH (~/.local/bin/ai-harness)
ai-harness install         # copies AGENTS.md, skills, opencode.json, SDD prompts into home dirs
```

**Rationale:** `pyproject.toml` is at the repo root, the project entry point is `ai-harness = "ai_harness.main:main"`, and `src/ai_harness/main.py` exposes the `install` command. A recursive search for `Makefile` returned no results, and `make install` is therefore not a real option in this worktree. `uv tool install .` is the single, reproducible command that places the `ai-harness` binary on PATH using the actual package metadata.

## Persona & voice notes

The bundled `src/ai_harness/resources/AGENTS.md` (which is what the CLI installs as the agent persona) states:

- Generated artifacts default to **English**.
- The Spanish/passionate/direct voice applies only to chat replies, **not** to README files, comments, or string literals.
- Rioplatense slang, voseo, and persona stylistic emphasis (CAPS, exclamations) must **not** leak into artifacts.

The current `README.md` is already in English and factual, so the rewrite should stay in English, direct, and free of marketing fluff. It should address the reader as an engineer evaluating the tool, not as an end user of a downstream product.

## Constraints & risks

- **Do not change sub-READMEs.** `src/ai_harness/resources/agent-clis/opencode/README.md` exists and explains the OpenCode agent graph; the root README may link to it but must not rewrite it.
- **Do not claim `make install`.** No `Makefile` exists in the worktree; recommending it would ship a broken command.
- **Do not claim `cli/`.** The project has been flattened; `pyproject.toml`, `src/ai_harness/`, `e2e/`, and `tasks.py` are at the repo root. The README's current `cd cli` paths are stale.
- **Do not claim `prompts/commands/*.md` generation.** `src/ai_harness/resources/prompts/` only contains `sdd/`; there is no `commands/` source in the bundled resources. The current README line about generating slash commands from `prompts/commands/*.md` does not match the implementation in `src/ai_harness/main.py`.
- **Do not invent contributor infrastructure.** There is no `.github/` directory, so the "Contributors" section should describe the actual test commands and invite issues/PRs to the canonical remote, not link to non-existent templates.
- **Open question for `sdd-propose`:** Should the new README keep the "Using the OpenSpec template in a new project" section? It is useful context but overlaps with a future quickstart doc; decide whether it stays or moves to a sub-readme.

## Recommended section order for the new README

1. `# ai-harness-setup` — one-line tagline.
2. `## Why we built this` — the pain of generic LLM output and repeated fix-it cycles.
3. `## What this tool does` — the solution: a planning-first SDD workflow driven from a single OpenSpec/SDD source, producing bounded, well-shaped implementation tasks.
4. `## Getting started` — canonical install sequence (`git clone`, `uv tool install .`, `ai-harness install`) plus Python >=3.12 requirement; mention `uv run ai-harness install` as the no-install alternative.
5. `## What's in here` — concise table mapping `src/ai_harness/resources/`, `src/ai_harness/`, `e2e/`, `templates/openspec/` to their purposes.
6. `## Running tests` — `uv run inv test`, per-category tasks, and `e2e/docker-test.sh`.
7. `## Contributing` — how to run tests, file issues, and open PRs against `git@github.com:diegoagd10/ai-harness-setup.git`.
8. `## See also` — link to `src/ai_harness/resources/agent-clis/opencode/README.md` for OpenCode wiring details.
