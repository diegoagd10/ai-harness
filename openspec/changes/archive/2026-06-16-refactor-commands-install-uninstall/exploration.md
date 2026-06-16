## Exploration: Refactor Typer commands and install/uninstall artifact handling

### Current State

`src/ai_harness/main.py` is a 287-line command bag that currently owns:

1. The Typer `app` definition and `main()` entry point.
2. All install/uninstall source/target constants (`AGENTS_MD_TARGETS`, `SKILLS_TARGET_DIRS`, `OPENCODE_*`, backup suffixes).
3. A small shared utility (`next_available_path`).
4. The `install` command (~92 lines) and `uninstall` command (~60 lines) — both are dense, sequential I/O scripts with duplicated backup/restore logic.
5. The `sdd-status` and `sdd-continue` commands and their shared `_run_sdd_resolve` helper.

The `install`/`uninstall` commands are the real mud ball. They interleave:

- Declarative source/target knowledge (what gets copied where).
- Content comparison and backup/restore policy.
- Concrete `shutil`/`pathlib` I/O.
- User-facing `console.print` output.
- Template substitution (`{{HOME}}` in `opencode.json`).

The same duplication appears across multiple artifact kinds (single file with backup, single file with conflict backup, directory tree merge, prompt files with backup). The code works and has good test coverage, but it violates information hiding: every caller (tests, e2e, the CLI itself) imports constants from `main.py` and knows the exact layout rules.

Tests currently reach deep into `main.py`:

- `tests/test_install.py` imports `AGENTS_MD_SRC`, `OPENCODE_JSON_SRC`, `OPENCODE_SDD_PROMPTS_SRC`, `SKILLS_SRC`, `app`.
- `tests/test_uninstall.py` imports `AGENTS_MD_TARGETS`, `OPENCODE_JSON_TARGET`, `OPENCODE_SDD_PROMPTS_SRC`, `OPENCODE_SDD_PROMPTS_TARGET_DIR`, `SKILLS_SRC`, `SKILLS_TARGET_DIRS`, `app`.
- `tests/test_cli_sdd.py` imports `app` from `main.py`.
- `e2e/test_harness_lifecycle.py` duplicates the same source/target constants.

### Affected Areas

- `src/ai_harness/main.py` — will shrink to app assembly, `main()`, and possibly the `callback()`.
- `src/ai_harness/commands/sdd/` — new package for `sdd-status` and `sdd-continue` commands plus the `_run_sdd_resolve` helper.
- `src/ai_harness/commands/artifacts/` — new package for `install` and `uninstall` commands. This name matches the real domain: installable harness artifacts such as AGENTS.md, skills, opencode config, and SDD prompts.
- `src/ai_harness/artifacts/` (tentative) — a deep module that hides the backup/restore/merge policy and I/O. Could live under `commands/artifacts/` if we want to keep the command package self-contained, but the domain logic should not depend on Typer.
- `tests/test_install.py` and `tests/test_uninstall.py` — will need to import the constants they actually need from the new locations, or (better) stop importing constants and test through the CLI surface plus file assertions.
- `tests/test_cli_sdd.py` — will import `app` from `ai_harness.main` still, or from `ai_harness.commands.sdd`.
- `e2e/test_harness_lifecycle.py` — imports many of the same constants; should be updated to import from the new installer module or from a shared manifest.
- `pyproject.toml` — entry point `ai-harness = "ai_harness.main:main"` does not need to change if `main.py` keeps `main()`, but it could be revisited.

### Approaches

#### 1. Move commands only, keep logic inline

Move `install`, `uninstall`, `sdd-status`, `sdd-continue` into submodules, but keep the current procedural I/O code largely unchanged. `main.py` becomes a thin assembly layer.

- Pros:
  - Low effort and low regression risk.
  - Satisfies the directory-layout requirement.
- Cons:
  - Does not address the mud ball; backup/restore duplication stays.
  - Tests still import constants from command modules, coupling them to layout details.
- Effort: Low

#### 2. Move commands and extract an `ArtifactInstaller` deep module (recommended)

Introduce a small, domain-specific installer module that hides the backup/restore/merge policy. Commands become thin orchestrators that describe *what* to install/uninstall; the deep module decides *how*.

Suggested public surface (draft):

```python
class ArtifactManifest:
    sources: list[ArtifactSource]

def install(manifest: ArtifactManifest, home: Path, console: Console) -> None: ...
def uninstall(manifest: ArtifactManifest, home: Path, console: Console) -> None: ...
```

Or even simpler, declarative source descriptors:

```python
class FileArtifact:
    source: Path
    target_relative: Path
    backup_suffix: str = ".ai-harness-backup"
    conflict_suffix: str = ".ai-harness-conflict-backup"
    template: dict[str, str] | None = None   # e.g. {"{{HOME}}": str(home)}

class DirArtifact:
    source: Path
    target_relative: Path
    merge_mode: "replace_matching" | "merge_preserve"  # skills vs. prompts?
```

Then `install.py` and `uninstall.py` in the command package just build the manifest and call `installer.install(...)` / `installer.uninstall(...)`.

- Pros:
  - Real information hiding: commands no longer know about backup suffixes or `shutil` details.
  - Eliminates duplication between install and uninstall.
  - Tests can assert behavior through the CLI or through the small installer API.
  - Makes the e2e test's constant duplication unnecessary.
- Cons:
  - Medium effort; need to be careful with the nuanced backup/restore semantics already covered by tests.
  - A too-generic abstraction can become its own mud ball; must keep the manifest model concrete.
- Effort: Medium

#### 3. Full declarative manifest + JSON/YAML resource catalog

Move the source/target mapping into a data file (e.g., `resources/manifest.yaml`) and drive install/uninstall from it.

- Pros:
  - Adding a new artifact requires only data changes, no code.
  - Very high-level abstraction.
- Cons:
  - Over-engineered for a small CLI.
  - Templating (`{{HOME}}`), directory merge rules, and backup semantics do not map cleanly to YAML without a parallel policy engine.
  - Tests would need to parse the manifest to set expectations, increasing coupling.
- Effort: High

### Recommendation

Use **Approach 2**: move the commands into `src/ai_harness/commands/sdd/` and `src/ai_harness/commands/artifacts/`, and extract an `ArtifactInstaller` deep module that owns the backup/restore/merge policy. Keep the manifest model concrete and text-based (Python dataclasses, not YAML).

Naming recommendation:

- `src/ai_harness/commands/sdd/status.py` — `sdd-status` command.
- `src/ai_harness/commands/sdd/continue_cmd.py` — `sdd-continue` command.
- `src/ai_harness/commands/sdd/__init__.py` — exports the commands or a registration helper.
- `src/ai_harness/commands/artifacts/install.py` — `install` command.
- `src/ai_harness/commands/artifacts/uninstall.py` — `uninstall` command.
- `src/ai_harness/artifacts/installer.py` — deep module for I/O policy.
- `src/ai_harness/artifacts/manifest.py` — manifest dataclasses/constants.

`main.py` keeps:

```python
app = typer.Typer()
register_sdd_commands(app)
register_artifact_commands(app)

def main() -> None:
    app()
```

This satisfies the user's directory request, solves the mud ball, and keeps the change bounded.

### Risks

- **Test import churn**: `test_install.py` and `test_uninstall.py` import many constants from `main.py`. Moving constants is a breaking change for tests, but not for end users. Prefer keeping the old constants in `main.py` as re-exports during the transition, or updating tests to import from the new manifest module.
- **Backup/restore semantics are subtle**: The existing tests cover fresh install, reinstall, conflict backup rotation, modified-file preservation, backup restoration, and idempotent uninstall. Any refactor must preserve these exact behaviors. The installer deep module needs its own focused unit tests.
- **e2e constant duplication**: `e2e/test_harness_lifecycle.py` duplicates constants. If those constants move, the e2e test must be updated or, better, import from the new manifest module.
- **Entry point stability**: `pyproject.toml` exposes `ai_harness.main:main`. Do not rename `main()` or change its module unless the entry point is updated in the same change.
- **Module-name collision**: Do not name the install/uninstall command package `install` because it collides with the command function name and is confusing. Use `artifacts`.

### Ready for Proposal

Yes. The next step is `sdd-propose`. The proposal should include:

1. The exact module names and directory layout.
2. The public API of the installer deep module.
3. A rollback plan (revert module moves and restore `main.py` if integration tests fail).
4. The list of packages/modules affected.
5. Updated test strategy (which tests change imports, which get added for the installer module).
