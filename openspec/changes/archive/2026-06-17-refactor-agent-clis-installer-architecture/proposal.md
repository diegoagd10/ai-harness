# Proposal: Refactor Agent-CLIs Installer Architecture

## Why

Prompt bodies for 15+ agents are duplicated byte-for-byte across three provider directories
(`claude/agents/`, `copilot-cli/agents/`, inline in `opencode.json`). Editing a prompt
requires lockstep changes in 2–3 files. Provider syntax, prompt content, and tool metadata
are entangled. This refactor extracts **canonical prompt bodies** into one location; each
installer owns only target-format construction.

## What Changes

1. **Canonical prompts** under `resources/prompts/`:
   - `sdd/` — unchanged (8 phase bodies).
   - `jd/` — 3 judgment-day agent bodies extracted from inline files.
   - `review/` — 4 review agent bodies extracted from inline files.
   - `orchestrator/` — two body variants (Agent-tool, task-tool).

2. **Per-provider metadata** as structured data inside installer classes
   (name, description, model, tools). Prompt bodies referenced by logical id.

3. **In-memory artifact generation** per installer:
   - `OpencodeInstaller`: builds `opencode.json`; inline strings → `{file:…}` references.
   - `ClaudeInstaller`: composes Markdown (frontmatter + body); generates `settings.json` rules from metadata.
   - `CopilotInstaller`: composes Markdown; generates `sdd-pre-tool-use.json` (allowlist, deny paths).

4. **E2e shim**: installers write generated output to **old** `agent-clis/<provider>/` paths
   so e2e source-path constants continue resolving. Old paths become write-only outputs.

5. **Remove duplicated bodies** from `agent-clis/claude/agents/` and `agent-clis/copilot-cli/agents/`.
   Frontmatter-only files remain as templates for manifest build.

## Impact

| Spec | Effect |
|------|--------|
| `claude-permissions` | No requirement change. Tool lists from metadata instead of file parsing. |
| `install-wizard` | No change. |
| `uninstall-wizard` | No change. |

## Non-Goals

- Modifying e2e tests. Changing user-facing flow, target paths, or wizard UI.
- Supporting new providers. Introducing a template engine.
- Changing AGENTS.md, skills/, or generic installer backup/restore logic.

## Approach

Installers receive `AgentMeta` (frontmatter + tools) and `PromptStore` (body-by-id).
`_build_manifest` constructs descriptors from both + provider composition. A final
shim write populates `agent-clis/<provider>/` so e2e passes unchanged.

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| E2e reads hard-coded `agent-clis/` paths break | Installers write generated shims to old paths. |
| Byte-layout changes break backup/uninstall idempotency | Preserve exact join logic; run full suite before merge. |
| Claude permissions computed from file paths | `install_permissions` receives tool lists from metadata directly. |
| Copilot 30K budget shifts | Compare composed lengths pre/post change. |

## Rollback

Revert the commit. No migration state; `agent-clis/` tree re-populated on revert.

## Open Question

- **Orchestrator body**: Claude variant uses `Agent` tool; Copilot/OpenCode uses `task`.
  Two separate source files, or one with substitution? Design phase decides.

## Success Criteria

- [ ] Zero duplicated prompt bodies under `agent-clis/`.
- [ ] `uv run pytest` passes.
- [ ] `e2e/docker-test.sh` passes (zero e2e modifications).
- [ ] `install --all` / `uninstall --all` produce byte-equivalent output vs. pre-refactor.
