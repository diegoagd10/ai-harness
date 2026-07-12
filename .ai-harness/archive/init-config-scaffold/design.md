# Design — init-config-scaffold

## Context

`ai-harness init` currently exposes legacy repository-root scaffolding behavior. The command must instead initialize `.ai-harness/config.yml` through the existing `ChangeConfigAdministrator` deep module and must have no ownership of root `CLAUDE.md`, `AGENTS.md`, or `CODING_STANDARDS.md`. The design preserves the public legacy `init_repo` and `InitResult` API for compatibility but removes it from the command path. No migration is performed: existing config and root documents are opaque user-owned files and remain byte-identical. The command edge owns only invocation and truthful reporting; configuration filesystem policy remains behind the administrator seam.

## Deep modules

### Change configuration administration
- Seam: `ChangeConfigAdministrator` in `src/ai_harness/modules/change_config/module.py`, called by the `init` command with the current repository root as its filesystem scope.
- Interface: `ChangeConfigAdministrator(...).initialize_config() -> None`. The operation recursively creates `.ai-harness/` and writes the bundled default to `.ai-harness/config.yml` only when the file is absent. An existing file is an unconditional successful no-op, regardless of its contents. The `None` result deliberately exposes no created-versus-existing state; filesystem failures propagate through the existing command error behavior.
- Hides: Default path derivation, parent-directory creation, bundled-template access, write mechanics, and the non-overwrite policy. It also hides the distinction between creation and idempotent no-op so callers cannot accidentally couple output to an implementation detail.
- Depth note: One operation encapsulates all config initialization policy and filesystem complexity; deleting this seam would force the command to duplicate path, template, and preservation rules.

### Init command adapter
- Seam: The Typer command in `src/ai_harness/commands/init.py`, exposed through the public `ai-harness init` CLI.
- Interface: No new application API. On invocation, resolve the current repository root, construct `ChangeConfigAdministrator`, call `initialize_config()` exactly once, then report `.ai-harness/config.yml` using wording valid for both creation and no-op. Exit successfully when initialization succeeds.
- Hides: CLI framework wiring and presentation only. It must not inspect config contents, preflight file existence, infer creation state, or call root-document scaffolding.
- Depth note: This is an intentionally thin system adapter rather than a new domain abstraction; introducing another wrapper class or service would merely move names around and fail the deletion test.

### Init behavior verification
- Seam: Observable CLI behavior through the Typer test runner in `tests/test_init.py` and the packaged executable in `e2e/e2e_test.sh`.
- Interface: Given an isolated repository state, invoke `init` and assert exit status, output, and resulting filesystem state. Fresh initialization must produce parseable YAML with the stable default commit format and eight phase rule sections. Existing and repeated initialization must preserve config bytes and modification time. Root documents must remain absent or byte-identical.
- Hides: Test fixture setup, YAML parsing, timestamp stabilization, packaged-binary invocation, and isolated repository cleanup. Unit tests provide focused command-contract feedback; Docker-backed tests verify installation and real executable wiring.
- Depth note: A compact behavior matrix protects several destructive edge cases through one public seam; tests do not reproduce or mock the administrator's internal filesystem algorithm.

## Internal collaborators

- The bundled default config template and the administrator's path/write helpers remain internal to `ChangeConfigAdministrator`. They are covered directly by existing `tests/test_change_config.py` and transitively by CLI tests; the command must neither import nor mock them.
- Typer output facilities are internal command-edge collaborators. Output states that configuration was initialized at `.ai-harness/config.yml`; it must not claim that a file was created, preserved, valid, or repaired.
- YAML parsing is a test-only collaborator used for stable schema assertions. Raw template text is not the contract and should not be copied into command tests.
- The legacy `init_repo`, `InitResult`, root-document constants, and mutation helpers remain owned by the harness module and publicly available for compatibility, but are disconnected from the `init` command. Their direct tests remain unchanged. This change neither deletes nor migrates that legacy surface.
- Root `CLAUDE.md`, `AGENTS.md`, and `CODING_STANDARDS.md` are outside every new seam. Tests treat them as sentinels only: init has no read, write, cleanup, or marker-interpretation responsibility for them.

## Seam map

```text
User / packaged executable
            |
            v
   Typer init command                 legacy public API (retained)
   [invoke + report]                  init_repo / InitResult
            |                                  |
            | initialize_config()              +--> root scaffolding internals
            v                                  (no command dependency)
 ChangeConfigAdministrator
 [path + template + preservation policy]
            |
            +--> absent config: create .ai-harness/config.yml
            +--> existing config: no-op
            `--> root documentation: no dependency, no access
```

```text
tests/test_init.py ---- Typer app ------+
                                         +--> same observable init contract
e2e/e2e_test.sh ---- packaged binary ---+

tests/test_change_config.py --> ChangeConfigAdministrator dependency contract
```

The command depends on the existing administrator seam directly. There is no intermediate initializer service, repository-document adapter, or filesystem abstraction. Filesystem persistence is real in tests under isolated temporary roots; per project testing rules, it is not mocked.

## Rejected alternatives

- Keep `init_repo()` behind the command and add config creation alongside it: rejected because root-document mutation remains reachable and the command would coordinate two unrelated initialization policies.
- Add a new `InitService` or wrapper around `ChangeConfigAdministrator`: rejected as a shallow by-pass seam whose interface and implementation would both be a single delegation. The Typer adapter can depend on the existing deep module directly.
- Reimplement directory creation, template loading, or non-overwrite checks in the command: rejected because it splits one invariant across seams, increases race and drift risk, and bypasses the established module.
- Check config existence before initialization or change `initialize_config()` to return creation state: rejected because output does not require that distinction, a preflight check creates duplicated policy and a time-of-check/time-of-use gap, and changing the established three-method module contract is out of scope.
- Validate, repair, or rewrite an existing config: rejected because initialization is non-destructive. Existing bytes, validity, and modification time are user-owned state.
- Remove `init_repo`, `InitResult`, or legacy root-scaffolding internals now: rejected because command disconnection achieves the product goal without broadening compatibility risk. Retirement requires a separate change with explicit API-removal impact.
- Migrate or clean managed blocks in root documentation: rejected because those files leave init ownership entirely; even reading markers would preserve an obsolete coupling.
- Assert the complete generated YAML as raw text: rejected as brittle coupling to formatting. Command tests assert parseability and stable schema values, while administrator tests retain detailed template coverage.
- Mock `ChangeConfigAdministrator` in command tests: rejected because the contract is filesystem behavior and project rules permit mocks only at persistence boundaries. Isolated temporary repositories test the real composition without touching the user system.
