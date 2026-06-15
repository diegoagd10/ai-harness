#!/usr/bin/env bash
#
# Build the e2e image and run the suite inside it. Hermetic tiers run by default.
# To include the gated live smoke tier, export RUN_LIVE_SMOKE=1 and a provider
# credential (e.g. ANTHROPIC_API_KEY) before invoking; both are forwarded into
# the container.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IMAGE:-ai-harness-e2e:local}"

echo "Building $IMAGE from $REPO_DIR ..."
# --network=host: the build downloads Go/Bun/OpenCode over TLS. On hosts whose
# Docker bridge MTU is smaller than the host link (common behind VPNs/overlays),
# the default bridge silently drops large TLS-handshake packets and downloads
# hang. Host networking sidesteps that and is harmless on normal networks.
# Override with BUILD_NETWORK= to use the default bridge.
docker build --network="${BUILD_NETWORK:-host}" \
  -f "$REPO_DIR/e2e/Dockerfile.ubuntu" -t "$IMAGE" "$REPO_DIR"

echo "Running e2e suite in $IMAGE ..."
docker run --rm \
  -e RUN_LIVE_SMOKE="${RUN_LIVE_SMOKE:-0}" \
  -e SMOKE_MODEL \
  -e ANTHROPIC_API_KEY \
  -e OPENAI_API_KEY \
  "$IMAGE"
