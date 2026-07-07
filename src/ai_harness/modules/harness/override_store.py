"""Override-store helper — load, save, and deep-merge the shared override store.

The override store lives at ``home/.ai-harness/overrides.json`` and holds the
per-agent user model/effort overrides the set-models wizard writes and the
provider administrators read on every render. The store is NOT
provider-specific product behavior — it is shared ai-harness state, so the
helper lives outside the renderer module and is consumed both by provider
administrators and by the set-models wizard.

Public surface
--------------
OVERRIDES_REL        The path relative to ``home`` where the store lives.
load_override_store  Load the store from disk; missing file returns ``{}``,
                     malformed JSON propagates ``json.JSONDecodeError``.
save_override_store  Deep-merge ``payload`` into the existing store and write
                     it back atomically (pretty JSON, stable key ordering).
deep_merge           Recursively merge ``override`` over ``base``; neither
                     input is mutated; dicts merge key-by-key; scalars,
                     lists, and ``None`` values replace.

All other helpers (``_deep_merge`` inside ``renderers.py`` and friends) are
private to the renderer module and consume this module rather than
re-implement its semantics.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

#: Home-relative POSIX path of the override store.
OVERRIDES_REL = ".ai-harness/overrides.json"


def load_override_store(home: Path) -> dict:
    """Return the per-agent override store at ``home/.ai-harness/overrides.json``.

    Returns ``{}`` when the file is absent (no prior override). Malformed
    JSON is propagated as ``json.JSONDecodeError`` so the user can fix the
    file rather than silently rendering template defaults.
    """
    path = home / OVERRIDES_REL
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_override_store(home: Path, payload: dict) -> None:
    """Deep-merge *payload* into the existing override store and write it back.

    Existing entries for other agents, or for the same agent under
    different fields, are preserved — only the keys present in *payload*
    change. The write is atomic: an in-memory merge, then a single write
    to ``~/.ai-harness/overrides.json`` (the parent directory is created
    on demand). Malformed existing JSON is raised as-is (matching the
    loader's contract).

    The output is pretty JSON with stable key ordering
    (``indent=2, sort_keys=True``) so repeated writes are byte-identical
    and downstream diff tools stay quiet.
    """
    existing = load_override_store(home)
    merged = deep_merge(existing, payload)
    path = home / OVERRIDES_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def deep_merge(base: dict, override: dict) -> dict:
    """Return a fresh dict with *override* recursively merged over *base*.

    Dicts merge key-by-key (recursively); scalars, lists, and ``None`` in
    *override* replace those in *base*. Neither input is mutated; the
    returned dict (and any nested dicts inside it) are fresh copies, so
    callers cannot accidentally mutate the shared template state by
    holding onto the returned value.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            result[key] = deep_merge(base_value, value)
        else:
            result[key] = copy.deepcopy(value)
    return result


__all__ = [
    "OVERRIDES_REL",
    "deep_merge",
    "load_override_store",
    "save_override_store",
]
