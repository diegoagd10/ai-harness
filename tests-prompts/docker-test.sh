#!/usr/bin/env bash
# docker-test.sh — Build & run the ai-harness prompt-test suite in an isolated container.
#
# Usage:
#   ./tests-prompts/docker-test.sh              # default tag, hello row only
#   IMAGE_TAG=my-tag:dev ./tests-prompts/docker-test.sh
#
# Exit codes:
#   0 — every CSV row passed inside the container
#   1 — at least one row failed
#
# Mirrors: e2e/docker-test.sh structural pattern (SCRIPT_DIR, PROJECT_ROOT,
# IMAGE_TAG, ENV_FLAGS, run_with_timeout, --network host, [BUILD]/[RUN] prefixes)
# so the two harnesses read as siblings and log scrapers reuse line prefixes.
set -uo pipefail

# ---------------------------------------------------------------------------
# Colors (duplicated here so the orchestrator can log independently of lib.sh)
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_TAG="${IMAGE_TAG:-ai-harness-prompt-tests:local}"

# Auth file the opencode CLI reads at runtime. Must exist on the host before
# we touch Docker — uv tool install + the model API call both need it.
HOST_AUTH_FILE="${HOST_AUTH_FILE:-/home/diegoagd10/.local/share/opencode/auth.json}"

# Style mirror from e2e/docker-test.sh. The prompt-test suite has no
# per-row timeout (per container-csv-runner:no-timeout-per-row), so this
# helper is a thin passthrough today; it exists so log scrapers that
# grep for `run_with_timeout` find the same identifier in both harnesses.
run_with_timeout() {
    "$@"
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    echo "Usage: $0"
    echo ""
    echo "Run the ai-harness prompt-test suite inside an isolated Docker container."
    echo ""
    echo "Environment variables:"
    echo "  IMAGE_TAG=...         Override the Docker image tag (default: ai-harness-prompt-tests:local)"
    echo "  HOST_AUTH_FILE=...    Override the host opencode auth path (default: /home/diegoagd10/.local/share/opencode/auth.json)"
    echo ""
    echo "Examples:"
    echo "  $0                              # default tag, hello row"
    echo "  IMAGE_TAG=my-tag:dev $0         # custom image tag"
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi

# ---------------------------------------------------------------------------
# Auth preflight — fail fast before any docker call.
# ---------------------------------------------------------------------------
if [ ! -f "$HOST_AUTH_FILE" ]; then
    printf "${RED}[FAIL]${NC} host opencode auth file not found: %s\n" "$HOST_AUTH_FILE" >&2
    printf "${RED}[FAIL]${NC} expected path: %s\n" "$HOST_AUTH_FILE" >&2
    printf "${RED}[FAIL]${NC} create the file (or run \`opencode auth\`) before retrying.\n" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
printf "${BLUE}[BUILD]${NC} Building image from tests-prompts/Dockerfile\n"
printf "${BLUE}[BUILD]${NC} Image tag: %s\n" "$IMAGE_TAG"
printf "${BLUE}[BUILD]${NC} Project root: %s\n" "$PROJECT_ROOT"

if ! docker build \
    -f "$SCRIPT_DIR/Dockerfile" \
    -t "$IMAGE_TAG" \
    "$PROJECT_ROOT" 2>&1; then
    printf "${RED}[BUILD]${NC} Build FAILED\n"
    exit 1
fi
printf "${GREEN}[BUILD]${NC} Image built successfully\n"

# ---------------------------------------------------------------------------
# Environment variable forwarding (room for future flags; empty for v1)
# ---------------------------------------------------------------------------
ENV_FLAGS=""

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
printf "${YELLOW}[RUN]${NC}   Running prompt tests inside container\n"
echo ""

# Three mounts, exactly per spec:
#   1) repo (read-only) -> /source-ro   (container copies to /workspace)
#   2) auth (read-only) -> /root/.local/share/opencode/auth.json
#   3) logs (writable)  -> /logs          (failure traces only)
# shellcheck disable=SC2086
if docker run --rm \
    --network host \
    $ENV_FLAGS \
    -v "$PROJECT_ROOT:/source-ro:ro" \
    -v "$HOST_AUTH_FILE:/root/.local/share/opencode/auth.json:ro" \
    -v "$SCRIPT_DIR/logs:/logs" \
    "$IMAGE_TAG" \
    bash /tests-prompts/run.sh 2>&1; then
    printf "${GREEN}[RUN]${NC}   All prompt tests PASSED\n"
    exit 0
else
    rc=$?
    printf "${RED}[RUN]${NC}   Prompt tests FAILED (exit=%d)\n" "$rc"
    exit "$rc"
fi