# Exploration — fix-tests-prompts-assertions

## Budget
30

## Affected Files
- `tests-prompts/cases.csv` — three rows (2, 4, 5) have unquoted commas in the prompt; the comma is parsed as a field separator, truncating the prompt and shifting the expected counts leftward. Root cause of the symptom the user reported.
- `tests-prompts/run.sh` — `parse_csv` (line 131) and the per-row comparison block (lines 191–205). The comparison block uses `[ "$a" -ne "$b" ]` on a value that, after the bad parse, is a non-integer string ("howareyoudoing?" / "comoestas?"). Bash prints `integer expression expected` to stderr, treats the test as "false → not equal → row_rc=1", so rows 2 and 4 fail loudly. But `set -uo pipefail` does NOT include `-e`, so the failure is contained to that one `if`; for **row 5** the parsed expected (`10`) IS a valid integer, so the comparison runs cleanly and the row passes whenever the orchestrator's tool count happens to equal 10.
- `tests-prompts/_extractor.py` — the schema-aware counter. Not the bug, but the **single source of truth** for what counts as a "tool call" (`tool_use` event with `part.type == "tool"`, name != `skill` and != `task`). If a fix changes what should count as a tool call (e.g. exclude `bash` for trivial prompts), this is the file to change.
- `tests-prompts/Dockerfile` and `tests-prompts/docker-test.sh` — runner plumbing. No change expected, but they are the path the feedback loop runs.

## Plan
1. **Reproduce the parse divergence.** Run the existing `parse_csv` helper from `run.sh` on the current `cases.csv` and dump the per-row `(prompt, tools, skills, subs)` tuples. This shows the prompt is truncated to `hello` / `Hola!!` / `Create a simple python script for fibonacci` and the trailing `,N,N,N` has been swallowed into the count fields. This is the "tight loop" — pure Python, ~1s, no Docker required. (See Test Surface.)
2. **Reproduce the assertion swallow.** Feed the per-row output back into a minimal bash harness that mirrors the `[ "$got" -ne "$exp" ]` block. Confirm that row 2/4 produce `integer expression expected` and exit non-zero, while row 5 produces a clean comparison that goes green if the orchestrator emits 10 tool events. (Same loop, ~1s.)
3. **Pin down user intent.** The CSV is clearly malformed, but the user wrote `Create a simple python script for fibonacci,10,0,0` and expected failure. The follow-up must confirm with the user whether the intent is (a) prompt = full literal `Create a simple python script for fibonacci,10,0,0` (then **quote** it), (b) prompt = `Create a simple python script for fibonacci` with **0** expected tool calls (the comma + `10,0,0` is junk — likely a typo for `0,0,0`), or (c) something else. The bug is the parser silently accepting both; the test's *meaning* is a separate question only the user can answer.
4. **Decide the fix shape** (after intent is confirmed):
   - **Data fix (minimal):** rewrite `cases.csv` so every prompt that contains a comma is RFC-4180 quoted. ~3 lines changed in `cases.csv`, no code change.
   - **Parser hardening (defense-in-depth):** in `parse_csv` (run.sh), validate that every row has exactly 4 fields and that the three trailing fields are integer-shaped. On failure, write to `$LOGS_DIR` and set a non-zero exit so the harness can never silently "pass" a malformed row. ~10–15 LOC.
   - **Bash assertion hardening:** replace `[ "$a" -ne "$b" ]` with a guarded form (e.g. `[[ "$a" =~ ^-?[0-9]+$ && "$b" =~ ^-?[0-9]+$ ]] || { row_rc=1; ... }`) so a non-integer expected is a hard failure with a clear message, not a swallowed bash error. ~5–10 LOC.
5. **Regression coverage.** Once the fix is chosen, the test that goes red on the bad CSV (step 1) becomes a permanent regression: a tiny shell test that asserts `parse_csv cases.csv` produces 5 rows with the *full* prompts, exact expected counts, and the trailing `None` field empty. This belongs in the change, not in product code, as a one-shot verifier (`tests-prompts/tests/parse_csv.test.sh` or similar) — confirm placement in design phase.
6. **Document the contract** in `tests-prompts/run.sh`'s header comment: "prompts containing commas MUST be RFC-4180 quoted; unquoted commas shift the expected-count fields and the comparison block will silently miscount or fail opaquely."

## Edge Cases
- **Quotes inside the prompt** (e.g. a prompt with literal `"`). RFC-4180 escape: double the quote (`""`). The current parser already handles this (it uses `csv.DictReader`), so the fix is purely on the data side. Worth a test row.
- **Empty cells.** `DictReader` returns `None` for missing trailing fields when a row is short. The current `parse_csv` defaults those to `"0"` via `or "0"`. Should be preserved.
- **Negative expected counts.** Not currently allowed (`-ne` is signed, but the column semantics don't make sense for negatives). Decide whether to validate.
- **Multiline prompts.** Already supported via the NUL bridge (commit `58bdff9`). A multiline prompt that *also* contains a comma will exercise both the NUL and the quoting path at once — a good end-to-end check.
- **Trailing newline / blank line.** `parse_csv` already skips blank-prompt rows; verify the new validation doesn't break that.
- **Bash `set -u` interaction with `row[None]`.** Not a concern here (it's all in Python); just noting that the run.sh script uses `set -uo pipefail` (no `-e`), which is what allows the silent integer-error swallow to happen.

## Test Surface
- **Tight feedback loop (no Docker, no model, ~1s):**
  ```bash
  # Replays the parse_csv bridge from run.sh against the current CSV
  # and prints the (prompt, tools, skills, subs) tuple per row.
  python3 - <<'PY'
  import csv, sys
  with open('tests-prompts/cases.csv', newline='') as f:
      r = csv.DictReader(f)
      for i, row in enumerate(r, 1):
          p = (row.get('prompt') or '').strip()
          t = (row.get(' tools calls (number)') or '0').strip() or '0'
          s = (row.get(' skills calls (number)') or '0').strip() or '0'
          u = (row.get(' sub-agent calls (number)') or '0').strip() or '0'
          print(f'{i:>2} | prompt={p!r} | tools={t!r} | skills={s!r} | subs={u!r} | extra={row.get(None)!r}')
  PY
  ```
  On the current `cases.csv` this prints:
  - Row 1 — prompt `hello`, counts 0/0/0, no extras. **Expected.**
  - Row 2 — prompt `hello` (truncated from `hello, how are you doing?`), `tools` is the literal string ` how are you doing?`, `None` carries `['0']`. **BUG.**
  - Row 3 — prompt `Hola`, counts 0/0/0, no extras. **Expected.**
  - Row 4 — prompt `Hola!!` (truncated from `Hola!!, como estas?`), `tools` is ` como estas?`, `None` carries `['0']`. **BUG.**
  - Row 5 — prompt `Create a simple python script for fibonacci` (truncated, the `,10,0,0` became the count columns), tools=10, skills=0, subs=0. **BUG — this is the row the user reported as "passing".**
- **Bash-comparison swallow check (also ~1s, no model):**
  ```bash
  bash -c '
  set -uo pipefail
  # Replay the run.sh comparison for each of the 5 parsed rows:
  for row in "hello|0|0|0" \
             "hello|how are you doing?|0|0" \
             "Hola|0|0|0" \
             "Hola!!|como estas?|0|0" \
             "Create a simple python script for fibonacci|10|0|0"; do
    IFS="|" read -r p t s u <<<"$row"
    rc=0
    for pair in "got_tools=$t:exp_tools=0" "got_skills=$s:exp_skills=0" "got_subs=$u:exp_subs=0"; do
      : # left as a stub: a got=0 vs the listed exp demonstrates the bash -ne error path
    done
    [ "0" -ne "$t" ] 2>/dev/null && echo "row [$p] tools compare: NOT EQUAL" || echo "row [$p] tools compare: equal (got=0, exp=$t)"
  done'
  ```
  Confirms rows 2/4 produce `bash: integer expression expected` (stderr only, comparison returns false) and row 5 compares cleanly.
- **End-to-end (slow, only after the fix lands):** `./tests-prompts/docker-test.sh` with the corrected `cases.csv`. ~minutes per row. Use to confirm the orchestrator's actual tool count against the user's intended expectation. **Not** part of the tight loop.
- **No existing automated tests** for `parse_csv` or the per-row comparison block — every test in `e2e/` is for the install/uninstall lifecycle, not the prompt runner. The fix should add a `parse_csv` regression test (see step 5 of the plan).

## Risks
- **Silent-regression risk on `set -e`.** Adding `set -e` to `run.sh` is tempting but out of scope: the script currently tolerates non-zero exits from `opencode run` (the `|| true` in `run_row`) and from the extractor (the `|| printf '0 0 0'`). A naïve `set -e` would break the suite. If the fix adds stricter validation, it must do so *inside* `parse_csv` / the per-row block, not via the global shell options.
- **Data-only fix is the wrong default.** Just fixing the CSV makes the suite pass on the current data, but a future contributor who adds an unquoted prompt reintroduces the same silent failure. Parser hardening is what actually closes the bug class; data fix alone is a one-shot.
- **User-intent ambiguity on row 5.** The user reported "the fibonacci test is passing when it should fail." Two readings:
  1. The user wanted the test to *assert something the orchestrator doesn't do* (e.g. expected 0 tool calls; the row should have been `...,0,0,0`). The current row happens to pass because `10` is what the orchestrator emits.
  2. The user wanted the *literal prompt* `Create a simple python script for fibonacci,10,0,0` (some custom syntax) and the parser swallowing the suffix is the bug.
  Picking the wrong reading produces a fix that the user immediately re-opens. **Follow-up must clarify intent before implementation.**
- **Tool-count is non-deterministic.** The orchestrator's tool count depends on the model, repo state, and prompt phrasing. Asserting on an *exact* count (currently the contract) is brittle — `10` is a magic number that will drift. The fix should at least surface this fragility in the per-row log; the long-term fix is a tolerance window, but that's a design call, not a bug fix.
- **No CI gate on the prompt suite.** The `docker-test.sh` runner is manual. The proposed `parse_csv.test.sh` regression lives on disk but won't run on PRs unless CI is updated. Flag in the PR description; do not silently assume.
