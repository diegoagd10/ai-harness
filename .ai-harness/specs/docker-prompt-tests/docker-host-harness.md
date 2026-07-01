# Spec — docker-host-harness

## Purpose

The host-side entrypoint `./tests-prompts/docker-test.sh` that a developer runs
from the repo root to execute the prompt-test suite. It owns the host-visible
contract: preflight (host auth must exist), image build (tag overridable via
`IMAGE_TAG`), mount composition (repo read-only, auth read-only, logs writable),
and the single `docker run --network host` invocation. Mirrors the
`e2e/docker-test.sh` style so the two harnesses feel like siblings.

## Requirements

### Requirement: auth-preflight
The system MUST fail before any `docker` call when the host opencode auth file
is missing at `/home/diegoagd10/.local/share/opencode/auth.json`, and the
failure message MUST name that exact path.

#### Scenario: auth missing — fail fast before docker
GIVEN the file `/home/diegoagd10/.local/share/opencode/auth.json` does not exist on the host
WHEN the user runs `./tests-prompts/docker-test.sh`
THEN the script exits non-zero, prints a message naming `/home/diegoagd10/.local/share/opencode/auth.json`, and does NOT invoke `docker build` or `docker run`.

#### Scenario: auth present — preflight passes
GIVEN the file `/home/diegoagd10/.local/share/opencode/auth.json` exists on the host
WHEN the user runs `./tests-prompts/docker-test.sh`
THEN the preflight passes, image build proceeds, and the script does NOT exit at the preflight step.

### Requirement: image-build
The system MUST build the image using `tests-prompts/Dockerfile` with the build
context at the repo root, and MUST tag the image `ai-harness-prompt-tests:local`
by default. The `IMAGE_TAG` environment variable, when set, MUST override the
default tag.

#### Scenario: default tag
GIVEN `IMAGE_TAG` is unset
WHEN the host harness builds the image
THEN `docker build` is invoked with tag `ai-harness-prompt-tests:local`.

#### Scenario: tag override
GIVEN `IMAGE_TAG=my-prompt-tests:dev`
WHEN the host harness builds the image
THEN `docker build` is invoked with tag `my-prompt-tests:dev` and the subsequent `docker run` references that same tag.

### Requirement: mount-composition
The system MUST launch the container with three mounts: the repo root at
`/source-ro:ro`, the host auth file at
`/root/.local/share/opencode/auth.json:ro` inside the container, and the local
`tests-prompts/logs/` directory at `/logs` (writable). The repo MUST be mounted
read-only so any container-initiated writes to repo files are blocked at the
filesystem level.

#### Scenario: all three mounts present
GIVEN the host harness is about to run the container
WHEN it invokes `docker run`
THEN the command line contains `-v <repo>:/source-ro:ro`, `-v /home/diegoagd10/.local/share/opencode/auth.json:/root/.local/share/opencode/auth.json:ro`, and `-v <tests-prompts>/logs:/logs`.

#### Scenario: repo mount is read-only
GIVEN the container is running
WHEN a process inside the container attempts to write a file under `/source-ro`
THEN the write fails with a read-only filesystem error.

### Requirement: network-host
The system MUST launch the container with `--network host` so that `uv tool
install .` can resolve PyPI dependencies and so that the model API call to
`minimax/minimax-m3` succeeds.

#### Scenario: network host enabled
GIVEN the host harness is launching the container
WHEN it invokes `docker run`
THEN the command line includes `--network host`.

### Requirement: aggregate-exit-code
The system MUST exit `0` only when the container-runner reports every CSV row
passed, and MUST exit non-zero when any row failed. The host harness MUST
propagate the container's exit code without masking it.

#### Scenario: all rows pass
GIVEN every CSV row passed inside the container
WHEN the container exits
THEN the host harness exits `0`.

#### Scenario: any row failed
GIVEN at least one CSV row failed inside the container
WHEN the container exits non-zero
THEN the host harness exits non-zero and the non-zero exit is preserved (no `|| true` masking).

### Requirement: fail-headline
On any per-row failure, the host harness MUST print a `[FAIL]` line that names
the failing row and the failing assertion before exiting.

#### Scenario: fail line is printed
GIVEN a row inside the container failed its count assertion
WHEN the host harness prints final output
THEN a `[FAIL]` line appears that names the row index (or row identifier) and the specific assertion (e.g. `tools calls expected 0 got 3`).

### Requirement: style-mirror-e2e
The host harness MUST mirror `e2e/docker-test.sh` in structural style so the
two harnesses read as siblings: it MUST define `SCRIPT_DIR` and `PROJECT_ROOT`,
support an `IMAGE_TAG` override, use `ENV_FLAGS`, use a `run_with_timeout`-style
helper or equivalent, and emit `[BUILD]` / `[RUN]` / `[FAIL]` line prefixes
compatible with log scrapers that already parse `e2e/docker-test.sh`.

#### Scenario: shared structural identifiers exist
GIVEN the host harness source
WHEN a reader greps for `SCRIPT_DIR`, `PROJECT_ROOT`, `IMAGE_TAG`, `ENV_FLAGS`, `run_with_timeout`
THEN each identifier is defined and used in the script (not just declared).