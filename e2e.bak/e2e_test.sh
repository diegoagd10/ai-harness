#!/usr/bin/env bash
#
# End-to-end test for `ai-harness install` and the OpenCode harness it produces.
#
# Tiers (each runs only when its prerequisite tool is present):
#   1. Install (always)      — build ai-harness, install into a clean HOME, and
#                              assert the generated opencode.json, copied files,
#                              command files are correct. Hermetic, no network.
#   2. OpenCode config-load  — requires the `opencode` binary. Proves OpenCode
#                              actually parses our agent graph (sdd-orchestrator
#                              + hidden subagents) and loads the plugin, with no
#                              LLM/auth (`opencode agent list`).
#   3a. Plugin unit test     — requires `bun`. Runs the model-variants unit test.
#   3b. Live smoke (gated)    — requires RUN_LIVE_SMOKE=1 and a configured provider
#                              key. Runs a real `opencode run` and checks the plugin
#                              wrote a non-empty model-variants cache. NOT hermetic.
#
# Exit code is non-zero if any assertion failed.

set -uo pipefail

E2E_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$E2E_DIR/.." && pwd)"
# shellcheck source=lib.sh
source "$E2E_DIR/lib.sh"

WORK="$(mktemp -d)"
H="$WORK/home"
BIN="$WORK/ai-harness"
OC_CFG="$H/.config/opencode"
mkdir -p "$H"
trap 'rm -rf "$WORK"' EXIT

# oc runs the opencode binary against the clean test HOME with a timeout, from a
# neutral cwd so no repo-local project config leaks in.
oc() {
  ( cd "$WORK" && timeout "${OPENCODE_TIMEOUT:-120}" \
      env HOME="$H" XDG_CONFIG_HOME="$H/.config" opencode "$@" )
}

# --- Tier 1: build + install (hermetic) -------------------------------------
log_section "Tier 1: build + install into clean HOME"

if ( cd "$REPO_DIR/cli" && go build -o "$BIN" ./cmd/ai-harness ); then
  log_pass "ai-harness binary builds"
else
  log_fail "ai-harness binary builds" "go build failed"
  print_summary; exit 1
fi

# Explicit --harness (and no stdin) so install never blocks on the interactive
# picker; this exercises the full multi-harness install non-interactively.
HOME="$H" "$BIN" install --harness opencode,claude,copilot --repo "$REPO_DIR" </dev/null >"$WORK/install.log" 2>&1
if [ $? -eq 0 ]; then log_pass "ai-harness install exits 0"; else log_fail "ai-harness install exits 0" "$(cat "$WORK/install.log")"; fi

# opencode.json: generated, valid, {{HOME}} substituted to the test HOME.
OC_JSON="$OC_CFG/opencode.json"
assert_file_exists "$OC_JSON" "opencode.json generated"
assert_valid_json  "$OC_JSON" "opencode.json is valid JSON"
assert_file_not_contains "$OC_JSON" "{{HOME}}" "opencode.json has no unsubstituted {{HOME}}"
assert_file_contains "$OC_JSON" "$H/.config/opencode/prompts/sdd" "opencode.json references the substituted home path"

# Per-agent default model assignments survive generation.
assert_file_contains "$OC_JSON" "openai/gpt-5.5" "opencode.json assigns gpt-5.5 to the primary orchestrator"
assert_file_not_contains "$OC_JSON" "opencode/gpt-5" "opencode.json does not assign stale opencode/gpt-5 to SDD stages"
assert_file_contains "$OC_JSON" "minimax/MiniMax-M2.7" "opencode.json assigns minimax to sdd-init/sdd-archive"
assert_file_contains "$OC_JSON" "openai/gpt-5.4-mini" "opencode.json assigns gpt-5.4-mini to sdd-apply"

# Copied OpenCode assets are regular files / directories, not symlinks.
assert_not_symlink "$OC_CFG/skills"      "skills directory is copied"
assert_not_symlink "$OC_CFG/AGENTS.md"   "AGENTS.md (persona) is copied"
assert_not_symlink "$OC_CFG/prompts/sdd" "prompts/sdd directory is copied"
assert_not_symlink "$OC_CFG/plugins"     "plugins directory is copied"

# The orchestrator prompt and plugin resolve from copied files.
assert_file_exists "$OC_CFG/prompts/sdd/sdd-orchestrator.md" "orchestrator prompt is copied"
assert_file_exists "$OC_CFG/plugins/model-variants.ts"        "model-variants plugin is copied"

# Manifest records the owned copied files.
MANIFEST="$H/.config/ai-harness/install-manifest.json"
assert_file_exists "$MANIFEST" "install manifest generated"
assert_file_contains "$MANIFEST" "$OC_CFG/AGENTS.md" "manifest records OpenCode AGENTS.md"
assert_file_contains "$MANIFEST" "$OC_CFG/opencode.json" "manifest records generated opencode.json"

# Generated slash-commands.
for cmd in sdd-new sdd-continue sdd-status sdd-init sdd-onboard; do
  assert_file_exists "$OC_CFG/commands/$cmd.md" "command generated: $cmd"
done

# --- Tier 2: OpenCode actually loads the config (hermetic, no auth) ----------
log_section "Tier 2: OpenCode config-load (opencode agent list)"

if ! command -v opencode >/dev/null 2>&1; then
  log_skip "opencode binary not installed — skipping config-load tier"
else
  agents_out="$(oc agent list --pure 2>&1)"
  agents_code=$?
  if [ "$agents_code" -eq 0 ]; then log_pass "opencode agent list --pure exits 0"; else log_fail "opencode agent list --pure exits 0" "$agents_out"; fi
  assert_str_contains "agent graph exposes sdd-orchestrator (primary)" "$agents_out" "sdd-orchestrator"
  for sub in sdd-apply sdd-verify jd-judge-a review-risk; do
    assert_str_contains "agent graph exposes subagent: $sub" "$agents_out" "$sub"
  done

  # Plugin enabled (no --pure): config + plugin load must not crash OpenCode.
  if oc agent list >/dev/null 2>&1; then
    log_pass "opencode loads with the model-variants plugin enabled"
  else
    log_fail "opencode loads with the model-variants plugin enabled" "agent list failed with plugins on"
  fi
fi

# --- Tier 3a: plugin unit test (hermetic) ------------------------------------
log_section "Tier 3a: model-variants plugin unit test (bun)"

if ! command -v bun >/dev/null 2>&1; then
  log_skip "bun not installed — skipping plugin unit test"
else
  if ( cd "$REPO_DIR/agent-clis/opencode/plugins" && bun test ) >"$WORK/bun.log" 2>&1; then
    log_pass "bun test (extractVariants) passes"
  else
    log_fail "bun test (extractVariants) passes" "$(cat "$WORK/bun.log")"
  fi
fi

# --- Tier 3b: live smoke (gated, non-hermetic) -------------------------------
log_section "Tier 3b: live smoke (gated)"

if [ "${RUN_LIVE_SMOKE:-0}" != "1" ]; then
  log_skip "RUN_LIVE_SMOKE != 1 — skipping live smoke (needs a provider key)"
elif ! command -v opencode >/dev/null 2>&1; then
  log_skip "opencode binary not installed — cannot run live smoke"
else
  # A real model call: the orchestrator must answer. Requires a provider
  # credential to be present in the environment / opencode auth.
  run_out="$(oc run --model "${SMOKE_MODEL:-anthropic/claude-haiku-4-5}" 'Reply with exactly: OK' 2>&1)"
  if grep -qiF "OK" <<<"$run_out"; then
    log_pass "opencode run produced a model response"
  else
    log_fail "opencode run produced a model response" "$run_out"
  fi
  # The plugin should have refreshed its cache against the live provider list.
  cache="$H/.ai-harness/cache/model-variants.json"
  if [ -s "$cache" ]; then
    log_pass "model-variants plugin wrote a non-empty cache"
  else
    log_fail "model-variants plugin wrote a non-empty cache" "missing or empty: $cache"
  fi
fi

# --- Post-install uninstall verification ------------------------------------
log_section "Post-install uninstall verification"

echo 'edited by e2e' >>"$OC_CFG/AGENTS.md"
printf 'keep me\n' >"$OC_CFG/custom.txt"
HOME="$H" "$BIN" uninstall --repo "$REPO_DIR" </dev/null >"$WORK/uninstall.log" 2>&1
if [ $? -eq 0 ]; then log_pass "ai-harness uninstall exits 0"; else log_fail "ai-harness uninstall exits 0" "$(cat "$WORK/uninstall.log")"; fi
assert_file_not_contains "$OC_CFG/AGENTS.md" "edited by e2e" "edited installed file removed on uninstall"
assert_file_exists "$OC_CFG/custom.txt" "unlisted custom file remains after uninstall"
assert_file_not_contains "$MANIFEST" "$OC_CFG/AGENTS.md" "manifest removed after uninstall"

print_summary
