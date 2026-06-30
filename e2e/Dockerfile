# syntax=docker/dockerfile:1.7
# Dockerfile — isolated test image for ai-harness e2e suite
# Built and run by e2e/docker-test.sh; not a public seam.
# Mirrors: gentle-ai/e2e/Dockerfile.ubuntu pattern
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system packages: bash, uv, jq, python3.
# bash: required for shell test scripts.
# uv: package manager for Python tool installation.
# jq: JSON manipulation for assertion helpers.
# python3: available for assert_valid_json fallback.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    jq \
    python3 \
    python3-venv \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Astral's fast Python package manager).
# Mirrors: gentle-ai installs Go; ai-harness needs uv for Python tool install.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy the full project source into the image at /build.
COPY . /build

# Ensure e2e test scripts are executable.
RUN chmod +x /build/e2e/e2e_test.sh /build/e2e/lib.sh

# Pre-install ai-harness as a tool so e2e tests can invoke it directly.
# uv tool install . requires being in the package directory.
WORKDIR /build
ENV UV_TOOL_DIR="/root/.local/share/uv/tools/ai-harness"
ENV UV_TOOL_BIN_DIR="/root/.local/bin"
RUN uv tool install . --python python3

# Default command: run the canonical e2e test suite.
# docker-test.sh overrides this with an explicit bash + args invocation.
CMD ["bash", "/build/e2e/e2e_test.sh"]
