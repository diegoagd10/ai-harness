"""Root-level Invoke tasks file — delegates to the e2e suite.

This exists so ``uv run inv test`` (and per-category variants) work from
both the repo root and the Docker container without ``-r`` flags.
"""

from e2e.tasks import (
    install,
    test,
    uninstall,
)
from invoke import Collection

ns = Collection(
    install,
    uninstall,
    test,
)
