FROM node:22-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
  git \
  curl \
  jq \
  && rm -rf /var/lib/apt/lists/*

# TODO: install your issue tracker's CLI here. See .sandcastle/SETUP_ISSUE_TRACKER.md

# Build-args for UID/GID alignment: sandcastle docker build-image
# defaults these to the host user's UID/GID so image-built files
# and bind-mounted files share an owner without runtime chown.
ARG AGENT_UID=1000
ARG AGENT_GID=1000

# Rename the base image's "node" user to "agent" and align UID/GID.
RUN groupmod -o -g $AGENT_GID node && usermod -o -u $AGENT_UID -g $AGENT_GID -d /home/agent -m -l agent node

USER ${AGENT_UID}:${AGENT_GID}

WORKDIR /home/agent

# Install pnpm package manager.
# SHELL is set to bash and ~/.bashrc is touched because the install script
# needs a shell config file to write the PATH export into — in a Docker RUN
# the agent user has no profile by default, which makes the script abort
# with ERR_PNPM_NO_SHELL_CONFIG. We don't rely on the profile edit anyway;
# PATH is set via ENV below.
ENV SHELL=/bin/bash
RUN touch ~/.bashrc && curl -fsSL https://get.pnpm.io/install.sh | sh -

# The install script adds pnpm to the shell profile; expose it to
# subsequent RUN commands and the runtime PATH explicitly.
ENV PNPM_HOME="/home/agent/.local/share/pnpm"
ENV PATH="${PNPM_HOME}/bin:${PATH}"

# Install OpenCode CLI and Claude Code globally via pnpm.
# --allow-build whitelists opencode-ai's postinstall (pnpm 10+ blocks
# postinstall by default for supply-chain safety). opencode-ai needs its
# postinstall.mjs to install its native binary; without it the CLI aborts
# at startup with "postinstall script was not run".
RUN pnpm add -g --allow-build=opencode-ai opencode-ai@latest @anthropic-ai/claude-code@latest

# In worktree sandbox mode, Sandcastle bind-mounts the git worktree at ${SANDBOX_REPO_DIR}
# and overrides the working directory to ${SANDBOX_REPO_DIR} at container start.
# Structure your Dockerfile so that ${SANDBOX_REPO_DIR} can serve as the project root.
ENTRYPOINT ["sleep", "infinity"]
