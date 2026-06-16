"""Root-level Invoke tasks file — delegates to the e2e suite.

This exists so ``uv run inv test`` (and per-category variants) work from
both the repo root and the Docker container without ``-r`` flags.
"""

from invoke import Collection

from e2e.tasks import install, sdd_continue, sdd_status, test, tool_lifecycle, uninstall

ns = Collection(
    install,
    uninstall,
    sdd_status,
    sdd_continue,
    tool_lifecycle,
    test,
)
