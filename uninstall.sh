#!/usr/bin/env bash
#
# Uninstall ai-harness-setup: remove ONLY the symlinks that point back into this
# repo. Real files (including *.bak.* backups created by install.sh) are left
# untouched, and symlinks pointing elsewhere are skipped.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
AGENTS_DIR="${HOME}/.agents"
COPILOT_DIR="${HOME}/.copilot"

unlink_if_ours() {
  local dest="$1"

  if [ -L "$dest" ]; then
    local target
    target="$(readlink "$dest")"
    case "$target" in
      "$REPO_DIR"/*)
        rm "$dest"
        echo "  - removed $dest (was -> $target)"
        ;;
      *)
        echo "  · skipped $dest (points elsewhere: $target)"
        ;;
    esac
  elif [ -e "$dest" ]; then
    echo "  · skipped $dest (real file, not a symlink)"
  else
    echo "  · absent  $dest"
  fi
}

echo "Uninstalling ai-harness-setup symlinks"
unlink_if_ours "$CLAUDE_DIR/skills"
unlink_if_ours "$CLAUDE_DIR/CLAUDE.md"
unlink_if_ours "$AGENTS_DIR/skills"
unlink_if_ours "$AGENTS_DIR/AGENTS.md"
unlink_if_ours "$COPILOT_DIR/copilot-instructions.md"
echo "Done. Any *.bak.* backups were left in place."
