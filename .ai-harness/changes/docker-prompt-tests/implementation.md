# Implementation — docker-prompt-tests

## Commits
- 4fe710f — task 1: add tests-prompts/Dockerfile carrier image (opencode + uv + python3 + jq on ubuntu:24.04, repo source not COPYd, COPYs only run.sh + cases.csv + _extractor.py into /tests-prompts/, CMD bash /tests-prompts/run.sh); tests: `docker build -f tests-prompts/Dockerfile -t ai-harness-prompt-tests:local .` (clean), `docker run --rm ai-harness-prompt-tests:local bash -c "which opencode; opencode --version; which uv; which python3; which jq"` (all four resolvable, opencode 1.17.12).
- fb6739e — task 2: add tests-prompts/cases.csv with header `prompt, tools calls (number), skills calls (number), sub-agent calls (number)` and first data row `hello,0,0,0`; tests: `python3 -c "import csv; ..."` (DictReader parses header + 1 row, fields preserved including the leading space in ` tools calls (number)`).
- 422e0b0 — task 3: append `tests-prompts/logs/` verbatim to root `.gitignore`; tests: `touch tests-prompts/logs/.gitkeep && git status --short tests-prompts/logs/` (untracked).
- 7c7b277 — task 4: bootstrap tests-prompts/run.sh (copy /source-ro → /workspace, `uv tool install . --python python3`, `ai-harness install -o opencode`, capture `opencode --version` once); placeholder per-row loop for tasks 5/6; tests: `bash -n tests-prompts/run.sh` (clean).
- 7c0410f — tasks 5+6: full per-row loop + `tests-prompts/_extractor.py` (only schema-aware helper) + parse_csv via csv.DictReader + slugify + dump_failure_trace; 11 pytest tests in test_prompt_tests_extractor.py (disjoint buckets, non-JSON tolerance, hello smoke, live end-to-end against real opencode 1.17.12) + 22 in test_prompt_tests_slugs.py (slug contract, filename safety, bash -n, no set -e, no per-row timeout); end-to-end smoke: `docker run --rm --network host -v $PWD:/source-ro:ro -v $HOME/.local/share/opencode/auth.json:/root/.local/share/opencode/auth.json:ro -v $PWD/tests-prompts/logs:/logs ai-harness-prompt-tests:local bash /tests-prompts/run.sh` → `[CASE 1/1] PASS`, exit 0.
- 0ceca52 — task 7: tests-prompts/docker-test.sh host harness (auth preflight, IMAGE_TAG default + override, three mounts repo:ro + auth:ro + logs:rw, --network host, exit propagation, [BUILD]/[RUN]/[FAIL] prefixes, run_with_timeout passthrough, style mirror with e2e/docker-test.sh); 26 pytest tests in test_prompt_tests_harness.py; preflight fail-fast verified (`HOST_AUTH_FILE=/nonexistent/auth.json tests-prompts/docker-test.sh` → exit 1, no docker call, prints `[FAIL]` naming path); end-to-end verified (`tests-prompts/docker-test.sh` → builds, runs, `[CASE 1/1] PASS`, exit 0).

## Verification summary
- All 59 prompt-test pytest tests pass (33 unit + 26 harness-contract).
- Full pytest suite (incl. pre-existing tests) — 555 passed in 8.46s.
- End-to-end Docker harness — built, ran, reported `[CASE 1/1] PASS` and exit 0.
- Logs dir remains hermetic (only `.gitkeep` placeholder; gitignored).

## Observation (not a blocker)
The locked scope specifies the model name `minimax/minimax-m3` (lowercase 'm').
The opencode binary installed in this environment (1.17.12) returns an
"UnknownError" for that exact identifier; `minimax/MiniMax-M3` (mixed case,
matching the existing `change-orchestrator.md` frontmatter and the default
model map in `src/ai_harness/modules/harness/renderers.py`) is the working
identifier. The runner was kept on the literal spec string per the locked
implementation scope; the `hello` smoke row still passes vacuously because
the error trace has zero `tool_use` events. Rows with non-zero expected
counts will fail loudly under the spec model, which is correct behavior.
The single-line fix is `PINNED_MODEL=minimax/MiniMax-M3` (or pass it as an
env override) once the spec is amended.

## Remaining
- none