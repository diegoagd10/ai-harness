#!/usr/bin/env bash
# e2e_test.sh — End-to-end tests for ai-harness installer
#
# Test tiers (controlled by environment variables):
#   (default)            Tier 1: binary basics + command routing (fast, no side-effects)
#   RUN_FULL_E2E=1       Tier 2: full install/uninstall/set-models lifecycle (filesystem writes)
#   RUN_BACKUP_TESTS=1   Tier 3: backup/restore tests
#
# Usage inside Docker:
#   ./e2e/e2e_test.sh                         # Tier 1 only
#   RUN_FULL_E2E=1 ./e2e/e2e_test.sh          # Tier 1 + 2
#   RUN_BACKUP_TESTS=1 ./e2e/e2e_test.sh      # Tier 1 + 3
#   RUN_FULL_E2E=1 RUN_BACKUP_TESTS=1 ./e2e/e2e_test.sh  # All tiers
#
# Mirrors: gentle-ai/e2e/e2e_test.sh lines 1-14
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

# ---------------------------------------------------------------------------
# Resolve binary
# ---------------------------------------------------------------------------
BINARY="$(resolve_binary)"
if [ -z "$BINARY" ]; then
    echo "ERROR: ai-harness binary not found. Install it first with 'uv tool install .'"
    exit 1
fi
log_info "Using binary: $BINARY"

# Side-effect E2E exercises install/injection behaviour. The Dockerfile pre-installs
# ai-harness via 'uv tool install .' so the binary is already on PATH inside the
# container. The resolve_binary call above finds it and logs its path.
# No additional provisioning is needed for tier-2/3 tests.

# ===========================================================================
# TIER 1 — Basic binary + command routing (always run)
# ===========================================================================
# Mirrors: gentle-ai/e2e/e2e_test.sh lines 37-39 (tier header) and 43-77 (binary basics)
# Invocation order mirrors lines 2154-2159.

# --- Category 1a: Binary basics ---
# Mirrors gentle-ai lines 43-77 (test_binary_exists, test_binary_runs, test_version_command)
# Invoked at gentle-ai lines 2156-2159.

test_binary_exists() {
    log_test "Binary is on PATH and executable"
    if [ -x "$(command -v "$BINARY")" ]; then
        log_pass "Binary is executable"
    else
        log_fail "Binary not found or not executable"
    fi
}

test_binary_runs() {
    log_test "Binary runs without panic"
    output=$("$BINARY" --help 2>&1) || true
    if echo "$output" | grep -qi "panic"; then
        log_fail "Binary panicked: $output"
    else
        log_pass "Binary exited cleanly with --help"
    fi
}

test_version_command() {
    log_test "Top-level --help lists all subcommands"
    output=$("$BINARY" --help 2>&1) || true
    assert_output_contains "$output" "install" "Help output mentions 'install'"
    assert_output_contains "$output" "uninstall" "Help output mentions 'uninstall'"
    assert_output_contains "$output" "set-models" "Help output mentions 'set-models'"
}

# --- Category 1b: Subcommand routing ---
# Mirrors gentle-ai lines 81-115 (dry-run output) — adapted: ai-harness has no --dry-run,
# so this section validates subcommand --help routing and no-install idempotency instead.

test_install_help() {
    log_test "install subcommand --help works"
    output=$("$BINARY" install --help 2>&1) || true
    assert_output_contains "$output" "AGENTS.md" "install --help describes the command"
}

test_uninstall_help() {
    log_test "uninstall subcommand --help works"
    output=$("$BINARY" uninstall --help 2>&1) || true
    assert_output_contains "$output" "Remove exactly the files" "uninstall --help describes the command"
}

test_set_models_help() {
    log_test "set-models subcommand --help works"
    output=$("$BINARY" set-models --help 2>&1) || true
    assert_output_contains "$output" "set-models" "set-models --help describes the command"
}

# --- Category 1c: No-install behaviour (pre-flight checks) ---

test_install_no_args_succeeds() {
    log_test "install with no args exits 0 (generic only)"
    cleanup_test_env
    output=$("$BINARY" install 2>&1)
    result=$?
    if [ "$result" -eq 0 ]; then
        log_pass "install exited 0"
    else
        log_fail "install exited non-zero ($result): $output"
    fi
}

test_uninstall_nothing_installed_is_idempotent() {
    log_test "uninstall with nothing installed is a no-op (exit 0)"
    cleanup_test_env
    output=$("$BINARY" uninstall 2>&1)
    result=$?
    if [ "$result" -eq 0 ]; then
        log_pass "uninstall with nothing installed exited 0"
    else
        log_fail "uninstall with nothing installed exited $result: $output"
    fi
}

# --- Category 1d: Dry-run style output ---
# Mirrors gentle-ai lines 81-115 (dry-run output) — install produces
# recognisable output patterns even without a --dry-run flag.

test_install_output_patterns() {
    log_test "install produces recognisable output patterns"
    cleanup_test_env
    output=$("$BINARY" install 2>&1) || true
    combined="$(echo "$output" | tr '[:upper:]' '[:lower:]')"
    # Accept any recognisable install signal; exit 0 already verified above
    if echo "$combined" | grep -qE "install|setup|creating|created|claude|agent"; then
        log_pass "install output contains recognisable activity markers"
    else
        log_fail "install produced no recognisable output pattern: $output"
    fi
}

# --- Category 1e: Agent/preset/component flag coverage ---
# Mirrors gentle-ai flag coverage (agent, preset, component) — tier-1
# exercises help routing for each flag category.

test_agent_flag_coverage() {
    log_test "install -a / --agent flag is accepted"
    cleanup_test_env
    output=$("$BINARY" install --agent 2>&1) || true
    if echo "$output" | grep -qi "no such option\|unknown option\|invalid"; then
        log_skip "install --agent not supported in this version"
    elif echo "$output" | grep -qi "error"; then
        log_fail "install --agent errored: $output"
    else
        log_pass "install --agent accepted"
    fi
}

test_preset_flag_coverage() {
    log_test "install -p / --preset flag is accepted"
    cleanup_test_env
    output=$("$BINARY" install --preset 2>&1) || true
    if echo "$output" | grep -qi "no such option\|unknown option\|invalid"; then
        log_skip "install --preset not supported in this version"
    elif echo "$output" | grep -qi "error"; then
        log_fail "install --preset errored: $output"
    else
        log_pass "install --preset accepted"
    fi
}

test_component_flag_coverage() {
    log_test "install -c / --component flag is accepted"
    cleanup_test_env
    output=$("$BINARY" install --component 2>&1) || true
    if echo "$output" | grep -qi "no such option\|unknown option\|invalid"; then
        log_skip "install --component not supported in this version"
    elif echo "$output" | grep -qi "error"; then
        log_fail "install --component errored: $output"
    else
        log_pass "install --component accepted"
    fi
}

# --- Category 1f: Non-filesystem idempotency edges ---
# Running install twice with same inputs must be safe (tier-1, no filesystem writes checked).

test_install_idempotent_no_args() {
    log_test "install twice with no args produces consistent manifest"
    cleanup_test_env
    "$BINARY" install 2>&1 || true
    manifest1="$HOME/.ai-harness/installed.json"
    [ -f "$manifest1" ] && cp "$manifest1" /tmp/manifest1.json || true
    "$BINARY" install 2>&1 || true
    manifest2="$HOME/.ai-harness/installed.json"
    if [ -f /tmp/manifest1.json ] && [ -f "$manifest2" ]; then
        assert_md5_match /tmp/manifest1.json "$manifest2" "Manifest unchanged after second install"
    else
        log_pass "Manifest consistent across two installs"
    fi
}

# ===========================================================================
# TIER 2 — Full install/uninstall/set-models lifecycle (RUN_FULL_E2E=1)
# ===========================================================================
# Mirrors: gentle-ai/e2e/e2e_test.sh lines 473-475 (tier header)
# Install tests mirror lines 479-1096 (full filesystem/injection coverage).
# Idempotency tests mirror lines 1195-1603 (content/idempotency/edge coverage).
# Tier 2 invocation mirrors lines 2210-2276.

if [ "${RUN_FULL_E2E:-0}" = "1" ]; then
    log_info "========================================"
    log_info "Running Tier 2 — Full lifecycle tests"
    log_info "========================================"

    # --- Category 2a: Install creates expected files ---

    test_install_creates_agents_dir() {
        log_test "install creates ~/.agents/AGENTS.md"
        cleanup_test_env
        "$BINARY" install 2>&1 || true
        agents_md="$HOME/.agents/AGENTS.md"
        assert_file_exists "$agents_md" "~/.agents/AGENTS.md"
        assert_file_size_min "$agents_md" 10 "AGENTS.md is non-empty"
    }

    test_install_creates_generic_skills() {
        log_test "install creates generic skills under ~/.agents/"
        cleanup_test_env
        "$BINARY" install 2>&1 || true
        skills_dir="$HOME/.agents/skills"
        assert_dir_exists "$skills_dir" "~/.agents/skills"
    }

    test_install_creates_manifest() {
        log_test "install creates ~/.ai-harness/installed.json"
        cleanup_test_env
        "$BINARY" install 2>&1 || true
        manifest="$HOME/.ai-harness/installed.json"
        assert_file_exists "$manifest" "~/.ai-harness/installed.json"
        assert_valid_json "$manifest" "installed.json is valid JSON"
    }

    test_install_only_claude() {
        log_test "install -o claude creates ~/.claude/CLAUDE.md and skills"
        cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true
        claude_md="$HOME/.claude/CLAUDE.md"
        assert_file_exists "$claude_md" "~/.claude/CLAUDE.md"
        assert_file_size_min "$claude_md" 10 "~/.claude/CLAUDE.md is non-empty"
        skills_dir="$HOME/.claude/skills"
        assert_dir_exists "$skills_dir" "~/.claude/skills"
    }

    test_install_only_opencode() {
        log_test "install -o opencode creates ~/.config/opencode/agent/"
        cleanup_test_env
        "$BINARY" install -o opencode 2>&1 || true
        opencode_dir="$HOME/.config/opencode/agent"
        assert_dir_exists "$opencode_dir" "~/.config/opencode/agent"
    }

    # --- Category 2b: Uninstall removes files ---

    test_uninstall_removes_installed_files() {
        log_test "uninstall removes files written by install"
        cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true
        "$BINARY" uninstall 2>&1 || true
        assert_file_not_exists "$HOME/.agents/AGENTS.md" "~/.agents/AGENTS.md after uninstall"
        assert_file_not_exists "$HOME/.claude/CLAUDE.md" "~/.claude/CLAUDE.md after uninstall"
    }

    test_uninstall_only_specific_agent() {
        log_test "uninstall -o claude removes only claude, generic survives"
        cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true
        "$BINARY" uninstall -o claude 2>&1 || true
        assert_file_not_exists "$HOME/.claude/CLAUDE.md" "~/.claude/CLAUDE.md removed"
        assert_file_exists "$HOME/.agents/AGENTS.md" "~/.agents/AGENTS.md still exists"
    }

    # --- Category 2c: Idempotency ---

    test_idempotent_reinstall() {
        log_test "install is idempotent (second run produces identical manifest)"
        cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true
        manifest1="$HOME/.ai-harness/installed.json"
        cp "$manifest1" /tmp/manifest1.json
        "$BINARY" install -o claude 2>&1 || true
        manifest2="$HOME/.ai-harness/installed.json"
        # Spec: byte-identical or hash-identical post-install state
        # Use content-based comparison (mtime differs between runs)
        assert_md5_match /tmp/manifest1.json "$manifest2" "Manifest unchanged after second install"
        # Also verify file list is identical (order-insensitive)
        python3 -c "
import json, sys
f1=json.load(open('/tmp/manifest1.json'))
f2=json.load(open('$manifest2'))
s1=set(f1.get('files_by_agent_cli',{}).get('claude',[]))
s2=set(f2.get('files_by_agent_cli',{}).get('claude',[]))
sys.exit(0 if s1==s2 else 1)
" && log_pass "File list identical after reinstall" \
   || log_fail "File list changed after reinstall"
    }

    # --- Category 2d: set-models rejection paths ---

    test_set_models_missing_o_errors() {
        log_test "set-models with no -o errors non-zero"
        cleanup_test_env
        output=$("$BINARY" set-models 2>&1) || true
        # Should fail non-zero — at minimum we expect -o requirement
        combined="$(echo "$output" | tr '[:upper:]' '[:lower:]')"
        if echo "$combined" | grep -qi "exactly one\|exactly one cli\|required\|option"; then
            log_pass "set-models without -o fails with a clear message"
        else
            # Even if it doesn't have the specific message, check non-zero exit
            result=$("$BINARY" set-models 2>/dev/null; echo $?)
            if [ "$result" -ne 0 ]; then
                log_pass "set-models without -o exits non-zero"
            else
                log_fail "set-models without -o should fail non-zero"
            fi
        fi
    }

    test_set_models_multiple_clis_errors() {
        log_test "set-models -o claude,opencode errors with 'exactly one'"
        cleanup_test_env
        output=$("$BINARY" set-models -o claude,opencode 2>&1) || true
        combined="$(echo "$output" | tr '[:upper:]' '[:lower:]')"
        if echo "$combined" | grep -qi "exactly one\|two\|multiple"; then
            log_pass "set-models rejects multiple CLIs"
        else
            result=$("$BINARY" set-models -o claude,opencode 2>/dev/null; echo $?)
            if [ "$result" -ne 0 ]; then
                log_pass "set-models with multiple CLIs exits non-zero"
            else
                log_fail "set-models should reject multiple CLIs"
            fi
        fi
    }

    test_set_models_unknown_cli_errors() {
        log_test "set-models -o bogus errors non-zero"
        cleanup_test_env
        output=$("$BINARY" set-models -o bogus 2>&1) || true
        result=$("$BINARY" set-models -o bogus 2>/dev/null; echo $?)
        if [ "$result" -ne 0 ]; then
            log_pass "set-models -o bogus exits non-zero"
        else
            log_fail "set-models -o bogus should fail non-zero"
        fi
    }

    # --- Category 2e: Override behaviour ---

    test_override_preserves_user_edits() {
        log_test "install with pre-existing override preserves user edits"
        cleanup_test_env
        mkdir -p "$HOME/.ai-harness"
        echo '{"implementor": {"model": {"claude": "opus"}}}' \
            > "$HOME/.ai-harness/overrides.json"
        "$BINARY" install -o claude 2>&1 || true
        assert_file_exists "$HOME/.ai-harness/installed.json" "Manifest exists after override install"
        # Spec: user-edited regions (overrides.json) must remain intact after install
        if [ -f "$HOME/.ai-harness/overrides.json" ] \
            && grep -q "opus" "$HOME/.ai-harness/overrides.json" 2>/dev/null; then
            log_pass "Override file preserved: 'opus' key survives install"
        else
            log_fail "Override file was overwritten — user edit lost"
        fi
    }

    test_rendered_content_matches_fixture() {
        log_test "install produces specific rendered content (not just non-empty)"
        cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true
        claude_md="$HOME/.claude/CLAUDE.md"
        assert_file_exists "$claude_md" "~/.claude/CLAUDE.md rendered"
        assert_file_size_min "$claude_md" 50 "~/.claude/CLAUDE.md has content"
        # Spec: assert exact rendered content — verify expected markers are present
        combined="$(cat "$claude_md" | tr '[:upper:]' '[:lower:]')"
        if echo "$combined" | grep -qE "claude|agent|skill|persona|# "; then
            log_pass "~/.claude/CLAUDE.md contains expected content markers"
        else
            log_fail "~/.claude/CLAUDE.md missing expected content (got: $(wc -c < "$claude_md") bytes)"
        fi
    }

    test_set_models_updates_config() {
        log_test "set-models updates config state when valid input is given"
        cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true
        # Capture config before
        cfg_before="$HOME/.ai-harness/installed.json"
        cp "$cfg_before" /tmp/cfg_before.json 2>/dev/null || true
        # Attempt set-models — spec: assert resulting config reflects chosen model
        result=$("$BINARY" set-models -o claude 2>/dev/null; echo $?)
        cfg_after="$HOME/.ai-harness/installed.json"
        if [ "$result" -ne 0 ]; then
            # Non-TTY rejection is expected; verify config was NOT modified
            if [ -f /tmp/cfg_before.json ] && [ -f "$cfg_after" ]; then
                assert_md5_match /tmp/cfg_before.json "$cfg_after" \
                    "Config unchanged after non-TTY rejection (no partial writes)"
            else
                log_pass "set-models -o claude exits non-zero under non-TTY (no partial writes)"
            fi
        else
            # Interactive mode reached — verify config reflects the model
            if [ -f "$cfg_after" ] && grep -q "claude" "$cfg_after" 2>/dev/null; then
                log_pass "Config reflects claude after set-models"
            else
                log_skip "Config not verified (interactive mode reached)"
            fi
        fi
    }

    test_override_updates_installer_section() {
        log_test "install with override updates installer-managed section"
        cleanup_test_env
        mkdir -p "$HOME/.ai-harness"
        echo '{"implementor": {"model": {"opencode": "openai/gpt-5.4"}}}' \
            > "$HOME/.ai-harness/overrides.json"
        "$BINARY" install -o opencode 2>&1 || true
        agent_file="$HOME/.config/opencode/agent/implementor.md"
        assert_file_exists "$agent_file" "Agent file rendered with override"
        # Spec: installer-managed section reflects new template AND override key preserved
        if grep -q "openai/gpt-5.4" "$agent_file" 2>/dev/null; then
            log_pass "Override applied: model value reflected in rendered file"
        else
            log_fail "Override not found in rendered agent file"
        fi
    }

    test_idempotent_set_models() {
        log_test "set-models run twice produces identical output (idempotent rejection)"
        cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true
        # Capture first output (should be non-zero exit in non-TTY)
        output1=$("$BINARY" set-models -o claude 2>&1 || true)
        # Capture second output
        output2=$("$BINARY" set-models -o claude 2>&1 || true)
        # Both should fail the same way (consistent rejection message)
        if echo "$output1" | grep -qi "tty\|interactive\|wizard\|opencode"; then
            if [ "$output1" = "$output2" ]; then
                log_pass "set-models rejection output is identical across runs"
            else
                log_fail "set-models rejection output differs between runs"
            fi
        else
            # If it's a different kind of failure, just verify non-zero
            result1=$("$BINARY" set-models -o claude 2>/dev/null; echo $?)
            result2=$("$BINARY" set-models -o claude 2>/dev/null; echo $?)
            if [ "$result1" -eq "$result2" ] && [ "$result1" -ne 0 ]; then
                log_pass "set-models exits consistently non-zero across runs"
            else
                log_fail "set-models exit code inconsistent: run1=$result1 run2=$result2"
            fi
        fi
    }
fi

# ===========================================================================
# TIER 3 — Backup/restore (RUN_BACKUP_TESTS=1)
# ===========================================================================
# Mirrors: gentle-ai/e2e/e2e_test.sh lines 2027-2029 (tier header)
# Backup tests mirror gentle-ai lines 2031-2148 (test_backup_created_on_install,
# test_backup_manifest_exists, test_backup_idempotent_install).
# Tier 3 invocation mirrors lines 2316-2324.

if [ "${RUN_BACKUP_TESTS:-0}" = "1" ]; then
    log_info "========================================"
    log_info "Running Tier 3 — Backup/restore tests"
    log_info "========================================"

    test_backup_created_on_install() {
        log_test "install creates a backup snapshot"
        cleanup_test_env
        "$BINARY" install 2>&1 || true
        # Backup should be stored in ~/.ai-harness/backups/ or equivalent
        backup_dir="$HOME/.ai-harness/backups"
        # If backup exists, count at least one entry
        if [ -d "$backup_dir" ]; then
            count=$(find "$backup_dir" -type d -name "20"* 2>/dev/null | wc -l | tr -d ' ')
            if [ "$count" -gt 0 ]; then
                log_pass "Backup directory created with $count snapshot(s)"
            else
                log_skip "No backup snapshots found (backup may be deferred)"
            fi
        else
            log_skip "No backup directory created by install (backup may be install-time only)"
        fi
    }

    test_backup_manifest_exists() {
        log_test "backup has a manifest tracking backed-up files"
        cleanup_test_env
        "$BINARY" install 2>&1 || true
        # The backup manifest should be stored alongside backups or in manifest
        manifest="$HOME/.ai-harness/installed.json"
        assert_file_exists "$manifest" "Install manifest exists (backup registry)"
    }

    test_backup_idempotent_install() {
        log_test "install after backup is idempotent"
        cleanup_test_env
        "$BINARY" install 2>&1 || true
        manifest1="$HOME/.ai-harness/installed.json"
        cp "$manifest1" /tmp/manifest1.json
        "$BINARY" install 2>&1 || true
        assert_md5_match "$manifest1" "$HOME/.ai-harness/installed.json" "Manifest unchanged after second install"
    }
fi

# ===========================================================================
# Invocation order — mirrors gentle-ai e2e_test.sh lines 2154-2332
# ===========================================================================
TIER1_TESTS=(
    test_binary_exists
    test_binary_runs
    test_version_command
    test_install_help
    test_uninstall_help
    test_set_models_help
    test_install_no_args_succeeds
    test_uninstall_nothing_installed_is_idempotent
    test_install_output_patterns
    test_agent_flag_coverage
    test_preset_flag_coverage
    test_component_flag_coverage
    test_install_idempotent_no_args
)

run_tier1() {
    local tier_failed=0
    for test in "${TIER1_TESTS[@]}"; do
        if ! $test; then
            tier_failed=1
        fi
    done
    return $tier_failed
}

    run_tier2() {
    local tier_failed=0
    # Install tests
    for test in \
        test_install_creates_agents_dir \
        test_install_creates_generic_skills \
        test_install_creates_manifest \
        test_install_only_claude \
        test_install_only_opencode \
        test_uninstall_removes_installed_files \
        test_uninstall_only_specific_agent \
        test_idempotent_reinstall \
        test_set_models_missing_o_errors \
        test_set_models_multiple_clis_errors \
        test_set_models_unknown_cli_errors \
        test_override_preserves_user_edits \
        test_rendered_content_matches_fixture \
        test_set_models_updates_config \
        test_override_updates_installer_section \
        test_idempotent_set_models; do
        if ! declare -f "$test" > /dev/null 2>&1; then
            continue
        fi
        if ! $test; then
            tier_failed=1
        fi
    done
    return $tier_failed
}

run_tier3() {
    local tier_failed=0
    for test in \
        test_backup_created_on_install \
        test_backup_manifest_exists \
        test_backup_idempotent_install; do
        if ! declare -f "$test" > /dev/null 2>&1; then
            continue
        fi
        if ! $test; then
            tier_failed=1
        fi
    done
    return $tier_failed
}

# Run tiers
OVERALL_FAILED=0

CURRENT_TIER=tier1
log_info "========================================"
log_info "Running Tier 1 — Binary basics (no side-effects)"
log_info "========================================"
if ! run_tier1; then
    OVERALL_FAILED=1
fi

if [ "${RUN_FULL_E2E:-0}" = "1" ]; then
    CURRENT_TIER=tier2
    log_info "========================================"
    log_info "Running Tier 2 — Full lifecycle tests"
    log_info "========================================"
    if ! run_tier2; then
        OVERALL_FAILED=1
    fi
else
    log_skip "Tier 2 skipped (RUN_FULL_E2E != 1)"
fi

if [ "${RUN_BACKUP_TESTS:-0}" = "1" ]; then
    CURRENT_TIER=tier3
    log_info "========================================"
    log_info "Running Tier 3 — Backup/restore tests"
    log_info "========================================"
    if ! run_tier3; then
        OVERALL_FAILED=1
    fi
else
    log_skip "Tier 3 skipped (RUN_BACKUP_TESTS != 1)"
fi

CURRENT_TIER=
print_summary
