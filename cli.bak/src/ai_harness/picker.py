"""Rich interactive multi-select harness picker.

The picker is split in two layers so tests can drive it deterministically
without a real TTY:

- :func:`pick_harnesses` is a pure function: it takes a sequence of key
  events and returns a :class:`PickerResult`. Tests use it to assert the
  navigation/toggle/confirm/cancel semantics.
- :func:`prompt_harnesses` is the real TTY loop: it reads one key at a
  time from stdin in raw mode and delegates to :func:`pick_harnesses`.
  It is not unit-tested; coverage of the navigation logic lives in the
  pure layer.
"""

from __future__ import annotations

import os
import select
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from rich.console import Console

from .install.harness import ALL_HARNESSES, Harness

PICKER_SELECTED = "selected"
PICKER_EMPTY = "empty"
PICKER_CANCELLED = "cancelled"

# The full set of keys the picker understands. Arrow keys arrive as the
# three-byte CSI sequence ESC [ A/B/C/D; we test the two we use (up/down).
KEY_DOWN = ("j", "\x1b[B")
KEY_UP = ("k", "\x1b[A")
KEY_TOGGLE = (" ",)
KEY_CONFIRM = ("\r", "\n")
KEY_CANCEL = ("\x1b",)

_PROMPT_TITLE = "Select agents/harnesses to install"
_UNINSTALL_PROMPT_TITLE = "Select agents/harnesses to uninstall"
_INSTRUCTIONS = (
    "Use ↑/↓ or j/k to move · Space to toggle · Enter to confirm · Esc to cancel"
)
_INSTALLED_HINT = "(installed)"
_CHECKED = "[x]"
_UNCHECKED = "[ ]"
_CURSOR = ">"


@dataclass(frozen=True)
class PickerResult:
    """The outcome of a picker run.

    ``kind`` is one of :data:`PICKER_SELECTED` / :data:`PICKER_EMPTY` /
    :data:`PICKER_CANCELLED`. ``selection`` is non-empty only for
    SELECTED; EMPTY means the user confirmed with no items checked;
    CANCELLED means the user pressed Escape.
    """

    kind: str
    selection: tuple[Harness, ...] = ()


def _read_arrow_or_esc(stream: Iterable[str]) -> str:
    """Consume the trailing bytes of a CSI sequence if the first byte is ESC.

    Arrow keys arrive as ESC [ A/B/C/D. We only need up/down; anything
    else is treated as a single ESC (cancel) so the picker fails closed
    when the user presses an unknown key.
    """
    iterator = iter(stream)
    try:
        first = next(iterator)
    except StopIteration:
        return ""
    if first != "\x1b":
        return first
    try:
        second = next(iterator)
    except StopIteration:
        return "\x1b"
    if second != "[":
        # Bare ESC or ESC followed by something other than '[': treat as cancel.
        return "\x1b"
    try:
        third = next(iterator)
    except StopIteration:
        return "\x1b"
    return first + second + third


def _move(cursor: int, delta: int, length: int) -> int:
    """Clamp the cursor inside ``[0, length)`` after a relative move."""
    return max(0, min(length - 1, cursor + delta))


def _format_line(
    cursor: int,
    index: int,
    harness: Harness,
    selected: set[Harness],
    installed: set[Harness],
) -> str:
    """Render one picker row: cursor + checkbox + harness + installed hint."""
    marker = _CURSOR if cursor == index else " "
    check = _CHECKED if harness in selected else _UNCHECKED
    hint = f" {_INSTALLED_HINT}" if harness in installed else ""
    return f" {marker} {check} {harness.value}{hint}"


def _render(
    console: Console,
    harnesses: Sequence[Harness],
    cursor: int,
    selected: set[Harness],
    installed: set[Harness],
    title: str,
) -> None:
    """Redraw the picker menu to ``console``.

    We render a small fixed-shape block: title, instructions, one line
    per harness, and a blank trailing line so the cursor can be redrawn
    cleanly. Rich handles the escape sequences; we only supply content.
    """
    console.print(title)
    console.print(_INSTRUCTIONS)
    for index, harness in enumerate(harnesses):
        console.print(
            _format_line(cursor, index, harness, selected, installed),
        )
    console.print("")


def pick_harnesses(
    harnesses: Sequence[Harness],
    keys: Iterable[str],
    console: Console,
    *,
    installed: Sequence[Harness] = (),
    title: str = _PROMPT_TITLE,
    pre_tokenized: bool = False,
) -> PickerResult:
    """Drive the picker over a key sequence; return the result.

    ``keys`` yields one entry per key event. When *pre_tokenized* is False
    (the default), entries may be raw bytes and :func:`_read_arrow_or_esc`
    handles CSI sequence assembly. When *pre_tokenized* is True, each entry
    is already a complete logical key (e.g. ``"\\x1b[B"`` for down-arrow or
    ``"\\x1b"`` for bare ESC) and is consumed as-is with no further reads
    — this avoids blocking on ``os.read`` when the source has already
    decided the token is complete.
    """
    selected: set[Harness] = set()
    cursor = 0
    installed_set = set(installed)
    key_stream = iter(keys)
    while True:
        _render(console, harnesses, cursor, selected, installed_set, title)
        try:
            raw = next(key_stream) if pre_tokenized else _read_arrow_or_esc(key_stream)
        except StopIteration:
            return PickerResult(kind=PICKER_EMPTY)
        if raw in KEY_DOWN:
            cursor = _move(cursor, +1, len(harnesses))
            continue
        if raw in KEY_UP:
            cursor = _move(cursor, -1, len(harnesses))
            continue
        if raw in KEY_TOGGLE:
            current = harnesses[cursor]
            if current in selected:
                selected.remove(current)
            else:
                selected.add(current)
            continue
        if raw in KEY_CONFIRM:
            if not selected:
                return PickerResult(kind=PICKER_EMPTY)
            # Stable order: the order harnesses were listed, so the CLI
            # gets a predictable Install sequence regardless of toggle order.
            ordered = tuple(h for h in harnesses if h in selected)
            return PickerResult(kind=PICKER_SELECTED, selection=ordered)
        if raw in KEY_CANCEL:
            return PickerResult(kind=PICKER_CANCELLED)
        # Unknown key: ignore and re-prompt.


def prompt_harnesses(
    console: Console,
    *,
    installed: Sequence[Harness] = (),
    title: str = _PROMPT_TITLE,
) -> PickerResult:
    """Run the real TTY picker; read keys from stdin in raw mode.

    POSIX-only: termios/tty are unavailable on Windows. The function
    degrades to :class:`RuntimeError` when the platform cannot provide
    raw mode, telling the caller to pass ``--harness`` instead.
    """
    if not sys.stdin.isatty():
        raise RuntimeError("prompt_harnesses requires a TTY; use --harness instead")
    if os.name != "posix":
        raise RuntimeError("prompt_harnesses is POSIX-only; use --harness instead")
    import termios
    import tty

    def _key_source() -> Iterable[str]:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = os.read(fd, 1).decode("utf-8", errors="ignore")
                if ch != "\x1b":
                    yield ch
                    continue
                # ESC received — peek for CSI follow-up bytes (arrow keys).
                # Use a short timeout so bare ESC cancels promptly instead
                # of blocking indefinitely on os.read(fd, 1).
                if select.select([fd], [], [], 0.05)[0]:
                    seq = ch
                    # Drain any remaining bytes of the escape sequence.
                    while select.select([fd], [], [], 0.01)[0]:
                        seq += os.read(fd, 1).decode("utf-8", errors="ignore")
                    yield seq
                else:
                    yield ch  # bare ESC
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    # Defer raw-mode teardown to the source; pick_harnesses drives the loop
    # and the generator's finally restores the tty when the caller breaks.
    return pick_harnesses(
        list(ALL_HARNESSES),
        _key_source(),
        console,
        installed=installed,
        title=title,
        pre_tokenized=True,
    )
