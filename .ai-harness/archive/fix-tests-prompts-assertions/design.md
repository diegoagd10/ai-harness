# Design — fix-tests-prompts-assertions

## Context

Two independent user reports share a Change folder.

**Track A** — `tests-prompts` produces wrong-but-plausible results because `cases.csv` is malformed and the parser silently tolerates it. Three rows (2, 4, 5) have unquoted commas inside the prompt; `csv.DictReader` treats each comma as a field separator, truncating the prompt and shifting the trailing `,N,N,N` into the expected-count columns. The per-row assertion block in `run.sh` then does `[ "$got" -ne "$exp" ]` with no integer guard. Rows 2/4 fail loudly (bash `integer expression expected`); row 5 — the user's reported case — silently passes because the shifted `10` IS an integer and happens to match the orchestrator's tool count. The bug is silent test meaninglessness, not a crash.

**Track B** — running `tests-prompts` or `e2e` from the host (without going through `docker-test.sh`) calls `ai-harness install -o opencode` and `e2e/lib.sh::cleanup_test_env`, both of which mutate `$HOME/.ai-harness` and adjacent paths. The user reports losing their local config and having to re-run `ai-harness` afterward. The two Dockerfiles already isolate `$HOME` inside the container (no `HOME` mount in either `docker run`), so the bug only triggers when the runner scripts are invoked directly on the host.

Module shape matters here because the temptation is to "fix the CSV and add an `rm -rf` guard." A CSV-only fix is shallow: a future contributor adds another unquoted row and the same silent failure returns. A path-by-path backup is also shallow: it walks the same shape as the bug instead of closing the bug class. The deeper cuts are: **(1) extract `parse_csv` into a real Python module that owns row-shape validation**, **(2) make the integer guard a first-class helper rather than a side-effect of `-ne`**, and **(3) refuse to run on the host entirely** so the host-config mutation class is closed at its source, not per-path.

## Deep modules

### `parse_csv` — row-shape-aware CSV reader

- **Seam**: `tests-prompts/parse_csv.py` (new file). Replaces the inline `python3 - "$path" <<'PYEOF' … PYEOF` heredoc inside `run.sh::parse_csv`.
- **Interface** (the contract `to-issues` slices within):
  - CLI: `python3 parse_csv.py <path>` → on stdout, records of `<prompt>\t<tools>\t<skills>\t<subs>\0` (NUL is the record terminator, TAB is the field separator — same wire format `run.sh` already consumes). On a row-shape error (wrong column count, non-integer count field, missing prompt), writes a labeled `[PARSE-FAIL] row <N> (<prompt-prefix>): <reason>` line to stderr and exits non-zero.
  - Python API: `parse_rows(path) -> Iterator[Row]` where `Row = tuple[str, int, int, int]` (prompt, tools, skills, subs). Raises `CsvShapeError(row_index, reason, offending_value)` on the first malformed row (fail-fast, not collect-all — see Rejected alternatives).
  - Header fields are matched by exact name (currently `prompt`, ` tools calls (number)`, ` skills calls (number)`, ` sub-agent calls (number)` — the leading spaces are part of the CSV header and are preserved as keys). Validation rules: (a) `len(row) == len(fieldnames)` AND `row.get(None) is None` (catches trailing-field shift); (b) each of the three trailing fields matches `^[0-9]+$` after stripping whitespace; (c) prompt is non-empty after stripping.
- **Hides**: csv parsing, header field-name matching, integer regex, error formatting, NUL/TAB wire format. `run.sh` consumes records; it does not know what csv.DictReader is.
- **Depth note**: This module earns its keep because deleting it would put all the validation logic back inside `run.sh` as inline shell + Python, which is exactly the shallow seam the bug came from. The interface is small (one CLI verb, one Python generator); the implementation owns row-shape correctness — the one thing the row-by-row bash loop cannot enforce.

### `compare_count` — integer-guarded assertion helper

- **Seam**: inline bash function in `tests-prompts/run.sh`, replacing the three copies of `[ "$got" -ne "$exp" ]` on lines 191/196/201.
- **Interface**: `compare_count <label> <got> <exp> <prompt> <row_index>` → returns 0 if `exp` matches `^[0-9]+$` AND `got == exp`; returns 1 otherwise and writes a labeled `[FAIL] row N (prompt): <label> expected <exp> got <got> — <reason>` to stderr. Two failure modes:
  - non-integer `exp` → `— non-integer expected: <exp>` (closes the bash `integer expression expected` swallow)
  - integer but unequal → `— calls expected <exp> got <got>` (preserves the current `[FAIL]` shape)
  - The non-zero `exp` value is preserved verbatim in the message so the failure trace names the offending string, not just "expected" vs "got".
- **Hides**: the regex guard, the dual failure-mode formatting, and the labeled exit code. The per-row loop sees one helper, not three copies of `-ne`.
- **Depth note**: Deleting it would re-spread three copies of `[ ... -ne ... ]` across the row loop and reintroduce the silent-swallow class. The interface is one function with five positional args; the implementation is ~10 LOC of bash that owns "an integer-compare that names its failures."

### `assert_container_required` — host-mutation guard

- **Seam**: `tests-prompts/run.sh` (inline, near the top) AND `e2e/lib.sh` (after the `set -uo pipefail` line, sourced by `e2e_test.sh`). Single helper, two copies — the duplication is intentional because `tests-prompts/run.sh` does not depend on `e2e/lib.sh` and creating a shared lib for one function is worse than two 12-line copies.
- **Interface**: `assert_container_required` (no args, no return value). On host detection, writes `[FATAL] refusing to run on the host: <runner> must be invoked via <entrypoint>. See <doc-path>.` to stderr and exits 2. Detection is the union of two checks (any one passes):
  - `$CONTAINER_REQUIRED_OK=1` env var (escape hatch for host-side development of the runner itself — `docker-test.sh` sets it inside the container; a developer running `bash run.sh` on the host can set it explicitly to bypass)
  - Standard Linux container markers, checked in order: `/run/.containerenv` exists (Podman/CRI-O), `/.dockerenv` exists (Docker), `/proc/1/cgroup` contains the substring `docker` or `containerd` (fallback for stripped images)
- **Hides**: the detection logic and the env-var escape hatch. Callers see a guard that either passes silently or `exit 2`s with a message.
- **Depth note**: This is the load-bearing seam for Track B. Deleting it (or weakening it to a warning) reopens the bug class — every host-side `rm -rf "$HOME/.ai-harness"` and `ai-harness install -o opencode` becomes possible again. The interface is zero-arg and exit-on-fail; the implementation owns "are we in a container?" without callers needing to know. Path-by-path backup/restore is rejected as a shallower alternative (see below).

### `parse_csv_regression` — pinned contract test

- **Seam**: `tests-prompts/tests/parse_csv.test.sh` (new file).
- **Interface**: standalone shell script. Invokes `python3 tests-prompts/parse_csv.py tests-prompts/cases.csv`, captures stdout, asserts: (a) exactly N data rows (N = current count, asserted as a literal in the test); (b) every prompt field byte-equals the original CSV source modulo RFC-4180 quoting (the test parses `cases.csv` independently with `csv.reader` for the ground truth and compares prompt-for-prompt); (c) every count field matches `^[0-9]+$`. Exits 0 on the fixed CSV, non-zero on the unfixed CSV (rows 2/4/5 fail the byte-equality check). Runs in <1s on the host with no Docker and no model.
- **Hides**: the exact assertions, the row count literal, the independent re-parse for ground truth. Future contributors see a test that goes red if they introduce an unquoted-comma row.
- **Depth note**: The tight feedback loop from `exploration.md` (the Python REPL snippet that printed per-row tuples) is the same loop, hardened into assertions and put on disk. Deleting it would mean the next bug of this class has no regression to catch it — which is exactly how this one slipped in.

### CSV contract — header comment

- **Seam**: top of `tests-prompts/run.sh` (extended existing header) and a single-line comment in `tests-prompts/cases.csv` itself.
- **Interface (documentation)**: states that prompts containing commas, quotes, or newlines MUST be RFC-4180 quoted; unquoted commas shift expected-count columns and the comparison block either fails opaquely (`integer expression expected`) or, worse, passes silently when the shifted value happens to be an integer that matches the orchestrator's tool count.
- **Hides**: nothing — this is documentation, not a module. It exists so the next contributor who edits `cases.csv` reads the rule before they break it.
- **Depth note**: not a deep module, but a deep *contract surface*. The header comment is the cheapest place to encode "prompts with commas must be quoted" so the bug class doesn't recur via a documentation gap.

## Internal collaborators

- **`slugify` (bash, inline in `run.sh`)** — fs-safe prefix used in failure-trace filenames. Tested transitively through the per-row `dump_failure_trace` call site; never mocked. Unchanged.
- **`dump_failure_trace` (bash, inline in `run.sh`)** — writes failure-only `/logs/<row_index>-<slug>.json`. Tested transitively through the row-loop fail path. Unchanged in shape; will receive a new caller from `parse_csv`'s stderr if the failure-trace-dump spec calls for it (deferred to implementation — the labeled stderr line is the minimum deliverable; writing a JSON trace for a parse-time failure is a nice-to-have that the parser-shape contract can carry without a separate seam).
- **`extract_counts` (Python, `tests-prompts/_extractor.py`)** — schema-aware counter. Unchanged. Out of scope per the PRD; not touched by this change.
- **`run_row` (bash, inline in `run.sh`)** — per-row `opencode run` invoker. Unchanged. Out of scope.
- **`resolve_binary`, `log_pass/fail/skip`, etc. (bash, `e2e/lib.sh`)** — e2e test helpers. Unchanged except that `assert_container_required` is added alongside them and `cleanup_test_env`'s callers are unchanged (the guard upstream makes `cleanup_test_env` unreachable from a host run, which is the point).

## Seam map

```
tests-prompts/tests/parse_csv.test.sh  ──executes──>  tests-prompts/parse_csv.py  ──reads──>  tests-prompts/cases.csv
                                                          │
                                                          │ (CLI: NUL/TAB records on stdout)
                                                          ▼
                            tests-prompts/run.sh::parse_csv caller
                                                          │
                                                          ▼
                            compare_count <label> <got> <exp> <prompt> <row_idx>
                                                          │
                                                          ▼
                                per-row PASS/FAIL → dump_failure_trace → $LOGS_DIR

tests-prompts/run.sh  ──asserts──>  assert_container_required  ──on host──> exit 2
e2e/lib.sh            ──asserts──>  assert_container_required  ──on host──> exit 2
```

The only public seams are the four modules above. The internal collaborators are tested through the seams that use them — no new mocks, no new test doubles.

## Rejected alternatives

**Track A — data-only fix (`fix-cases-csv` alone).** RFC-4180 quoting the three rows makes the suite pass on current data, but a future contributor who adds an unquoted prompt reintroduces the same silent failure. The parser hardening is what closes the bug class; the data fix is one-shot. Implementation MUST do both, in this order: parser first, data second.

**Track A — collect-all-bad-rows vs fail-fast.** `parse_csv` could collect every malformed row and report them in one go, or fail on the first. Collect-all is friendlier for a 100-row CSV; for the current 5-row CSV it adds complexity (a list of errors to format, a single non-zero exit) for negligible user benefit. Fail-fast is chosen. If the CSV grows or the contributor workflow changes, this is a one-line behavior swap inside `parse_csv.py`.

**Track B — per-path snapshot/restore (`cleanup_test_env` becomes backup-then-rm-then-restore).** Walks the shape of the bug: enumerate `$HOME/.ai-harness`, `$HOME/.config/opencode`, `$HOME/.claude`, `$HOME/.agents`, `$HOME/.copilot`, `$HOME/.github`, snapshot each to a tempdir, run the test, restore from the tempdir. Rejected because (a) it does not close the bug class — any path the runner mutates that is NOT in the enumeration is still at risk; the user's report explicitly named `~/.ai-harness` but the failure mode is "any path the runner writes"; (b) it adds a restore path that can itself fail and leave the user in a worse state than the original bug (partial restore → partial config loss); (c) it is more LOC than the container guard and harder to verify (the verification is "snapshot is byte-identical after" — but the snapshot must exist, which means the test harness must create it, which means the test harness now writes to disk too). The container-required guard closes the bug class at its source: if the runner cannot run on the host, the host cannot be mutated.

**Track B — make `e2e_test.sh` container-only by deleting the host-side script.** Stronger version of the container guard — refuse the script outright rather than guard at runtime. Rejected because (a) it changes the script's public surface and breaks anyone who has the host entrypoint in their muscle memory or CI; (b) the guard with a `$CONTAINER_REQUIRED_OK=1` escape hatch preserves legitimate use cases (developing the runner itself, debugging the test harness) without removing the host-safety net.

**Track A — `set -e` in `run.sh`.** Would catch the malformed-row case via shell-level error propagation. Rejected because `run.sh` intentionally tolerates non-zero exits from `opencode run` (`|| true`) and from the extractor (`|| printf '0 0 0'`); a naïve `set -e` would break the suite. Validation MUST live inside `parse_csv` / `compare_count`, not in the global shell options.

**Track A — tolerance window for tool counts (e.g. `±1`).** Out of scope per the PRD; loosening the exact-equality contract is a separate design call that the per-row failure trace can surface (it already names `expected <exp> got <got>`) without requiring a code change here.

## Implementation notes (not a module — discovery items)

- **`cases.csv` row 5 user-intent ambiguity.** The PRD captures two readings of `Create a simple python script for fibonacci,10,0,0`: (a) literal prompt with expected `0,0,0` (the comma + `10,0,0` is a typo for the row's own suffix); (b) literal prompt with expected `0,0,0` AND the `10` is a typo for an empty/missing cell. Implementation MUST surface this as a user-confirmation question before quoting row 5. The two unambiguous rows (2 and 4) can be quoted without further input. If the user does not answer in time, the design says: quote rows 2 and 4, leave row 5's quoting as a TODO with a labeled stderr line from `parse_csv` until resolved.
- **Exact host config paths.** The user's report named the symptom ("re-run `ai-harness` after tests") but not the exact path. The container-required guard sidesteps enumeration: by refusing host-side runs, no host path can be mutated regardless of which one `cleanup_test_env` or `ai-harness install -o opencode` would have touched. No inventory script is needed for this change.
- **CI wiring for `parse_csv.test.sh`.** The new regression lives on disk but is not gated by CI today. The PRD flags this; implementation should mention it in the PR description. Wiring is a separate ops change.