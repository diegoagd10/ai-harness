"""Shared layout used by every eval. Eval-specific paths live in the eval
module (e.g. implementor_eval.py), not here."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parents[0]

ARTIFACTS = PROJECT_ROOT / "artifacts"
RESOURCES = PROJECT_ROOT / "resources"

MODEL = os.environ.get("OPENCODE_PROMPT_EVAL_MODEL", "minimax/MiniMax-M2.7")
