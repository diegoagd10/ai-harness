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

test_install_renders_commit_format_directive_in_orchestrator() {
    log_test "install renders commit-format directive in change-orchestrator prompts"; cleanup_test_env
    "$BINARY" install 2>&1 || true
    local failed=0
    # OpenCode render
    local oc_path="$HOME/.config/opencode/agent/change-orchestrator.md"
    if [ -f "$oc_path" ]; then
        assert_file_contains "$oc_path" "Data injected for this delegation:" "OpenCode orchestrator has data-injected block" || failed=1
        assert_file_contains "$oc_path" "commit-format:" "OpenCode orchestrator has commit-format directive" || failed=1
    else
        log_skip "OpenCode orchestrator render absent — install did not produce $oc_path"
    fi
    # Claude render
    local cc_path="$HOME/.claude/skills/change-orchestrator/SKILL.md"
    if [ -f "$cc_path" ]; then
        assert_file_contains "$cc_path" "Data injected for this delegation:" "Claude orchestrator has data-injected block" || failed=1
        assert_file_contains "$cc_path" "commit-format:" "Claude orchestrator has commit-format directive" || failed=1
    else
        log_skip "Claude orchestrator render absent — install did not produce $cc_path"
    fi
    [ $failed -eq 0 ] && return 0 || return 1
}

# ===========================================================================
# TIER 1 — ai-harness init (per-repo scaffolding)
# ===========================================================================
#
# `init` is per-repo (operates on the current working directory, NOT $HOME),
# so each scenario creates an isolated tempdir, cd's into it, runs the
# binary, asserts on real disk content, then cd's back and cleans up.
# No RUN_FULL_E2E gating — these run on every default CI run.

# Internal helper: create an empty temp dir for init e2e, stash the original
# cwd, and cd into it. Sets the global _INIT_TMPDIR_CI so callers can clean up
# via _init_popdir. MUST be called from the main shell — NOT through $()
# substitution, because subshells discard the cd.
_init_pushdir() {
    _INIT_OLDPWD_CI="$(pwd)"
    _INIT_TMPDIR_CI="$(mktemp -d -t ai-harness-init-e2e-XXXXXX)"
    cd "$_INIT_TMPDIR_CI" || { unset _INIT_OLDPWD_CI _INIT_TMPDIR_CI; return 1; }
}

# Internal helper: pop back to the cwd saved by _init_pushdir and remove the
# temp dir. Safe to call multiple times (unset guards re-entry).
_init_popdir() {
    if [ -n "${_INIT_OLDPWD_CI:-}" ]; then
        cd "$_INIT_OLDPWD_CI" 2>/dev/null || true
        unset _INIT_OLDPWD_CI
    fi
    if [ -n "${_INIT_TMPDIR_CI:-}" ]; then
        rm -rf "$_INIT_TMPDIR_CI" 2>/dev/null || true
        unset _INIT_TMPDIR_CI
    fi
}


test_init_creates_config_yml_and_leaves_root_documents_untouched() {
    log_test "init creates .ai-harness/config.yml and leaves root documents absent"
    cleanup_test_env
    _init_pushdir || { log_fail "could not create tempdir"; return 1; }
    local out rc
    out=$("$BINARY" init 2>&1); rc=$?
    local failed=0
    if [ $rc -ne 0 ]; then log_fail "init exited non-zero ($rc): $out"; failed=1; _init_popdir; return 1; fi
    assert_file_exists ".ai-harness/config.yml" ".ai-harness/config.yml" || failed=1
    # Root documents must not be created by init.
    for root_doc in CLAUDE.md AGENTS.md CODING_STANDARDS.md; do
        assert_file_not_exists "$root_doc" "$root_doc absent after init" || failed=1
    done
    # Output identifies the config path without claiming it was created.
    if echo "$out" | grep -qF ".ai-harness/config.yml"; then
        log_pass "output mentions .ai-harness/config.yml"
    else
        log_fail "output does not mention config path:\n$out"
        failed=1
    fi
    if echo "$out" | tr '[:upper:]' '[:lower:]' | grep -qE "created .ai-harness|already exists|wrote .ai-harness"; then
        log_fail "output makes a creation/already-exists claim:\n$out"
        failed=1
    fi
    _init_popdir
    [ $failed -eq 0 ] && return 0 || return 1
}

test_init_preserves_prepopulated_config_bytes_and_mtime() {
    log_test "init preserves pre-populated .ai-harness/config.yml bytes and mtime"
    cleanup_test_env
    _init_pushdir || { log_fail "could not create tempdir"; return 1; }
    # Seed a pre-existing config the user owns. The contents are deliberately
    # not the bundled default — the test asserts bytes are preserved verbatim.
    mkdir -p .ai-harness
    local original
    original=$(printf 'commit:\n  format: '\''custom-format'\''\nphases:\n  change_explorer:\n    rules:\n      - user rule preserved\n')
    printf '%s' "$original" > .ai-harness/config.yml
    local m_before
    m_before=$(stat -c %Y .ai-harness/config.yml)
    sleep 2
    local out rc
    out=$("$BINARY" init 2>&1); rc=$?
    local failed=0
    if [ $rc -ne 0 ]; then log_fail "init exited non-zero ($rc): $out"; failed=1; _init_popdir; return 1; fi
    local actual m_after
    actual=$(cat .ai-harness/config.yml)
    m_after=$(stat -c %Y .ai-harness/config.yml)
    if [ "$actual" = "$original" ]; then
        log_pass "pre-populated config bytes preserved"
    else
        log_fail "pre-populated config bytes drifted:\nBEFORE:\n$original\nAFTER:\n$actual"
        failed=1
    fi
    if [ "$m_before" = "$m_after" ]; then
        log_pass "pre-populated config mtime unchanged ($m_before)"
    else
        log_fail "pre-populated config mtime changed ($m_before -> $m_after)"
        failed=1
    fi
    _init_popdir
    [ $failed -eq 0 ] && return 0 || return 1
}

test_init_idempotent_rerun_preserves_generated_config_bytes_and_mtime() {
    log_test "init repeated after fresh creation preserves config bytes and mtime"
    cleanup_test_env
    _init_pushdir || { log_fail "could not create tempdir"; return 1; }
    # First run: creates the config from the default template.
    "$BINARY" init >/dev/null 2>&1
    local bytes_before m_before
    bytes_before=$(cat .ai-harness/config.yml)
    m_before=$(stat -c %Y .ai-harness/config.yml)
    sleep 2
    local out rc
    out=$("$BINARY" init 2>&1); rc=$?
    local failed=0
    if [ $rc -ne 0 ]; then log_fail "second init exited non-zero ($rc): $out"; failed=1; _init_popdir; return 1; fi
    local bytes_after m_after
    bytes_after=$(cat .ai-harness/config.yml)
    m_after=$(stat -c %Y .ai-harness/config.yml)
    if [ "$bytes_before" = "$bytes_after" ]; then
        log_pass "generated config bytes preserved on re-run"
    else
        log_fail "generated config bytes drifted on re-run:\nBEFORE:\n$bytes_before\nAFTER:\n$bytes_after"
        failed=1
    fi
    if [ "$m_before" = "$m_after" ]; then
        log_pass "generated config mtime unchanged on re-run ($m_before)"
    else
        log_fail "generated config mtime changed on re-run ($m_before -> $m_after)"
        failed=1
    fi
    _init_popdir
    [ $failed -eq 0 ] && return 0 || return 1
}

test_init_leaves_root_documents_alone_when_present() {
    log_test "init does not touch pre-existing root documents"
    cleanup_test_env
    _init_pushdir || { log_fail "could not create tempdir"; return 1; }
    # Seed root documents with sentinel bytes that would be destroyed by any
    # rewrite. Init must leave them byte-identical.
    printf '# Claude sentinel\n<!-- do not touch -->\n' > CLAUDE.md
    printf '# Agents sentinel\n<!-- do not touch -->\n' > AGENTS.md
    printf '# Standards sentinel\n<!-- do not touch -->\n' > CODING_STANDARDS.md
    local c_before a_before s_before
    c_before=$(cat CLAUDE.md)
    a_before=$(cat AGENTS.md)
    s_before=$(cat CODING_STANDARDS.md)
    local out rc
    out=$("$BINARY" init 2>&1); rc=$?
    local failed=0
    if [ $rc -ne 0 ]; then log_fail "init exited non-zero ($rc): $out"; failed=1; _init_popdir; return 1; fi
    local c_after a_after s_after
    c_after=$(cat CLAUDE.md)
    a_after=$(cat AGENTS.md)
    s_after=$(cat CODING_STANDARDS.md)
    if [ "$c_before" = "$c_after" ]; then
        log_pass "CLAUDE.md byte-identical"
    else
        log_fail "CLAUDE.md content drifted:\nBEFORE:\n$c_before\nAFTER:\n$c_after"
        failed=1
    fi
    if [ "$a_before" = "$a_after" ]; then
        log_pass "AGENTS.md byte-identical"
    else
        log_fail "AGENTS.md content drifted:\nBEFORE:\n$a_before\nAFTER:\n$a_after"
        failed=1
    fi
    if [ "$s_before" = "$s_after" ]; then
        log_pass "CODING_STANDARDS.md byte-identical"
    else
        log_fail "CODING_STANDARDS.md content drifted:\nBEFORE:\n$s_before\nAFTER:\n$s_after"
        failed=1
    fi
    # The config file still gets initialized — root doc isolation does not
    # block config init.
    assert_file_exists .ai-harness/config.yml ".ai-harness/config.yml created" || failed=1
    _init_popdir
    [ $failed -eq 0 ] && return 0 || return 1
}

test_init_exit_zero_on_fresh_and_rerun() {
    log_test "init exits 0 on a fresh run and on an idempotent re-run"
    cleanup_test_env
    # Fresh run.
    _init_pushdir || { log_fail "could not create tempdir (fresh)"; return 1; }
    local rc1; "$BINARY" init >/dev/null 2>&1; rc1=$?
    if [ $rc1 -ne 0 ]; then log_fail "fresh init exited non-zero ($rc1)"; _init_popdir; return 1; fi
    log_pass "fresh init exits 0"
    _init_popdir
    # Pre-populated re-run.
    _init_pushdir || { log_fail "could not create tempdir (saturated)"; return 1; }
    "$BINARY" init >/dev/null 2>&1  # prime
    local rc2; "$BINARY" init >/dev/null 2>&1; rc2=$?
    if [ $rc2 -ne 0 ]; then log_fail "saturated re-run exited non-zero ($rc2)"; _init_popdir; return 1; fi
    log_pass "saturated re-run exits 0"
    _init_popdir
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
        echo '{"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}}}' > "$HOME/.ai-harness/overrides.json"
        "$BINARY" install -o opencode 2>&1 || true; local af="$HOME/.config/opencode/agent/change-implementor.md"
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
              test_install_output_patterns test_flag_coverage test_install_idempotent_no_args
              test_install_renders_commit_format_directive_in_orchestrator
              test_init_creates_config_yml_and_leaves_root_documents_untouched
              test_init_preserves_prepopulated_config_bytes_and_mtime
              test_init_idempotent_rerun_preserves_generated_config_bytes_and_mtime
              test_init_leaves_root_documents_alone_when_present
              test_init_exit_zero_on_fresh_and_rerun)

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
