# PRD — init-config-scaffold

## Intent

Make `ai-harness init` initialize the harness configuration file through the existing change-config module, while ending the command's ownership of repository-root instruction and standards documents.

## Scope

### In

- Change the `ai-harness init` command to call `ChangeConfigAdministrator.initialize_config()` from `src/ai_harness/modules/change_config/module.py`.
- Create `.ai-harness/config.yml` with the administrator's default template when no config exists.
- Preserve any existing `.ai-harness/config.yml` exactly, including empty, invalid, or user-edited files.
- Ensure repeated initialization succeeds without changing config content or modification time.
- Ensure init neither creates nor modifies root `CLAUDE.md`, `AGENTS.md`, or `CODING_STANDARDS.md`.
- Update command output so it truthfully identifies config initialization without claiming whether the file was newly created.
- Add or update unit and Docker-backed end-to-end coverage for fresh, existing, and repeated initialization.

### Out

- Removing or changing the public legacy `init_repo` and `InitResult` API or its direct tests.
- Deleting legacy root-scaffolding internals that are no longer invoked by the CLI.
- Migrating, cleaning, or interpreting managed blocks in existing root documentation.
- Validating, repairing, or overwriting an existing config during init.
- Changing the config template, config schema, phase rules, or the three-method `ChangeConfigAdministrator` surface.
- Creating specs, design documents, implementation tasks, or implementation code in this phase.

## Capabilities

- Config scaffold initialization: A fresh `ai-harness init` creates `.ai-harness/config.yml` through `ChangeConfigAdministrator.initialize_config()` using the established default template.
- Non-destructive reinitialization: Running init when config already exists succeeds and leaves the file's bytes and modification time unchanged.
- Root-document isolation: Init leaves root `CLAUDE.md`, `AGENTS.md`, and `CODING_STANDARDS.md` absent when absent and byte-identical when present.
- Initialization observability: The CLI exits successfully and reports the config path with wording valid for both creation and an idempotent no-op.
- Init behavior coverage: Unit and packaged end-to-end tests verify the new filesystem contract across fresh, pre-populated, and repeated runs.

## Approach

Keep the Typer command as a thin adapter: construct `ChangeConfigAdministrator` for the current repository root, invoke `initialize_config()`, and report the config path. Reuse the administrator's existing recursive directory creation, template writing, and non-overwrite behavior rather than duplicating filesystem logic at the command edge.

Retain the legacy harness initialization API for compatibility, but disconnect it from `ai-harness init`. Tests should focus on observable filesystem behavior. Parse generated YAML or assert stable schema values instead of relying on a brittle whole-file text comparison.

```text
ai-harness init
      |
      v
Typer init command
      |
      v
ChangeConfigAdministrator.initialize_config()
      |
      +--> create .ai-harness/config.yml when absent
      +--> no-op when config.yml already exists
      +--> never touch repository-root documentation
```

## Affected Areas

- `src/ai_harness/commands/init.py` — replace legacy root scaffold delegation and reporting with config initialization.
- `tests/test_init.py` — assert CLI config creation, valid defaults, idempotency, existing-config preservation, root-document isolation, and truthful output.
- `e2e/e2e_test.sh` — replace legacy Tier 1 root-document scenarios with packaged-binary config scenarios and update the Tier 1 invocation list.
- `src/ai_harness/modules/change_config/module.py` — consumed as the existing implementation dependency; no functional change is expected.
- `tests/test_change_config.py` — retain dependency-level coverage for template shape, recursive directory creation, validation, and non-overwrite behavior.

## Risks

- Stale end-to-end scenarios or invocation entries may continue to enforce forbidden root-document mutations.
- The administrator returns no created-versus-existing status; command wording that claims creation could be false on reruns.
- Brittle raw-YAML assertions could fail on harmless formatting changes instead of contract regressions.
- Keeping `init_repo` publicly available preserves an obsolete capability, but removing it here would unnecessarily expand compatibility risk.
- Modification-time checks can be filesystem-sensitive; end-to-end coverage must reliably distinguish an untouched file from a rewrite.

## Rollback Plan

Revert the init command and its corresponding unit and end-to-end expectations to the prior `init_repo` behavior. No data migration is required: the new behavior only adds `.ai-harness/config.yml` when absent and does not modify existing config or root documents. A rollback must not delete a config file created by a user or by the new initializer.

## Dependencies

- Existing `ChangeConfigAdministrator` implementation and bundled default config template.
- Typer command wiring and its current repository-root execution context.
- YAML parsing available to tests for schema-level assertions.
- Existing pytest unit suite and Docker-backed end-to-end harness.
- Quality gates: Ruff format and lint, duplicate-code lint, pytest, and `./e2e/docker-test.sh`.

## Success Criteria

- On a fresh repository, `ai-harness init` exits zero, recursively creates `.ai-harness/`, and writes `.ai-harness/config.yml` from the established default template.
- The generated config parses as valid YAML and contains the stable default contract, including the expected commit format and all eight phase rule sections.
- The command implementation invokes `ChangeConfigAdministrator.initialize_config()` rather than `init_repo()` or equivalent root-document scaffold logic.
- If `.ai-harness/config.yml` already exists, init exits zero and preserves its exact bytes and modification time, regardless of whether its content is valid.
- A repeated init exits zero and preserves the generated config's bytes and modification time.
- If root `CLAUDE.md`, `AGENTS.md`, and `CODING_STANDARDS.md` are absent, init does not create them.
- If any root documentation file exists, init leaves its bytes unchanged, including files containing legacy or current managed markers.
- CLI output identifies `.ai-harness/config.yml` without asserting an unknowable created-versus-existing state.
- Unit tests cover fresh initialization, config structure, existing-config preservation, rerun idempotency, root-document absence, root-document preservation, and command output.
- Docker-backed end-to-end tests exercise the packaged command in isolated fresh, pre-populated, and repeated-init repositories and assert the same filesystem contract.
- Ruff formatting and lint, duplicate-code lint, the full pytest suite, and the Docker-backed end-to-end gate pass.
