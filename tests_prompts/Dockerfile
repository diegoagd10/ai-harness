# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /work

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git npm \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g opencode-ai

COPY . /work

WORKDIR /work/tests_prompts

CMD ["python", "implementor_eval.py"]
