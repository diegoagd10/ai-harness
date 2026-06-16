# cli-artifact-commands Specification

## Purpose

Typer commands `install` and `uninstall` registered on the Typer `app`, living under `ai_harness.commands.artifacts`. They SHALL preserve all existing console output strings, file placement logic, backup/restore behavior, and exit codes (always 0 except for unrecoverable I/O errors).

## Requirements

### Requirement: install places harness artifacts into HOME

The `install` command SHALL copy project resources to the user's home directory. Targets: AGENTS.md to `.agents/AGENTS.md`, `.claude/CLAUDE.md`, `.copilot/copilot-instructions.md`, and `.config/opencode/AGENTS.md`; skills to `.agents/skills/` and `.claude/skills/`; `opencode.json` with `{{HOME}}` substitution to `.config/opencode/opencode.json`; SDD prompts from `resources/prompts/sdd/` to `.config/opencode/prompts/sdd/`.

Console output for each installed/backed-up target SHALL match the current strings exactly (e.g. `"Installed <path>"`, `"Backed up <from> to <to>"`).

#### Scenario: Fresh install copies all artifacts

- GIVEN an empty HOME directory
- WHEN `install` is invoked
- THEN exit code is 0
- AND AGENTS.md appears at all four target paths with identical content
- AND project skills appear under both `.agents/skills/` and `.claude/skills/`
- AND `opencode.json` exists at `.config/opencode/opencode.json` with `{{HOME}}` replaced by the actual home path
- AND SDD prompt `*.md` files exist under `.config/opencode/prompts/sdd/`

#### Scenario: Reinstall overrides stale files and preserves custom skills

- GIVEN a stale skill file and a user-authored custom skill not in the project
- WHEN `install` is invoked
- THEN the stale skill is replaced with fresh content
- AND the custom skill is untouched

#### Scenario: Install backs up existing modified opencode files

- GIVEN a pre-existing `opencode.json` or `AGENTS.md` with user content different from source
- WHEN `install` is invoked
- THEN the original is copied to `<name>.ai-harness-backup` with console message "Backed up"
- AND the target is overwritten with the project version

#### Scenario: Repeated install rotates conflict backups

- GIVEN a target was installed, then modified by user, then installed again
- WHEN install runs a second time after user modification
- THEN the modified content is saved to `<name>.ai-harness-conflict-backup`
- AND if that backup already exists, a numbered rotation is used (`<name>.ai-harness-conflict-backup.1`, `.2`, ...)
- AND the original first-install backup is preserved

### Requirement: uninstall removes and restores harness artifacts

The `uninstall` command SHALL remove only project-owned artifacts from HOME. It SHALL restore user backups when the current content matches the project source. It SHALL be idempotent: running on a clean directory succeeds with exit code 0.

#### Scenario: Uninstall removes all installed artifacts

- GIVEN a prior `install` was run
- WHEN `uninstall` is invoked
- THEN all AGENTS.md targets, project skills, `opencode.json`, and SDD prompt files are removed
- AND unrelated files are untouched

#### Scenario: Uninstall restores user backup when content matches

- GIVEN `opencode.json` had user content before install, and backup exists
- WHEN `uninstall` is invoked
- THEN the project version is removed
- AND the user backup is restored to the original path
- AND the backup file no longer exists

#### Scenario: Uninstall preserves modified content

- GIVEN a target was installed then modified by the user (no longer matches source)
- WHEN `uninstall` is invoked
- THEN the modified file is NOT removed
- AND the backup is preserved

#### Scenario: Uninstall is idempotent on clean directory

- GIVEN no prior install
- WHEN `uninstall` is invoked
- THEN exit code is 0 and no errors occur
