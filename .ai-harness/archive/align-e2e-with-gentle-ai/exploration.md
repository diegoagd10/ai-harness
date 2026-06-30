# Exploration — align-e2e-with-gentle-ai

## Budget
560 LOC

## Affected Files
- e2e/Dockerfile — current single-image Python sandbox may need replacement or narrowing.
- e2e/docker-test.sh — likely new top-level orchestrator, matching gentle-ai's build/run wrapper.
- e2e/*.py — current lifecycle tests/harness may need porting or decomposition.
- tasks.py, e2e/tasks.py — Invoke entrypoints may become thin wrappers or disappear.
- README.md, CODING_STANDARDS.md, CONTEXT.md — commands and test workflow docs.
- pyproject.toml — only if Invoke remains; otherwise task/dependency cleanup.

## Plan
- Decide target shape first: keep Python test bodies but adopt shell/Docker orchestration, or port suite to gentle-ai-style shell tiers.
- Add shared shell helpers + docker orchestrator pattern, then land one tracer-bullet lifecycle through it.
- Update docs and task entrypoints to point at the new e2e command surface.

## Edge Cases
- Distro variance: gentle-ai validates Ubuntu/Arch/Fedora; ai-harness may only need one image, but any matrix must keep command paths stable.
- Host contamination: current suite relies on sandboxed `uv tool install`; shell/Docker flow must preserve isolation and cleanup.
- Non-TTY behavior: `set-models` currently guards interactive wizards; new harness must keep rejection paths deterministic.
- Fixture drift: current Python tests assert exact rendered files and override semantics; a port must keep those paths and contents aligned.

## Test Surface
- New `./e2e/docker-test.sh` (or equivalent) as outer gate.
- Any new `e2e/e2e_test.sh` / `e2e/lib.sh` helpers if the suite moves to shell.
- Existing install/uninstall/set-models coverage, especially path assertions and idempotency.
- Docs/CI gates that advertise the canonical e2e command.

## Risks
- Full shell rewrite could balloon scope; mitigate with one vertical slice before broad porting.
- Multi-platform Docker matrix adds build-time and networking flakiness; keep initial slice to one known-good distro.
- Mixing current Python harness with new shell harness can create duplicate sources of truth; pick one command surface early.
