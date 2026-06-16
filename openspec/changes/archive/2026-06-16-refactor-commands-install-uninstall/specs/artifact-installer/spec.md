# artifact-installer Specification

## Purpose

A deep module under `ai_harness.artifacts` that owns the policy for installing and uninstalling harness artifacts. It exposes declarative dataclasses (`FileArtifact`, `DirArtifact`, `ArtifactManifest`) and two public functions: `install(manifest, home, console)` and `uninstall(manifest, home, console)`. Callers describe *what* to place; the module decides *how*.

## Requirements

### Requirement: Declarative artifact descriptors

The module SHALL provide immutable descriptors:

| Dataclass | Fields |
|-----------|--------|
| `FileArtifact` | `source: Path`, `target_relative: Path`, `backup_suffix: str` (default `".ai-harness-backup"`), `conflict_suffix: str` (default `".ai-harness-conflict-backup"`), `template: dict[str,str]\|None` |
| `DirArtifact` | `source: Path`, `target_relative: Path`, `merge_mode: str` (values `"replace_matching"` \| `"merge_preserve"`) |
| `ArtifactManifest` | `files: list[FileArtifact]`, `dirs: list[DirArtifact]` |

#### Scenario: FileArtifact with template substitution

- GIVEN a `FileArtifact` with `template={"{{HOME}}": "/users/alice"}`
- WHEN `install` is invoked
- THEN the source text is read, `"{{HOME}}"` replaced, and written to the target

### Requirement: Install with backup and conflict rotation

`install(manifest, home, console)` SHALL, for each `FileArtifact`:
1. Create target parent directories.
2. If target does NOT exist → copy source (with template substitution) and print `"Installed <target>"`.
3. If target exists AND content differs from prepared source → backup original to `<target><backup_suffix>` (print `"Backed up <target> to <backup>"`); if backup already exists, rotate via `<target><conflict_suffix>` then `<target><conflict_suffix>.<N>` (find lowest unused index); then overwrite target.

For each `DirArtifact` with `merge_mode="replace_matching"`: enumerate source subdirs, remove target subdir if present, copy source subdir. Print `"Installed skills to <target_dir>"` for skills; `"Installed opencode SDD prompts to <target_dir>"` for prompts.

#### Scenario: Fresh file install requires no backup

- GIVEN target file does not exist
- WHEN `install` runs
- THEN source is copied to target with template substitution applied
- AND no backup file is created

#### Scenario: Conflicting file is backed up

- GIVEN target exists with modified content
- WHEN `install` runs
- THEN original is copied to `<name>.ai-harness-backup`
- AND target is overwritten

#### Scenario: Repeated conflict rotates backup

- GIVEN `<name>.ai-harness-backup` already exists and target was modified again
- WHEN `install` runs a second time
- THEN modified content is saved to `<name>.ai-harness-conflict-backup` (or `.1`, `.2` if occupied)

### Requirement: Uninstall with restore and idempotency

`uninstall(manifest, home, console)` SHALL, for each artifact: if target exists AND content matches prepared source → remove target and print `"Removed <target>"`; then if backup exists and target is absent → restore backup via rename, print `"Restored <target> from <backup>"`.

#### Scenario: Matching content is removed and backup restored

- GIVEN target content matches source and a backup exists
- WHEN `uninstall` runs
- THEN target is removed
- AND backup is moved to target path
- AND backup file no longer exists

#### Scenario: Modified content is preserved

- GIVEN target content differs from source (user-modified)
- WHEN `uninstall` runs
- THEN target is NOT removed
- AND backup is preserved

#### Scenario: Idempotent uninstall succeeds

- GIVEN no targets exist (clean directory)
- WHEN `uninstall` runs
- THEN function returns without error
- AND exit code of calling command is 0
