"""Harness package — core install/uninstall logic, no CLI.

Re-exports the public surface so callers import from the package root:
``from ai_harness.modules.harness import Target, InstallManifest, install_targets``.
"""

from ai_harness.modules.harness.models import InstallManifest, Target
from ai_harness.modules.harness.operations import install_targets, uninstall_targets

__all__ = ["Target", "InstallManifest", "install_targets", "uninstall_targets"]
