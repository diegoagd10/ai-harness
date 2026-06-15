"""install: copy every Config mapping, generate OpenCode extras, write manifest.

The orchestration is deliberately simple: walk the mappings, run the
``ops.install_one`` primitive, accumulate a Report and a manifest slice,
then (when OpenCode is selected) generate the command files and the
``opencode.json``. The manifest is written at the end so a partial failure
still records what DID land — that is what makes the late-failure path in
the CLI tests pass.
"""

from __future__ import annotations

import os

from .config import Config
from .generators import generate_commands, generate_opencode_json
from .harness import Harness
from .manifest import ManifestEntry, write_manifest
from .ops import Outcome, install_one


def install(cfg: Config) -> tuple[list[Outcome], list[ManifestEntry], str | None]:
    """Install every mapping in ``cfg``; return (report, entries, error).

    The ``error`` is a string message (not an exception) so the caller can
    decide whether to print and exit or surface a different exit code.
    The manifest is written with whatever entries succeeded, so an
    ``uninstall`` can clean up the partial install afterwards.
    """
    report: list[Outcome] = []
    entries: list[ManifestEntry] = []
    error: str | None = None
    for src, dest in cfg.mappings():
        try:
            outcome, owned = install_one(src, dest)
        except FileNotFoundError as err:
            error = str(err)
            report.append(
                Outcome(dest=str(dest), src=str(src), action="source missing")
            )
            continue
        except OSError as err:
            error = f"{dest}: {err}"
            continue
        report.append(outcome)
        entries.extend(owned)
    if cfg.wants(Harness.OPENCODE):
        command_dir = cfg.opencode_dir / "commands"
        try:
            command_outcomes = generate_commands(cfg.repo_dir, command_dir)
        except (FileNotFoundError, ValueError, OSError) as err:
            error = error or f"generate commands: {err}"
        else:
            for outcome in command_outcomes:
                report.append(
                    Outcome(
                        dest=str(outcome.dest),
                        src=str(outcome.src) if outcome.src else "",
                        action=outcome.action,
                    )
                )
                entries.append(
                    ManifestEntry(
                        dest=str(outcome.dest), source=str(outcome.src), kind="file"
                    )
                )
        try:
            json_outcome = generate_opencode_json(
                cfg.repo_dir, cfg.opencode_dir, os.environ.get("HOME", "")
            )
        except (FileNotFoundError, OSError) as err:
            error = error or f"generate opencode.json: {err}"
        else:
            report.append(
                Outcome(
                    dest=str(json_outcome.dest),
                    src=str(json_outcome.src) if json_outcome.src else "",
                    action=json_outcome.action,
                )
            )
            entries.append(
                ManifestEntry(
                    dest=str(json_outcome.dest), source=str(json_outcome.src), kind="file"
                )
            )
    write_manifest(cfg.opencode_dir, entries)
    return report, entries, error
