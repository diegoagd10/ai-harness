# Delta for cli-sdd

## ADDED Requirements

### Requirement: CopilotInstaller agent composition at install time

`CopilotInstaller` SHALL compose `.agent.md` files at install time by concatenating each agent's frontmatter template from `resources/agent-clis/copilot-cli/agents/*.agent.md` with its corresponding shared prompt body from `resources/prompts/sdd/*.md` (or extracted judgment-day/reviewer prompts). The composed content SHALL be deterministic: same frontmatter + same prompt SHALL produce identical bytes every time.

#### Scenario: Phase agent composition

- GIVEN the frontmatter template `sdd-spec.agent.md` and the shared prompt `prompts/sdd/sdd-spec.md`
- WHEN `CopilotInstaller.install()` is invoked
- THEN the installed `~/.copilot/agents/sdd-spec.agent.md` contains the frontmatter block followed by a newline followed by the full prompt body
- AND repeated installs with identical sources produce byte-identical output

#### Scenario: Judgment-day and reviewer agent composition

- GIVEN a frontmatter template (e.g., `jd-fix-agent.agent.md` or `review-risk.agent.md`) and its extracted prompt body
- WHEN `CopilotInstaller.install()` is invoked
- THEN the installed agent file follows the same `frontmatter + newline + body` concatenation pattern

#### Scenario: Every composed agent under 30,000 characters

- GIVEN any agent composed at install time
- WHEN its total character count (frontmatter + body) is measured
- THEN the count SHALL be ≤ 30,000

### Requirement: Hook file installation

`CopilotInstaller` SHALL copy all JSON hook files from `resources/agent-clis/copilot-cli/hooks/` to `~/.copilot/hooks/` verbatim using `FileArtifact` descriptors.

#### Scenario: Fresh hook install

- GIVEN a HOME directory with no `~/.copilot/hooks/`
- WHEN `ai-harness install` runs
- THEN `~/.copilot/hooks/sdd-pre-tool-use.json` exists with content matching the adapter source

#### Scenario: Hook uninstall and restore

- GIVEN hooks were installed and backed up by a prior install
- WHEN `ai-harness uninstall` runs
- THEN hook files matching source content are removed
- AND backup files are restored to their original locations

### Requirement: Skill directory installation to `~/.copilot/skills/`

`CopilotInstaller` SHALL install shared skills from `resources/skills/` into `~/.copilot/skills/` as a `DirArtifact`. The catalog `SKILLS_TARGET_DIRS` SHALL include `.copilot/skills`.

#### Scenario: Skills installed

- GIVEN a fresh HOME directory
- WHEN `ai-harness install` runs
- THEN `~/.copilot/skills/` exists and contains a `SKILL.md` file for every skill discovered by the catalog

### Requirement: Reinstall preservation behavior

On reinstall, `CopilotInstaller` SHALL preserve user-authored files that differ from the composed source content by creating `.ai-harness-backup` copies before overwriting. Files whose content matches the composed source SHALL be overwritten silently.

#### Scenario: User-modified agent backed up then overridden

- GIVEN a user has edited `~/.copilot/agents/sdd-spec.agent.md` after a previous install
- WHEN `ai-harness install` runs again
- THEN a `.ai-harness-backup` is created with the user's edited content
- AND the file is replaced with the current project source composition

#### Scenario: Unchanged agent silently refreshed

- GIVEN `~/.copilot/agents/sdd-spec.agent.md` matches the composed source content
- WHEN `ai-harness install` runs again
- THEN the file is overwritten with fresh source content without creating a backup

### Requirement: Uninstall with backup restore

`ai-harness uninstall` SHALL remove all copilot-cli installed files whose content matches the composed source and SHALL restore `.ai-harness-backup` content to its original location.

#### Scenario: Full uninstall cycle

- GIVEN `ai-harness install` was previously run for copilot-cli
- WHEN `ai-harness uninstall` runs
- THEN agent files matching source content under `~/.copilot/agents/` are removed
- AND hook files matching source content under `~/.copilot/hooks/` are removed
- AND skill subdirectories matching source under `~/.copilot/skills/` are removed
- AND `.ai-harness-backup` files are restored to their original paths
- AND `~/.copilot/copilot-instructions.md` continues to be managed by the existing wiring
