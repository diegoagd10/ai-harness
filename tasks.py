"""Root-level Invoke tasks file — thin wrapper delegating to the canonical e2e suite.

Canonical e2e entry: ./e2e/docker-test.sh
Invoke is a thin shim for backward compatibility only.
"""

from invoke import Collection, task


@task(default=True)
def test(ctx) -> None:
    """Run the e2e suite inside an isolated Docker container.

    Equivalent to running ./e2e/docker-test.sh directly.
    """
    ctx.run("./e2e/docker-test.sh")


ns = Collection(test)
