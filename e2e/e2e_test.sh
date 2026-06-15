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

check_install_targets() {
  local home="$1" label="$2"

  assert_same_content "$home/.agents/AGENTS.md" "$AGENTS_MD" \
    "AGENTS.md -> ~/.agents/AGENTS.md ($label)"
  assert_same_content "$home/.claude/CLAUDE.md" "$AGENTS_MD" \
    "AGENTS.md -> ~/.claude/CLAUDE.md ($label)"
  assert_same_content "$home/.copilot/copilot-instructions.md" "$AGENTS_MD" \
    "AGENTS.md -> ~/.copilot/copilot-instructions.md ($label)"

  for skills_root in "$home/.agents/skills" "$home/.claude/skills"; do
    assert_same_content "$skills_root/example/SKILL.md" "$SKILLS_DIR/example/SKILL.md" \
      "skills/example -> $skills_root ($label)"
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
printf '# my custom skill\n' >"$HOME2/.agents/skills/my-custom-skill/SKILL.md"
printf '# stale content\n' >"$HOME2/.claude/skills/example/SKILL.md"

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

custom_content="$(cat "$HOME2/.agents/skills/my-custom-skill/SKILL.md")"
if [ "$custom_content" = "# my custom skill" ]; then
  echo "PASS: user-authored skill preserved after uninstall ($HOME2/.agents/skills/my-custom-skill)"
else
  echo "FAIL: user-authored skill preserved after uninstall (got: $custom_content)"
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
