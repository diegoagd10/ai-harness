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

import io
import sys

from rich.console import Console

from ai_harness.install.harness import ALL_HARNESSES, Harness
from ai_harness.picker import (
    PICKER_CANCELLED,
    PICKER_EMPTY,
    PICKER_SELECTED,
    PickerResult,
    pick_harnesses,
    prompt_harnesses,
)


def _console() -> Console:
    return Console(file=io.StringIO(), force_terminal=False, width=80)


# --- PickerResult ---------------------------------------------------------


def test_picker_result_selected_carries_selection() -> None:
    result = PickerResult(kind=PICKER_SELECTED, selection=(Harness.CLAUDE,))
    assert result.kind == PICKER_SELECTED
    assert result.selection == (Harness.CLAUDE,)


def test_picker_result_empty_has_no_selection() -> None:
    result = PickerResult(kind=PICKER_EMPTY)
    assert result.kind == PICKER_EMPTY
    assert result.selection == ()


# --- Navigation -----------------------------------------------------------


def test_picker_initial_state_is_first_item_unselected() -> None:
    # No keys pressed: the picker must not return a result; it is waiting
    # for input. We use a key that means "do nothing" to break out — but
    # since no such key exists, the test simply asserts the picker still
    # has not produced a result. We confirm by sending Enter with no
    # selection toggled.
    keys = iter(["\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_EMPTY


def test_picker_j_moves_to_next_harness() -> None:
    # j (down) then space (toggle) then enter: should select harness[1].
    keys = iter(["j", " ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_SELECTED
    assert result.selection == (Harness.CLAUDE,)


def test_picker_k_moves_to_previous_harness() -> None:
    # j then k returns to harness[0]; toggle + confirm.
    keys = iter(["j", "k", " ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_SELECTED
    assert result.selection == (Harness.OPENCODE,)


def test_picker_down_arrow_moves_to_next() -> None:
    keys = iter(["\x1b[B", " ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.selection == (Harness.CLAUDE,)


def test_picker_up_arrow_moves_to_previous() -> None:
    keys = iter(["\x1b[B", "\x1b[A", " ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.selection == (Harness.OPENCODE,)


def test_picker_k_at_top_stays_at_top() -> None:
    # Cannot go above the first item.
    keys = iter(["k", " ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.selection == (Harness.OPENCODE,)


def test_picker_j_at_bottom_stays_at_bottom() -> None:
    # 2 j presses past the end; the cursor should still be on the last item.
    keys = iter(["j", "j", "j", "j", " ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.selection == (Harness.COPILOT,)


# --- Toggling -------------------------------------------------------------


def test_picker_space_toggles_selection_on() -> None:
    keys = iter([" ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.selection == (Harness.OPENCODE,)


def test_picker_space_toggles_selection_off() -> None:
    # Toggle opencode on, then off again; confirm with nothing selected.
    keys = iter([" ", " ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_EMPTY


def test_picker_selects_multiple_harnesses() -> None:
    # Toggle opencode, j, toggle claude, j, toggle copilot, confirm.
    keys = iter([" ", "j", " ", "j", " ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_SELECTED
    assert result.selection == ALL_HARNESSES


# --- Confirm / cancel -----------------------------------------------------


def test_picker_enter_with_no_selection_returns_empty() -> None:
    keys = iter(["\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_EMPTY
    assert result.selection == ()


def test_picker_escape_cancels() -> None:
    keys = iter([" ", "\x1b"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_CANCELLED
    assert result.selection == ()


def test_picker_escape_immediately_cancels() -> None:
    keys = iter(["\x1b"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_CANCELLED


# --- Installed hints ------------------------------------------------------


# --- Byte-by-byte TTY simulation (regression for ESC blocking) ----------


def test_picker_byte_by_byte_arrow_down_moves_to_next() -> None:
    """CSI sequence delivered byte-by-byte (real TTY behaviour)."""
    keys = iter(["\x1b", "[", "B", " ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_SELECTED
    assert result.selection == (Harness.CLAUDE,)


def test_picker_byte_by_byte_escape_cancels() -> None:
    """Bare ESC as a single byte must cancel without blocking."""
    keys = iter(["\x1b"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_CANCELLED


def test_picker_byte_by_byte_escape_after_toggle_cancels() -> None:
    """Toggle + bare ESC byte-by-byte must cancel."""
    keys = iter([" ", "\x1b"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.kind == PICKER_CANCELLED


def test_picker_byte_by_byte_up_arrow_moves_to_previous() -> None:
    keys = iter(["\x1b", "[", "B", "\x1b", "[", "A", " ", "\r"])
    result = pick_harnesses(ALL_HARNESSES, keys, _console())
    assert result.selection == (Harness.OPENCODE,)


# --- Tokenized source regression (bare ESC must not re-read) ---------


def test_tokenized_bare_escape_does_not_reread() -> None:
    """Bare ESC from a pre-tokenized source must cancel without re-reading.

    _read_arrow_or_esc treats single-byte \\x1b as the start of a
    CSI sequence and calls next(iterator) again to look for [.  With a
    real TTY _key_source generator that yields already-tokenized keys,
    that second read goes back to os.read(fd, 1) and blocks until
    another key arrives. This test uses a custom iterator class whose
    __next__ raises RuntimeError on any second call, proving the
    pre_tokenized path avoids the blocking re-read.
    """

    class _SingleEsc:
        """Iterator that yields ``\\x1b`` once, then raises on any second read."""

        def __init__(self) -> None:
            self._called = False

        def __next__(self) -> str:
            if self._called:
                raise RuntimeError(
                    "Unexpected second read after bare ESC — "
                    "would hang in real TTY"
                )
            self._called = True
            return "\x1b"

        def __iter__(self) -> "_SingleEsc":
            return self

    result = pick_harnesses(
        ALL_HARNESSES,
        _SingleEsc(),
        _console(),
        pre_tokenized=True,
    )
    assert result.kind == PICKER_CANCELLED


def test_tokenized_csi_arrow_still_works() -> None:
    """Pre-tokenized CSI down-arrow must move cursor as before."""
    result = pick_harnesses(
        ALL_HARNESSES,
        iter(["\x1b[B", " ", "\r"]),
        _console(),
        pre_tokenized=True,
    )
    assert result.kind == PICKER_SELECTED
    assert result.selection == (Harness.CLAUDE,)


def test_tokenized_escape_after_toggle_cancels() -> None:
    """Toggle + pre-tokenized bare ESC must cancel."""
    result = pick_harnesses(
        ALL_HARNESSES,
        iter([" ", "\x1b"]),
        _console(),
        pre_tokenized=True,
    )
    assert result.kind == PICKER_CANCELLED


def test_picker_renders_installed_marker(tmp_path) -> None:
    # When a caller marks a harness as installed, the picker must render
    # the "(installed)" hint next to it. We assert the hint is present in
    # the console output.
    console = _console()
    keys = iter(["\x1b"])
    pick_harnesses(
        ALL_HARNESSES,
        keys,
        console,
        installed=(Harness.CLAUDE,),
    )
    rendered = console.file.getvalue()  # type: ignore[attr-defined]
    assert "installed" in rendered.lower()


def test_prompt_harnesses_wires_pre_tokenized_true(
    monkeypatch,
) -> None:
    """prompt_harnesses() must pass pre_tokenized=True to pick_harnesses().

    Monkeypatches pick_harnesses to capture the pre_tokenized kwarg and
    return a fixed result.  Also monkeypatches sys.stdin.isatty to return
    True so prompt_harnesses does not raise RuntimeError early.

    The internal _key_source() generator is never consumed because the
    monkeypatched pick_harnesses returns immediately — no real TTY
    operations execute.
    """
    import ai_harness.picker as picker_mod

    captured: dict[str, bool | None] = {"pre_tokenized": None}

    def _fake_pick(*args: object, **kwargs: object) -> PickerResult:
        captured["pre_tokenized"] = kwargs.get("pre_tokenized")  # type: ignore[assignment]
        return PickerResult(kind=PICKER_SELECTED, selection=(Harness.CLAUDE,))

    monkeypatch.setattr(picker_mod, "pick_harnesses", _fake_pick)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    result = prompt_harnesses(_console())

    assert captured["pre_tokenized"] is True, (
        f"Expected pre_tokenized=True, got {captured['pre_tokenized']}"
    )
    assert result.kind == PICKER_SELECTED
