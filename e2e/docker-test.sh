#!/usr/bin/env bash
# Build the e2e image and run the suite inside it.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IMAGE:-ai-harness-cli-e2e:local}"

# DOCKER_BUILDKIT=1 enables BuildKit features (cache mounts, retry loops).
# BUILDKIT_SANDBOX_HOSTNAME=host avoids DNS issues that can break PyPI fetches
# from inside the build sandbox. ``--network=host`` lets the build reach PyPI
# via the host's network stack, which is often more reliable than the default
# bridge network in restricted environments.
export DOCKER_BUILDKIT=1
export BUILDKIT_SANDBOX_HOSTNAME=host

docker build --network=host -f "$REPO_DIR/e2e/Dockerfile" -t "$IMAGE" "$REPO_DIR"
docker run --rm --network=host "$IMAGE"
