# Exploration — docker-prompt-tests

## Budget
300

## Affected Files
- `tests-prompts/docker-test.sh` (NEW) — host-side orchestrator: auth preflight, image build, mount/copy, container run. Mirrors `e2e/docker-test.sh` structural style (colors, `SCRIPT_DIR`/`PROJECT_ROOT`, `run_with_timeout`, `IMAGE_TAG`, `ENV_FLAGS`, `--network host`).
- `tests-prompts/Dockerfile` (NEW) — installs `opencode` (fresh) + `uv` + `bash` + `python3` + `jq`. Does NOT pre-install ai-harness (source is mounted at runtime so writes die with the container).
- `tests-prompts/run.sh` (NEW, in-container) — parses `cases.csv` with the Python `csv` stdlib, runs one fresh `opencode run` per row against the real `change-orchestrator` agent, parses the JSON trace, counts `skill`/`task`/other tool calls, asserts, and dumps the trace to `/logs/` on failure.
- `tests-prompts/cases.csv` (NEW) — header `prompt,tools calls (number),skills calls (number),sub-agent calls (number)` plus the smoke row `hello,0,0,0` and a handful of follow-up rows.
- `.gitignore` (MODIFY, +1 line) — append `tests-prompts/logs/`.

## Plan
1. Scaffold `tests-prompts/` directory with `Dockerfile`, `run.sh`, `cases.csv`, `docker-test.sh`. Match `e2e/docker-test.sh` colour + run_with_timeout + build/run layout so the two feel like siblings.
2. **Host preflight** in `tests-prompts/docker-test.sh`: `if [ ! -f /home/diegoagd10/.local/share/opencode/auth.json ]; then exit 1 fi`. Fail with a clear message before any docker call.
3. **Dockerfile**:
   - Base `ubuntu:24.04`, `bash curl jq python3 python3-venv ca-certificates`, install `uv` from astral, install `opencode` from the canonical installer (`curl -fsSL https://opencode.ai/install | bash`), set `PATH` to include `/root/.local/bin` and the opencode install dir.
   - No `COPY .` of project source, no build-time `uv tool install .`. Source arrives at runtime via mount+copy so "all repo writes die with the container".
4. **Container runtime contract** (executed by `CMD ["bash", "/tests-prompts/run.sh"]`):
   - Copy `/source-ro` (host mount, read-only) → `/workspace` (writable).
   - `cd /workspace && uv tool install . --python python3` so the real `ai-harness` CLI lands in `/root/.local/bin`.
   - `ai-harness install -o opencode` (non-interactive — already proven in `e2e/e2e_test.sh` Tier 2).
   - Mount host auth at `/root/.local/share/opencode/auth.json:ro` (opencode runs as root in the container).
   - `python3` parses `cases.csv` with `csv.DictReader`, loops rows, runs `opencode run --agent change-orchestrator --auto --format json --model minimax/minimax-m3 --dir /workspace "$prompt"` per row, parses the JSON-event stream, counts tool calls by name, compares to expected, and prints pass/fail summary.
5. **Host run block** mirrors `e2e/docker-test.sh`:
   - Build image tagged `ai-harness-prompt-tests:local` (override via `IMAGE_TAG`).
   - `mkdir -p tests-prompts/logs`.
   - `docker run --rm --network host` with:
     - `-v $PROJECT_ROOT:/source-ro:ro`
     - `-v /home/diegoagd10/.local/share/opencode/auth.json:/root/.local/share/opencode/auth.json:ro`
     - `-v $SCRIPT_DIR/logs:/logs` (host-visible dump of failed traces)
   - Exit code aggregated across rows: `0` if every row passed, `1` if any failed.
6. **Counts contract** (disjoint, exact):
   - `tools calls` = tool invocations whose tool name is NOT `skill` and NOT `task`.
   - `skills calls` = tool invocations with name `skill`.
   - `sub-agent calls` = tool invocations with name `task`.
7. **Gitignore**: append `tests-prompts/logs/`.

## Edge Cases
- Host auth missing — fail fast before docker, with the exact expected path in the error.
- Opencode JSON output is a stream of `type`-tagged events, not one document — implementer must parse line-delimited JSON (or accumulate into a JSON array) and locate the tool-use events. The exact event field for tool name (`name` vs `toolName` vs nested `tool.name`) must be probed on first run; exploration note for implementer: do one throwaway `opencode run --format json` and inspect a tool-using event.
- Prompt containing commas / newlines / quotes — Python `csv.DictReader` handles these natively. Do NOT split on commas.
- Empty expected counts (first row `hello,0,0,0`) — model may still emit non-tool events (text, thinking). Only count actual `tool`/`skill`/`task` invocations.
- Container starts as root and reads auth from `/root/.local/share/opencode/auth.json`. Host file UID mismatch is harmless because the mount is bind, not copy; mode `0600` is preserved and root can read it.
- `uv tool install .` needs network for dep resolution → `--network host` mandatory (mirrors e2e).
- `opencode` installer modifies `~/.local` paths inside the container; those die with the container, satisfying "writes die with the container" for repo files. opencode cache/state under `/root/.local/share/opencode/` is also ephemeral, which is the desired behaviour.
- Sub-issue: if opencode ever returns a non-JSON line on stderr that bleeds into stdout under `--format json`, the parser must tolerate malformed lines and still fail closed on count mismatch.
- Row index collisions on log filenames — sanitize prompt to filesystem-safe characters per row (first 32 chars of a slugified prompt + index).

## Test Surface
- `tests-prompts/docker-test.sh` IS the test harness; no separate unit tests.
- Static gates:
  - `bash -n tests-prompts/docker-test.sh` — syntax.
  - `bash -n tests-prompts/run.sh` — syntax (after inlining in Dockerfile).
  - `python3 -c "import csv; rows=list(csv.DictReader(open('tests-prompts/cases.csv'))); assert rows, rows[0]"` — CSV sanity.
- Smoke run: `./tests-prompts/docker-test.sh` with valid auth → expect build success, container run, per-row PASS/FAIL summary, exit `0` if all green.
- Failure path: temporarily mutate `cases.csv` to expect `tools calls=99` on the `hello` row → expect exit `1`, `[FAIL]` line naming the row + assertion, and a JSON trace written under `tests-prompts/logs/`.

## Risks
- **opencode CLI flags drift across versions.** The user's intent specifies `--auto`, `--format json`, `--model minimax/minimax-m3`. Host v1.17.12 supports all three plus `--agent` and `--dir`. Mitigate by pinning to a known-good install method (canonical installer, latest at build time) and asserting in `run.sh` that `opencode --version` was captured before the loop so any CLI-shape break fails loud, not silent.
- **opencode `--format json` event schema is undocumented.** Field names for tool calls can change. Mitigate by isolating the tool-name extraction to a single small helper in `run.sh` so any future rename is a one-line fix. Probe once with a smoke run before locking the counts.
- **`uv tool install .` requires the host repo to be a valid Python project.** Already true (`pyproject.toml` exists). Risk only if the worktree has uncommitted edits that break the install — `uv tool install .` should still succeed (build happens from disk, not from a registry).
- **`ai-harness install -o opencode` writes to `~/.config/opencode/agent/`.** These are session-local inside the container; nothing leaks to host.
- **Network access required at runtime.** Without `--network host` (or `docker network create`) the model call and PyPI dep resolution both fail. Mirrored from `e2e/docker-test.sh` so precedent is established.
- **Host path hard-coded (`/home/diegoagd10/.local/share/opencode/auth.json`).** Acceptable for v1 per shared understanding. Future-proofing via env var (`OPENCODE_AUTH_PATH`) is a follow-up; not in scope here.
- **CSV with very large prompts.** Per-row `opencode run` invocations can be slow (model latency). No per-row timeout is in scope per shared understanding; aggregate run can be slow but bounded by total row count.
- **`change-orchestrator` may itself call other tools** (e.g. read files, run bash) — those count as `tools calls`, which is the intended disjoint partitioning.