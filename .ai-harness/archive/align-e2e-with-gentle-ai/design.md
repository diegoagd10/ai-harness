# Design — align-e2e-with-gentle-ai

## Context

The ai-harness e2e suite is currently fragmented across multiple Python files and
Invoke tasks, with no single place a maintainer can read to understand behavior
coverage. The PRD aligns this repo with the proven gentle-ai pattern: one canonical
e2e test file containing many `test_*` functions, a shared helper library, tiered
execution gated by env vars, and one outer Docker runner that is the only command
surface for local and CI use. The design must hold the line on that invariant —
**exactly one public e2e test file and exactly one public e2e runner** — while
preserving existing install/uninstall/set-models/path/idempotency coverage, all
inside a 560 LOC budget.

## Deep modules

### `e2e/e2e_test.sh` — Canonical Behavior Suite

- **Seam**: filesystem path `e2e/e2e_test.sh`; executed inside the container via
  `bash e2e/e2e_test.sh`. This is the **only** place behavior tests live.
- **Interface**:
  - Entrypoint: the script itself. Running it executes all enabled tier tests in
    fixed order from a bottom-of-file invocation block, prints a summary, and
    exits non-zero on any failure.
  - Env-gated tiers (mirroring gentle-ai lines 4–13):
    - Tier 1 runs by default: binary basics, dry-run output, agent/preset/component
      flag coverage, override/idempotency edge cases.
    - `RUN_FULL_E2E=1` enables Tier 2: full filesystem install, rendered-file
      content, skill coverage, exact-path assertions.
    - `RUN_BACKUP_TESTS=1` enables Tier 3: backup/restore/snapshot behavior.
  - Sibling contract: must source `e2e/lib.sh` for all reusable mechanics — never
    duplicate assertion or cleanup logic inline.
  - Exit code: `0` = pass, `1` = any failed test. Summary on stdout.
- **Hides**:
  - Every `test_*` function and its assertions (~300 LOC of behavior coverage for
    install/uninstall/set-models/path/idempotency/override).
  - Tier gating expressions (`if [ "${RUN_FULL_E2E:-0}" = "1" ]; then …`).
  - Bottom-of-file invocation ordering (which tier runs after which).
  - Section comment headers that organize the file into readable categories.
- **Depth note**: a 3-line interface (`bash <path>`, two env vars, exit code)
  backed by the entire behavior suite — reviewers read this single file to see
  every assertion ai-harness makes about its installer. Deletion test: removing
  it loses the entire suite, so it earns its keep. Reject any version that splits
  tests across sibling files or that duplicates behavior in another harness.

### `e2e/docker-test.sh` — Outer Isolated Runner

- **Seam**: filesystem path `e2e/docker-test.sh`; invoked as
  `./e2e/docker-test.sh` from repo root by both humans and CI. This is the
  **only** e2e entry point.
- **Interface**:
  - CLI: zero positional arguments required for the v1 scope (single canonical
    image). One optional positional argument reserved as the future platform slot,
    e.g. `./e2e/docker-test.sh ubuntu` — accepted, ignored, or routed to the
    image tag when the matrix lands.
  - Forwards env vars into the container: `RUN_FULL_E2E`, `RUN_BACKUP_TESTS`,
    `GITHUB_TOKEN` (if set on the host). Anything else stays out.
  - Wraps the test invocation with `run_with_timeout`.
  - Exit code mirrors `e2e_test.sh`'s exit code so CI gates stay dumb.
- **Hides**:
  - Image build context (`docker build` invocation, tag computation).
  - Decision that v1 uses a single image rather than a distro matrix.
  - Container cleanup and pass/fail aggregation across platforms (a no-op for
    v1 because there is only one platform, but the seam is shaped so adding
    Ubuntu/Arch/Fedora later does not change the interface).
  - Whether the runner also handles non-e2e CI tasks (it does not — that is a
    different concern, and bleeding it in here would make this runner shallow).
- **Depth note**: callers see "run `./e2e/docker-test.sh` and read the exit
  code." Everything about Docker is hidden behind that one CLI. Deletion test:
  removing it puts `docker build` and `docker run` back into CI and docs — both
  start to drift, which is precisely the regression the PRD is preventing.
  Keeps the surface so small that adding a second runner would have nowhere to
  land.

## Internal collaborators

### `e2e/lib.sh` — Shared Shell Helpers

- Sourced by `e2e_test.sh`; **never** invoked standalone, never executed in
  CI directly.
- **Interface** (the names that cross into tests):
  - Logging/counters: `log_test`, `log_pass`, `log_fail`, `log_skip`, `log_info`,
    accumulators `PASSED`/`FAILED`/`SKIPPED`, `print_summary`.
  - Assertions: `assert_file_exists`, `assert_file_not_exists`,
    `assert_file_contains`, `assert_file_not_contains`, `assert_dir_exists`,
    `assert_file_size_min`, `assert_valid_json`, `assert_output_contains`,
    `assert_output_not_contains`, `assert_md5_match`.
  - Environment: `cleanup_test_env`, `setup_*` for fake binaries and fixtures,
    `resolve_binary`.
- **Hides**: shell one-liners (grep/sed/jq mechanics), temp-dir path conventions,
  how `FAILED`/`SKIPPED` are aggregated.
- Tested **transitively** through `e2e_test.sh` — never mocked, never run in
  isolation. Deletion test: removing it forces every test to inline assertion
  noise, shrinking signal and growing line count past budget.

### `e2e/Dockerfile` — Isolated Test Image

- Built only by `docker-test.sh`.
- **Interface** (contract to its caller): produces an image that exposes
  `e2e_test.sh` and `lib.sh` at their canonical paths, with `bash`, `uv`,
  `jq`, and a writable home dir for sandboxed `uv tool install`.
- **Hides**: base image choice (Ubuntu, per gentle-ai), system packages,
  COPY/ENV ordering.
- Tested transitively through `docker-test.sh`; not a public seam.

### Docs surface — `README.md`, `CODING_STANDARDS.md`, `CONTEXT.md`

- Not code modules. Each update is a single short section that:
  - Advertises `./e2e/docker-test.sh` as the only e2e command.
  - States the invariant: one canonical `e2e/e2e_test.sh` with many `test_*`,
    helpers split into `e2e/lib.sh`.
  - Documents the tier env vars and the rule for adding new tests (mirror
    gentle-ai `docs/docker-e2e-testing.md` lines 74–80).
- Changes live in existing files only; no new doc files.

### Task entrypoints — `tasks.py`, `e2e/tasks.py`, `pyproject.toml`

- `e2e/tasks.py` and the relevant `tasks.py` e2e entry become thin wrappers that
  delegate to `./e2e/docker-test.sh`, or are removed if they no longer earn their
  keep. `pyproject.toml` loses e2e-specific Python test dependencies that the
  new shell suite does not need. Deletion test on each wrapper individually —
  if invoking the wrapper adds nothing the runner cannot say, drop it.

## Seam map

```
      maintainer / CI
              |
              v
   e2e/docker-test.sh        <-- PUBLIC SEAM 1 (outer runner)
        |    |    |
        |    |    +--- forwards RUN_FULL_E2E, RUN_BACKUP_TESTS, GITHUB_TOKEN
        |    +-------- build/run via e2e/Dockerfile (internal collaborator)
        |
        v
   e2e/e2e_test.sh           <-- PUBLIC SEAM 2 (canonical suite)
        |
        | sources
        v
     e2e/lib.sh              <-- internal collaborator (helpers)
```

Exactly two public seams. Everything else is hidden behind one of them. No
parallel harness, no matrix in v1, no alternate entry points.

## Rejected alternatives

- **Keep Python tests, wrap them in a shell orchestrator.** Creates two sources
  of truth (shell tier gating + Python pytest). Violates the PRD's explicit
  out-of-scope clause against maintaining parallel e2e harnesses. Would also
  force adapter shims between bash tier env vars and pytest markers — net
  shallow, over budget.

- **Replicate gentle-ai's full Ubuntu/Arch/Fedora matrix in v1.** Three
  Dockerfiles plus matrix orchestration exhausts the 560 LOC budget before any
  tests land. The PRD's "Stable isolated runner" capability only requires *one*
  isolated runner; the matrix is a separate, future change. The runner's
  interface already reserves a platform argument so this can land later without
  changing the seam.

- **Keep Invoke as the primary e2e entry and add `docker-test.sh` alongside.**
  Two documented entry points means two places for the suite to drift from.
  Invoke may still call `docker-test.sh`, but the runner remains the only
  command humans and CI type.

- **Inline all helpers in `e2e_test.sh`, no `lib.sh`.** Gentle-ai explicitly
  splits helpers into `lib.sh` so test definitions stay scannable. Cramming
  150 lines of assertion mechanics into the same file as 300 lines of behavior
  blurs what each `test_*` actually proves. Deletion test: shrinks the suite
  file ~30% but inflates per-test noise by more, losing depth.
