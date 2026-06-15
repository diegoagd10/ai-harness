#!/usr/bin/env bash
# Build the e2e image and run the suite inside it.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IMAGE:-ai-harness-cli-e2e:local}"

docker build -f "$REPO_DIR/e2e/Dockerfile" -t "$IMAGE" "$REPO_DIR"
docker run --rm "$IMAGE"
