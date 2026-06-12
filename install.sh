#!/usr/bin/env bash
#
# Install ai-harness-setup: symlink the shared agent config into your home so
# every code harness (Claude Code, opencode, Codex, ...) reads the same source.
#
#   ~/.claude/skills    -> <repo>/skills
#   ~/.claude/CLAUDE.md -> <repo>/AGENTS.md   (single source of truth)
#   ~/.agents/skills    -> <repo>/skills
#   ~/.agents/AGENTS.md -> <repo>/AGENTS.md
#
# Idempotent: re-running repoints existing symlinks. A real file in the way is
# backed up to <path>.bak.<timestamp> before linking.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
AGENTS_DIR="${HOME}/.agents"
COPILOT_DIR="${HOME}/.copilot"

link() {
  local src="$1" dest="$2"

  if [ ! -e "$src" ]; then
    echo "  ✗ source missing, skipping: $src" >&2
    return 1
  fi

  mkdir -p "$(dirname "$dest")"

  if [ -L "$dest" ]; then
    ln -sfn "$src" "$dest"
    echo "  ↻ relinked $dest -> $src"
  elif [ -e "$dest" ]; then
    local backup
    backup="${dest}.bak.$(date +%Y%m%d%H%M%S)"
    mv "$dest" "$backup"
    ln -s "$src" "$dest"
    echo "  ⬆ backed up $dest -> $backup"
    echo "  + linked   $dest -> $src"
  else
    ln -s "$src" "$dest"
    echo "  + linked   $dest -> $src"
  fi
}

echo "Installing ai-harness-setup from $REPO_DIR"
link "$REPO_DIR/skills"    "$CLAUDE_DIR/skills"
link "$REPO_DIR/AGENTS.md" "$CLAUDE_DIR/CLAUDE.md"
link "$REPO_DIR/skills"    "$AGENTS_DIR/skills"
link "$REPO_DIR/AGENTS.md" "$AGENTS_DIR/AGENTS.md"
link "$REPO_DIR/AGENTS.md" "$COPILOT_DIR/copilot-instructions.md"
echo "Done."
