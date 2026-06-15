# Base image: Debian "bookworm-slim" with Python 3.12 and the `uv` binary
# already installed. Provides uv + the cli source; e2e_test.sh drives the
# actual uv tool install / reinstall / uninstall lifecycle.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set the working directory for subsequent instructions (created if missing).
WORKDIR /build

# Copy the project source from the build context (repo root) into the image
# at /build. AGENTS.md and skills/ live inside src/ai_harness/resources as package
# data, so a non-editable `uv tool install` carries them along.
COPY . /build

# Copy the e2e test script alongside it.
COPY e2e/e2e_test.sh /e2e_test.sh

# `uv tool install` puts executables in ~/.local/bin. The container runs as
# root, so that's /root/.local/bin — prepend it to PATH so `ai-harness` is
# found once e2e_test.sh installs it.
ENV PATH="/root/.local/bin:${PATH}"

# Default command when the container runs: execute the e2e test script.
CMD ["/e2e_test.sh"]
