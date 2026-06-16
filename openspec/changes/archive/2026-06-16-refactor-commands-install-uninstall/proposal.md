# Proposal: Refactor Typer commands and extract installer deep module

## Intent

`src/ai_harness/main.py` is a 287-line bag mixing I/O, backup policy, shutil, and console output. Tests import layout constants from `main.py`. Refactor: commands move to subpackages; a deep installer module owns *how* artifacts are installed; commands declare only *what*.

## Scope

### In Scope
- Move `sdd-status`, `sdd-continue`, `_run_sdd_resolve` → `src/ai_harness/commands/sdd/`
- Move `install`, `uninstall` → `src/ai_harness/commands/artifacts/`
- Extract `ArtifactInstaller` deep module: backup/restore, conflict rotation, template substitution, file I/O
- Declarative `FileArtifact`/`DirArtifact` dataclasses (source, target, backup suffix, merge policy)
- Slim `main.py` to app assembly + `main()` (target: <40 lines)
- Update test imports; add `test_installer.py`
- Preserve all CLI behavior and signatures

### Out of Scope
- YAML/JSON catalog for artifact definitions
- Changing `pyproject.toml` entry point or CLI command names
- Refactoring `compat`, `rendering`, or `sdd/*` internals

## Capabilities

### New Capabilities
- `cli-sdd-commands`: sdd-status, sdd-continue in `ai_harness.commands.sdd`
- `cli-artifact-commands`: install, uninstall in `ai_harness.commands.artifacts`
- `artifact-installer`: deep module for backup/restore/merge policy, conflict rotation, template substitution

### Modified Capabilities
None

## Approach

Exploration **Approach 2**: thin command orchestrators + deep installer.

```
src/ai_harness/
  main.py                     # app + callback() + main()
  commands/
    sdd/
      status.py, continue_cmd.py, _resolve.py
    artifacts/
      install.py, uninstall.py         # thin: build manifest, call installer
  artifacts/
    manifest.py                        # constants + ArtifactManifest dataclasses
    installer.py                       # ArtifactInstaller: hides backup, shutil, comparison
```

Commands build an `ArtifactManifest`; `installer.install(manifest, home, console)` handles the rest.

## Affected Areas

| Area | Impact |
|------|--------|
| `src/ai_harness/main.py` | Modified — shrink to assembly |
| `src/ai_harness/commands/{sdd,artifacts}/` | New |
| `src/ai_harness/artifacts/` | New |
| `tests/test_install.py`, `test_uninstall.py` | Modified — update imports |
| `tests/test_cli_sdd.py` | Modified — import `app` from new location only if needed |
| `tests/test_installer.py` | New |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Test import churn breaks CI | Med | Re-export old constants from `main.py` during transition only if needed |
| Backup/restore semantics regress | Low | 18 tests cover exact behavior; installer unit tests added first |
| `continue` keyword collision | Low | File named `continue_cmd.py` |

## Rollback Plan

`git revert`. All changes confined to `main.py`, `commands/`, `artifacts/`, and test imports. No data migrations.

## Dependencies

- `ai_harness.sdd.resolve`, `ai_harness.compat` (existing, unchanged)

## Success Criteria

- [ ] All 18 existing install/uninstall/sdd tests pass
- [ ] New installer unit tests: fresh install, backup-on-conflict, conflict rotation, template substitution, uninstall restore, idempotent uninstall
- [ ] `main.py` under 40 lines
- [ ] `install`, `uninstall`, `sdd-status --json`, `sdd-continue --json` output unchanged
