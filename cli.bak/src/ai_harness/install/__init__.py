"""ai-harness installer package (migration slice).

This package owns the Python install/uninstall pipeline that replaces the Go
``internal/install`` + ``internal/commands`` + ``internal/opencode`` packages.
The Go code is preserved as a fallback for one more iteration; once Python
e2e passes, the Go install path is retired.
"""

from __future__ import annotations
