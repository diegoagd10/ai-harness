"""Commit-format helpers — resolver shared by the change orchestrator.

This package owns the read side of the orchestrator-injects pattern
(design §Deep modules). The orchestrator calls
:func:`resolve_commit_format` to inline the canonical per-task commit
format into the implementor delegation block. The implementor never
imports this package — the dependency is one-way (orchestrator ->
resolver).
"""

from ai_harness.modules.commit.format_resolver import CommitFormatError, resolve_commit_format

__all__ = ["CommitFormatError", "resolve_commit_format"]
