#!/usr/bin/env bash
# End-to-end test for the ai-harness CLI install lifecycle: `uv tool install`,
# `ai-harness install` (the installed binary, not `uv run`), `uv tool install
# --reinstall`, and `uv tool uninstall`.
set -euo pipefail

CLI_DIR=/build/cli
expected="hello muppet"

echo "==> uv tool install ."
uv tool install "$CLI_DIR"

actual="$(ai-harness install)"
if [ "$actual" = "$expected" ]; then
  echo "PASS: ai-harness install -> '$actual'"
else
  echo "FAIL: expected '$expected', got '$actual'"
  exit 1
fi

echo "==> uv tool install --reinstall ."
uv tool install --reinstall "$CLI_DIR"

actual="$(ai-harness install)"
if [ "$actual" = "$expected" ]; then
  echo "PASS: ai-harness install (after reinstall) -> '$actual'"
else
  echo "FAIL: expected '$expected', got '$actual'"
  exit 1
fi

echo "==> uv tool uninstall cli"
uv tool uninstall cli

if command -v ai-harness >/dev/null 2>&1; then
  echo "FAIL: ai-harness still on PATH after uninstall"
  exit 1
else
  echo "PASS: ai-harness removed from PATH after uninstall"
fi
