"""Verify-report "clearly passing" heuristic.

A report clearly passes when it has at least one pass-signal line AND zero blocker
lines. The patterns below mirror the Go reference implementation exactly — this is
the trickiest contract in the package and small wording differences change the
outcome.
"""

from __future__ import annotations

import re

# Go's regexp engine (RE2) treats \b, \s, \d, \w as ASCII-only. Python's re
# defaults to Unicode semantics, so every pattern is compiled with re.ASCII to
# preserve byte-for-byte parity around non-ASCII characters (the emoji literals
# below are matched verbatim and are unaffected by the flag).
_ASCII = re.ASCII

# reportField parses an optionally-bulleted, optionally-bold "Label: value" line,
# capturing the label and the value.
_REPORT_FIELD = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\*\*)?([A-Za-z][A-Za-z\s-]*?)(?:\*\*)?\s*:\s*(.*)$", _ASCII
)

# passValue matches a value that, on its own, signals a pass.
_PASS_VALUE = re.compile(
    r"^(?:PASS|PASSED|PASS\s+WITH\s+WARNINGS|SUCCESS|SUCCESSFUL)$", re.I | _ASCII
)

# failValue matches a value that, on its own, signals a failure.
_FAIL_VALUE = re.compile(r"^(?:FAIL|FAILED|FAILING|FAILURE|BLOCKED|UNTESTED)$", re.I | _ASCII)

# glyphFailStatus matches a red-cross glyph followed by a fail keyword.
_GLYPH_FAIL_STATUS = re.compile(
    r"\u274c\s*(?:FAIL|FAILED|FAILING|FAILURE|BLOCKED|UNTESTED)\b", re.I | _ASCII
)

# passNegation matches "not passed"-style phrases or "pass: no" style denials.
_PASS_NEGATION = re.compile(
    r"\bnot\s+(?:pass|passed|passing|successful|complete|completed)\b"
    r"|\b(?:pass|passed|success|successful|complete|completed)\s*:\s*no\b",
    re.I | _ASCII,
)

# pendingWord matches outstanding-work markers.
_PENDING_WORD = re.compile(r"\b(?:TODO|PENDING)\b", re.I | _ASCII)

# benignValue matches values that, for an otherwise-blocking field, are safe.
_BENIGN_VALUE = re.compile(
    r"^(?:none|no|n/a|not\s+applicable|0\s+(?:failed|blockers?|critical|issues?))\.?$",
    re.I | _ASCII,
)

# failedCountPatterns capture a numeric failed count in either order.
_FAILED_COUNT_PATTERNS = [
    re.compile(r"\bfailed\s*:\s*(\d+)\b", re.I | _ASCII),
    re.compile(r"\b(\d+)\s+failed\b", re.I | _ASCII),
]

_BLOCKER_FIELDS = {
    "critical",
    "blocker",
    "blockers",
    "verificationblocker",
    "verificationblockers",
    "failure",
    "fail",
    "failed",
}
_VERDICT_FIELDS = {
    "verdict",
    "status",
    "result",
    "verification",
    "finalverdict",
    "build",
    "tests",
}


def report_is_clearly_passing(path: str) -> bool:
    """Read the verify report and report whether it clearly passes. An empty path
    or blank report is not passing. Any blocker line wins."""
    if not path:
        return False
    # errors="replace" mirrors Go's lossy string(bytes): invalid UTF-8 never raises.
    with open(path, encoding="utf-8", errors="replace") as handle:
        content = handle.read()
    if content.strip() == "":
        return False

    has_pass_signal = False
    for raw in content.split("\n"):
        line = raw.strip()
        if _line_has_blocker(line):
            return False
        if _line_has_pass_signal(line):
            has_pass_signal = True
    return has_pass_signal


def _line_has_blocker(line: str) -> bool:
    if line == "":
        return False
    if _PASS_NEGATION.search(line) or _PENDING_WORD.search(line):
        return True
    if _GLYPH_FAIL_STATUS.search(line):
        return True
    for pattern in _FAILED_COUNT_PATTERNS:
        match = pattern.search(line)
        if match is not None and match.group(1) != "0":
            return True
    field = _parse_report_field(line)
    if field is not None and _field_is_blocking(field[0], field[1]):
        return True
    return _FAIL_VALUE.search(_strip_markdown_signal(line)) is not None


def _field_is_blocking(label: str, value: str) -> bool:
    """Decide whether a "Label: value" field is a blocker. Blocker fields block
    unless their value is benign; verdict fields block when their value reads as a
    failure."""
    trimmed = value.strip()
    name = _normalize_field_name(label)
    if name in _BLOCKER_FIELDS:
        return not _value_is_benign(trimmed)
    if name in _VERDICT_FIELDS:
        return _FAIL_VALUE.search(_strip_markdown_signal(trimmed)) is not None
    return False


def _line_has_pass_signal(line: str) -> bool:
    if line == "":
        return False
    field = _parse_report_field(line)
    if field is not None and _PASS_VALUE.search(_strip_markdown_signal(field[1])) is not None:
        return True
    stripped = _strip_markdown_signal(line)
    return _PASS_VALUE.search(stripped) is not None or _equals_any_fold(
        stripped,
        "all checks passed",
        "all checks passed.",
        "ready for archive",
        "ready for archive.",
    )


def _parse_report_field(line: str) -> tuple[str, str] | None:
    match = _REPORT_FIELD.match(line)
    if match is None:
        return None
    return match.group(1), match.group(2)


def _value_is_benign(value: str) -> bool:
    """Report whether a blocker field's value is safe (empty, zero, none, "no
    blockers", etc.)."""
    value = _strip_markdown_signal(value).strip()
    if value == "" or value == "0":
        return True
    return _BENIGN_VALUE.search(value) is not None or value.lower() == "no blockers"


def _strip_markdown_signal(value: str) -> str:
    """Remove surrounding markdown emphasis and a leading status emoji so the
    underlying keyword can be matched."""
    value = value.strip()
    value = value.strip("*`_")
    value = value.strip()
    for prefix in ("\u2705", "\u274c", "\u26a0\ufe0f", "\u26a0"):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
    return value.strip()


def _normalize_field_name(value: str) -> str:
    """Lowercase a label and keep only its letters so that "Verification Blocker"
    and "verificationblocker" compare equal."""
    return "".join(ch for ch in value.lower() if "a" <= ch <= "z")


def _equals_any_fold(value: str, *candidates: str) -> bool:
    lowered = value.lower()
    return any(lowered == candidate.lower() for candidate in candidates)
