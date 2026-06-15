"""Harness identifier and selection parsers.

Defines the stable, ordered set of supported harnesses (opencode, claude,
copilot) and the parsers that turn human-typed tokens and comma-separated
lists into a validated selection. The CLI depends only on the public parse
functions; the underlying string values are an implementation detail.
"""

from __future__ import annotations

import pytest

from ai_harness.install.harness import (
    ALL_HARNESSES,
    Harness,
    parse_harness_list,
    parse_harness_token,
    parse_selection_line,
)

# --- Harness enum -----------------------------------------------------------


def test_all_harnesses_has_three_in_stable_order() -> None:
    assert ALL_HARNESSES == (Harness.OPENCODE, Harness.CLAUDE, Harness.COPILOT)


def test_harness_values_are_lowercase_strings() -> None:
    # The wire contract (Go-compat) expects lowercase harness names; enforce it.
    assert Harness.OPENCODE.value == "opencode"
    assert Harness.CLAUDE.value == "claude"
    assert Harness.COPILOT.value == "copilot"


# --- parse_harness_token ----------------------------------------------------


def test_parse_harness_token_accepts_names() -> None:
    assert parse_harness_token("opencode") is Harness.OPENCODE
    assert parse_harness_token("claude") is Harness.CLAUDE
    assert parse_harness_token("copilot") is Harness.COPILOT


def test_parse_harness_token_accepts_numeric_aliases() -> None:
    # 1=opencode, 2=claude, 3=copilot (matches the prompt's listing order).
    assert parse_harness_token("1") is Harness.OPENCODE
    assert parse_harness_token("2") is Harness.CLAUDE
    assert parse_harness_token("3") is Harness.COPILOT


def test_parse_harness_token_is_case_insensitive() -> None:
    assert parse_harness_token("Claude") is Harness.CLAUDE
    assert parse_harness_token("OPENCODE") is Harness.OPENCODE


def test_parse_harness_token_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="bogus"):
        parse_harness_token("bogus")


def test_parse_harness_token_rejects_empty() -> None:
    with pytest.raises(ValueError):
        parse_harness_token("")


# --- parse_harness_list -----------------------------------------------------


def test_parse_harness_list_single_name() -> None:
    assert parse_harness_list("claude") == [Harness.CLAUDE]


def test_parse_harness_list_comma_separated() -> None:
    assert parse_harness_list("claude,copilot") == [Harness.CLAUDE, Harness.COPILOT]


def test_parse_harness_list_with_spaces() -> None:
    assert parse_harness_list("claude, copilot") == [Harness.CLAUDE, Harness.COPILOT]


def test_parse_harness_list_dedupes_repeats() -> None:
    assert parse_harness_list("claude,claude,copilot") == [Harness.CLAUDE, Harness.COPILOT]


def test_parse_harness_list_skips_empty_tokens() -> None:
    # Trailing comma / repeated spaces produce empty tokens; ignore them.
    assert parse_harness_list("claude, ,copilot,") == [Harness.CLAUDE, Harness.COPILOT]


def test_parse_harness_list_rejects_unknown_token() -> None:
    with pytest.raises(ValueError, match="bogus"):
        parse_harness_list("claude,bogus")


def test_parse_harness_list_rejects_empty_input() -> None:
    # Empty / whitespace-only must raise so callers can distinguish "not
    # provided" from "provided but empty".
    with pytest.raises(ValueError):
        parse_harness_list("")
    with pytest.raises(ValueError):
        parse_harness_list("   ")


# --- parse_selection_line ----------------------------------------------------


def test_parse_selection_line_blank_returns_all() -> None:
    assert parse_selection_line("") == list(ALL_HARNESSES)
    assert parse_selection_line("   \n") == list(ALL_HARNESSES)


def test_parse_selection_line_all_keyword_returns_all() -> None:
    assert parse_selection_line("all") == list(ALL_HARNESSES)
    assert parse_selection_line("ALL") == list(ALL_HARNESSES)


def test_parse_selection_line_numbers_only() -> None:
    assert parse_selection_line("2") == [Harness.CLAUDE]


def test_parse_selection_line_numbers_comma_separated() -> None:
    assert parse_selection_line("1,3") == [Harness.OPENCODE, Harness.COPILOT]


def test_parse_selection_line_mixed_numbers_and_names() -> None:
    assert parse_selection_line("1, claude") == [Harness.OPENCODE, Harness.CLAUDE]


def test_parse_selection_line_rejects_bad_token() -> None:
    with pytest.raises(ValueError, match="bogus"):
        parse_selection_line("claude, bogus")
