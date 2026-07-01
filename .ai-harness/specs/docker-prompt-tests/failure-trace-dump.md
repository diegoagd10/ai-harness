# Spec — failure-trace-dump

## Purpose

The failure-path protocol: when a CSV row's count assertion fails, the runner
writes the full `opencode run --format json` stdout to a file under `/logs/`
(host-visible at `tests-prompts/logs/`, gitignored), and both the container
runner and the host harness print a `[FAIL]` line naming the failing row and
the failing assertion. No trace is written for passing rows in v1.

## Requirements

### Requirement: failure-only-dump
The system MUST write a per-row failure trace to `/logs/` ONLY when the row's
count assertion fails. Passing rows MUST NOT produce a trace file.

#### Scenario: passing row writes nothing
GIVEN a CSV row whose count assertion passes
WHEN the runner moves to the next row
THEN no file is added under `/logs/` for that row.

#### Scenario: failing row writes a trace
GIVEN a CSV row whose count assertion fails
WHEN the runner finishes processing that row
THEN exactly one file appears under `/logs/` whose contents are the raw `opencode run` stdout from that row (the JSON event stream as captured, no reformatting).

### Requirement: trace-filename
The trace filename MUST be derived from the row index plus a slugified prompt
prefix so failures are uniquely identifiable without collisions. The filename
MUST be filesystem-safe: it MUST contain only `[A-Za-z0-9._-]`, MUST strip or
collapse any other characters to `-`, and MUST be no longer than 64 characters
total.

#### Scenario: filename includes row index
GIVEN row index `3` with any prompt
WHEN the trace is written
THEN the filename begins with `3-`.

#### Scenario: filename slugifies the prompt
GIVEN a row whose prompt contains spaces, punctuation, and unicode (e.g. `say, "hello"!`)
WHEN the trace filename is constructed
THEN non-`[A-Za-z0-9_-]` characters are replaced with `-`, repeats of `-` are collapsed, and only the first 32 characters of the slugified prompt are used (plus the index prefix and `.json` suffix).

#### Scenario: filename is filesystem-safe
GIVEN any row
WHEN the trace filename is constructed
THEN the resulting filename contains only `[A-Za-z0-9._-]`, contains no `/`, contains no leading `.`, and is ≤ 64 characters long.

#### Scenario: no filename collision between rows
GIVEN two rows whose slugified prompts would collide (e.g. one with prompt `a/b` and one with prompt `a b`)
WHEN both fail and both are dumped
THEN the filenames differ — either by row-index prefix uniqueness or by slug differentiation — and neither trace overwrites the other.

### Requirement: fail-headline-line
The system MUST print a `[FAIL]` line that names the failing row and the
specific failing assertion. Both the container runner (printed during the run)
and the host harness (printed as it aggregates the failure) MUST emit this
line. The line MUST be human-readable and MUST identify the row distinctly
(e.g. by 1-based row index, by prompt, or both) and MUST identify the specific
count that mismatched (e.g. `tools calls expected 0 got 3`).

#### Scenario: container prints fail line
GIVEN a CSV row whose count assertion fails
WHEN the container runner reports the row
THEN a `[FAIL]` line is printed before the runner moves to the next row, naming the row identifier and the specific mismatched count.

#### Scenario: host prints fail line
GIVEN at least one CSV row failed inside the container
WHEN the host harness aggregates the result and exits
THEN a `[FAIL]` line is printed naming the row and the assertion, matching the message the container emitted.

#### Scenario: fail line is greppable
GIVEN any run output (passing, failing, or mixed)
WHEN a reader greps for `^\[FAIL\]`
THEN every per-row failure appears as exactly one matching line, and no passing row contributes a matching line.

### Requirement: aggregate-exit-on-failure
The system MUST exit non-zero overall when at least one row failed. The
non-zero exit MUST be preserved by the host harness (no `|| true` masking).

#### Scenario: single row failure yields non-zero exit
GIVEN one of N rows fails
WHEN the runner completes
THEN the runner exits non-zero and the host harness exits non-zero, even if the remaining N-1 rows passed.

### Requirement: gitignore
The directory `tests-prompts/logs/` MUST be listed in the repo-root
`.gitignore` so failure traces are not committed.

#### Scenario: gitignore contains the logs directory
GIVEN the repo-root `.gitignore`
WHEN a reader greps for `tests-prompts/logs/`
THEN exactly one line in `.gitignore` matches `tests-prompts/logs/` (verbatim, not a substring match against a longer path).

#### Scenario: logs dir is untracked
GIVEN a failure has just been dumped to `tests-prompts/logs/foo.json`
WHEN the user runs `git status`
THEN no entry under `tests-prompts/logs/` appears as a tracked-changes file (the directory is ignored).

### Requirement: hermetic-host-writes
The system MUST write only to `tests-prompts/logs/` on the host. The runner
MUST NOT write anywhere else under the repo on the host (no temp files in the
repo root, no files under `tests-prompts/` other than the logs dir, no
mutation of `cases.csv`).

#### Scenario: only logs dir is touched on host
GIVEN a full suite run, passing or failing
WHEN the host filesystem is inspected under the repo root
THEN the only post-run artifacts under the repo are inside `tests-prompts/logs/`; `cases.csv`, `Dockerfile`, `docker-test.sh`, and `run.sh` are unchanged on disk.