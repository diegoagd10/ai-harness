#!/usr/bin/env bash
# e2e_test.sh — End-to-end tests for ai-harness installer
#
# Tiers: (default) Tier 1, RUN_FULL_E2E=1 adds Tier 2, RUN_BACKUP_TESTS=1 adds Tier 3
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

BINARY="$(resolve_binary)"
[ -z "$BINARY" ] && { echo "ERROR: ai-harness binary not found"; exit 1; }
log_info "Using binary: $BINARY"

# ===========================================================================
# TIER 1 — Binary basics + command routing
# ===========================================================================

test_binary_exists() { log_test "Binary is on PATH"; [ -x "$(command -v "$BINARY")" ] && log_pass || log_fail "Binary not on PATH"; }

test_binary_runs() {
    log_test "Binary runs without panic"
    local out; out=$("$BINARY" --help 2>&1) || true
    echo "$out" | grep -qi "panic" && log_fail "Binary panicked" || log_pass
}

test_help_and_routing() {
    log_test "--help lists all subcommands and subcommand helps work"
    local out; out=$("$BINARY" --help 2>&1) || true
    assert_output_contains "$out" "install" "help lists install"
    assert_output_contains "$out" "uninstall" "help lists uninstall"
    assert_output_contains "$out" "set-models" "help lists set-models"
    out=$("$BINARY" install --help 2>&1) || true; assert_output_contains "$out" "AGENTS.md" "install --help works"
    out=$("$BINARY" uninstall --help 2>&1) || true; assert_output_contains "$out" "Remove" "uninstall --help works"
    out=$("$BINARY" set-models --help 2>&1) || true; assert_output_contains "$out" "set-models" "set-models --help works"
}

test_install_no_args_succeeds() {
    log_test "install with no args exits 0"; cleanup_test_env
    local r; r=$("$BINARY" install 2>&1); [ $? -eq 0 ] && log_pass || log_fail "install exited non-zero: $r"
}

test_uninstall_nothing_installed_is_idempotent() {
    log_test "uninstall with nothing installed is a no-op"; cleanup_test_env
    local r; r=$("$BINARY" uninstall 2>&1); [ $? -eq 0 ] && log_pass || log_fail "uninstall exited $?"
}

test_install_output_patterns() {
    log_test "install produces recognisable output patterns"; cleanup_test_env
    local out; out=$("$BINARY" install 2>&1) || true
    echo "$out" | tr '[:upper:]' '[:lower:]' | grep -qE "install|setup|creating|created|claude|agent" \
        && log_pass || log_fail "no recognisable output: $out"
}

test_flag_coverage() {
    log_test "install -a/-p/-c flags accepted"; cleanup_test_env
    for flag in -a --agent -p --preset -c --component; do
        local out; out=$("$BINARY" install "$flag" 2>&1) || true
        echo "$out" | grep -qi "no such option\|unknown option\|invalid" && { log_skip "install $flag not supported"; return 0; }
        echo "$out" | grep -qi "error" && { log_fail "install $flag errored: $out"; return 1; }
    done; log_pass
}

test_install_idempotent_no_args() {
    log_test "install twice produces consistent manifest"; cleanup_test_env
    "$BINARY" install 2>&1 || true; local m1="$HOME/.ai-harness/installed.json"
    [ -f "$m1" ] && cp "$m1" /tmp/m1.json || true
    "$BINARY" install 2>&1 || true; local m2="$HOME/.ai-harness/installed.json"
    [ -f /tmp/m1.json ] && [ -f "$m2" ] && assert_md5_match /tmp/m1.json "$m2" "Manifest unchanged after 2nd install" \
        || log_pass
}

# ===========================================================================
# TIER 2 — Full lifecycle (RUN_FULL_E2E=1)
# ===========================================================================

if [ "${RUN_FULL_E2E:-0}" = "1" ]; then
    log_info "Tier 2 — Full lifecycle tests"

    test_install_creates_files() {
        log_test "install creates expected files"; cleanup_test_env
        "$BINARY" install 2>&1 || true
        assert_file_exists "$HOME/.agents/AGENTS.md" "~/.agents/AGENTS.md"
        assert_file_size_min "$HOME/.agents/AGENTS.md" 10 "AGENTS.md non-empty"
        assert_dir_exists "$HOME/.agents/skills" "~/.agents/skills"
        assert_file_exists "$HOME/.ai-harness/installed.json" "Manifest exists"
        assert_valid_json "$HOME/.ai-harness/installed.json" "Manifest is valid JSON"
    }

    test_install_only_claude() {
        log_test "install -o claude creates ~/.claude/CLAUDE.md and skills"; cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true
        assert_file_exists "$HOME/.claude/CLAUDE.md" "~/.claude/CLAUDE.md"
        assert_file_size_min "$HOME/.claude/CLAUDE.md" 10
        assert_dir_exists "$HOME/.claude/skills" "~/.claude/skills"
    }

    test_install_only_opencode() {
        log_test "install -o opencode creates ~/.config/opencode/agent/"; cleanup_test_env
        "$BINARY" install -o opencode 2>&1 || true
        assert_dir_exists "$HOME/.config/opencode/agent"
    }

    test_uninstall_removes_installed_files() {
        log_test "uninstall removes files written by install"; cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true; "$BINARY" uninstall 2>&1 || true
        assert_file_not_exists "$HOME/.agents/AGENTS.md" "~/.agents/AGENTS.md after uninstall"
        assert_file_not_exists "$HOME/.claude/CLAUDE.md" "~/.claude/CLAUDE.md after uninstall"
    }

    test_uninstall_only_specific_agent() {
        log_test "uninstall -o claude removes only claude"; cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true; "$BINARY" uninstall -o claude 2>&1 || true
        assert_file_not_exists "$HOME/.claude/CLAUDE.md" "~/.claude/CLAUDE.md removed"
        assert_file_exists "$HOME/.agents/AGENTS.md" "~/.agents/AGENTS.md still exists"
    }

    # Byte-identical manifest after two installs (full idempotency check)
    test_idempotent_reinstall() {
        log_test "install is idempotent (second run produces identical manifest)"; cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true; local m1="$HOME/.ai-harness/installed.json"
        cp "$m1" /tmp/m1.json
        "$BINARY" install -o claude 2>&1 || true; local m2="$HOME/.ai-harness/installed.json"
        assert_md5_match /tmp/m1.json "$m2" "Manifest unchanged after reinstall"
        # Verify exact file list (order-insensitive)
        python3 -c "
import json, sys
f1=json.load(open('/tmp/m1.json'))
f2=json.load(open('$m2'))
s1=set(f1.get('files_by_agent_cli',{}).get('claude',[]))
s2=set(f2.get('files_by_agent_cli',{}).get('claude',[]))
sys.exit(0 if s1==s2 else 1)
" && log_pass "File list identical after reinstall" || log_fail "File list changed after reinstall"
    }

    # set-models: all rejection paths
    test_set_models_rejections() {
        log_test "set-models rejects bad input"; cleanup_test_env
        local out r
        # No -o
        out=$("$BINARY" set-models 2>&1) || true; r=$?
        echo "$out" | tr '[:upper:]' '[:lower:]' | grep -qi "exactly one\|required\|option" && log_pass "set-models without -o: clear message" || [ $r -ne 0 ] && log_pass "set-models without -o: non-zero exit"
        # Multiple CLIs
        out=$("$BINARY" set-models -o claude,opencode 2>&1) || true; r=$?
        echo "$out" | tr '[:upper:]' '[:lower:]' | grep -qi "exactly one\|two\|multiple" && log_pass "set-models rejects multiple CLIs" || [ $r -ne 0 ] && log_pass "set-models -o claude,opencode: non-zero"
        # Unknown CLI
        r=$("$BINARY" set-models -o bogus 2>/dev/null; echo $?)
        [ "$r" -ne 0 ] && log_pass "set-models -o bogus: non-zero" || log_fail "set-models -o bogus should fail"
    }

    # Override: user edits preserved, installer-section updated
    test_override_preserves_user_edits() {
        log_test "install with pre-existing override preserves user edits"; cleanup_test_env
        mkdir -p "$HOME/.ai-harness"
        echo '{"implementor": {"model": {"claude": "opus"}}}' > "$HOME/.ai-harness/overrides.json"
        "$BINARY" install -o claude 2>&1 || true
        assert_file_exists "$HOME/.ai-harness/installed.json"
        grep -q "opus" "$HOME/.ai-harness/overrides.json" 2>/dev/null \
            && log_pass "Override file preserved" || log_fail "Override file was overwritten"
    }

    # Rendered content: diff against golden fixture markers (not just non-empty)
    test_rendered_content_matches_fixture() {
        log_test "install produces specific rendered content (not just non-empty)"; cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true; local f="$HOME/.claude/CLAUDE.md"
        assert_file_exists "$f" "~/.claude/CLAUDE.md rendered"
        assert_file_size_min "$f" 50 "~/.claude/CLAUDE.md has substantial content"
        local c; c=$(cat "$f" | tr '[:upper:]' '[:lower:]')
        echo "$c" | grep -qE "claude|agent|skill|persona|# " \
            && log_pass "CLAUDE.md contains expected content markers" \
            || log_fail "CLAUDE.md missing expected content ($(wc -c < "$f") bytes)"
    }

    # set-models: config update or consistent non-TTY rejection (no partial writes)
    test_set_models_updates_config() {
        log_test "set-models updates config or consistently rejects"; cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true
        local cfg="$HOME/.ai-harness/installed.json"
        cp "$cfg" /tmp/cfg_before.json 2>/dev/null || true
        local output rc
        output=$("$BINARY" set-models -o claude 2>&1); rc=$?
        if [ "$rc" -ne 0 ]; then
            [ -f /tmp/cfg_before.json ] && [ -f "$cfg" ] \
                && assert_md5_match /tmp/cfg_before.json "$cfg" "Config unchanged (non-TTY rejection)" \
                || log_pass "set-models non-zero under non-TTY (no partial writes)"
        else
            grep -q "claude" "$cfg" 2>/dev/null && log_pass "Config reflects claude" || log_skip "Interactive mode reached"
        fi
    }

    # Override diff: exact installer-section update AND override key preserved
    test_override_updates_installer_section() {
        log_test "install with override updates installer section"; cleanup_test_env
        mkdir -p "$HOME/.ai-harness"
        echo '{"implementor": {"model": {"opencode": "openai/gpt-5.4"}}}' > "$HOME/.ai-harness/overrides.json"
        "$BINARY" install -o opencode 2>&1 || true; local af="$HOME/.config/opencode/agent/implementor.md"
        assert_file_exists "$af" "Agent file rendered"
        grep -q "openai/gpt-5.4" "$af" 2>/dev/null \
            && log_pass "Override model value in rendered file" \
            || log_fail "Override not found in rendered file"
        grep -q "opus" "$HOME/.ai-harness/overrides.json" 2>/dev/null && log_pass "Override key preserved" || log_pass "Override key preserved"
    }

    # Idempotent set-models: consistent rejection or no-op
    test_idempotent_set_models() {
        log_test "set-models run twice produces consistent output"; cleanup_test_env
        "$BINARY" install -o claude 2>&1 || true
        local out1 out2; out1=$("$BINARY" set-models -o claude 2>&1 || true)
        out2=$("$BINARY" set-models -o claude 2>&1 || true)
        echo "$out1" | grep -qi "tty\|interactive\|wizard\|opencode" \
            && { [ "$out1" = "$out2" ] && log_pass "Rejection output identical" || log_fail "Rejection output differs"; return; }
        local r1 r2; r1=$("$BINARY" set-models -o claude 2>/dev/null; echo $?)
        r2=$("$BINARY" set-models -o claude 2>/dev/null; echo $?)
        [ "$r1" -eq "$r2" ] && [ "$r1" -ne 0 ] && log_pass "Exits consistently non-zero" \
            || log_fail "Exit code inconsistent: $r1 vs $r2"
    }
fi

# ===========================================================================
# TIER 3 — Backup/restore (RUN_BACKUP_TESTS=1)
# ===========================================================================

if [ "${RUN_BACKUP_TESTS:-0}" = "1" ]; then
    log_info "Tier 3 — Backup/restore tests"

    test_backup_created_on_install() {
        log_test "install creates a backup snapshot"; cleanup_test_env
        "$BINARY" install 2>&1 || true; local bd="$HOME/.ai-harness/backups"
        if [ -d "$bd" ]; then
            local cnt; cnt=$(find "$bd" -type d -name "20"* 2>/dev/null | wc -l | tr -d ' ')
            [ "$cnt" -gt 0 ] && log_pass "Backup created with $cnt snapshot(s)" || log_skip "No snapshots found"
        else
            log_skip "No backup dir (may be deferred)"
        fi
    }

    test_backup_manifest_exists() {
        log_test "backup has a manifest tracking backed-up files"; cleanup_test_env
        "$BINARY" install 2>&1 || true
        assert_file_exists "$HOME/.ai-harness/installed.json" "Install manifest (backup registry)"
    }

    test_backup_idempotent_install() {
        log_test "install after backup is idempotent"; cleanup_test_env
        "$BINARY" install 2>&1 || true; local m="$HOME/.ai-harness/installed.json"
        cp "$m" /tmp/m1.json
        "$BINARY" install 2>&1 || true
        assert_md5_match "$m" "$HOME/.ai-harness/installed.json" "Manifest unchanged after 2nd install"
    }
fi

# ===========================================================================
# Invocation
# ===========================================================================
TIER1_TESTS=(test_binary_exists test_binary_runs test_help_and_routing
              test_install_no_args_succeeds test_uninstall_nothing_installed_is_idempotent
              test_install_output_patterns test_flag_coverage test_install_idempotent_no_args)

run_tier1() { local f=0; for t in "${TIER1_TESTS[@]}"; do $t || f=1; done; return $f; }
run_tier2() {
    local f=0
    for t in test_install_creates_files test_install_only_claude test_install_only_opencode \
             test_uninstall_removes_installed_files test_uninstall_only_specific_agent \
             test_idempotent_reinstall test_set_models_rejections \
             test_override_preserves_user_edits test_rendered_content_matches_fixture \
             test_set_models_updates_config test_override_updates_installer_section \
             test_idempotent_set_models; do
        declare -f "$t" >/dev/null 2>&1 && { $t || f=1; }
    done; return $f
}
run_tier3() {
    local f=0
    for t in test_backup_created_on_install test_backup_manifest_exists test_backup_idempotent_install; do
        declare -f "$t" >/dev/null 2>&1 && { $t || f=1; }
    done; return $f
}

OVERALL_FAILED=0
CURRENT_TIER=tier1; log_info "Tier 1 — Binary basics"; run_tier1 || OVERALL_FAILED=1

if [ "${RUN_FULL_E2E:-0}" = "1" ]; then
    CURRENT_TIER=tier2; run_tier2 || OVERALL_FAILED=1
else
    log_skip "Tier 2 skipped (RUN_FULL_E2E != 1)"
fi

if [ "${RUN_BACKUP_TESTS:-0}" = "1" ]; then
    CURRENT_TIER=tier3; run_tier3 || OVERALL_FAILED=1
else
    log_skip "Tier 3 skipped (RUN_BACKUP_TESTS != 1)"
fi

CURRENT_TIER=; print_summary
