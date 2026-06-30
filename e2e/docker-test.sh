#!/usr/bin/env bash
# docker-test.sh — Build & run the ai-harness E2E test suite in an isolated container.
#
# Usage:
#   ./e2e/docker-test.sh                      # Tier 1 only (default)
#   RUN_FULL_E2E=1 ./e2e/docker-test.sh       # Tier 1 + 2
#   RUN_BACKUP_TESTS=1 ./e2e/docker-test.sh  # Tier 1 + 3
#   RUN_FULL_E2E=1 RUN_BACKUP_TESTS=1 ./e2e/docker-test.sh  # All tiers
#
# Exit codes:
#   0 — tests passed
#   1 — at least one test failed
#
# Mirrors: gentle-ai/e2e/docker-test.sh structural pattern
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
IMAGE_TAG="${IMAGE_TAG:-ai-harness-e2e:local}"
PLATFORM_TIMEOUT_SECONDS="${E2E_PLATFORM_TIMEOUT_SECONDS:-900}"

# Optional positional argument: reserved for future platform selection.
# Currently accepted but ignored (v1 uses a single Ubuntu image).
PLATFORM_ARG="${1:-}"

run_with_timeout() {
    if command -v timeout >/dev/null 2>&1; then
        timeout "$PLATFORM_TIMEOUT_SECONDS" "$@"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    echo "Usage: $0 [platform]"
    echo ""
    echo "Run the ai-harness e2e test suite inside an isolated Docker container."
    echo ""
    echo "Arguments:"
    echo "  platform  (optional) reserved for future platform selection; ignored in v1"
    echo ""
    echo "Environment variables:"
    echo "  RUN_FULL_E2E=1       Enable Tier 2 (install/uninstall/set-models lifecycle)"
    echo "  RUN_BACKUP_TESTS=1  Enable Tier 3 (backup/restore tests)"
    echo "  GITHUB_TOKEN=...     Forward GitHub token for GitHub API access inside container"
    echo "  IMAGE_TAG=...        Override the Docker image tag (default: ai-harness-e2e:local)"
    echo "  E2E_PLATFORM_TIMEOUT_SECONDS=...  Override per-platform timeout (default: 900)"
    echo ""
    echo "Examples:"
    echo "  $0                           # Tier 1 tests only"
    echo "  RUN_FULL_E2E=1 $0            # Tier 1 + 2"
    echo "  RUN_BACKUP_TESTS=1 $0         # Tier 1 + 3"
    echo "  RUN_FULL_E2E=1 RUN_BACKUP_TESTS=1 $0  # All tiers"
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
printf "${BLUE}[BUILD]${NC} Building image from e2e/Dockerfile\n"
printf "${BLUE}[BUILD]${NC} Image tag: %s\n" "$IMAGE_TAG"
printf "${BLUE}[BUILD]${NC} Project root: %s\n" "$PROJECT_ROOT"

if ! run_with_timeout docker build \
    -f "$SCRIPT_DIR/Dockerfile" \
    -t "$IMAGE_TAG" \
    "$PROJECT_ROOT" 2>&1; then
    printf "${RED}[BUILD]${NC} Build FAILED\n"
    exit 1
fi
printf "${GREEN}[BUILD]${NC} Image built successfully\n"

# ---------------------------------------------------------------------------
# Environment variable forwarding
# ---------------------------------------------------------------------------
ENV_FLAGS=""
[ "${RUN_FULL_E2E:-0}" = "1" ]      && ENV_FLAGS="$ENV_FLAGS -e RUN_FULL_E2E=1"
[ "${RUN_BACKUP_TESTS:-0}" = "1" ] && ENV_FLAGS="$ENV_FLAGS -e RUN_BACKUP_TESTS=1"
[ -n "${GITHUB_TOKEN:-}" ]           && ENV_FLAGS="$ENV_FLAGS -e GITHUB_TOKEN=$GITHUB_TOKEN"

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
printf "${YELLOW}[RUN]${NC}   Running e2e tests inside container\n"
echo ""

# shellcheck disable=SC2086
if run_with_timeout docker run --rm \
    --network host \
    $ENV_FLAGS \
    -v "$PROJECT_ROOT:/build" \
    "$IMAGE_TAG" \
    bash /build/e2e/e2e_test.sh 2>&1; then
    printf "${GREEN}[RUN]${NC}   All tests PASSED\n"
    exit 0
else
    printf "${RED}[RUN]${NC}   Tests FAILED\n"
    exit 1
fi
