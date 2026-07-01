# syntax=docker/dockerfile:1.7
# tests-prompts/Dockerfile — carrier image for the prompt-test suite.
#
# Built and run by tests-prompts/docker-test.sh; not a public seam.
# Carries the opencode CLI + uv + python3 + jq on ubuntu:24.04 so the
# in-container runner can resolve the model API and run ai-harness.
#
# Source NOT COPYd at build time — the repo arrives via the host harness
# mount at /source-ro so any container writes die with the container.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system packages:
#   bash        — required by run.sh
#   curl        — needed by the opencode installer
#   jq          — JSON helpers for run.sh
#   python3     — csv.DictReader + the schema-aware extract_counts helper
#   ca-certificates — TLS for PyPI + opencode model API
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    jq \
    python3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Astral's fast Python package manager).
# Needed inside the container so run.sh can `uv tool install .` from /workspace.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Install the opencode CLI from the canonical installer.
# This is the binary run.sh invokes via `opencode run ...` per row.
RUN curl -fsSL https://opencode.ai/install | bash
ENV PATH="/root/.opencode/bin:${PATH}"

# Copy ONLY the runner scripts + CSV; repo source arrives via mount.
# Each Python helper listed here is invoked by run.sh at container
# runtime via an absolute /tests-prompts/<name>.py path, so any helper
# that run.sh calls MUST appear in this list or the suite explodes on
# `parse_csv: command not found` (or equivalent) before row 1 runs.
# If you add a new helper consumed by run.sh, add the COPY here too.
COPY tests-prompts/run.sh /tests-prompts/run.sh
COPY tests-prompts/cases.csv /tests-prompts/cases.csv
COPY tests-prompts/_extractor.py /tests-prompts/_extractor.py
COPY tests-prompts/parse_csv.py /tests-prompts/parse_csv.py
COPY tests-prompts/_dump_parse_trace.py /tests-prompts/_dump_parse_trace.py
RUN chmod +x /tests-prompts/run.sh \
    /tests-prompts/_extractor.py \
    /tests-prompts/parse_csv.py \
    /tests-prompts/_dump_parse_trace.py

# Default command runs the per-row loop. docker-test.sh may override.
CMD ["bash", "/tests-prompts/run.sh"]