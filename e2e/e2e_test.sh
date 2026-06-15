#!/usr/bin/env bash
# End-to-end test for the ai-harness CLI install lifecycle: `uv tool install`,
# `ai-harness install` (the installed binary, not `uv run`), `uv tool install
# --reinstall`, and `uv tool uninstall`.
#
# `ai-harness install` fans AGENTS.md and skills/ out to the harness config
# directories under $HOME. AGENTS.md and skills/ are bundled as package data
# under src/ai_harness/resources, so a plain (non-editable) `uv tool install` carries
# them along — this test exercises exactly that.
set -euo pipefail

CLI_DIR=/build
RESOURCES_DIR="$CLI_DIR/src/ai_harness/resources"
AGENTS_MD="$RESOURCES_DIR/AGENTS.md"
SKILLS_DIR="$RESOURCES_DIR/skills"
OPENCODE_JSON="$RESOURCES_DIR/agent-clis/opencode/opencode.json"
SDD_PROMPTS_DIR="$RESOURCES_DIR/prompts/sdd"

assert_same_content() {
  local actual="$1" expected="$2" label="$3"
  if [ ! -f "$actual" ]; then
    echo "FAIL: $label (missing: $actual)"
    exit 1
  fi
  if [ "$(cat "$actual")" = "$(cat "$expected")" ]; then
    echo "PASS: $label"
  else
    echo "FAIL: $label (content mismatch: $actual vs $expected)"
    exit 1
  fi
}

assert_opencode_json_installed() {
  local actual="$1" home="$2" label="$3"
  local expected
  expected="$(sed "s|{{HOME}}|$home|g" "$OPENCODE_JSON")"

  if [ ! -f "$actual" ]; then
    echo "FAIL: $label (missing: $actual)"
    exit 1
  fi
  if [ "$(cat "$actual")" = "$expected" ]; then
    echo "PASS: $label"
  else
    echo "FAIL: $label (content mismatch after {{HOME}} substitution: $actual)"
    exit 1
  fi
}

check_install_targets() {
  local home="$1" label="$2"

  assert_same_content "$home/.agents/AGENTS.md" "$AGENTS_MD" \
    "AGENTS.md -> ~/.agents/AGENTS.md ($label)"
  assert_same_content "$home/.claude/CLAUDE.md" "$AGENTS_MD" \
    "AGENTS.md -> ~/.claude/CLAUDE.md ($label)"
  assert_same_content "$home/.copilot/copilot-instructions.md" "$AGENTS_MD" \
    "AGENTS.md -> ~/.copilot/copilot-instructions.md ($label)"
  assert_same_content "$home/.config/opencode/AGENTS.md" "$AGENTS_MD" \
    "AGENTS.md -> ~/.config/opencode/AGENTS.md ($label)"

  for skills_root in "$home/.agents/skills" "$home/.claude/skills"; do
    assert_same_content "$skills_root/example/SKILL.md" "$SKILLS_DIR/example/SKILL.md" \
      "skills/example -> $skills_root ($label)"
  done

  assert_opencode_json_installed "$home/.config/opencode/opencode.json" "$home" \
    "opencode.json -> ~/.config/opencode/opencode.json ($label)"

  for prompt_file in "$SDD_PROMPTS_DIR"/*.md; do
    assert_same_content "$home/.config/opencode/prompts/sdd/$(basename "$prompt_file")" "$prompt_file" \
      "prompts/sdd/$(basename "$prompt_file") -> ~/.config/opencode/prompts/sdd ($label)"
  done
}

echo "==> uv tool install ."
uv tool install "$CLI_DIR"

# --- Fresh install: AGENTS.md + skills land in every harness dir -----------
HOME1="$(mktemp -d)"
HOME="$HOME1" ai-harness install
check_install_targets "$HOME1" "fresh install"

# --- Re-running install preserves unrelated user skills, but overrides -----
# --- any skill matching a name from this project ---------------------------
HOME2="$(mktemp -d)"
mkdir -p "$HOME2/.agents/skills/my-custom-skill" "$HOME2/.claude/skills/example"
mkdir -p "$HOME2/.config/opencode/prompts/sdd" "$HOME2/.config/opencode/prompts/custom"
printf '# my custom skill\n' >"$HOME2/.agents/skills/my-custom-skill/SKILL.md"
printf '# stale content\n' >"$HOME2/.claude/skills/example/SKILL.md"
printf '{"stale": true}\n' >"$HOME2/.config/opencode/opencode.json"
printf '# user opencode instructions\n' >"$HOME2/.config/opencode/AGENTS.md"
printf '# stale prompt\n' >"$HOME2/.config/opencode/prompts/sdd/sdd-apply.md"
printf '# custom prompt\n' >"$HOME2/.config/opencode/prompts/custom/user.md"

HOME="$HOME2" ai-harness install

custom_content="$(cat "$HOME2/.agents/skills/my-custom-skill/SKILL.md")"
if [ "$custom_content" = "# my custom skill" ]; then
  echo "PASS: user-authored skill preserved ($HOME2/.agents/skills/my-custom-skill)"
else
  echo "FAIL: user-authored skill preserved (got: $custom_content)"
  exit 1
fi
assert_same_content "$HOME2/.claude/skills/example/SKILL.md" "$SKILLS_DIR/example/SKILL.md" \
  "stale project skill overridden with fresh content"
assert_opencode_json_installed "$HOME2/.config/opencode/opencode.json" "$HOME2" \
  "stale opencode.json overridden with fresh content"
assert_same_content "$HOME2/.config/opencode/prompts/sdd/sdd-apply.md" "$SDD_PROMPTS_DIR/sdd-apply.md" \
  "stale SDD prompt overridden with fresh content"

# --- Reinstall keeps the same behaviour -------------------------------------
echo "==> uv tool install --reinstall ."
uv tool install --reinstall "$CLI_DIR"

HOME3="$(mktemp -d)"
HOME="$HOME3" ai-harness install
check_install_targets "$HOME3" "after reinstall"

# --- ai-harness uninstall reverses install, preserving unrelated content ---
echo "==> ai-harness uninstall"
HOME="$HOME2" ai-harness uninstall

for relative_target in ".agents/AGENTS.md" ".claude/CLAUDE.md" ".copilot/copilot-instructions.md"; do
  if [ -e "$HOME2/$relative_target" ]; then
    echo "FAIL: $HOME2/$relative_target still exists after uninstall"
    exit 1
  else
    echo "PASS: $HOME2/$relative_target removed by uninstall"
  fi
done

for skills_root in "$HOME2/.agents/skills" "$HOME2/.claude/skills"; do
  if [ -e "$skills_root/example" ]; then
    echo "FAIL: $skills_root/example still exists after uninstall"
    exit 1
  else
    echo "PASS: $skills_root/example removed by uninstall"
  fi
done

restored_opencode_config="$(cat "$HOME2/.config/opencode/opencode.json")"
if [ "$restored_opencode_config" = '{"stale": true}' ]; then
  echo "PASS: pre-existing opencode.json restored after uninstall"
else
  echo "FAIL: pre-existing opencode.json restored after uninstall (got: $restored_opencode_config)"
  exit 1
fi

restored_opencode_agents="$(cat "$HOME2/.config/opencode/AGENTS.md")"
if [ "$restored_opencode_agents" = "# user opencode instructions" ]; then
  echo "PASS: pre-existing opencode AGENTS.md restored after uninstall"
else
  echo "FAIL: pre-existing opencode AGENTS.md restored after uninstall (got: $restored_opencode_agents)"
  exit 1
fi

if [ -e "$HOME2/.config/opencode/AGENTS.md.ai-harness-backup" ]; then
  echo "FAIL: opencode AGENTS.md backup still exists after uninstall"
  exit 1
else
  echo "PASS: opencode AGENTS.md backup removed after restore"
fi

if [ -e "$HOME2/.config/opencode/opencode.json.ai-harness-backup" ]; then
  echo "FAIL: opencode backup still exists after uninstall"
  exit 1
else
  echo "PASS: opencode backup removed after restore"
fi

for prompt_file in "$SDD_PROMPTS_DIR"/*.md; do
  target="$HOME2/.config/opencode/prompts/sdd/$(basename "$prompt_file")"
  if [ "$(basename "$prompt_file")" = "sdd-apply.md" ]; then
    restored_prompt_content="$(cat "$target")"
    if [ "$restored_prompt_content" = "# stale prompt" ]; then
      echo "PASS: pre-existing prompts/sdd/sdd-apply.md restored after uninstall"
    else
      echo "FAIL: pre-existing prompts/sdd/sdd-apply.md restored after uninstall (got: $restored_prompt_content)"
      exit 1
    fi
    if [ -e "$target.ai-harness-backup" ]; then
      echo "FAIL: prompts/sdd/sdd-apply.md backup still exists after uninstall"
      exit 1
    else
      echo "PASS: prompts/sdd/sdd-apply.md backup removed after restore"
    fi
    continue
  fi
  if [ -e "$target" ]; then
    echo "FAIL: $target still exists after uninstall"
    exit 1
  else
    echo "PASS: prompts/sdd/$(basename "$prompt_file") removed by uninstall"
  fi
done

custom_content="$(cat "$HOME2/.agents/skills/my-custom-skill/SKILL.md")"
if [ "$custom_content" = "# my custom skill" ]; then
  echo "PASS: user-authored skill preserved after uninstall ($HOME2/.agents/skills/my-custom-skill)"
else
  echo "FAIL: user-authored skill preserved after uninstall (got: $custom_content)"
  exit 1
fi

custom_prompt_content="$(cat "$HOME2/.config/opencode/prompts/custom/user.md")"
if [ "$custom_prompt_content" = "# custom prompt" ]; then
  echo "PASS: user-authored opencode prompt preserved after uninstall"
else
  echo "FAIL: user-authored opencode prompt preserved after uninstall (got: $custom_prompt_content)"
  exit 1
fi

echo "==> uv tool uninstall ai-harness"
uv tool uninstall ai-harness

# Forget bash's cached path for ai-harness from the earlier invocations above,
# otherwise `command -v` reports the stale hashed location even though the
# binary was removed.
hash -r

if command -v ai-harness >/dev/null 2>&1; then
  echo "FAIL: ai-harness still on PATH after uninstall"
  exit 1
else
  echo "PASS: ai-harness removed from PATH after uninstall"
fi
