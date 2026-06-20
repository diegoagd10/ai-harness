# syntax=docker/dockerfile:1.7
# Base image: Debian "bookworm-slim" with Python 3.12 and the `uv` binary
# already installed. Provides uv + the cli source; the e2e suite runs via
# ``uv run inv test`` which exercises the full install/reinstall/uninstall
# lifecycle.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set the working directory for subsequent instructions (created if missing).
WORKDIR /build

# Copy the project source from the build context (repo root) into the image
# at /build.
COPY . /build

# Install dev dependencies (invoke, pytest, etc.) so ``uv run inv test`` works.
# The uv cache is mounted as a build cache so wheel downloads persist across
# builds, and ``uv sync`` is retried because PyPI fetches inside the build
# network occasionally time out.
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    UV_HTTP_TIMEOUT=180 \
    bash -c 'set -e; \
      for attempt in 1 2 3 4 5; do \
        uv sync --group dev && break; \
        echo "uv sync attempt $attempt/5 failed, retrying in $((attempt*10))s..."; \
        sleep $((attempt*10)); \
      done'

# ``uv tool install`` puts executables in ~/.local/bin. The container runs as
# root, so that's /root/.local/bin — prepend it to PATH so ``ai-harness`` is
# found once the suite provisions it.
ENV PATH="/root/.local/bin:${PATH}"

# Default command: run the full e2e suite via Invoke.
CMD ["uv", "run", "inv", "test"]
