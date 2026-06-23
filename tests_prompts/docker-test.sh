#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IMAGE:-ai-harness-prompt-evals:local}"
AUTH_JSON="${OPENCODE_AUTH_JSON:-$HOME/.local/share/opencode/auth.json}"

if [[ ! -f "$AUTH_JSON" ]]; then
  echo "OpenCode auth file not found: $AUTH_JSON" >&2
  exit 1
fi

mkdir -p "$REPO_DIR/tests_prompts/artifacts"

export DOCKER_BUILDKIT=1
export BUILDKIT_SANDBOX_HOSTNAME=host

docker build --network=host -f "$REPO_DIR/tests_prompts/Dockerfile" -t "$IMAGE" "$REPO_DIR"
docker run --rm --network=host \
  --mount "type=bind,source=$AUTH_JSON,target=/root/.local/share/opencode/auth.json,readonly" \
  --mount "type=bind,source=$REPO_DIR/tests_prompts/artifacts,target=/work/tests_prompts/artifacts" \
  -e "OPENCODE_PROMPT_EVAL_MODEL=${OPENCODE_PROMPT_EVAL_MODEL:-minimax/MiniMax-M2.7}" \
  "$IMAGE"
