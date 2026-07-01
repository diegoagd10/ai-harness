# PRD — fix-tests-prompts-assertions

## Intent

The `tests-prompts` suite produces **wrong-but-plausible** results because its CSV input is malformed in a way the parser silently tolerates. Concretely:

- A row whose prompt contains an unquoted comma (e.g. `Create a simple python script for fibonacci,10,0,0`) is parsed by `csv.DictReader` as **four fields**, not one — the comma is the separator, so the prompt is truncated and the trailing `,10,0,0` is swallowed into the expected-count columns.
- Because the per-row assertion block in `tests-prompts/run.sh` runs `[ "$got" -ne "$exp" ]` with no prior validation of `$exp`, two failure modes coexist:
  - **Row 2 / Row 4** — the swallowed suffix (`how are you doing?`, `como estas?`) becomes the "expected tools" string; bash prints `integer expression expected` to stderr but the `if` is treated as false, so the row fails loudly but opaquely.
  - **Row 5** (the user's reported case) — the swallowed `10` IS a valid integer, the comparison runs cleanly, and the row passes whenever the orchestrator happens to emit exactly 10 tool events. The test is meaningless.

The product outcome is: every `tests-prompts` row means what its author wrote, the suite fails loudly with a clear message when a row is malformed or the orchestrator deviates, and — as a related outcome from a separate user report — neither `tests-prompts` nor `e2e` runs may destroy or mutate a developer's local `~/.ai-harness` configuration on the host.

## Scope

### In

- **Validate `cases.csv` rows at parse time.** `parse_csv` must reject (non-zero exit + clear stderr) any row whose column count does not match the header, or whose count columns are not integer-shaped. The same check must apply whether `parse_csv` is invoked from `run.sh` or from a unit/regression harness.
- **Guard numeric comparisons.** Replace `[ "$got" -ne "$exp" ]` in the per-row block with a regex-validated integer form, so a non-integer expected count is reported as a per-row error with row index, prompt, and the offending value — not swallowed bash noise.
- **Repair `tests-prompts/cases.csv`.** Quote the three malformed rows per RFC-4180 so `csv.DictReader` sees a single prompt field. The intended semantics of row 5 (Fibonacci) is a follow-up question for the user; the PRD captures both possible interpretations and the fix is data-only — quoting does not invent expected counts.
- **Add a regression test for `parse_csv`.** A shell/Python harness that asserts on the current `cases.csv`: N data rows, every prompt text matches the source CSV byte-for-byte (modulo quoting), every count column parses as a non-negative integer. Lives next to `run.sh` (e.g. `tests-prompts/tests/parse_csv.test.sh`) so CI can run it without Docker or a model.
- **Document the CSV contract.** Header comment in `tests-prompts/run.sh` stating: prompts containing commas, quotes, or newlines MUST be RFC-4180 quoted; unquoted commas shift expected-count columns silently and produce meaningless pass/fail signals.
- **Test-runner config isolation.** Both `tests-prompts` and `e2e` runners must not mutate or destroy the developer's local `~/.ai-harness` (or adjacent `~/.config/opencode`, `~/.claude`, `~/.agents`, `~/.copilot`, `~/.github`) configuration on the host. Concrete candidates — to be resolved in the design phase — include: keep all runs inside their existing Docker containers with isolated `HOME`, or snapshot/restore any host config the runner touches.
- **Surface the fix in the row's failure trace.** When a row is rejected by `parse_csv`, write a structured entry to `$LOGS_DIR` (same shape as `dump_failure_trace`) so CI scrapers and humans see the same artifact regardless of where the failure originates.

### Out

- Changing the **schema** of `cases.csv` (column names, count semantics, adding/removing columns). The bug is the parser's tolerance of malformed input, not the schema.
- Changing what counts as a "tool call" in `_extractor.py`. The exploration flagged this as the single source of truth for `tool_use` events; touching it would re-open a different discussion about non-determinism in tool counts.
- Tolerating approximate tool counts (e.g. ±1 window) instead of exact equality. The user's contract is exact equality; loosening it is a separate design call.
- Refactoring `e2e/` test infrastructure beyond the config-isolation issue. The `rm -rf "$HOME/.ai-harness"` line in `e2e/lib.sh::cleanup_test_env` is in scope only insofar as it must be made safe for the host; its broader test-helper design is not.
- Adding CI gating to `docker-test.sh`. The regression test for `parse_csv` is added on disk, but wiring it into CI is a separate ops decision.
- Resolving the user-intent ambiguity on row 5's expected counts. The PRD captures the two readings; implementation must confirm with the user before picking one.

## Capabilities

- **validate-csv-row-shape**: `parse_csv` rejects any row whose field count differs from the header, or whose trailing three columns are not non-negative integers, with a clear per-row error (row index, offending value, reason) and a non-zero exit code. Independent spec: a small Python test fixture with a deliberately malformed row goes red on the unfixed parser and green on the validated one.
- **guard-bash-numeric-comparison**: the per-row assertion block in `run.sh` uses a regex-validated integer form (`[[ "$exp" =~ ^[0-9]+$ ]]` guard) before any arithmetic comparison, so a non-integer expected value produces a labeled `[FAIL]` with the offending value instead of `bash: integer expression expected`. Independent spec: a row whose expected tool count is the literal string `how are you doing?` produces the labeled fail message under the new code and the bash integer-error noise under the old code.
- **fix-cases-csv-encoding**: `tests-prompts/cases.csv` rows 2, 4, and 5 are quoted per RFC-4180 so that `csv.DictReader` treats the comma-containing prompt as a single field. The fix is data-only — it does not invent expected counts; the row-5 user-intent ambiguity is resolved by the user (or flagged as TBD in the spec). Independent spec: a parser dump test shows row 5's prompt as `Create a simple python script for fibonacci` (not truncated) and the count columns as `0,0,0` unless the user confirms otherwise.
- **add-parse-csv-regression-test**: a runnable verifier (likely `tests-prompts/tests/parse_csv.test.sh`) that exercises `parse_csv` on `cases.csv` and asserts on (a) exact row count, (b) byte-equality of each prompt against the CSV source, (c) integer-shape of every count column. Runs without Docker or a model — under a second on the host. Independent spec: the test goes red on the unfixed CSV (rows 2/4/5 fail the byte-equality check) and green after `fix-cases-csv-encoding`.
- **isolate-host-config-from-test-runs**: neither `tests-prompts` nor `e2e` invocations mutate or destroy a developer's local `~/.ai-harness` (or `~/.config/opencode`, `~/.claude`, `~/.agents`, `~/.copilot`, `~/.github`) configuration on the host. The exact mechanism — container-only execution with isolated `HOME`, or backup/restore of touched host paths — is a design-phase decision. Independent spec: a host-side smoke test that backs up `~/.ai-harness` into a tempdir, runs `./tests-prompts/docker-test.sh` (or its equivalent), and asserts the backup is byte-identical afterward.

## Approach

The work splits into two parallel tracks because the two user reports are independent failure modes that happen to share a Change folder:

**Track A — CSV / assertion correctness.** This is the smaller, fully-mechanical half. The diagnosis is already in `exploration.md`:

1. Fix `cases.csv` (data-only, ~3 lines, RFC-4180 quoting).
2. Harden `parse_csv` in `run.sh` to validate field count and integer shape per row, returning non-zero + a labeled error on the first bad row (or collecting all bad rows — design call).
3. Harden the per-row comparison block in `run.sh` with a regex guard so non-integer expected values surface as labeled `[FAIL]` messages.
4. Add `tests-prompts/tests/parse_csv.test.sh` as a permanent regression.
5. Document the CSV contract in the header comment of `run.sh`.

Track A's tight feedback loop is the Python REPL snippet from `exploration.md` ("Test Surface"), runnable in under a second on the host. The test that goes red on the unfixed CSV is the same snippet extended with assertions — it becomes the regression.

**Track B — host config isolation.** Independent diagnosis:

1. Inventory every place `tests-prompts/` and `e2e/` write to `$HOME/.ai-harness` (and adjacent paths). Known candidates from exploration: `tests-prompts/run.sh` calls `ai-harness install -o opencode` which writes to `$HOME/.ai-harness` and `$HOME/.config/opencode`; `e2e/lib.sh::cleanup_test_env` `rm -rf`s those paths on the host.
2. Decide isolation mechanism — likely a combination of (a) requiring the existing Docker path for `tests-prompts` (already the documented entrypoint via `docker-test.sh`) and (b) confirming `e2e` is container-only or making it so. The exact config path the user is losing is a discovery gap if not surfaced during design.
3. Add a host-side smoke test (see capability `isolate-host-config-from-test-runs`) so regressions surface before merge.

The two tracks share no code. Track B's outcome is verifiable by a before/after md5sum of `~/.ai-harness` across a test run; Track A's outcome is verifiable by the regression test in capability `add-parse-csv-regression-test`.

## Affected Areas

- `tests-prompts/cases.csv` — three rows quoted per RFC-4180.
- `tests-prompts/run.sh` — `parse_csv` adds row-shape validation; per-row comparison block replaces `[ -ne ]` with a regex-validated form; header comment updated with the CSV contract.
- `tests-prompts/tests/parse_csv.test.sh` — new regression verifier (placement TBD with the design phase).
- `tests-prompts/docker-test.sh` — likely unchanged; verify it still mounts an isolated `HOME` inside the container.
- `e2e/lib.sh` — `cleanup_test_env` must not destroy host config; exact change depends on isolation mechanism chosen in design.
- `e2e/docker-test.sh` — verify container isolation is sufficient.
- `docs/agents/` — if there's a developer-facing note about running the test suite on the host, it should be updated to reflect the new contract.

## Risks

- **User-intent ambiguity on row 5.** Two readings: (a) the user meant a literal prompt `Create a simple python script for fibonacci,10,0,0` (then the comma is intentional and the row should be quoted as-is), or (b) the user meant prompt `Create a simple python script for fibonacci` with `0,0,0` expected counts (the comma + counts are junk — likely a typo for the row's own suffix). **Implementation must confirm intent before quoting row 5.** Picking the wrong reading produces a "fix" the user re-opens within minutes.
- **Data-only fix is the wrong default.** Quoting the three rows makes the suite pass on the current data, but a future contributor who adds an unquoted prompt reintroduces the same silent failure. Parser hardening (capability `validate-csv-row-shape`) is what actually closes the bug class. The data fix alone is insufficient.
- **`set -e` temptation.** Adding `set -e` to `run.sh` is tempting because it would also catch the malformed-row case, but the script intentionally tolerates non-zero exits from `opencode run` (`|| true`) and from the extractor (`|| printf '0 0 0'`). A naïve `set -e` breaks the suite. Validation must be **inside** `parse_csv` / the per-row block, not via global shell options.
- **Tool-count non-determinism.** The orchestrator's tool count depends on model, repo state, and prompt phrasing. Asserting an exact count is brittle — `10` is a magic number that will drift over time. This change does **not** loosen the contract (out of scope), but it should at least make the per-row log surface the drift so the next iteration can decide on a tolerance window. Mentioned in the per-row failure trace; do not silently swallow.
- **Config-isolation mechanism has its own blast radius.** If Track B's fix is "make `e2e` container-only," contributors who currently run `e2e_test.sh` directly on their host will see a behavior change. If the fix is "backup/restore touched paths," the backup must include `~/.config/opencode`, `~/.claude`, `~/.agents`, `~/.copilot`, `~/.github`, and `~/.ai-harness` — missing one means the user still has to re-configure.
- **No CI gate on the prompt suite today.** The new `parse_csv.test.sh` lives on disk but won't run on PRs unless CI is updated. Flag in the PR description; do not silently assume CI coverage.
- **Discovery gap on the exact host config path.** The user described the symptom ("I have to run `ai-harness` again after the tests") but did not name the path. The PRD captures this as a design-phase discovery item. If the path turns out to be something outside the standard `~/.ai-harness` family (e.g. a per-repo `.ai-harness/installed.json`), the isolation scope widens.

## Rollback Plan

- **Track A is reversible by data + small script edits.** Reverting `cases.csv`, `parse_csv`, the comparison block, and the regression test restores the previous behavior. No database, no migration, no schema change.
- **Track B's rollback depends on the chosen mechanism.** Container-only: revert the documentation/run-script guard. Backup/restore: revert the backup hooks. Both are small diffs; neither touches user data.
- **No coordinated deploy is required.** This is a developer-facing test suite; a broken `tests-prompts` does not affect end users of ai-harness. Rollback is "revert the merge commit" if a regression slips through.
- **Acceptable to ship Track A without Track B (and vice versa).** They are independent vertical slices. If Track B's isolation mechanism proves contentious, Track A can land first to close the more embarrassing correctness bug.

## Dependencies

- `tests-prompts/run.sh` is the single integration point for Track A. No upstream/downstream coupling inside the product — `_extractor.py` and `Dockerfile` are unchanged.
- Track B depends on a design-phase discovery of the exact host config paths the test runners mutate. If that discovery surfaces a non-`~/.ai-harness` path (e.g. per-repo state), the implementation must widen the isolation scope.
- The `e2e` suite's Tier 2 / Tier 3 tests actively use `$HOME/.ai-harness/installed.json` and `$HOME/.ai-harness/overrides.json`. Any isolation change must keep those tests' in-container setup working — they assume they own the filesystem inside their sandbox.
- No external library or runtime change. Python `csv.DictReader`, bash 4+ regex matching, and the existing `jq`/`python3` in the container image are sufficient.

## Success Criteria

1. **Malformed rows fail loudly, never silently pass.** `cases.csv` rows whose prompt contains an unquoted comma are either (a) quoted so the parser sees one prompt field, or (b) rejected by `parse_csv` with a labeled error. There is no third outcome — in particular, the Fibonacci row no longer passes due to column shifting.
2. **Non-integer expected counts surface as labeled errors.** When a row's expected count is not a non-negative integer, the per-row block prints `[FAIL] row N (<prompt>): <count-name> expected <value> got <got> — non-integer expected`, sets `row_rc=1`, and the failure trace lands in `$LOGS_DIR`. The bash `integer expression expected` swallow is gone.
3. **`parse_csv` regression test is in the repo and runnable.** `tests-prompts/tests/parse_csv.test.sh` (or equivalent) exits 0 against the fixed `cases.csv` and exits non-zero against the unfixed one. It runs without Docker or a model, under a second on the host, and is documented in `run.sh`'s header comment.
4. **CSV contract is documented.** `tests-prompts/run.sh`'s header comment states that prompts with commas, quotes, or newlines must be RFC-4180 quoted, and explains what happens otherwise (column shift, silent pass or opaque fail).
5. **Test runs do not destroy host `~/.ai-harness` config.** A host-side smoke test that snapshots `~/.ai-harness` (and adjacent paths) before running `tests-prompts/docker-test.sh` and `e2e/docker-test.sh` shows the snapshot is byte-identical after the run. The user no longer needs to re-run `ai-harness` after running the test suite.
6. **The Fibonacci row's status is unambiguous.** After the fix, row 5 either (a) passes for a clear, documented reason the user accepts, or (b) fails with a labeled message that names the actual tool count and the expected count. There is no path where it silently passes due to parser error.