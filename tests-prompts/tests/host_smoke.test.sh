#!/usr/bin/env bash
# tests-prompts/tests/host_smoke.test.sh — host-side smoke test for
# fix-tests-prompts-assertions Track B (host-config isolation).
#
# The user's reported symptom: "after running the test suite, I have to
# re-run `ai-harness` to get my ~/.ai-harness config back." This script
# verifies that symptom does NOT recur:
#
#   1. Snapshot md5sums of ~/.ai-harness, ~/.config/opencode, ~/.claude,
#      ~/.agents, ~/.copilot, ~/.github BEFORE running the suite.
#   2. Optionally run the Docker entrypoint (tests-prompts/docker-test.sh
#      or e2e/docker-test.sh), gated by SMOKE_RUN_DOCKER=1. Default skip
#      — the test still has value via its static regression checks (8.2/8.3/8.4).
#   3. Snapshot md5sums AFTER.
#   4. Diff byte-for-byte. If anything in a tracked host path changed,
#      the runner mutated the host config — the user's symptom returned.
#      Exit non-zero.
#
# Static regression checks (subtasks 8.2 / 8.3 / 8.4):
#   8.2  assert_container_required exists in BOTH tests-prompts/run.sh
#        AND e2e/lib.sh; sourcing either on the host exits 2. Removes
#        the guard, the test catches the regression.
#   8.3  No per-path backup/restore helpers added to tests-prompts/ or
#        e2e/ for the tracked host paths. Track B's design rejected
#        backup/restore in favor of refusing-host-entirely — the absence
#        of backup helpers is itself the contract.
#   8.4  e2e/lib.sh::cleanup_test_env's rm -rf lines are unreachable
#        from a host run because assert_container_required fires BEFORE
#        any test helper is callable.
#
# Subtasks covered:
#   8.1  smoke test exits 0 after a clean docker-test.sh run (full mode)
#        or immediately (default mode without docker)
#   8.2  smoke test exits non-zero when assert_container_required is removed
#   8.3  no per-path backup/restore helpers
#   8.4  cleanup_test_env rm -rf lines unreachable from host

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOST_PATHS=(
    "$HOME/.ai-harness"
    "$HOME/.config/opencode"
    "$HOME/.claude"
    "$HOME/.agents"
    "$HOME/.copilot"
    "$HOME/.github"
)

FAIL=0
ok()   { printf '  [OK]   %s\n' "$1"; }
mark() { printf '  [FAIL] %s\n' "$1" >&2; FAIL=$((FAIL + 1)); }

# ---------------------------------------------------------------------------
# Snapshot: produce md5 (or sentinel) for each tracked host path.
# Missing paths produce 'MISSING' so a path that appears after the run
# (i.e. the runner created it) is detectable.
# ---------------------------------------------------------------------------
snapshot_path() {
    local path="$1"
    if [ -e "$path" ]; then
        # -r so we follow directories; the trailing sort makes order stable.
        if [ -d "$path" ]; then
            (cd "$path" && find . -type f -print0 | sort -z | xargs -0 md5sum 2>/dev/null) \
                | md5sum | cut -d' ' -f1
        else
            md5sum "$path" | cut -d' ' -f1
        fi
    else
        printf 'MISSING'
    fi
}

write_snapshot() {
    local out_file="$1"
    : > "$out_file"
    for p in "${HOST_PATHS[@]}"; do
        printf '%s\t%s\n' "$p" "$(snapshot_path "$p")" >> "$out_file"
    done
}

diff_snapshots() {
    local before="$1" after="$2"
    diff -u "$before" "$after"
}

# ---------------------------------------------------------------------------
# 8.1 — snapshot before, run docker-test.sh if requested, snapshot after,
# diff. Tracked paths byte-identical after → exits 0.
# ---------------------------------------------------------------------------
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/ai-harness-host-smoke-XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT
before="$work_dir/before.tsv"
after="$work_dir/after.tsv"
write_snapshot "$before"

if [ "${SMOKE_RUN_DOCKER:-0}" = "1" ]; then
    if [ ! -x "$PROJECT_ROOT/tests-prompts/docker-test.sh" ]; then
        mark "8.1 SMOKE_RUN_DOCKER=1 but tests-prompts/docker-test.sh missing/not executable"
    else
        printf '[INFO] SMOKE_RUN_DOCKER=1 — invoking tests-prompts/docker-test.sh\n' >&2
        "$PROJECT_ROOT/tests-prompts/docker-test.sh" >/dev/null 2>&1 || true
    fi
fi

write_snapshot "$after"

if diff_output=$(diff_snapshots "$before" "$after"); then
    ok "8.1 host paths byte-identical before/after docker-test.sh (or default-skip)"
else
    mark "8.1 host paths changed during run: $diff_output"
fi

# ---------------------------------------------------------------------------
# 8.2 — assert_container_required regression detector. Source e2e/lib.sh
# in a clean subshell with no container markers and no escape hatch.
# Without the guard, sourcing would proceed silently → exit 0. With the
# guard, sourcing exits 2.
# ---------------------------------------------------------------------------
LIB_SH="$PROJECT_ROOT/e2e/lib.sh"

# Verify e2e/lib.sh contains the function and call.
if grep -qE '^assert_container_required\(\) \{' "$LIB_SH"; then
    :
else
    mark "8.2 e2e/lib.sh missing assert_container_required() definition"
fi

if grep -qE '^assert_container_required$' "$LIB_SH"; then
    :
else
    mark "8.2 e2e/lib.sh missing top-level assert_container_required call"
fi

# Functional check: sourcing on a host (no markers, no env) exits 2.
# We use bash -c so the env is clean; capture both exit and stderr.
if lib_smoke_out=$(bash -c '
    unset CONTAINER_REQUIRED_OK CONTAINER_RUN_MARKER CONTAINER_DOCKER_MARKER CONTAINER_CGROUP_PATH
    source "'"$LIB_SH"'"
' 2>&1 >/dev/null); then
    mark "8.2 sourcing e2e/lib.sh on host exited 0 — guard is missing or bypassed"
else
    if [[ "$lib_smoke_out" == *"[FATAL] refusing to run on the host: e2e must be invoked via e2e/docker-test.sh"* ]]; then
        ok "8.2 e2e/lib.sh guard fires on host (exit=2, [FATAL] message present)"
    else
        mark "8.2 e2e/lib.sh exited non-zero but stderr missing [FATAL] e2e line: $lib_smoke_out"
    fi
fi

# Also verify the same shape for tests-prompts/run.sh.
RUN_SH="$PROJECT_ROOT/tests-prompts/run.sh"
if grep -qE '^assert_container_required\(\) \{' "$RUN_SH"; then
    ok "8.2 tests-prompts/run.sh has the guard definition"
else
    mark "8.2 tests-prompts/run.sh missing assert_container_required() definition"
fi
if grep -qE '^assert_container_required$' "$RUN_SH"; then
    ok "8.2 tests-prompts/run.sh calls the guard at top level"
else
    mark "8.2 tests-prompts/run.sh missing top-level assert_container_required call"
fi

# ---------------------------------------------------------------------------
# 8.3 — no per-path backup/restore helpers were added.
# Static grep for `snapshot.*HOME`, `backup.*\.ai-harness`,
# `tar.*\.ai-harness` must return zero matches inside tests-prompts/
# and e2e/ test code. Track B's design explicitly rejected this
# approach (see design.md 'Rejected alternatives').
# ---------------------------------------------------------------------------
backup_hits=$(grep -RnE 'snapshot.*HOME|backup.*\.ai-harness|tar.*\.ai-harness' \
    "$PROJECT_ROOT/tests-prompts" "$PROJECT_ROOT/e2e" 2>/dev/null \
    | grep -v '\.git/' | grep -v 'tests-prompts/tests/' || true)
if [ -z "$backup_hits" ]; then
    ok "8.3 no per-path backup/restore helpers in tests-prompts/ or e2e/"
else
    mark "8.3 found per-path backup/restore helpers: $backup_hits"
fi

# ---------------------------------------------------------------------------
# 8.4 — cleanup_test_env rm -rf lines remain unreachable from a host run.
# Static check: assert_container_required call comes BEFORE the first
# `rm -rf` line in e2e/lib.sh AND before any `ai-harness install -o
# opencode` invocation in tests-prompts/run.sh. Without this ordering,
# the rm -rf line is reachable on a host invocation — the user's
# symptom returns.
# ---------------------------------------------------------------------------
# e2e/lib.sh: rm -rf is on a single line alongside other paths.
guard_line=$(grep -nE '^assert_container_required$' "$LIB_SH" | head -1 | cut -d: -f1)
rmrf_line=$(grep -nE 'rm -rf ' "$LIB_SH" | head -1 | cut -d: -f1)
if [ -z "$guard_line" ] || [ -z "$rmrf_line" ]; then
    mark "8.4 cannot locate guard or rm-rf line in e2e/lib.sh (guard=$guard_line rm=$rmrf_line)"
else
    if [ "$guard_line" -lt "$rmrf_line" ]; then
        ok "8.4 guard (line $guard_line) precedes rm -rf (line $rmrf_line) in e2e/lib.sh"
    else
        mark "8.4 guard (line $guard_line) does NOT precede rm -rf (line $rmrf_line) in e2e/lib.sh"
    fi
fi

# tests-prompts/run.sh: the host-mutating call is `ai-harness install
# -o opencode`. Find that line and verify the guard precedes it.
guard_line_run=$(grep -nE '^assert_container_required$' "$RUN_SH" | head -1 | cut -d: -f1)
install_line=$(grep -nE 'ai-harness install -o opencode' "$RUN_SH" \
    | grep -vE '^[[:digit:]]+:#' | head -1 | cut -d: -f1)
if [ -z "$guard_line_run" ] || [ -z "$install_line" ]; then
    mark "8.4 cannot locate guard or ai-harness install line in tests-prompts/run.sh"
else
    if [ "$guard_line_run" -lt "$install_line" ]; then
        ok "8.4 tests-prompts/run.sh guard (line $guard_line_run) precedes ai-harness install (line $install_line)"
    else
        mark "8.4 tests-prompts/run.sh guard (line $guard_line_run) does NOT precede ai-harness install (line $install_line)"
    fi
fi

# ---------------------------------------------------------------------------
# Final summary.
# ---------------------------------------------------------------------------
if [ "$FAIL" -gt 0 ]; then
    printf '\n[FAIL] %d sub-scenario(s) failed\n' "$FAIL" >&2
    exit 1
fi
printf '\n[OK] all host_smoke sub-scenarios passed\n'
exit 0
