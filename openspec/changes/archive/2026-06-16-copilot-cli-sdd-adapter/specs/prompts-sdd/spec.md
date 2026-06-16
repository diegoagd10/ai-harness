# Delta for prompts-sdd

## MODIFIED Requirements

### Requirement: Transport-agnostic task-tool reference

The `sdd-orchestrator.md` prompt SHALL reference "the platform's native `task` tool" and SHALL NOT contain the string "OpenCode's native `task` tool". Both occurrences (lines 7 and 252) SHALL be replaced.
(Previously: lines 7 and 252 said "OpenCode's native `task` tool".)

#### Scenario: OpenCode phrasing removed

- GIVEN the file `prompts/sdd/sdd-orchestrator.md`
- WHEN searched for the string "OpenCode's native `task` tool"
- THEN zero matches are found
- AND at lines 7 and 252 the text "the platform's native `task` tool" appears instead

#### Scenario: Non-target opencode references preserved

- GIVEN the file `prompts/sdd/sdd-orchestrator.md` at line 26
- WHEN searching for "Do not touch `opencode.json`"
- THEN that line SHALL remain unchanged (valid instruction for opencode users, no-op for other platforms)

### Requirement: Expanded skill search paths in all 9 prompts

All 9 shared prompt files in `prompts/sdd/*.md` SHALL list `.copilot/skills/` and `.claude/skills/` in their skill-resolution search paths, in addition to the existing `.agents/skills/`, `{project-root}/skills/`, `.opencode/skills/`, and `~/.config/opencode/skills/` paths. No existing path SHALL be removed.
(Previously: the 9 prompts listed only `.agents/skills/`, `~/.config/opencode/skills/`, `{project-root}/skills/`, and `{project-root}/.opencode/skills/` as scan paths.)

#### Scenario: All 9 prompts list copilot-cli and claude paths

- GIVEN any of the 9 `prompts/sdd/*.md` files
- WHEN the skill-resolution section is read
- THEN `.copilot/skills/` appears as a project-level scan path
- AND `.claude/skills/` appears as a project-level scan path
- AND all existing paths (`.agents/skills/`, `{project-root}/skills/`, `.opencode/skills/`, `~/.config/opencode/skills/`) are still present

#### Scenario: Single-line scan path in sdd-verify updated

- GIVEN the file `prompts/sdd/sdd-verify.md` (which names scan paths in one inline sentence at line 50)
- WHEN the line's scan directory list is read
- THEN it includes `.copilot/skills/` and `.claude/skills/` alongside the existing paths

### Requirement: Additive-only guarantee — no path removal

The prompt generic-ification SHALL be additive only. Existing tests for opencode and claude adapter installs SHALL continue to pass after the changes.

#### Scenario: No existing path removed from any prompt

- GIVEN the set of path references in the 9 prompts before generic-ification
- WHEN comparing to the set after generic-ification
- THEN every pre-existing path reference is still present
- AND `~/.config/opencode/skills/` is never removed from `sdd-verify.md` or any other prompt

#### Scenario: OpenCode and Claude adapter tests pass

- GIVEN the 9 shared prompts have been generic-ified
- WHEN `uv run pytest` is executed
- THEN all pre-existing opencode and claude adapter install/uninstall tests SHALL pass
- AND no test SHALL fail due to a missing skill path reference
