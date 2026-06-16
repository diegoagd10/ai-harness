## Context

Claude Code subagent bodies are literal system-prompt text: the CLI cannot resolve `@import` or `{file:...}` indirection. The current `ClaudeInstaller` copies the `agent-clis/claude/agents/` directory verbatim via `DirArtifact`, so the 8 SDD-phase files (which contain only YAML frontmatter) end up installed with empty bodies. The shared `prompts/sdd/<phase>.md` files already hold the correct bodies. This change must compose each installed Claude phase file from its resource frontmatter plus the matching shared prompt body, keeping `prompts/sdd/*.md` the single source of truth.

## Current State

- `src/ai_harness/artifacts/manifest.py:13` defines only `FileArtifact` (single source file → target, with optional `template` substitution) and `DirArtifact` (whole-tree copy). There is no composition artifact type.
- `src/ai_harness/artifacts/installer.py:30` `_prepare_content` applies `template` string replacement to a single source file. It has no concept of joining a frontmatter file with a body file.
- `src/ai_harness/artifacts/installers/claude.py:84` adds the agents directory as a `DirArtifact`:
  ```python
  DirArtifact(
      source=assets.agents_dir,
      target_relative=Path(".claude/agents"),
  )
  ```
  This copies every `.md` file verbatim, including the frontmatter-only phase files.
- `src/ai_harness/artifacts/installers/opencode.py:88` installs each SDD prompt as a separate `FileArtifact` under `.config/opencode/prompts/sdd/`. The OpenCode `opencode.json` references them by path, so no composition is needed there.
- `src/ai_harness/commands/artifacts/install.py:23` instantiates `ClaudeInstaller(catalog)` alongside the other installers; the CLI surface is `ai-harness install` / `ai-harness uninstall`.
- `src/ai_harness/resources/agent-clis/claude/agents/*.md` contains 15 files:
  - 8 phase files (`sdd-explore.md`, `sdd-propose.md`, `sdd-spec.md`, `sdd-design.md`, `sdd-tasks.md`, `sdd-apply.md`, `sdd-verify.md`, `sdd-archive.md`) are frontmatter only (6 lines each).
  - 3 judgment-day files and 4 reviewer files contain frontmatter plus a self-contained inline body.
- `src/ai_harness/resources/agent-clis/claude/sdd-orchestrator/SKILL.md` is self-contained inline (no shared prompt source).
- `src/ai_harness/resources/prompts/sdd/*.md` contains 9 files; the 8 phase prompts (`sdd-explore.md` through `sdd-archive.md`) are non-empty and serve as the single source of truth. `sdd-orchestrator.md` is not used by any agent file.

## Archived Spec Reference

From `openspec/changes/archive/2026-06-16-add-agent-clis-claude-config/specs/agent-clis-claude/spec.md`:

> ### Requirement: Phase Body Composed From Shared Prompt
> Each of the 8 SDD-phase subagent bodies MUST be composed from the agent's frontmatter plus the content of the shared `prompts/sdd/<phase>.md`, keeping `prompts/sdd/*.md` the single source of truth. A phase body MUST NOT rely on `@import` or `{file:...}` indirection, since Claude subagent bodies are literal system-prompt text.

> #### Scenario: Phase body matches shared prompt
> - GIVEN the staged `sdd-explore` subagent
> - WHEN its body is compared to `prompts/sdd/sdd-explore.md`
> - THEN the body contains that shared prompt content verbatim
> - AND no `@import` or `{file:...}` reference is present

The same archived spec also requires exactly 15 subagents, reviewer/judge bodies inline, and no duplication of OpenCode-only assets.

## Mechanism Gap

1. `manifest.py` has no artifact type that describes "take the frontmatter from file A and append the body from file B".
2. `installer.py` `_prepare_content` reads a single `artifact.source`; it cannot join two sources.
3. `installers/claude.py` uses a `DirArtifact` for the agents directory, which is the wrong abstraction for composed output. It must be replaced with per-file artifacts so that the 8 phases become composed files while the 7 inline agents remain simple copies.
4. Because composition currently happens at authoring time for the orchestrator skill but not at all for the phase agents, the installer is the only place that can keep `prompts/sdd/*.md` as the single source of truth without duplicating bodies into the resource files.

## Test Pattern for OpenCode Installer

The OpenCode installer behavior is covered at two levels:

- **CLI-level** in `tests/test_install.py`: uses `typer.testing.CliRunner`, monkey-patches `HOME` to `tmp_path`, invokes `app install`, then asserts installed file content equals source content, backup creation, and conflict rotation. `tests/test_uninstall.py` mirrors this for removal, preservation, and restore.
- **Generic installer** in `tests/test_installer.py`: tests `ai_harness.artifacts.installer.install/uninstall` directly with `ArtifactManifest`, `FileArtifact`, and `DirArtifact`, using a `Console` fixture and `tmp_path` as the simulated home.

For the Claude composition change, the new tests should follow the same shape: CLI-level tests in `tests/test_install.py` (or a dedicated `tests/test_claude_install.py`) that invoke `app install` with a synthetic `HOME` and assert that `~/.claude/agents/sdd-<phase>.md` contains the frontmatter plus the verbatim body from `prompts/sdd/<phase>.md`, while inline agents remain unchanged.

## Proposed Direction (high-level only)

1. **Add a `ComposedFileArtifact` dataclass** in `manifest.py` that names a frontmatter source, a body source, and a target. `installer.py` learns to concatenate them during install/uninstall. This is clean and explicit, matching the proposal's stated direction, but it grows the public API.
2. **Extend `FileArtifact` with a `body_source` field** (optional). The generic installer joins `source` (frontmatter) + `body_source` (body) when `body_source` is present. Reuses the existing artifact type, but it conflates single-file and composed semantics and may complicate the `template` contract.
3. **Keep composition inside `installers/claude.py`** and generate ordinary `FileArtifact` instances whose `source` is a temporary/derived composed file. This avoids changing `manifest.py`/`installer.py`, but it pushes file-system staging into the installer and makes backup/uninstall content matching harder to reason about.

## Open Questions

- Should composition be a generic `manifest.py`/`installer.py` concept, or a Claude-specific helper inside `installers/claude.py`?
- What is the exact separator between frontmatter and body? The resource files already end with `---`; should the installed file be `frontmatter + "\n" + body`, `frontmatter.rstrip() + "\n\n" + body`, or something else?
- Should `{{HOME}}` template substitution apply to composed bodies, or only to the frontmatter? The existing `FileArtifact.template` mechanism applies to the whole prepared content.
- How should uninstall content matching work for composed files? The generic installer compares target content against `_prepare_content`; composed files must produce the same prepared string at uninstall time.
- Do we keep the orchestrator skill as a flat `DirArtifact` copy, or also model it as composed? It is currently self-contained inline.
- Should the 7 inline agents remain a `DirArtifact`, or be converted to per-file `FileArtifact` entries for symmetry and clearer uninstall semantics?

## Files To Touch

- `src/ai_harness/artifacts/manifest.py` — add composition artifact descriptor (under option 1) or extend `FileArtifact` (under option 2).
- `src/ai_harness/artifacts/installer.py` — implement composed content preparation and preserve backup/restore/conflict rotation.
- `src/ai_harness/artifacts/installers/claude.py` — replace the agents `DirArtifact` with composed artifacts for the 8 phases and simple artifacts for the 7 inline agents.
- `tests/test_install.py` or `tests/test_claude_install.py` — assert composed phase bodies, inline agents unchanged, and backup behavior.
- `tests/test_uninstall.py` — assert composed files are removed and backups restored only when content matches.
- `tests/test_installer.py` — if a generic composition artifact is added, cover its install/uninstall lifecycle.
- `e2e/test_harness_lifecycle.py` — extend lifecycle assertions to cover `.claude/agents/*.md` composition and the orchestrator skill.
