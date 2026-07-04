# pylint: disable=duplicate-code
"""Unit tests for the set-models wizard pure helpers and CLI arg validation.

Behavioural tests for the data-prep layer (``pure`` module) and the typer
adapter (``set_models`` command). The interactive questionary/rich shell
is intentionally untested — it is a thin adapter with no business logic.

Pure helpers covered
--------------------
- Fixed Claude model and effort sets are exact, in the right order.
- Agent list excludes the orchestrator (the Claude skill).
- Picker-row builders mark the current value, leave others unmarked.
- Confirmation rows render ``agent: model / effort``.
- Override-store writer deep-merges over the existing store atomically.
- CLI ``-o`` arg parser rejects missing and multiple Agent CLIs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from ai_harness.commands import parse_agent_clis
from ai_harness.main import app
from ai_harness.modules.harness import AgentCli
from ai_harness.modules.harness.renderers import (
    _load_override_store,
    write_override_store,
)
from ai_harness.modules.wizard.pure import (
    AgentMode,
    ModelSelection,
    align_label_rows,
    build_agent_list_rows,
    build_confirmation_rows,
    build_effort_picker_rows,
    build_model_picker_rows,
    build_opencode_model_picker_rows,
    build_opencode_override_payload,
    build_override_payload,
    claude_efforts,
    claude_models,
    claude_wizard_agents,
    format_selection_label,
    join_opencode_catalog,
    opencode_change_agents,
    opencode_efforts,
    opencode_model_is_reasoning,
    parse_agent_mode,
)

if TYPE_CHECKING:
    pass

runner = CliRunner()

OVERRIDES_REL = ".ai-harness/overrides.json"


# ---------------------------------------------------------------------------
# parse_agent_clis — CLI arg parsing (the set_models command enforces len == 1)
# ---------------------------------------------------------------------------


def test_parse_agent_clis_accepts_valid_name() -> None:
    """A single known agent CLI is parsed verbatim."""
    assert parse_agent_clis("claude") == [AgentCli.CLAUDE]


def test_parse_agent_clis_strips_whitespace() -> None:
    """Surrounding whitespace is stripped from the input."""
    assert parse_agent_clis("  claude  ") == [AgentCli.CLAUDE]


def test_parse_agent_clis_returns_empty_for_blank() -> None:
    """An empty / whitespace-only string returns an empty list (caller decides)."""
    assert parse_agent_clis("") == []
    assert parse_agent_clis("   ") == []


def test_parse_agent_clis_accepts_multiple_via_comma() -> None:
    """Comma-separated input parses to a list — the set_models command rejects len != 1."""
    assert parse_agent_clis("claude,opencode") == [AgentCli.CLAUDE, AgentCli.OPENCODE]


# ---------------------------------------------------------------------------
# Fixed Claude sets — the wizard's vocabulary lives in the pure module
# ---------------------------------------------------------------------------


def test_claude_models_is_the_fixed_set() -> None:
    """Claude model picker offers exactly opus/sonnet/haiku/fable/inherit in that order."""
    assert claude_models() == ("opus", "sonnet", "haiku", "fable", "inherit")


def test_claude_efforts_is_the_fixed_set() -> None:
    """Claude effort picker offers low/medium/high/xhigh/max in that order."""
    assert claude_efforts() == ("low", "medium", "high", "xhigh", "max")


def test_claude_wizard_agents_includes_all_nine() -> None:
    """The Claude wizard presents all 9 change agents including the orchestrator."""
    assert claude_wizard_agents() == (
        "change-orchestrator",
        "change-explorer",
        "change-implementor",
        "change-validator",
        "change-archiver",
        "change-design",
        "change-propose",
        "change-specs",
        "change-tasks",
    )


# ---------------------------------------------------------------------------
# Fixed OpenCode vocabulary — the wizard's vocabulary lives in the pure module
# ---------------------------------------------------------------------------


def test_opencode_efforts_is_the_reasoning_effort_set() -> None:
    """OpenCode's ``reasoningEffort`` values are the fixed (low, medium, high) set."""
    assert opencode_efforts() == ("low", "medium", "high")


# ---------------------------------------------------------------------------
# Change-agent vocabulary + AgentMode parser — set-models -a change branch
# ---------------------------------------------------------------------------


def test_opencode_change_agents_returns_eight_change_agents() -> None:
    """The change-agent set is exactly the eight named agents, orchestrator first.

    Mirrors ``test_claude_wizard_agents_includes_all_nine``:
    the orchestrator leads because on OpenCode it is a primary agent
    carrying a model and effort (not a skill). Order is intentional and
    pinned — a future rename / re-order is a deliberate design change,
    not a typo fix.
    """
    assert opencode_change_agents() == (
        "change-orchestrator",
        "change-explorer",
        "change-implementor",
        "change-validator",
        "change-archiver",
        "change-propose",
        "change-design",
        "change-specs",
        "change-tasks",
    )


def test_opencode_change_agents_returns_same_tuple_object_each_call() -> None:
    """The accessor returns the same tuple object on every call (identity-stable).

    The wizard's dispatcher reads the agent tuple at the seam; passing
    the same object down (instead of fresh tuples each call) keeps the
    seam's reference stable for any future memoisation / debug logging.
    """
    assert opencode_change_agents() is opencode_change_agents()


def test_parse_agent_mode_accepts_change() -> None:
    """``parse_agent_mode`` round-trips the only valid lowercase value."""
    assert parse_agent_mode("change") == AgentMode.CHANGE
    # StrEnum values compare equal to raw strings — keeps downstream == / Choice(value=...) working.
    assert parse_agent_mode("change") == "change"


def test_parse_agent_mode_rejects_loop() -> None:
    """``"loop"`` is no longer a valid value and raises ValueError."""
    with pytest.raises(ValueError) as excinfo:
        parse_agent_mode("loop")

    message = str(excinfo.value).lower()
    assert "change" in message
    assert "loop" in message  # the rejected value is in the message so the user sees what was wrong


def test_parse_agent_mode_rejects_unknown_value() -> None:
    """Unknown values raise ValueError naming the valid set explicitly."""
    with pytest.raises(ValueError) as excinfo:
        parse_agent_mode("bogus")

    message = str(excinfo.value).lower()
    assert "change" in message
    assert "bogus" in message  # the rejected value is in the message so the user sees what was wrong


def test_parse_agent_mode_rejects_uppercase_strict_lowercase() -> None:
    """Uppercase / mixed-case variants are rejected — strict-lowercase vocabulary.

    Matches the existing lowercase vocabulary in ``CLAUDE_MODELS`` and
    ``OPENCODE_REASONING_EFFORTS``. ``"CHANGE"`` and ``"cHaNgE"`` are NOT
    normalised; both raise with the valid-set hint.
    """
    for raw in ("CHANGE", "cHaNgE"):
        with pytest.raises(ValueError) as excinfo:
            parse_agent_mode(raw)
        assert "change" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# join_opencode_catalog — pure join of ``opencode models`` ids with
# ``~/.cache/opencode/models.json`` cost/reasoning metadata.
# ---------------------------------------------------------------------------


def test_join_opencode_catalog_flattens_nested_provider_shape() -> None:
    """The native ``models.json`` shape (provider → models → id → entry) is flattened to id-keyed.

    Real-world ``models.json`` nests as ``{provider: {models: {id: entry}}}``;
    the join must walk that tree to find cost and reasoning. Order follows
    the ids argument (which mirrors ``opencode models`` output order).
    """
    catalog = {
        "alpha": {
            "id": "alpha",
            "models": {
                "openai/gpt-5.5": {"id": "openai/gpt-5.5", "reasoning": True, "cost": {"input": 1, "output": 2}},
            },
        },
        "beta": {
            "id": "beta",
            "models": {
                "openai/gpt-5.5-mini": {
                    "id": "openai/gpt-5.5-mini",
                    "reasoning": False,
                    "cost": {"input": 0.1, "output": 0.2},
                },
            },
        },
    }
    joined = join_opencode_catalog(["openai/gpt-5.5", "openai/gpt-5.5-mini"], catalog)

    assert [e.id for e in joined] == ["openai/gpt-5.5", "openai/gpt-5.5-mini"]
    by_id = {e.id: e for e in joined}
    assert by_id["openai/gpt-5.5"].reasoning is True
    assert by_id["openai/gpt-5.5"].cost_input == 1
    assert by_id["openai/gpt-5.5"].cost_output == 2
    assert by_id["openai/gpt-5.5-mini"].reasoning is False
    assert by_id["openai/gpt-5.5-mini"].cost_input == 0.1
    assert by_id["openai/gpt-5.5-mini"].cost_output == 0.2


def test_join_opencode_catalog_accepts_flat_shape() -> None:
    """A flat ``{id: entry}`` catalog (test fixture) is also supported.

    The pure helper should not assume a particular nesting depth — tests
    and hand-rolled fixtures may pass flat dicts, and the loader is free
    to pass either shape.
    """
    catalog = {
        "openai/gpt-5.5": {"id": "openai/gpt-5.5", "reasoning": True, "cost": {"input": 3, "output": 15}},
    }
    joined = join_opencode_catalog(["openai/gpt-5.5"], catalog)

    assert len(joined) == 1
    assert joined[0].reasoning is True
    assert joined[0].cost_input == 3
    assert joined[0].cost_output == 15


def test_join_opencode_catalog_missing_id_marked_unknown() -> None:
    """An id absent from the catalog is still listed, with cost ``None`` and reasoning ``False``.

    Acceptance criterion: pure helpers unit-tested with an injected id
    list and catalog — including the "id missing from catalog" case. The
    wizard must show the model (otherwise a stale ``opencode models``
    listing would silently lose a row) and fall back to "unknown" cost
    plus the safe non-reasoning default.
    """
    catalog = {
        "openai/gpt-5.5": {"id": "openai/gpt-5.5", "reasoning": True, "cost": {"input": 3, "output": 15}},
    }
    joined = join_opencode_catalog(["openai/gpt-5.5", "openai/mystery-model"], catalog)

    by_id = {e.id: e for e in joined}
    assert by_id["openai/gpt-5.5"].cost_input == 3
    assert by_id["openai/mystery-model"].cost_input is None
    assert by_id["openai/mystery-model"].cost_output is None
    assert by_id["openai/mystery-model"].reasoning is False


def test_join_opencode_catalog_preserves_input_order() -> None:
    """Row order follows the ``opencode models`` id list, not catalog order."""
    catalog = {
        "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
        "openai/gpt-5.4": {"reasoning": True, "cost": {"input": 2, "output": 10}},
    }
    # Pass ids in reverse-alphabetical order — join must preserve that.
    joined = join_opencode_catalog(["openai/gpt-5.4", "openai/gpt-5.5"], catalog)

    assert [e.id for e in joined] == ["openai/gpt-5.4", "openai/gpt-5.5"]


def test_join_opencode_catalog_skips_malformed_cost_entries() -> None:
    """A cost entry that is not a number is rendered as ``None`` rather than crashing.

    Real-world catalogs can carry non-numeric ``cost`` values (null,
    strings, missing sub-keys). The picker tolerates those by showing
    ``$?`` instead of crashing the wizard.
    """
    catalog = {
        "weird/model": {"id": "weird/model", "reasoning": False, "cost": "unknown"},
        "openai/gpt-5.5": {"id": "openai/gpt-5.5", "reasoning": True, "cost": {"input": 1, "output": 2}},
    }
    joined = join_opencode_catalog(["weird/model", "openai/gpt-5.5"], catalog)
    by_id = {e.id: e for e in joined}

    assert by_id["weird/model"].cost_input is None
    assert by_id["weird/model"].cost_output is None
    assert by_id["openai/gpt-5.5"].cost_input == 1


# ---------------------------------------------------------------------------
# opencode_model_is_reasoning — pure gate for the effort prompt.
# ---------------------------------------------------------------------------


def test_opencode_model_is_reasoning_true_for_reasoning_entry() -> None:
    """Catalog entry with ``reasoning: true`` returns True."""
    catalog = {"openai/gpt-5.5": {"reasoning": True}}
    assert opencode_model_is_reasoning("openai/gpt-5.5", catalog) is True


def test_opencode_model_is_reasoning_false_for_non_reasoning_entry() -> None:
    """Catalog entry with ``reasoning: false`` (or absent) returns False."""
    catalog = {"openai/gpt-5.5-mini": {"reasoning": False}}
    assert opencode_model_is_reasoning("openai/gpt-5.5-mini", catalog) is False


def test_opencode_model_is_reasoning_false_for_missing_id() -> None:
    """An id missing from the catalog is treated as non-reasoning (safe default)."""
    catalog = {"openai/gpt-5.5": {"reasoning": True}}
    assert opencode_model_is_reasoning("openai/unknown", catalog) is False


def test_opencode_model_is_reasoning_walks_nested_shape() -> None:
    """The reasoning check works on the nested provider→models shape too."""
    catalog = {
        "alpha": {"models": {"openai/gpt-5.5": {"reasoning": True}}},
        "beta": {"models": {"openai/gpt-5.5-mini": {"reasoning": False}}},
    }
    assert opencode_model_is_reasoning("openai/gpt-5.5", catalog) is True
    assert opencode_model_is_reasoning("openai/gpt-5.5-mini", catalog) is False


# ---------------------------------------------------------------------------
# build_opencode_model_picker_rows — model picker with cost labels
# ---------------------------------------------------------------------------


def test_build_opencode_model_picker_rows_shows_cost_in_label() -> None:
    """Each model picker row shows the model id, input cost, and output cost."""
    from ai_harness.modules.wizard.pure import OpencodeModelEntry

    joined = [
        OpencodeModelEntry(id="openai/gpt-5.5", cost_input=3, cost_output=15, reasoning=True),
        OpencodeModelEntry(id="openai/gpt-5.5-mini", cost_input=0.1, cost_output=0.2, reasoning=False),
    ]
    rows = build_opencode_model_picker_rows(joined, "openai/gpt-5.5")

    by_id = {r.value: r for r in rows}
    assert "openai/gpt-5.5" in by_id["openai/gpt-5.5"].label
    assert "3" in by_id["openai/gpt-5.5"].label
    assert "15" in by_id["openai/gpt-5.5"].label
    assert "0.1" in by_id["openai/gpt-5.5-mini"].label


def test_build_opencode_model_picker_rows_unknown_cost_renders_dollar_question() -> None:
    """A model missing from the catalog is shown with ``$?`` cost (still selectable).

    The user must be able to pick a model the catalog doesn't know
    about (e.g. a freshly added provider that the local cache hasn't
    refreshed for) — the picker row just shows ``$?`` instead of ``$N``.
    """
    from ai_harness.modules.wizard.pure import OpencodeModelEntry

    joined = [OpencodeModelEntry(id="openai/unknown", cost_input=None, cost_output=None, reasoning=False)]
    rows = build_opencode_model_picker_rows(joined, "")

    assert len(rows) == 1
    assert "$?" in rows[0].label


def test_build_opencode_model_picker_rows_marks_current() -> None:
    """The row whose value equals *current_model* is marked as current."""
    from ai_harness.modules.wizard.pure import OpencodeModelEntry

    joined = [
        OpencodeModelEntry(id="openai/gpt-5.5", cost_input=3, cost_output=15, reasoning=True),
        OpencodeModelEntry(id="openai/gpt-5.5-mini", cost_input=0.1, cost_output=0.2, reasoning=False),
    ]
    rows = build_opencode_model_picker_rows(joined, "openai/gpt-5.5")

    current = [r for r in rows if r.is_current]
    assert len(current) == 1
    assert current[0].value == "openai/gpt-5.5"


def test_build_opencode_model_picker_rows_unknown_current_marks_none() -> None:
    """A current model that is not in the list marks no row (no false preselection)."""
    from ai_harness.modules.wizard.pure import OpencodeModelEntry

    joined = [OpencodeModelEntry(id="openai/gpt-5.5", cost_input=3, cost_output=15, reasoning=True)]
    rows = build_opencode_model_picker_rows(joined, "stale/model")

    assert all(not r.is_current for r in rows)


# ---------------------------------------------------------------------------
# build_opencode_override_payload — selective OpenCode-flavored override writer.
# ---------------------------------------------------------------------------


def test_build_opencode_effort_picker_rows_uses_opencode_set() -> None:
    """The OpenCode effort picker uses ``(low, medium, high)``, not Claude's ``(low, medium, high, xhigh, max)``."""
    from ai_harness.modules.wizard.pure import build_opencode_effort_picker_rows

    rows = build_opencode_effort_picker_rows("implementor", "high")
    assert [r.value for r in rows] == list(opencode_efforts())
    current = [r for r in rows if r.is_current]
    assert len(current) == 1
    assert current[0].value == "high"


def test_build_opencode_override_payload_no_changes_returns_empty() -> None:
    """Unchanged selections produce an empty payload (caller skips the write)."""
    baseline = {
        "explorer": {"model": "openai/gpt-5.5", "effort": "high"},
        "implementor": {"model": "openai/gpt-5.5-mini", "effort": None},
    }
    selections = {
        "explorer": ModelSelection("openai/gpt-5.5", "high"),
        "implementor": ModelSelection("openai/gpt-5.5-mini", None),
    }
    assert build_opencode_override_payload(baseline, selections) == {}


def test_build_opencode_override_payload_keys_under_opencode() -> None:
    """Each emitted model/effort is nested under the ``opencode`` CLI key.

    The deep-merge in :func:`write_override_store` uses these keys to land
    in the right per-CLI slot of the override store — same convention
    as :func:`build_override_payload` uses for ``claude``.
    """
    baseline = {"implementor": {"model": "openai/gpt-5.5-mini", "effort": None}}
    selections = {"implementor": ModelSelection("openai/gpt-5.5", "high")}

    payload = build_opencode_override_payload(baseline, selections)

    assert payload == {
        "implementor": {
            "model": {"opencode": "openai/gpt-5.5"},
            "effort": {"opencode": "high"},
        },
    }


def test_build_opencode_override_payload_does_not_collide_with_claude() -> None:
    """The OpenCode payload must NOT carry any ``claude`` key.

    A user running ``set-models -o opencode`` only changes OpenCode-side
    overrides; the Claude slot for the same agent must remain untouched.
    """
    baseline = {"implementor": {"model": "sonnet", "effort": None}}
    selections = {"implementor": ModelSelection("openai/gpt-5.5", "high")}

    payload = build_opencode_override_payload(baseline, selections)

    assert "claude" not in str(payload)


def test_build_opencode_override_payload_clears_stale_effort_on_non_reasoning_model() -> None:
    """Switching to a non-reasoning model clears a previously set effort override.

    The TUI forces effort to ``None`` for non-reasoning models. If the
    baseline had a reasoning model's effort, that override would
    otherwise carry over and the renderer would emit ``reasoningEffort``
    in the agent's frontmatter — defeating the "non-reasoning models
    skip effort" acceptance criterion. This diff clears the stale slot.
    """
    baseline = {"validator": {"model": "openai/gpt-5.5", "effort": "high"}}
    selections = {"validator": ModelSelection("openai/gpt-5.5-mini", None)}

    payload = build_opencode_override_payload(baseline, selections)

    assert payload == {
        "validator": {
            "model": {"opencode": "openai/gpt-5.5-mini"},
            "effort": {"opencode": None},
        },
    }


# ---------------------------------------------------------------------------
# OpencodeUnavailable + catalog loader — the IO seam.
#
# The TUI's catalog loader is the only piece of wizard code that touches
# the filesystem (``~/.cache/opencode/models.json``) and a subprocess
# (``opencode models``). Both are injectable so this layer is testable
# without standing up an OpenCode install. The accepted-criterion contract
# is "if OpenCode is absent, the command errors with install/configure
# guidance; no static fallback list is used."
# ---------------------------------------------------------------------------


def test_load_opencode_catalog_joins_subprocess_ids_with_catalog_file(
    tmp_path: Path,
) -> None:
    """The loader returns ``(ids, catalog)`` from the injected subprocess and the file."""
    from ai_harness.modules.wizard import tui

    catalog_path = tmp_path / ".cache" / "opencode" / "models.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(
        json.dumps(
            {
                "alpha": {
                    "models": {
                        "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_runner(args: list[str], timeout: float) -> str:
        return "openai/gpt-5.5\n"

    ids, catalog = tui._load_opencode_catalog(tmp_path, runner=fake_runner)

    assert ids == ["openai/gpt-5.5"]
    assert "alpha" in catalog  # the raw dict — flattening is the pure layer's job


def test_load_opencode_catalog_raises_on_missing_binary(
    tmp_path: Path,
) -> None:
    """A FileNotFoundError from the runner is converted to OpencodeUnavailable."""
    from ai_harness.modules.wizard import tui

    def missing_binary(args: list[str], timeout: float) -> str:
        raise FileNotFoundError("No such file: opencode")

    with pytest.raises(tui.OpencodeUnavailable) as excinfo:
        tui._load_opencode_catalog(tmp_path, runner=missing_binary)

    # The message must include actionable guidance — the acceptance
    # criterion requires "install and configure OpenCode first" wording
    # (or close enough that the user knows what to do next).
    message = str(excinfo.value).lower()
    assert "opencode" in message or "install" in message


def test_load_opencode_catalog_raises_on_nonzero_exit(tmp_path: Path) -> None:
    """A non-zero exit code is converted to OpencodeUnavailable with a clear message."""
    import subprocess

    from ai_harness.modules.wizard import tui

    def nonzero_runner(args: list[str], timeout: float) -> str:
        raise subprocess.CalledProcessError(returncode=1, cmd=args, output="", stderr="auth required")

    with pytest.raises(tui.OpencodeUnavailable) as excinfo:
        tui._load_opencode_catalog(tmp_path, runner=nonzero_runner)

    assert "opencode" in str(excinfo.value).lower() or "install" in str(excinfo.value).lower()


def test_load_opencode_catalog_raises_on_empty_id_list(tmp_path: Path) -> None:
    """An empty ``opencode models`` result is treated as OpenCode unavailable.

    Real-world triggers: the user authenticated for no providers, or the
    binary is misconfigured and returns success with no body. The
    acceptance criterion forbids a static fallback — the wizard must
    error instead.
    """
    from ai_harness.modules.wizard import tui

    catalog_path = tmp_path / ".cache" / "opencode" / "models.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps({}), encoding="utf-8")

    def empty_runner(args: list[str], timeout: float) -> str:
        return "  \n  \n"  # whitespace only — no real ids

    with pytest.raises(tui.OpencodeUnavailable) as excinfo:
        tui._load_opencode_catalog(tmp_path, runner=empty_runner)

    assert "no model" in str(excinfo.value).lower() or "authenticate" in str(excinfo.value).lower()


def test_load_opencode_catalog_raises_on_missing_catalog_file(tmp_path: Path) -> None:
    """A successful ``opencode models`` with no catalog file is OpencodeUnavailable."""
    from ai_harness.modules.wizard import tui

    def fake_runner(args: list[str], timeout: float) -> str:
        return "openai/gpt-5.5\n"

    # tmp_path has no .cache/opencode/models.json
    with pytest.raises(tui.OpencodeUnavailable) as excinfo:
        tui._load_opencode_catalog(tmp_path, runner=fake_runner)

    message = str(excinfo.value)
    assert ".cache" in message or "opencode" in message.lower()


def test_load_opencode_catalog_raises_on_malformed_catalog_json(tmp_path: Path) -> None:
    """A catalog file with invalid JSON is OpencodeUnavailable (no silent fallback)."""
    from ai_harness.modules.wizard import tui

    catalog_path = tmp_path / ".cache" / "opencode" / "models.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text("not valid json {{{", encoding="utf-8")

    def fake_runner(args: list[str], timeout: float) -> str:
        return "openai/gpt-5.5\n"

    with pytest.raises(tui.OpencodeUnavailable) as excinfo:
        tui._load_opencode_catalog(tmp_path, runner=fake_runner)

    assert "opencode" in str(excinfo.value).lower() or "parse" in str(excinfo.value).lower()


def test_load_opencode_catalog_strips_blank_lines_and_whitespace(tmp_path: Path) -> None:
    """Leading/trailing whitespace and blank lines from the subprocess are ignored."""
    from ai_harness.modules.wizard import tui

    catalog_path = tmp_path / ".cache" / "opencode" / "models.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps({"alpha": {"models": {}}}), encoding="utf-8")

    def fake_runner(args: list[str], timeout: float) -> str:
        return "\n  openai/gpt-5.5  \n\n\n  openai/gpt-5.5-mini  \n"

    ids, _ = tui._load_opencode_catalog(tmp_path, runner=fake_runner)

    assert ids == ["openai/gpt-5.5", "openai/gpt-5.5-mini"]


def test_default_subprocess_runner_accepts_positional_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real runner accepts ``timeout`` positionally, matching every call site and fake.

    Regression test for #52: the runner's own signature made ``timeout``
    keyword-only while ``_load_opencode_catalog`` (and all test fakes) call
    it positionally, raising ``TypeError`` at runtime.
    """
    import subprocess

    from ai_harness.modules.wizard import tui

    captured: dict[str, object] = {}

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(tui.subprocess, "run", fake_run)

    result = tui._default_subprocess_runner(["echo", "x"], 5.0)

    assert result == "ok\n"
    assert captured["timeout"] == 5.0


def test_resolve_opencode_binary_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``shutil.which`` returning None is reported as no install."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.shutil, "which", lambda _name: None)
    assert tui._resolve_opencode_binary() is None


# ---------------------------------------------------------------------------
# run_opencode_wizard — full-flow tests with monkey-patched questionary.
#
# These mirror the slice-2 Claude tests: each scriptable stub queues the
# values the wizard would otherwise ask the user for, so we can drive a
# full happy path or a cancel path without a TTY. The pure helpers carry
# the decision logic; these tests are guard rails for the IO glue.
# ---------------------------------------------------------------------------


def test_run_opencode_wizard_no_changes_does_not_create_override_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opening the wizard and confirming without edits leaves overrides.json absent.

    Regression for the slice-2 default-pollution bug carried into slice 3.
    The TUI must NOT serialize template defaults into the store just
    because the user opened the wizard and confirmed without changing
    anything.
    """
    from ai_harness.modules.wizard import tui

    # Stub the binary resolution + catalog loader so the wizard gets a
    # well-formed OpenCode environment without standing up the real one.
    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5", "openai/gpt-5.5-mini"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                    "openai/gpt-5.5-mini": {"reasoning": False, "cost": {"input": 0.1, "output": 0.2}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)

    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # User does not pick any agent — both phases go straight to confirm.
    scripted = _ScriptedSelect()
    scripted.queue("__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    assert not _override_file(tmp_path).exists(), (
        "confirming without edits must NOT create overrides.json — that would "
        "be the default-pollution bug carried from slice 2."
    )


def test_run_opencode_wizard_non_reasoning_model_skips_effort_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-reasoning model selection skips the effort prompt and clears the effort override.

    Acceptance criterion: effort is offered only when the selected model
    has ``reasoning: true``. When the user picks a non-reasoning model
    (here ``openai/gpt-5.5-mini``) the wizard must not ask for effort —
    and, if a prior effort override was set, must clear it so the
    renderer does not emit ``reasoningEffort`` in the frontmatter.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5", "openai/gpt-5.5-mini"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                    "openai/gpt-5.5-mini": {"reasoning": False, "cost": {"input": 0.1, "output": 0.2}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    # Phase 1: pick implementor → pick non-reasoning model → continue → continue
    # Phase 2: continue (the wizard's gating skips effort for non-reasoning)
    # Phase 3: confirm
    scripted.queue(
        "change-implementor",  # pick agent
        "openai/gpt-5.5-mini",  # pick model
        "__continue__",  # continue past model phase
        "__continue__",  # continue past effort phase (no effort was asked)
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # Only the model changed; effort was never asked (and the baseline had None).
    assert overrides == {
        "change-implementor": {"model": {"opencode": "openai/gpt-5.5-mini"}},
    }
    # No effort entry was written for this agent.
    assert "effort" not in overrides["change-implementor"]


def test_run_opencode_wizard_reasoning_model_prompts_for_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reasoning model selection does prompt for effort.

    Companion to the non-reasoning test: the gating fires the OTHER way
    for ``reasoning: true`` models and the user is asked for an effort
    level.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",  # model phase: pick agent
        "openai/gpt-5.5",  # pick reasoning model
        "__continue__",  # continue past model phase
        "change-implementor",  # effort phase: pick agent
        "high",  # pick effort
        "__continue__",  # continue past effort phase
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert overrides == {
        "change-implementor": {
            "model": {"opencode": "openai/gpt-5.5"},
            "effort": {"opencode": "high"},
        },
    }


def test_run_opencode_wizard_opencode_absent_returns_false_with_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the opencode binary is missing, the wizard returns False and prints guidance.

    Acceptance criterion: ``set-models -o opencode`` must error when
    OpenCode is absent. The wizard surfaces a clear install/configure
    message and writes nothing.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: None)
    monkeypatch.setattr(tui, "_load_opencode_catalog", lambda *a, **kw: pytest.fail("should not be called"))

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is False
    assert not _override_file(tmp_path).exists()


def test_run_opencode_wizard_preserves_existing_install_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The OpenCode re-render must NOT drop other CLIs from ``installed.json``.

    Mirrors the slice-2 Claude regression test. With multiple CLIs
    installed, the wizard's scoped re-render (for OpenCode only) must
    leave the install manifest entries for generic, claude, copilot
    intact.
    """
    from ai_harness.modules.harness import install_for_agent_clis
    from ai_harness.modules.wizard import tui

    install_for_agent_clis(
        [AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.OPENCODE],
        home=tmp_path,
    )
    manifest_path = tmp_path / ".ai-harness" / "installed.json"
    before = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(before["agent_clis"]) == {"generic", "claude", "opencode"}

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5", "openai/gpt-5.5-mini"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                    "openai/gpt-5.5-mini": {"reasoning": False, "cost": {"input": 0.1, "output": 0.2}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Edit change-implementor's model (non-reasoning → skip effort) then confirm.
    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "openai/gpt-5.5-mini",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    after = json.loads(manifest_path.read_text(encoding="utf-8"))
    # All three CLIs survive — the re-render is scoped to OpenCode change agents only.
    assert set(after["agent_clis"]) == {"generic", "claude", "opencode"}
    assert set(after["files_by_agent_cli"]) == {"generic", "claude", "opencode"}


def test_run_opencode_wizard_ctrl_c_at_model_phase_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Ctrl+C during the model pass cancels without writing overrides.

    Acceptance criterion: Ctrl+C cancels with nothing written. The
    wizard must NOT serialize partial selections to the override store
    on cancel.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)

    class _CtrlC:
        def ask(self) -> None:
            return None  # simulates Ctrl+C → questionary returns None

    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: _CtrlC())

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is False
    assert not _override_file(tmp_path).exists()


def test_run_opencode_wizard_back_from_model_picker_returns_to_agent_choice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Picking "Back" inside the OpenCode model picker returns to the model phase's agent chooser.

    Issue #50, transition 1 (OpenCode side). Backing out must not record
    "__back__" as a model value for that agent.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "__back__",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    assert not _override_file(tmp_path).exists(), (
        "backing out of the OpenCode model picker must not write '__back__' "
        "as the agent's model — no override should exist."
    )


def test_run_opencode_wizard_back_from_effort_picker_returns_to_agent_choice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Picking "Back" inside the OpenCode effort picker returns to the effort phase's agent chooser.

    Issue #50, transition 2 (OpenCode side).
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1: pick change-implementor -> reasoning model -> continue.
    # Phase 2: pick change-implementor -> back out of effort picker -> continue.
    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "openai/gpt-5.5",
        "__continue__",
        "change-implementor",
        "__back__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # Only the model change survives; no effort entry was ever recorded.
    assert overrides == {"change-implementor": {"model": {"opencode": "openai/gpt-5.5"}}}


def test_run_opencode_wizard_back_from_effort_phase_returns_to_model_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Picking "← Back" on the OpenCode effort phase's agent chooser re-enters the model phase.

    Issue #50, transition 3 (OpenCode side). The model edit made before
    backing out must survive the round trip and must not re-run the
    catalog loader subprocess (`_load_opencode_catalog`) a second time.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    load_calls: list[int] = []

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        load_calls.append(1)
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1: pick change-implementor -> reasoning model -> continue.
    # Phase 2: back -> re-enters phase 1 (model).
    # Phase 1 again: continue (change-implementor stays on the prior model edit).
    # Phase 2 again: continue.
    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "openai/gpt-5.5",
        "__continue__",
        "__back__",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert overrides == {"change-implementor": {"model": {"opencode": "openai/gpt-5.5"}}}
    assert load_calls == [1], "going back into the model phase must not re-run the catalog loader"


def test_run_opencode_wizard_no_back_choice_in_first_model_phase_agent_chooser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The OpenCode model phase's agent chooser must NOT offer "← Back" — there is no prior phase."""
    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_opencode_continue_or_agent("model", {}, opencode_change_agents())

    assert captured, "the agent chooser did not call _filterable_select"
    values = [choice.value for choice in captured[0]]
    assert "__back__" not in values


def test_run_opencode_wizard_esc_on_effort_phase_agent_chooser_returns_to_model_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Esc on the OpenCode effort phase's agent chooser goes back to the model phase."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "openai/gpt-5.5",
        "__continue__",
        tui.Nav.ESC_BACK,
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert overrides == {"change-implementor": {"model": {"opencode": "openai/gpt-5.5"}}}


def test_run_opencode_wizard_esc_at_model_phase_agent_chooser_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Esc at the OpenCode model phase's agent chooser is a no-op (no predecessor)."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {}

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    scripted.queue(
        tui.Nav.ESC_BACK,
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    assert not _override_file(tmp_path).exists()


# ---------------------------------------------------------------------------
# Opencode wizard — change-agent set (-a change) full-flow + re-render scope
# ---------------------------------------------------------------------------


def test_run_opencode_wizard_change_agent_set_writes_eight_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``-a change`` happy path: editing each of the 8 change agents writes 8 override keys.

    Acceptance scenario 1: the wizard's agent chooser lists the 8 change
    agents (orchestrator first), and after confirm the override store
    contains exactly those 8 agent keys. The selective-write contract
    means every edited agent produces a (model) override; agents the
    user does not touch stay out of the store.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    # Model phase: edit each of the 8 change agents, then advance to effort.
    change_agents = list(opencode_change_agents())
    for agent in change_agents:
        scripted.queue(agent, "openai/gpt-5.5")
    # Continue past model phase, continue past effort phase (no edits).
    scripted.queue("__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=tuple(change_agents))

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # All 9 change-agent keys present, each with the picked model under model.opencode.
    assert set(overrides.keys()) == set(change_agents), (
        f"expected exactly the 9 change-agent keys, got {sorted(overrides.keys())}"
    )
    for agent in change_agents:
        assert overrides[agent]["model"]["opencode"] == "openai/gpt-5.5"
        # No effort override — the test never picked one.
        assert "effort" not in overrides[agent]


def test_run_opencode_wizard_change_agent_set_re_renders_change_agent_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``-a change`` re-renders all 9 .config/opencode/agent/*.md files (re-render scope locked at 9).

    Acceptance criterion ``req:re-render-scope-001``: ``_discover_agents``
    walks ``change-agent/`` and re-emits all 9 change-agent files so that
    every on-disk prompt reflects fresh override state after a ``-a change``
    confirm.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    change_agents = list(opencode_change_agents())
    for agent in change_agents:
        scripted.queue(agent, "openai/gpt-5.5")
    scripted.queue("__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=tuple(change_agents))

    assert wrote is True
    # The 9 change-agent files the renderer discovered.
    expected_names = list(opencode_change_agents())
    assert len(expected_names) == 9, "change agents must total 9 — discovery sanity"

    agent_dir = tmp_path / ".config" / "opencode" / "agent"
    assert agent_dir.is_dir(), "the wizard must have written the agent dir on re-render"
    for name in expected_names:
        path = agent_dir / f"{name}.md"
        assert path.is_file(), f"expected re-rendered file at {path}"

    # All 9 change-agent files must carry the picked model in their frontmatter.
    for name in change_agents:
        text = (agent_dir / f"{name}.md").read_text(encoding="utf-8")
        # Frontmatter is the YAML block between the first '---' markers; the
        # renderer's _yaml_dump_frontmatter places `model: <id>` plainly.
        assert "model: openai/gpt-5.5" in text, (
            f"{name}.md frontmatter must contain the picked model, got:\n{text[:300]}"
        )


# ---------------------------------------------------------------------------
# Claude wizard — ``-a`` flag is silently ignored
# ---------------------------------------------------------------------------


def test_cli_set_models_agent_flag_with_claude_is_silently_ignored(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``set-models -o claude -a change`` runs the Claude wizard with no override pollution.

    Acceptance scenarios 3 + 4: the ``-a`` flag is fully silent when
    ``-o claude`` is selected. No warning, no error, no informational
    notice. After confirm the override store MUST NOT gain any
    ``change-*`` / ``propose`` / ``design`` / ``specs`` / ``tasks`` key
    (those are the change-agent names — they don't belong on the
    Claude branch).
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Edit one change agent (change-implementor) → opus, then confirm.
    scripted = _ScriptedSelect()
    scripted.queue("change-implementor", "opus", "__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    # Drive the CLI with -o claude -a change. CliRunner has no TTY but the
    # wizard is fully scripted — the run_wizard_or_bail TTY guard short-circuits
    # to True without touching questionary. We patch the seam so the test
    # actually exercises the wizard body without a TTY.
    from ai_harness.commands import set_models as set_models_mod

    captured_stdout: list[str] = []

    def fake_run_wizard_or_bail(cli, *, home, agent_mode=AgentMode.CHANGE):
        # The Claude wizard must reach the body with no TTY guard firing.
        # Bypass by patching sys.stdin.isatty() via the existing bail code's path:
        # call the wizard directly, bypassing the TTY check.
        from ai_harness.modules.harness import AgentCli as _AgentCli

        assert cli == _AgentCli.CLAUDE
        # agent_mode is threaded but must be ignored — the body runs unchanged.
        result = tui.run_claude_wizard(home=home, agent_mode=agent_mode)
        captured_stdout.append("done")
        return result

    monkeypatch.setattr(set_models_mod, "run_wizard_or_bail", fake_run_wizard_or_bail)

    result = runner.invoke(app, ["set-models", "-o", "claude", "-a", "change"])

    # Wizard completed without error — the flag was silently ignored.
    assert result.exit_code == 0, f"unexpected non-zero exit, output:\n{result.stdout}\n{result.stderr}"
    combined = f"{result.stdout} {result.stderr}".lower()
    # The captured output must NOT mention "ignored" / "warning" / "note":
    # the silent-ignore contract is byte-stable.
    for forbidden in ("ignored", "warning", "note"):
        assert forbidden not in combined, f"silent-ignore contract violated: output mentions {forbidden!r}\n{combined}"

    # Override store must NOT contain any loop-agent keys; the Claude wizard
    # manages change agents exclusively.
    overrides_path = isolated_home / ".ai-harness" / "overrides.json"
    if overrides_path.exists():
        overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        keys = set(overrides.keys())
        loop_agent_keys = {"implementor", "explorer", "validator", "loop-orchestrator"}
        polluted = {k for k in keys if k in loop_agent_keys}
        assert not polluted, f"Claude wizard must NOT write loop-agent keys; polluted: {sorted(polluted)}"


# ---------------------------------------------------------------------------
# Agent chooser — label format, Continue label, Separator (issue #55)
# ---------------------------------------------------------------------------


def test_ask_continue_or_agent_uses_dash_label_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Claude agent chooser renders aligned ``{agent} - {value}`` rows with equal ``len()``."""
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_continue_or_agent("model", {"change-implementor": "opus"})

    titles = [choice.title for choice in captured[0] if isinstance(choice, questionary.Choice)]
    # The "opus" row is padded to the longest right-column width across
    # the visible row set — it ends with trailing spaces.
    opus_title = next(t for t in titles if "opus" in t)
    assert opus_title.rstrip().endswith("- opus")
    assert "opus" in opus_title
    # No legacy "(current: ...)" leakage from ``build_agent_list_rows``.
    assert not any("(current:" in title for title in titles)
    # Equal raw len() across agent rows — the alignment helper's invariant.
    # Filter out navigation rows ("← Back", Separator, "Continue") which
    # are intentionally NOT padded by the helper.
    agent_titles = [t for t in titles if t not in ("Continue",) and not t.startswith(("←", "-"))]
    assert agent_titles, "expected at least one agent row in titles"
    assert len({len(t) for t in agent_titles}) == 1


def test_ask_opencode_continue_or_agent_uses_dash_label_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """The OpenCode agent chooser renders ``{agent} - {value}``, not ``(current: ...)``."""
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_opencode_continue_or_agent("model", {"change-implementor": "openai/gpt-5.5"}, opencode_change_agents())

    titles = [choice.title for choice in captured[0] if isinstance(choice, questionary.Choice)]
    assert "change-implementor - openai/gpt-5.5" in titles
    assert not any("(current:" in title for title in titles)


def test_ask_continue_or_agent_continue_label_has_no_arrow(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Continue choice's label is plain "Continue" — no "-> {next_phase}" suffix."""
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_continue_or_agent("model", {})

    continue_choice = next(c for c in captured[0] if isinstance(c, questionary.Choice) and c.value == "__continue__")
    assert continue_choice.title == "Continue"


def test_ask_continue_or_agent_has_separator_before_continue(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Separator sits immediately before the Continue choice (Claude path)."""
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_continue_or_agent("model", {})

    choices = captured[0]
    continue_index = next(
        i for i, c in enumerate(choices) if isinstance(c, questionary.Choice) and c.value == "__continue__"
    )
    assert isinstance(choices[continue_index - 1], questionary.Separator)


def test_ask_opencode_continue_or_agent_has_separator_before_continue(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Separator sits immediately before the Continue choice (OpenCode path)."""
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_opencode_continue_or_agent("model", {}, opencode_change_agents())

    choices = captured[0]
    continue_index = next(
        i for i, c in enumerate(choices) if isinstance(c, questionary.Choice) and c.value == "__continue__"
    )
    assert isinstance(choices[continue_index - 1], questionary.Separator)


def test_ask_continue_or_agent_has_separator_after_back_on_effort_phase(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Separator sits immediately after "← Back" and before the agent rows (Claude, effort phase)."""
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_continue_or_agent("effort", {})

    choices = captured[0]
    back_index = next(i for i, c in enumerate(choices) if isinstance(c, questionary.Choice) and c.value == "__back__")
    assert isinstance(choices[back_index + 1], questionary.Separator)


def test_ask_continue_or_agent_model_phase_has_no_leading_separator(monkeypatch: pytest.MonkeyPatch) -> None:
    """The model phase has no "← Back" choice, so it gets no leading Separator either (Claude path)."""
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_continue_or_agent("model", {})

    choices = captured[0]
    assert not any(c.value == "__back__" for c in choices if isinstance(c, questionary.Choice))
    assert isinstance(choices[0], questionary.Choice)


def test_ask_opencode_continue_or_agent_has_separator_after_back_on_effort_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Separator sits immediately after "← Back" and before the agent rows (OpenCode, effort phase)."""
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_opencode_continue_or_agent("effort", {}, opencode_change_agents())

    choices = captured[0]
    back_index = next(i for i, c in enumerate(choices) if isinstance(c, questionary.Choice) and c.value == "__back__")
    assert isinstance(choices[back_index + 1], questionary.Separator)


def test_ask_opencode_continue_or_agent_model_phase_has_no_leading_separator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The model phase has no "← Back" choice, so it gets no leading Separator either (OpenCode path)."""
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_opencode_continue_or_agent("model", {}, opencode_change_agents())

    choices = captured[0]
    assert not any(c.value == "__back__" for c in choices if isinstance(c, questionary.Choice))
    assert isinstance(choices[0], questionary.Choice)


# ---------------------------------------------------------------------------
# Picker row builders — mark current, leave others unmarked
# ---------------------------------------------------------------------------


def test_build_model_picker_rows_marks_current_model() -> None:
    """The row matching the current model is marked; others are unmarked."""
    rows = build_model_picker_rows("implementor", "opus")

    # All fixed Claude models are present
    assert [r.value for r in rows] == list(claude_models())
    # Exactly one row is marked as current
    assert sum(1 for r in rows if r.is_current) == 1
    # The marked row is the current model
    current = next(r for r in rows if r.is_current)
    assert current.value == "opus"


def test_build_model_picker_rows_falls_back_when_current_unknown() -> None:
    """When the current model is not in the fixed set, no row is marked."""
    rows = build_model_picker_rows("implementor", "mystery-model")
    assert all(not r.is_current for r in rows)


def test_build_effort_picker_rows_marks_current_effort() -> None:
    """The row matching the current effort is marked."""
    rows = build_effort_picker_rows("validator", "high")

    assert [r.value for r in rows] == list(claude_efforts())
    current = next(r for r in rows if r.is_current)
    assert current.value == "high"


def test_build_effort_picker_rows_handles_none() -> None:
    """A ``None`` current effort (unset) marks no row."""
    rows = build_effort_picker_rows("explorer", None)
    assert all(not r.is_current for r in rows)


def test_build_agent_list_rows_shows_current_per_agent() -> None:
    """Each row in the agent list shows that agent's current model."""
    current = {
        "explorer": "haiku",
        "implementor": "opus",
        "validator": "sonnet",
    }
    rows = build_agent_list_rows(claude_wizard_agents(), current)

    # Order matches the configured agent list
    assert [r.value for r in rows] == list(claude_wizard_agents())
    # Every row is marked (the agent list always shows the current value)
    assert all(r.is_current for r in rows)


def test_build_agent_list_rows_missing_agent_gets_default_model() -> None:
    """An agent missing from the current map gets the Claude default 'sonnet' (template baseline)."""
    rows = build_agent_list_rows(claude_wizard_agents(), {})

    # All nine rows present, all marked
    assert len(rows) == 9
    assert all(r.is_current for r in rows)


# ---------------------------------------------------------------------------
# Confirmation rows — render the per-agent chosen model + effort
# ---------------------------------------------------------------------------


def test_build_confirmation_rows_includes_model_and_effort() -> None:
    """Confirmation rows show ``agent: model / effort`` for each agent."""
    selections = {
        "explorer": ModelSelection("haiku", "low"),
        "implementor": ModelSelection("opus", "high"),
        "validator": ModelSelection("sonnet", None),
    }
    rows = build_confirmation_rows(selections)

    # All agents are listed
    assert {r.value for r in rows} == set(selections.keys())
    # The label carries the model and effort
    by_value = {r.value: r.label for r in rows}
    assert "haiku" in by_value["explorer"]
    assert "low" in by_value["explorer"]
    assert "opus" in by_value["implementor"]
    assert "high" in by_value["implementor"]
    # None effort renders as a placeholder
    assert "sonnet" in by_value["validator"]


def test_build_confirmation_rows_unset_effort_renders_unset_placeholder() -> None:
    """Confirm panel: a ``None`` effort renders the literal ``"(unset)"`` placeholder, not ``"(NA)"``.

    Locks in the contract that the confirm panel routes ``None`` effort
    through the ``(unset)`` branch. The ``has_effort_support=True``
    constant at this call site is the load-bearing suppression of the
    ``(NA)`` branch — confirmed by spec ``effort-phase-label-formatter``.
    """
    rows = build_confirmation_rows({"change-implementor": ModelSelection("opus", None)})

    assert len(rows) == 1
    assert rows[0].label == "change-implementor: opus / (unset)"


def test_build_confirmation_rows_set_effort_renders_effort_value() -> None:
    """Confirm panel: a set effort renders the effort value as-is."""
    rows = build_confirmation_rows({"change-implementor": ModelSelection("opus", "high")})

    assert len(rows) == 1
    assert rows[0].label == "change-implementor: opus / high"


def test_build_confirmation_rows_never_renders_na_on_confirm_panel() -> None:
    """Confirm panel NEVER renders ``"(NA)"`` — even for non-reasoning-looking models.

    The model-switch reset (task 2) keeps any non-reasoning model from
    carrying a stale effort by the time the user reaches the confirm
    screen. ``build_confirmation_rows`` encodes that invariant by
    passing ``has_effort_support=True`` as a CONSTANT — so a ``None``
    effort routes to ``"(unset)"`` here, never to ``"(NA)"``.
    """
    rows = build_confirmation_rows(
        {"change-implementor": ModelSelection("minimax/non-reasoning", None)},
    )

    assert len(rows) == 1
    assert "(NA)" not in rows[0].label
    assert "(unset)" in rows[0].label


# ---------------------------------------------------------------------------
# align_label_rows — pure helper: two-column dynamic-width label formatter.
#
# Load-bearing seam shared by the model / effort / confirm surfaces in the
# set-models wizard. Locks the invariants listed in the spec
# (specs/alignment.md, "Helper tests" section): equal raw len(), separator
# at the same column, trailing-space right padding, order preservation,
# empty input → [], single-row uses self as max, placeholders pass through,
# and the keyword-only ``separator`` argument.
# ---------------------------------------------------------------------------


def test_align_label_rows_default_separator_and_signature() -> None:
    """``align_label_rows`` is callable with only the positional ``pairs`` argument.

    The signature is ``align_label_rows(pairs, *, separator=" - ")`` —
    ``separator`` is keyword-only with default ``" - "``. The returned
    labels use ``" - "`` between the two columns when no separator is
    supplied.
    """
    import inspect

    sig = inspect.signature(align_label_rows)
    assert "pairs" in sig.parameters
    separator_param = sig.parameters["separator"]
    assert separator_param.kind is inspect.Parameter.KEYWORD_ONLY
    assert separator_param.default == " - "

    labels = align_label_rows([("a", "b")])
    assert " - " in labels[0]


def test_align_label_rows_pairs_are_opaque() -> None:
    """The helper does NOT inspect, parse, or normalise the input strings.

    Widths come from ``len()`` alone — characters that look like separators
    inside either column do NOT trigger re-splitting or stripping. The
    right column ``"b/e"`` (with an internal slash) is treated as one
    opaque unit and the left column ``"a-a"`` (with an internal dash) is
    not split either.
    """
    labels = align_label_rows([("a-a", "b/e"), ("c", "d")])
    # Right column widths are computed purely from len(), so the long row
    # ("a-a" / "b/e" = 3 chars) drives right_width = 3.
    assert labels == ["a-a - b/e", "c   - d  "]
    # Both labels must have identical len() — the helper's load-bearing
    # invariant.
    assert len(labels[0]) == len(labels[1])


def test_align_label_rows_equal_raw_len_across_rows() -> None:
    """Mixed-width input → every label has the same raw ``len()``.

    The common length equals ``left_width + len(separator) + right_width``
    where the widths are the per-call maxima over the provided pairs.
    """
    pairs = [
        ("change-implementor", "opus"),
        ("change-validator", "openai/gpt-5.5"),
    ]
    labels = align_label_rows(pairs)

    lengths = {len(label) for label in labels}
    assert len(lengths) == 1, f"expected equal len() across rows, got {lengths}"
    expected_len = len("change-implementor") + len(" - ") + len("openai/gpt-5.5")
    assert next(iter(lengths)) == expected_len


def test_align_label_rows_equal_widths_passthrough() -> None:
    """Uniform-width input gets no extra padding — the row IS the max."""
    labels = align_label_rows([("a", "x"), ("b", "y")])

    # left_width = 1, right_width = 1, separator = 3 → 5 chars per label.
    assert labels == ["a - x", "b - y"]
    assert len(labels[0]) == len(labels[1]) == 5


def test_align_label_rows_separator_at_same_column() -> None:
    """The separator substring begins at the same column index in every label.

    That column index equals ``left_width`` — the maximum ``len(left)``
    over the provided pairs.
    """
    pairs = [
        ("change-validator", "openai/gpt-5.5"),
        ("a", "opus"),
        ("change-implementor", "sonnet"),
    ]
    labels = align_label_rows(pairs)

    left_width = max(len(left) for left, _ in pairs)
    for label in labels:
        assert label.index(" - ") == left_width


def test_align_label_rows_trailing_space_padding_for_shorter_right() -> None:
    """Shorter right values are right-padded with ASCII spaces to the max width.

    ``repr()`` is used to make the trailing spaces visible in the assertion
    output — the failure message would otherwise hide them.
    """
    labels = align_label_rows([("a", "opus"), ("a", "haiku")])

    # "haiku" is shorter than "opus" by one character → the "opus" row is
    # padded with one trailing space. ``repr()`` shows the trailing space
    # explicitly so a regression that loses the padding fails visibly.
    assert repr(labels[0]) == "'a - opus '"
    assert labels[0].endswith(" ")
    assert len(labels[0]) == len(labels[1])


def test_align_label_rows_padding_survives_round_trip() -> None:
    """Trailing spaces survive assignment to ``questionary.Choice.title`` and back."""
    import questionary

    labels = align_label_rows([("a", "opus"), ("a", "haiku")])
    choice = questionary.Choice(title=labels[0], value="agent")

    assert choice.title.endswith(" ")
    assert choice.title == labels[0]


def test_align_label_rows_preserves_input_order() -> None:
    """Shuffled input → labels are returned in the same shuffled order.

    Output index N corresponds to input pair index N — the helper MUST NOT
    sort, group, or reorder the pairs.
    """
    pairs = [("c", "3"), ("a", "1"), ("b", "2")]
    labels = align_label_rows(pairs)

    # Right halves (after the separator) must match the input's right column.
    rights = [label.split(" - ", 1)[1].rstrip() for label in labels]
    assert rights == ["3", "1", "2"]
    # Left halves too — full input order is preserved verbatim.
    assert [label.split(" - ", 1)[0].rstrip() for label in labels] == ["c", "a", "b"]


def test_align_label_rows_empty_input_returns_empty_list() -> None:
    """``[]`` returns ``[]`` without raising."""
    assert align_label_rows([]) == []


def test_align_label_rows_single_row_uses_self_as_max() -> None:
    """A single pair returns one label sized to its own lengths — no extra padding."""
    labels = align_label_rows([("change-implementor", "opus")])

    assert len(labels) == 1
    expected = len("change-implementor") + len(" - ") + len("opus")
    assert len(labels[0]) == expected
    assert labels[0] == "change-implementor - opus"


def test_align_label_rows_opencode_long_ids_set_wider_right() -> None:
    """Long OpenCode ``provider/model`` IDs drive ``right_width`` to the long ID.

    Mixing a short Claude alias (``"opus"``) with a long OpenCode id
    (``"openai/gpt-5.5"``) must size ``right_width`` to the longer id —
    not a hard-coded constant. The short alias gets right-padded with
    trailing spaces to match.
    """
    pairs = [
        ("change-implementor", "opus"),
        ("change-validator", "openai/gpt-5.5"),
    ]
    labels = align_label_rows(pairs)

    right_width = max(len(right) for _, right in pairs)
    assert right_width == len("openai/gpt-5.5")
    # The "opus" row's right column must be right-padded with spaces.
    assert labels[0].endswith(" " * (right_width - len("opus")))
    assert labels[0][len("change-implementor") + len(" - ") :] == "opus" + " " * (right_width - len("opus"))


def test_align_label_rows_unset_placeholder_verbatim() -> None:
    """The ``(unset)`` substring passes through the helper untouched."""
    labels = align_label_rows([("change-implementor", "opus / (unset)")])

    assert "/ (unset)" in labels[0]
    # Verbatim — case, parentheses, and surrounding spaces preserved.
    assert labels[0].endswith("opus / (unset)")


def test_align_label_rows_na_placeholder_verbatim() -> None:
    """The ``(NA)`` substring passes through the helper untouched, uppercase."""
    labels = align_label_rows([("change-implementor", "opus / (NA)")])

    assert "/ (NA)" in labels[0]
    # Uppercase NA — no lowercasing, no translation.
    assert "(na)" not in labels[0]


def test_align_label_rows_custom_separator_kwarg() -> None:
    """A caller-supplied ``separator=" | "`` produces ``" | "``-separated labels."""
    labels = align_label_rows([("a", "x"), ("b", "y")], separator=" | ")

    assert all(" | " in label for label in labels)
    assert labels == ["a | x", "b | y"]
    # Equal-len() invariant still holds with the custom separator.
    assert len(labels[0]) == len(labels[1])


def test_align_label_rows_default_separator_is_dash() -> None:
    """The default separator (kwarg omitted) is ``" - "``."""
    labels = align_label_rows([("change-orchestrator", "opus")])

    assert " - " in labels[0]
    # Default is exactly " - " — three chars: dash with surrounding spaces.
    assert labels[0] == "change-orchestrator - opus"


# ---------------------------------------------------------------------------
# format_selection_label — pure helper: the single source of truth for the
# ``model / <state>`` right-column display used by both the effort phase
# and the confirm panel. The agent prefix is added later by the alignment
# helper (``align_label_rows``); this function returns the right column
# only.
# ---------------------------------------------------------------------------


def test_format_selection_label_supported_model_with_effort() -> None:
    """Supported model + set effort → ``"opus / high"`` (right column only)."""
    label = format_selection_label("change-implementor", "opus", "high", True)
    assert label == "opus / high"
    # The agent prefix MUST NOT appear in the right column — the alignment
    # helper wraps it back on after this returns.
    assert "change-implementor" not in label


def test_format_selection_label_supported_model_no_effort_emits_unset() -> None:
    """Supported model + ``None`` effort → ``"opus / (unset)"`` (right column only)."""
    label = format_selection_label("change-implementor", "opus", None, True)
    assert label == "opus / (unset)"
    assert "change-implementor" not in label


def test_format_selection_label_unsupported_model_no_effort_emits_na() -> None:
    """Unsupported model + ``None`` effort → ``"opus / (NA)"`` (right column only).

    ``has_effort_support=False`` dominates: the function returns the
    ``(NA)`` branch even when effort is ``None`` — never ``(unset)``.
    """
    label = format_selection_label("change-implementor", "minimax/non-reasoning", None, False)
    assert label == "minimax/non-reasoning / (NA)"
    assert "change-implementor" not in label
    assert "(unset)" not in label


def test_format_selection_label_unsupported_model_ignores_effort_value() -> None:
    """Unsupported model + effort value → effort is ignored, ``(NA)`` still emitted.

    Spec: ``has_effort_support=False`` always routes to the ``(NA)``
    branch — the effort value must NOT appear in the rendered string.
    """
    label = format_selection_label("change-implementor", "minimax/non-reasoning", "high", False)
    assert label == "minimax/non-reasoning / (NA)"
    assert "high" not in label
    assert "change-implementor" not in label


def test_format_selection_label_empty_model_does_not_raise() -> None:
    """Defensive empty-model edge: ``model=""`` must not crash; ``(unset)`` still renders.

    Locks in the contract that the formatter does not raise on an empty
    model string — useful as a regression guard for any future code
    path that feeds an uninitialised model value into the helper.
    """
    label = format_selection_label("change-implementor", "", None, True)
    assert "(unset)" in label
    # Right-column-only — no agent prefix in the returned string.
    assert "change-implementor" not in label


def test_format_selection_label_no_agent_prefix_in_output() -> None:
    """The agent name MUST NOT appear anywhere in the right-column output.

    Locks the narrowing: the alignment helper wraps the agent name around
    whatever this returns, so the function MUST NOT re-introduce the
    ``agent: `` prefix that the old code path emitted.
    """
    label = format_selection_label("change-implementor", "opus", "high", True)
    assert "change-implementor" not in label
    # No leading agent prefix pattern — the string starts with the model.
    assert not label.startswith("change-implementor")


def test_format_selection_label_no_agent_prefix_on_na_branch() -> None:
    """The ``(NA)`` branch also drops the agent prefix.

    Locks the same invariant on the unsupported-model branch with a long
    OpenCode ``provider/model`` id — both branches must return the right
    column only.
    """
    label = format_selection_label("change-validator", "openai/gpt-5.5", "low", False)
    assert label == "openai/gpt-5.5 / (NA)"
    assert "change-validator" not in label


def test_format_selection_label_unset_case_preserved() -> None:
    """``(unset)`` is lowercase verbatim — no lowercasing/normalisation."""
    label = format_selection_label("a", "opus", None, True)
    assert "(unset)" in label
    assert "(UNSET)" not in label
    assert "(Unset)" not in label


def test_format_selection_label_na_case_preserved() -> None:
    """``(NA)`` is uppercase verbatim — no translation to ``(na)`` or ``(Not Available)``."""
    label = format_selection_label("a", "opus", "high", False)
    assert "(NA)" in label
    assert "(na)" not in label
    assert "(Not Available)" not in label


# ---------------------------------------------------------------------------
# build_override_payload — selective write keeps the override store partial.
#
# The override store contract (issue #44) is "only fields I changed are
# stored; the rest falls back to template defaults". The wizard must NOT
# serialize template defaults into the store just because the user opened
# it and confirmed without changing anything. This helper isolates that
# decision so the TUI does not have to re-derive it.
# ---------------------------------------------------------------------------


def _baseline(**agents: str | None) -> dict[str, dict[str, str | None]]:
    """Build a baseline map ``agent -> {"model": m, "effort": e}`` from kwargs.

    Convenience for the tests below — keeps each test focused on the agents
    it cares about instead of repeating the nested dict literal.
    """
    return {
        agent: {"model": kw.get("model"), "effort": kw.get("effort")}  # type: ignore[dict-item]
        for agent, kw in agents.items()  # type: ignore[arg-type]
    }


def test_build_override_payload_no_changes_returns_empty() -> None:
    """When every selection matches the baseline, the payload is empty."""
    baseline = {
        "explorer": {"model": "sonnet", "effort": None},
        "implementor": {"model": "sonnet", "effort": None},
        "validator": {"model": "sonnet", "effort": None},
    }
    selections = {
        "explorer": ModelSelection("sonnet", None),
        "implementor": ModelSelection("sonnet", None),
        "validator": ModelSelection("sonnet", None),
    }
    assert build_override_payload(baseline, selections) == {}


def test_build_override_payload_does_not_pollute_with_template_defaults() -> None:
    """A fresh install (no override file) keeps the store empty when nothing changes.

    This is the validator's "no default pollution" requirement: opening the
    wizard and confirming without touching anything must not write
    ``{"implementor": {"model": {"claude": "sonnet"}}}`` to overrides.json.
    """
    baseline = {agent: {"model": "sonnet", "effort": None} for agent in claude_wizard_agents()}
    selections = {agent: ModelSelection("sonnet", None) for agent in claude_wizard_agents()}
    payload = build_override_payload(baseline, selections)

    # No agent appears in the payload at all.
    assert payload == {}
    # Defensive: no agent accidentally leaked a default-model entry.
    for agent in claude_wizard_agents():
        assert agent not in payload


def test_build_override_payload_only_changed_model_is_written() -> None:
    """Changing one agent's model writes only that (agent, model) entry."""
    baseline = {
        "explorer": {"model": "sonnet", "effort": None},
        "implementor": {"model": "sonnet", "effort": None},
        "validator": {"model": "sonnet", "effort": None},
    }
    selections = {
        "explorer": ModelSelection("sonnet", None),
        "implementor": ModelSelection("opus", None),
        "validator": ModelSelection("sonnet", None),
    }
    payload = build_override_payload(baseline, selections)

    assert payload == {"implementor": {"model": {"claude": "opus"}}}


def test_build_override_payload_only_changed_effort_is_written() -> None:
    """Setting an effort where baseline had None writes only that field."""
    baseline = {
        "validator": {"model": "sonnet", "effort": None},
    }
    selections = {
        "validator": ModelSelection("sonnet", "high"),
    }
    payload = build_override_payload(baseline, selections)

    assert payload == {"validator": {"effort": {"claude": "high"}}}


def test_build_override_payload_both_fields_changed_writes_both() -> None:
    """Changing both model and effort for the same agent writes both entries."""
    baseline = {
        "implementor": {"model": "sonnet", "effort": None},
    }
    selections = {
        "implementor": ModelSelection("opus", "high"),
    }
    payload = build_override_payload(baseline, selections)

    assert payload == {
        "implementor": {"model": {"claude": "opus"}, "effort": {"claude": "high"}},
    }


def test_build_override_payload_keeps_existing_non_default_override_untouched() -> None:
    """When the user keeps a non-default existing value, nothing is written for it.

    The existing override entry already in the store survives because we do
    not re-serialize it — write_override_store deep-merges, so untouched
    fields are preserved verbatim.
    """
    # Existing override: implementor had been previously set to haiku.
    baseline = {
        "explorer": {"model": "sonnet", "effort": None},
        "implementor": {"model": "haiku", "effort": None},
        "validator": {"model": "sonnet", "effort": None},
    }
    # User changes nothing — confirms with current values as-is.
    selections = {
        "explorer": ModelSelection("sonnet", None),
        "implementor": ModelSelection("haiku", None),
        "validator": ModelSelection("sonnet", None),
    }
    payload = build_override_payload(baseline, selections)

    # The non-default baseline for implementor must not be re-serialized —
    # serializing it would write "haiku" to the store, masking the fact that
    # the user never touched it. Cleaner: leave the store alone.
    assert payload == {}


def test_build_override_payload_effort_change_from_value_to_other() -> None:
    """Changing effort from one set value to another writes only the effort."""
    baseline = {
        "implementor": {"model": "sonnet", "effort": "low"},
    }
    selections = {
        "implementor": ModelSelection("sonnet", "high"),
    }
    payload = build_override_payload(baseline, selections)

    assert payload == {"implementor": {"effort": {"claude": "high"}}}


def test_build_override_payload_unsetting_effort_writes_empty_effort_entry() -> None:
    """Picking ``None`` effort (clearing it) writes an empty effort entry.

    The override store uses ``None`` to mean "fall back to template"; we
    preserve that semantic by emitting an explicit ``effort: {}`` slot so
    the merge replaces the prior value with no value.
    """
    baseline = {
        "validator": {"model": "sonnet", "effort": "high"},
    }
    selections = {
        "validator": ModelSelection("sonnet", None),
    }
    payload = build_override_payload(baseline, selections)

    assert payload == {"validator": {"effort": {"claude": None}}}


def test_build_override_payload_ignores_agent_missing_from_baseline() -> None:
    """An agent with no baseline entry is treated as fresh defaults.

    Defensive: the wizard always seeds baseline from ``_current_claude_*``
    for every wizard agent, but if a caller forgets one, the helper still
    produces a sensible payload by comparing against ``None`` (which
    ``_current_claude_effort`` returns when unset).
    """
    baseline: dict[str, dict[str, str | None]] = {}
    selections = {
        "explorer": ModelSelection("opus", "high"),
    }
    payload = build_override_payload(baseline, selections)

    assert payload == {"explorer": {"model": {"claude": "opus"}, "effort": {"claude": "high"}}}


# ---------------------------------------------------------------------------
# write_override_store — deep-merge writer next to the loader
# ---------------------------------------------------------------------------


def test_write_override_store_writes_new_payload(tmp_path: Path) -> None:
    """Writing a fresh payload creates ``~/.ai-harness/overrides.json`` with that JSON."""
    write_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})

    path = tmp_path / OVERRIDES_REL
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"implementor": {"model": {"claude": "opus"}}}


def test_write_override_store_preserves_unrelated_existing_entries(tmp_path: Path) -> None:
    """An existing entry for another agent survives a new write."""
    existing_path = tmp_path / OVERRIDES_REL
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text(
        json.dumps({"validator": {"model": {"claude": "haiku"}}}),
        encoding="utf-8",
    )

    write_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})

    data = json.loads(existing_path.read_text(encoding="utf-8"))
    assert data["validator"] == {"model": {"claude": "haiku"}}
    assert data["implementor"] == {"model": {"claude": "opus"}}


def test_write_override_store_merges_partial_override_for_same_agent(tmp_path: Path) -> None:
    """Writing model for an agent merges with an existing effort override for the same agent."""
    existing_path = tmp_path / OVERRIDES_REL
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text(
        json.dumps({"implementor": {"effort": {"claude": "high"}}}),
        encoding="utf-8",
    )

    write_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})

    data = json.loads(existing_path.read_text(encoding="utf-8"))
    assert data["implementor"]["model"] == {"claude": "opus"}
    assert data["implementor"]["effort"] == {"claude": "high"}


def test_write_override_store_round_trips_through_loader(tmp_path: Path) -> None:
    """What we write is what the existing override loader reads back."""
    payload = {
        "implementor": {"model": {"claude": "opus"}, "effort": {"claude": "high"}},
        "validator": {"model": {"claude": "haiku"}},
    }
    write_override_store(tmp_path, payload)

    loaded = _load_override_store(tmp_path)
    assert loaded == payload


def test_write_override_store_creates_parent_directory(tmp_path: Path) -> None:
    """The parent ``~/.ai-harness/`` directory is created on first write."""
    assert not (tmp_path / ".ai-harness").exists()
    write_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})
    assert (tmp_path / ".ai-harness").is_dir()
    assert (tmp_path / OVERRIDES_REL).is_file()


# ---------------------------------------------------------------------------
# set_models CLI — argument validation paths
# ---------------------------------------------------------------------------


def test_cli_set_models_missing_o_errors(isolated_home: Path) -> None:
    """Running `set-models` with no `-o` errors with a clear, non-zero exit."""
    result = runner.invoke(app, ["set-models"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    assert (
        "set-models" in combined.lower()
        or "missing" in combined.lower()
        or "required" in combined.lower()
        or "-o" in combined
    )


def test_cli_set_models_multiple_clis_errors(isolated_home: Path) -> None:
    """Two CLIs in -o errors with a clear, non-zero exit."""
    result = runner.invoke(app, ["set-models", "-o", "claude,opencode"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    assert "exactly one" in combined.lower() or "single" in combined.lower() or "one" in combined.lower()


def test_cli_set_models_repeated_o_flags_error(isolated_home: Path) -> None:
    """Repeated ``-o`` flags must trigger the same exactly-one validation as comma input.

    Regression for the validator's BLOCKER on issue #45: typer's default
    behaviour for a single-value ``str`` option silently keeps only the
    LAST occurrence of a repeated flag. So ``set-models -o claude -o
    opencode`` used to pass through with ``to="opencode"`` and produce
    the misleading "not yet implemented" error instead of a clear
    "exactly one Agent CLI" validation error that surfaces BOTH values.
    """
    result = runner.invoke(app, ["set-models", "-o", "claude", "-o", "opencode"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    # The validation message must mention BOTH clis — proof that the
    # repeated -o was collected, not silently dropped.
    assert "claude" in combined.lower(), f"expected 'claude' in error, got: {combined!r}"
    assert "opencode" in combined.lower(), f"expected 'opencode' in error, got: {combined!r}"
    assert "exactly one" in combined.lower() or "got 2" in combined.lower(), (
        f"expected exactly-one validation message, got: {combined!r}"
    )


def test_cli_set_models_repeated_o_same_value_still_errors(isolated_home: Path) -> None:
    """Two identical ``-o`` flags (``-o claude -o claude``) must still fail the exactly-one check.

    Even when the user repeats the same value, the validation must reject
    the input — silently collapsing duplicates would mask shell quoting
    bugs and aliases that expand to the same flag. The command must
    require exactly one occurrence of ``-o``, not exactly one distinct CLI.
    """
    result = runner.invoke(app, ["set-models", "-o", "claude", "-o", "claude"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    assert "exactly one" in combined.lower() or "got 2" in combined.lower(), (
        f"expected exactly-one validation message for repeated identical -o, got: {combined!r}"
    )


def test_cli_set_models_unknown_cli_errors(isolated_home: Path) -> None:
    """An unknown CLI in -o errors with a clear, non-zero exit."""
    result = runner.invoke(app, ["set-models", "-o", "bogus"])

    assert result.exit_code != 0


def test_cli_set_models_opencode_non_tty_errors(isolated_home: Path) -> None:
    """OpenCode is now a valid single-CLI input; the command errors clearly without a TTY.

    The command's arg-validation no longer rejects ``-o opencode`` —
    slice 3 implemented the OpenCode wizard. CliRunner runs without a
    TTY by default and the test environment has no ``opencode`` on
    PATH, so the wizard's binary guard fires before the TTY guard:
    the user sees the install/configure guidance, not a "requires
    TTY" message. Either error message is acceptable as long as the
    exit is non-zero with a non-empty explanation — the binary guard
    is what surfaces in practice.
    """
    result = runner.invoke(app, ["set-models", "-o", "opencode"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    # The binary guard fires first when OpenCode is absent, so the
    # message will name the install/auth remediation. Accept the TTY
    # message too in case a developer machine has opencode on PATH.
    lowered = combined.lower()
    assert "opencode" in lowered or "tty" in lowered or "interactive" in lowered, (
        f"expected install/configure or TTY guidance, got: {combined!r}"
    )


def test_cli_set_models_copilot_not_supported(isolated_home: Path) -> None:
    """Copilot is rejected with a message that names the Copilot-native model mechanism.

    Acceptance criterion: ``set-models -o copilot`` must still reject, but the
    rejection message must point the user at the Copilot-native way to set a
    model (``/model`` or ``~/.copilot/settings.json``) — no wizard, catalog,
    or per-agent override-store support is added for copilot.
    """
    result = runner.invoke(app, ["set-models", "-o", "copilot"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    lowered = combined.lower()
    assert "copilot" in lowered
    # The message must reference the Copilot-native mechanism.
    assert "/model" in lowered or "settings.json" in lowered, (
        f"expected /model or settings.json in copilot rejection, got: {combined!r}"
    )


def test_cli_set_models_generic_not_supported(isolated_home: Path) -> None:
    """Generic is not in the wizard's vocabulary at all."""
    result = runner.invoke(app, ["set-models", "-o", "generic"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    assert "generic" in combined.lower()


def test_cli_set_models_no_cli_invalid_choice_message_scoped(isolated_home: Path) -> None:
    """Empty -o ('') yields a 'Valid:' suffix scoped to claude/opencode only."""
    result = runner.invoke(app, ["set-models", "-o", ""])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}".lower()
    assert "claude" in combined
    assert "opencode" in combined
    assert "generic" not in combined
    assert "copilot" not in combined


def test_cli_set_models_repeated_flag_invalid_choice_message_scoped(isolated_home: Path) -> None:
    """Repeated -o flags yield a 'Valid:' suffix scoped to claude/opencode only."""
    result = runner.invoke(app, ["set-models", "-o", "claude", "-o", "opencode"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}".lower()
    assert "valid: claude, opencode" in combined


def test_cli_set_models_help_mentions_only_claude_opencode() -> None:
    """``--help`` must mention only claude and opencode, not generic or copilot."""
    result = runner.invoke(app, ["set-models", "--help"])

    assert result.exit_code == 0
    lowered = result.stdout.lower()
    assert "claude" in lowered
    assert "opencode" in lowered
    assert "generic" not in lowered
    assert "copilot" not in lowered


# ---------------------------------------------------------------------------
# -a/--agent flag — strict-lowercase validation + default-is-change + help text
# ---------------------------------------------------------------------------


def test_cli_set_models_default_agent_flag_is_change(isolated_home: Path) -> None:
    """Omitting ``-a`` defaults to ``change`` — the only valid agent set.

    Acceptance scenario 5: ``set-models -o opencode`` (no ``-a``) routes
    the wizard through the change-agent branch. Here we verify the flag's
    *absence* keeps the CLI surface intact (a non-zero exit only because
    CliRunner has no TTY / no opencode binary — the rejection happens
    AFTER ``-a`` is parsed and defaults).
    """
    # Patch the wizard dispatch so we can verify the parsed AgentMode reached
    # the seam without standing up a real TUI / opencode install. We patch
    # the symbol where set_models.py imported it (commands.set_models), not
    # the wizard's own module — module-level imports bind the name once.
    from ai_harness.commands import set_models as set_models_mod

    captured: dict[str, object] = {}

    def fake_run_wizard_or_bail(cli, *, home, agent_mode=AgentMode.CHANGE):
        captured["cli"] = cli
        captured["agent_mode"] = agent_mode
        return False  # force the command to exit non-zero so we can inspect captured

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(set_models_mod, "run_wizard_or_bail", fake_run_wizard_or_bail)
    try:
        result = runner.invoke(app, ["set-models", "-o", "opencode"])
        assert result.exit_code != 0  # we forced non-zero from the fake
        assert captured.get("cli") == AgentCli.OPENCODE
        assert captured.get("agent_mode") == AgentMode.CHANGE
    finally:
        monkeypatch.undo()


def test_cli_set_models_loop_agent_flag_errors(isolated_home: Path) -> None:
    """``-a loop`` is rejected — the loop agent set has been removed.

    Acceptance scenario: the rejection message names ``change`` as the
    only valid value. typer maps ``typer.BadParameter`` to exit code 2.
    """
    result = runner.invoke(app, ["set-models", "-o", "opencode", "-a", "loop"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}".lower()
    assert "change" in combined
    # typer exit code 2 for BadParameter; 1 is also acceptable on this CLI surface
    assert result.exit_code in (1, 2)


def test_cli_set_models_unknown_agent_flag_errors(isolated_home: Path) -> None:
    """``-a bogus`` is rejected with a typer error naming the valid set.

    Acceptance scenario 6: the rejection message names ``change`` so
    the user knows which value is accepted. typer maps
    ``typer.BadParameter`` to exit code 2.
    """
    result = runner.invoke(app, ["set-models", "-o", "opencode", "-a", "bogus"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}".lower()
    assert "change" in combined
    # typer exit code 2 for BadParameter; 1 is also acceptable on this CLI surface
    assert result.exit_code in (1, 2)


def test_cli_set_models_uppercase_agent_flag_errors(isolated_home: Path) -> None:
    """``-a CHANGE`` (uppercase) is rejected — strict lowercase vocabulary.

    Acceptance scenario 7: case-insensitive matching is explicitly out
    of scope. ``-a CHANGE`` errors with the same valid-values hint as
    ``-a bogus``. ``typer.BadParameter`` → exit code 2.
    """
    result = runner.invoke(app, ["set-models", "-o", "opencode", "-a", "CHANGE"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}".lower()
    assert "change" in combined


def test_cli_set_models_help_mentions_agent_flag_and_valid_values() -> None:
    """``--help`` documents the ``-a/--agent`` flag, names the valid value, and states the claude-ignored note.

    Acceptance criterion ``req:help-text-honest-001``: future refactors
    must not silently drop the valid-values list or the claude-ignored
    note. A unit test pins the wording so a typo / drift shows up here.
    """
    result = runner.invoke(app, ["set-models", "--help"])

    assert result.exit_code == 0
    lowered = result.stdout.lower()
    # Flag is advertised with both short and long forms.
    assert "-a" in lowered
    assert "--agent" in lowered
    # The valid value is named explicitly.
    assert "change" in lowered
    # The claude-ignored note is present so users discover the silent-ignore contract.
    assert "claude" in lowered
    assert "ignored" in lowered or "ignore" in lowered


# ---------------------------------------------------------------------------
# set_models CLI — non-TTY guard for claude (must not hang waiting for stdin)
# ---------------------------------------------------------------------------


def test_cli_set_models_claude_non_tty_errors(isolated_home: Path) -> None:
    """Without a TTY, the Claude wizard errors immediately rather than blocking on stdin."""
    # CliRunner runs without a TTY by default; questionary.select fails
    # on EOF rather than blocking. The command must convert that into a
    # non-zero exit with a clear message.
    result = runner.invoke(app, ["set-models", "-o", "claude"])

    assert result.exit_code != 0
    combined = f"{result.stdout} {result.stderr}"
    # Either "tty", "stdin", or "interactive" is in the message — or simply
    # the wizard bailed cleanly because no input was available.
    assert combined.strip() != "", "expected some output explaining the bail-out"


# ---------------------------------------------------------------------------
# set_models — OpenCode binary guard (acceptance criterion for issue #46)
# ---------------------------------------------------------------------------


def test_cli_set_models_opencode_absent_errors_with_install_guidance(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``-o opencode`` with no OpenCode on PATH errors with install/configure guidance.

    Acceptance criterion for issue #46: when ``opencode`` is not on the
    user's PATH, ``set-models -o opencode`` must fail non-zero and
    surface install/auth guidance rather than hanging on a TTY prompt
    or producing a misleading "not implemented" message.

    The flow now runs the OpenCode binary check BEFORE the TTY check in
    :func:`run_wizard_or_bail` — so this CliRunner (no TTY) reliably
    reaches the binary-missing path. Patching
    :func:`_resolve_opencode_binary` to ``None`` makes the test
    independent of whether the developer happens to have opencode
    installed locally.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: None)

    result = runner.invoke(app, ["set-models", "-o", "opencode"])

    assert result.exit_code != 0, (
        f"expected non-zero exit for absent opencode, got {result.exit_code}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = f"{result.stdout} {result.stderr}"
    # The guard must surface install/configure guidance — both the
    # missing tool name AND a remediation step.
    assert "opencode" in combined.lower(), f"expected 'opencode' in error, got: {combined!r}"
    lowered = combined.lower()
    assert "install" in lowered or "auth" in lowered, (
        f"expected install/configure guidance ('install' or 'auth') in error, got: {combined!r}"
    )


def test_run_wizard_or_bail_opencode_absent_skips_tty_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``run_wizard_or_bail`` for OpenCode checks the binary BEFORE the TTY.

    Direct unit test for the ordering: when OpenCode is absent, the
    function must return ``False`` with the install/auth message even
    though the test process has no TTY. If the TTY check fired first,
    the function would return ``False`` with the wrong message and
    ``_resolve_opencode_binary`` would never be consulted.
    """
    from ai_harness.modules.harness import AgentCli
    from ai_harness.modules.wizard import tui

    binary_calls: list[str] = []
    monkeypatch.setattr(
        tui,
        "_resolve_opencode_binary",
        lambda: binary_calls.append("called") or None,
    )

    # CliRunner runs without a TTY — the test harness is no exception.
    # If the TTY check fired before the binary check, this would
    # return False with a TTY message instead of the install guidance.
    wrote = tui.run_wizard_or_bail(AgentCli.OPENCODE, home=tmp_path)

    assert wrote is False
    assert binary_calls == ["called"], "binary check must fire before TTY check for OpenCode"


# ---------------------------------------------------------------------------
# Wizard pickers — type-to-filter wiring (acceptance criterion: search filter)
# ---------------------------------------------------------------------------
# These tests do NOT drive the full TUI. They spy on questionary.select to
# confirm the picker functions wire the ``use_search_filter=True`` kwarg that
# enables type-to-filter navigation. Driving the actual prompt would test
# the questionary library, not us.


class _SelectSpy:
    """Captures kwargs from each questionary.select call and returns None from .ask().

    The ``None`` return simulates a Ctrl+C cancel so the wizard bails out
    cleanly without needing a real terminal.
    """

    instances: list[_SelectSpy] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs
        _SelectSpy.instances.append(self)

    def ask(self) -> None:
        return None


def test_model_picker_enables_search_filter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The Claude model picker must enable type-to-filter (acceptance criterion)."""
    from ai_harness.modules.wizard import tui

    _SelectSpy.instances = []
    monkeypatch.setattr(tui.questionary, "select", _SelectSpy)

    tui._ask_claude_model("change-implementor", tmp_path)  # type: ignore[attr-defined]

    assert _SelectSpy.instances, "questionary.select was not called"
    assert _SelectSpy.instances[0].kwargs.get("use_search_filter") is True


def test_effort_picker_enables_search_filter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The Claude effort picker must enable type-to-filter (acceptance criterion)."""
    from ai_harness.modules.wizard import tui

    _SelectSpy.instances = []
    monkeypatch.setattr(tui.questionary, "select", _SelectSpy)

    tui._ask_claude_effort("change-validator", tmp_path)  # type: ignore[attr-defined]

    assert _SelectSpy.instances, "questionary.select was not called"
    assert _SelectSpy.instances[0].kwargs.get("use_search_filter") is True


def test_claude_effort_picker_capitalizes_display_label_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The effort picker shows "High" etc. but the underlying value stays lowercase "high"."""
    from ai_harness.modules.wizard import tui

    _SelectSpy.instances = []
    monkeypatch.setattr(tui.questionary, "select", _SelectSpy)

    tui._ask_claude_effort("change-validator", tmp_path)  # type: ignore[attr-defined]

    choices = _SelectSpy.instances[0].kwargs["choices"]
    high_choice = next(c for c in choices if c.value == "high")
    assert high_choice.title == "change-validator → High"
    assert high_choice.value == "high"


def test_claude_model_picker_does_not_capitalize_label(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The model picker's labels must never be capitalized — model ids stay lowercase."""
    from ai_harness.modules.wizard import tui

    _SelectSpy.instances = []
    monkeypatch.setattr(tui.questionary, "select", _SelectSpy)

    tui._ask_claude_model("change-implementor", tmp_path)  # type: ignore[attr-defined]

    choices = _SelectSpy.instances[0].kwargs["choices"]
    sonnet_choice = next(c for c in choices if c.value == "sonnet")
    assert sonnet_choice.title == "change-implementor → sonnet"


def test_opencode_effort_picker_capitalizes_display_label_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The OpenCode effort picker capitalizes the display only; value stays lowercase."""
    from ai_harness.modules.wizard import tui

    _SelectSpy.instances = []
    monkeypatch.setattr(tui.questionary, "select", _SelectSpy)

    tui._ask_opencode_effort("change-validator", tmp_path)  # type: ignore[attr-defined]

    choices = _SelectSpy.instances[0].kwargs["choices"]
    high_choice = next(c for c in choices if c.value == "high")
    assert high_choice.title == "change-validator → High"
    assert high_choice.value == "high"


def test_agent_continue_picker_enables_search_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent-picker (with the Continue sentinel) must also enable search filtering."""
    from ai_harness.modules.wizard import tui

    _SelectSpy.instances = []
    monkeypatch.setattr(tui.questionary, "select", _SelectSpy)

    tui._ask_continue_or_agent("model", {"implementor": "opus"})  # type: ignore[attr-defined]

    assert _SelectSpy.instances, "questionary.select was not called"
    assert _SelectSpy.instances[0].kwargs.get("use_search_filter") is True


def test_keybinding_legend_advertises_jk_and_filter() -> None:
    """The header/footer legend must advertise j/k navigation AND type-to-filter.

    Acceptance requires BOTH vim-style j/k navigation and type-to-filter. The
    questionary pickers delegate to a custom wrapper that wires j/k to
    navigation (not filter input) and keeps the search filter active.
    """
    from ai_harness.modules.wizard import tui

    legend = tui._KEYBINDING_LEGEND
    assert "type to filter" in legend
    assert "↑/↓" in legend
    assert "j/k" in legend


def test_header_phase_renders_legend_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The navigation header must not be duplicated on screen.

    Regression test for #48: ``_print_header`` rendered the keybinding
    legend inside its panel, and a separate ``_print_footer`` call printed
    the same legend again right below it, reading as a duplicated header.
    A wizard phase must call into ``_console.print`` only once to render
    the header+legend, with no second call carrying the same legend text.
    """
    from ai_harness.modules.wizard import tui

    printed: list[object] = []
    monkeypatch.setattr(tui._console, "print", lambda *args, **kwargs: printed.append(args))

    tui._print_header("set-models · claude")

    assert len(printed) == 1, f"expected exactly one _console.print call for the header phase, got {len(printed)}"
    panel_text = str(printed[0][0].renderable)
    legend_occurrences = panel_text.count(tui._KEYBINDING_LEGEND)
    assert legend_occurrences == 1, f"expected legend rendered exactly once, got {legend_occurrences}"
    assert not hasattr(tui, "_print_footer"), "_print_footer must be removed, not just left unused"


# ---------------------------------------------------------------------------
# run_wizard — clear console on entry (issue #49)
# ---------------------------------------------------------------------------


def test_run_wizard_clears_console_before_header(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``run_wizard`` must clear the terminal once, before any output, on every path.

    Regression guard for #49: prior wizard runs left earlier command output
    on screen when the wizard's first screen rendered. The clear must happen
    exactly once and strictly before the first ``_console.print`` call.
    """
    from unittest.mock import PropertyMock

    from ai_harness.modules.harness import AgentCli
    from ai_harness.modules.wizard import tui

    calls: list[str] = []
    monkeypatch.setattr(type(tui._console), "is_terminal", PropertyMock(return_value=True))
    monkeypatch.setattr(tui._console, "clear", lambda: calls.append("clear"))
    monkeypatch.setattr(tui, "run_claude_wizard", lambda **kwargs: calls.append("claude") or True)
    monkeypatch.setattr(tui, "run_opencode_wizard", lambda **kwargs: calls.append("opencode") or True)

    tui.run_wizard(AgentCli.CLAUDE, home=tmp_path)

    assert calls == ["clear", "claude"], f"expected clear before claude wizard dispatch, got {calls}"

    calls.clear()
    tui.run_wizard(AgentCli.OPENCODE, home=tmp_path)

    assert calls == ["clear", "opencode"], f"expected clear before opencode wizard dispatch, got {calls}"


def test_run_wizard_skips_clear_when_not_a_terminal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``run_wizard`` must not clear when stdout is not a terminal (e.g. CI, pytest capture)."""
    from unittest.mock import PropertyMock

    from ai_harness.modules.harness import AgentCli
    from ai_harness.modules.wizard import tui

    calls: list[str] = []
    monkeypatch.setattr(type(tui._console), "is_terminal", PropertyMock(return_value=False))
    monkeypatch.setattr(tui._console, "clear", lambda: calls.append("clear"))
    monkeypatch.setattr(tui, "run_claude_wizard", lambda **kwargs: True)

    tui.run_wizard(AgentCli.CLAUDE, home=tmp_path)

    assert calls == [], "clear must not be called when _console.is_terminal is False"


# ---------------------------------------------------------------------------
# _print_header — clear on every render (issue #51)
# ---------------------------------------------------------------------------


def test_print_header_clears_terminal_before_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_print_header`` must clear the terminal before printing its panel.

    Regression guard for #51: moving between wizard parts (model -> effort
    -> confirm, including back-navigation and repeated agent-edit loops)
    left prior output stacked on screen. Folding the clear into
    ``_print_header`` makes "clear + render header" one atomic unit so
    every phase render starts from a clean screen.
    """
    from unittest.mock import PropertyMock

    from ai_harness.modules.wizard import tui

    calls: list[str] = []
    monkeypatch.setattr(type(tui._console), "is_terminal", PropertyMock(return_value=True))
    monkeypatch.setattr(tui._console, "clear", lambda: calls.append("clear"))
    monkeypatch.setattr(tui._console, "print", lambda *a, **kw: calls.append("print"))

    tui._print_header("set-models · claude — model")

    assert calls == ["clear", "print"], f"expected clear before header print, got {calls}"


def test_print_header_skips_clear_when_not_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_print_header`` must not clear when stdout is not a terminal (e.g. CI, pytest capture)."""
    from unittest.mock import PropertyMock

    from ai_harness.modules.wizard import tui

    calls: list[str] = []
    monkeypatch.setattr(type(tui._console), "is_terminal", PropertyMock(return_value=False))
    monkeypatch.setattr(tui._console, "clear", lambda: calls.append("clear"))

    tui._print_header("set-models · claude — model")

    assert calls == [], "clear must not be called when _console.is_terminal is False"


# ---------------------------------------------------------------------------
# Phase spacing — blank line between header and title (issue #55)
# ---------------------------------------------------------------------------


def test_claude_model_phase_prints_blank_line_after_header(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The Claude model phase prints a blank line right after the header panel."""
    from ai_harness.modules.wizard import tui

    printed: list[tuple[object, ...]] = []
    monkeypatch.setattr(tui._console, "print", lambda *a, **kw: printed.append(a))
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []
    scripted = _ScriptedSelect()
    scripted.queue("__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    tui.run_claude_wizard(home=tmp_path)

    # First print is the header Panel; the next must be a bare blank-line print.
    assert printed[0][0].__class__.__name__ == "Panel"
    assert printed[1] == ("",)


def test_ask_confirm_prints_blank_line_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """The confirm screen prints a blank line right after the header panel."""
    from ai_harness.modules.wizard import tui

    printed: list[tuple[object, ...]] = []
    monkeypatch.setattr(tui._console, "print", lambda *a, **kw: printed.append(a))
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: _ScriptedConfirm().queue(True))

    tui._ask_confirm("set-models · claude — confirm", {"implementor": ModelSelection("opus", "high")})

    assert printed[0][0].__class__.__name__ == "Panel"
    assert printed[1] == ("",)


# ---------------------------------------------------------------------------
# Wizard pickers — j/k navigation binding (acceptance criterion: vim-style nav)
# ---------------------------------------------------------------------------
# These tests verify that ``_filterable_select`` attaches j/k key bindings to
# the prompt_toolkit Application that drive the underlying InquirerControl's
# ``select_next`` / ``select_previous``. We do NOT drive the full prompt —
# just confirm the bindings exist and call the right methods.


def test_filterable_select_attaches_jk_bindings() -> None:
    """The custom select wrapper must add j/k bindings to the prompt's key registry."""
    import questionary

    from ai_harness.modules.wizard import tui

    choices = [questionary.Choice(title="alpha", value="a"), questionary.Choice(title="beta", value="b")]
    question = tui._filterable_select("Test:", choices=choices)

    keys = {b.keys[0] for b in question.application.key_bindings.bindings}
    assert "j" in keys
    assert "k" in keys


def test_filterable_select_attaches_escape_binding() -> None:
    """The custom select wrapper must add an Esc binding to the prompt's key registry."""
    import questionary
    from prompt_toolkit.keys import Keys

    from ai_harness.modules.wizard import tui

    choices = [questionary.Choice(title="alpha", value="a"), questionary.Choice(title="beta", value="b")]
    question = tui._filterable_select("Test:", choices=choices)

    keys = {b.keys[0] for b in question.application.key_bindings.bindings}
    assert Keys.Escape in keys


def test_filterable_select_escape_exits_with_esc_back_sentinel() -> None:
    """Pressing Esc on a filterable select exits the Application with the _ESC_BACK sentinel."""
    import prompt_toolkit.key_binding.key_processor as kp
    import questionary
    from prompt_toolkit.key_binding import KeyPress
    from prompt_toolkit.keys import Keys

    from ai_harness.modules.wizard import tui

    kp.KeyProcessor._start_timeout = lambda self: None

    choices = [questionary.Choice(title="alpha", value="a"), questionary.Choice(title="beta", value="b")]
    question = tui._filterable_select("Test:", choices=choices)

    exit_results: list[object] = []
    question.application.exit = lambda result=None, **kw: exit_results.append(result)

    processor = question.application.key_processor
    processor.feed(KeyPress(Keys.Escape, "\x1b"))
    processor.process_keys()

    assert exit_results == [tui.Nav.ESC_BACK]


def test_filterable_select_jk_moves_inquirer_pointer() -> None:
    """Pressing j / k on the picker actually moves the InquirerControl's pointer."""
    import prompt_toolkit.key_binding.key_processor as kp
    import questionary
    from prompt_toolkit.key_binding import KeyPress

    from ai_harness.modules.wizard import tui

    # Avoid prompt_toolkit trying to start an event-loop timeout in tests.
    kp.KeyProcessor._start_timeout = lambda self: None

    choices = [
        questionary.Choice(title="alpha", value="a"),
        questionary.Choice(title="beta", value="b"),
        questionary.Choice(title="gamma", value="c"),
    ]
    question = tui._filterable_select("Test:", choices=choices)
    inquirer_control = tui._find_inquirer_control(question.application.layout.container)
    assert inquirer_control is not None
    assert inquirer_control.pointed_at == 0

    processor = question.application.key_processor
    # j → next
    processor.feed(KeyPress("j", "j"))
    processor.process_keys()
    assert inquirer_control.pointed_at == 1

    # j → next
    processor.feed(KeyPress("j", "j"))
    processor.process_keys()
    assert inquirer_control.pointed_at == 2

    # k → previous
    processor.feed(KeyPress("k", "k"))
    processor.process_keys()
    assert inquirer_control.pointed_at == 1


# ---------------------------------------------------------------------------
# Confirm screen — Esc-binding regression (issue #56)
# ---------------------------------------------------------------------------
# Every other test in this module that exercises ``_ask_confirm`` stubs
# ``questionary.confirm`` with ``_ScriptedConfirm``, which has no
# ``.application`` attribute — so ``_ask_confirm``'s ``getattr(question,
# "application", None)`` short-circuits and the Esc-binding code never runs.
# That's how issue #56's crash slipped past every #55 test: a REAL
# ``questionary.confirm(...).application.key_bindings`` is a prompt_toolkit
# ``_MergedKeyBindings`` (because ``PromptSession`` merges internally), which
# has no ``.add`` method — unlike ``questionary.select``'s plain
# ``KeyBindings``. These tests build a real prompt_toolkit ``Application``
# (via ``create_pipe_input`` / ``DummyOutput``) so the merge bug is actually
# exercised.


def test_ask_confirm_esc_binding_real_application_does_not_raise() -> None:
    """Attaching the Esc binding to a REAL confirm Application must not raise.

    Regression for #56: ``application.key_bindings.add(...)`` blew up with
    ``AttributeError: '_MergedKeyBindings' object has no attribute 'add'``
    because a real ``questionary.confirm`` Application's key_bindings are
    merged, not a plain ``KeyBindings`` registry.
    """
    import questionary
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from ai_harness.modules.wizard import tui

    with create_pipe_input() as inp:
        question = questionary.confirm("Confirm?", default=True, input=inp, output=DummyOutput())
        # Exercise the exact helper _ask_confirm relies on to attach Esc.
        tui._attach_esc_back(question.application, tui.Nav.ESC_BACK)


def test_ask_confirm_esc_binding_real_application_exits_with_esc_back() -> None:
    """Pressing Esc on a real confirm Application exits with the _ESC_BACK sentinel."""
    import questionary
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from ai_harness.modules.wizard import tui

    with create_pipe_input() as inp:
        question = questionary.confirm("Confirm?", default=True, input=inp, output=DummyOutput())
        tui._attach_esc_back(question.application, tui.Nav.ESC_BACK)

        inp.send_text("\x1b")
        answer = question.ask()

    assert answer == tui.Nav.ESC_BACK


def test_filterable_select_esc_binding_uses_shared_helper_real_application() -> None:
    """``_filterable_select``'s Esc binding also works through the shared helper.

    Confirms the merge-based helper is safe for the select path too (plain
    ``KeyBindings``, not merged) — same helper, same behaviour, no regression
    to the #55 j/k bindings.
    """
    import prompt_toolkit.key_binding.key_processor as kp
    import questionary
    from prompt_toolkit.key_binding import KeyPress
    from prompt_toolkit.keys import Keys

    from ai_harness.modules.wizard import tui

    kp.KeyProcessor._start_timeout = lambda self: None

    choices = [questionary.Choice(title="alpha", value="a"), questionary.Choice(title="beta", value="b")]
    question = tui._filterable_select("Test:", choices=choices)

    exit_results: list[object] = []
    question.application.exit = lambda result=None, **kw: exit_results.append(result)

    processor = question.application.key_processor
    processor.feed(KeyPress(Keys.Escape, "\x1b"))
    processor.process_keys()

    assert exit_results == [tui.Nav.ESC_BACK]


def test_filterable_select_jk_skips_disabled_choices() -> None:
    """j/k navigation must skip disabled choices, matching the arrow-key behaviour."""
    import prompt_toolkit.key_binding.key_processor as kp
    import questionary
    from prompt_toolkit.key_binding import KeyPress

    from ai_harness.modules.wizard import tui

    kp.KeyProcessor._start_timeout = lambda self: None

    choices = [
        questionary.Choice(title="alpha", value="a"),
        questionary.Choice(title="blocked", value="b", disabled="not available"),
        questionary.Choice(title="gamma", value="c"),
    ]
    question = tui._filterable_select("Test:", choices=choices)
    inquirer_control = tui._find_inquirer_control(question.application.layout.container)
    assert inquirer_control is not None

    processor = question.application.key_processor
    processor.feed(KeyPress("j", "j"))
    processor.process_keys()
    # j from index 0 should skip the disabled "blocked" and land on "gamma" (index 2).
    assert inquirer_control.get_pointed_at().value == "c"


def test_filterable_select_keeps_type_to_filter_for_other_chars() -> None:
    """Non-navigation letters must still feed the InquirerControl's search filter."""
    import prompt_toolkit.key_binding.key_processor as kp
    import questionary
    from prompt_toolkit.key_binding import KeyPress

    from ai_harness.modules.wizard import tui

    kp.KeyProcessor._start_timeout = lambda self: None

    choices = [
        questionary.Choice(title="alpha", value="a"),
        questionary.Choice(title="beta", value="b"),
    ]
    question = tui._filterable_select("Test:", choices=choices)
    inquirer_control = tui._find_inquirer_control(question.application.layout.container)
    assert inquirer_control is not None
    assert inquirer_control.search_filter is None

    processor = question.application.key_processor
    # Press 'a' — not bound to our j/k handler, so it must hit the search filter.
    processor.feed(KeyPress("a", "a"))
    processor.process_keys()
    assert inquirer_control.search_filter == "a"


# ---------------------------------------------------------------------------
# Always-visible filter box, positioned ABOVE the list (issue #55)
# ---------------------------------------------------------------------------


def test_filterable_select_filter_row_sits_immediately_above_the_list() -> None:
    """The filter row is inserted directly above the rendered choice list, not below."""
    import questionary

    from ai_harness.modules.wizard import tui

    choices = [questionary.Choice(title="alpha", value="a"), questionary.Choice(title="beta", value="b")]
    question = tui._filterable_select("Test:", choices=choices)

    slot = tui._find_inquirer_window_slot(question.application.layout.container)
    assert slot is not None
    children, list_index = slot

    assert list_index > 0, "the list window must have a sibling above it (the filter row)"
    filter_row = children[list_index - 1]
    # The filter row's inner control renders "Filter: " — distinguishing it
    # from any other sibling that might be inserted above the list.
    window = getattr(filter_row, "content", None)
    control = getattr(window, "content", None)
    tokens = control.text()
    assert any("Filter: " in text for _, text in tokens)


def test_filterable_select_has_spacer_between_title_and_filter_row() -> None:
    """A blank spacer row sits between the prompt title and the filter row."""
    import questionary

    from ai_harness.modules.wizard import tui

    choices = [questionary.Choice(title="alpha", value="a")]
    question = tui._filterable_select("Test:", choices=choices)

    slot = tui._find_inquirer_window_slot(question.application.layout.container)
    children, list_index = slot
    # children: [title, spacer, filter, list, ...]
    filter_index = list_index - 1
    spacer_index = filter_index - 1
    assert spacer_index >= 0
    spacer_tokens = children[spacer_index].content.content.text()
    filter_tokens = children[filter_index].content.content.text()
    assert all(text == "" for _, text in spacer_tokens)
    assert any("Filter: " in text for _, text in filter_tokens)


def test_filterable_select_filter_row_visible_before_any_keystroke() -> None:
    """The filter row renders "Filter: " even with no search filter typed yet.

    Unlike questionary's own hidden-until-first-keystroke search box, the
    wizard's filter row must be visible from the start (always-visible
    requirement).
    """
    import questionary

    from ai_harness.modules.wizard import tui

    choices = [questionary.Choice(title="alpha", value="a")]
    question = tui._filterable_select("Test:", choices=choices)

    slot = tui._find_inquirer_window_slot(question.application.layout.container)
    children, list_index = slot
    filter_row = children[list_index - 1]
    tokens = filter_row.content.content.text()
    assert tokens == [("class:text", "Filter: ")]


def test_filterable_select_filter_row_updates_live_with_keystrokes() -> None:
    """Typing updates the always-visible filter row's rendered text live."""
    import prompt_toolkit.key_binding.key_processor as kp
    import questionary
    from prompt_toolkit.key_binding import KeyPress

    from ai_harness.modules.wizard import tui

    kp.KeyProcessor._start_timeout = lambda self: None

    choices = [questionary.Choice(title="alpha", value="a"), questionary.Choice(title="beta", value="b")]
    question = tui._filterable_select("Test:", choices=choices)

    processor = question.application.key_processor
    processor.feed(KeyPress("a", "a"))
    processor.process_keys()

    slot = tui._find_inquirer_window_slot(question.application.layout.container)
    children, list_index = slot
    filter_row = children[list_index - 1]
    tokens = filter_row.content.content.text()
    assert tokens == [("class:text", "Filter: a")]


def test_filterable_select_filter_row_still_preserves_jk_and_search() -> None:
    """Inserting the filter row must not break existing j/k nav or type-to-filter."""
    import prompt_toolkit.key_binding.key_processor as kp
    import questionary
    from prompt_toolkit.key_binding import KeyPress

    from ai_harness.modules.wizard import tui

    kp.KeyProcessor._start_timeout = lambda self: None

    choices = [
        questionary.Choice(title="alpha", value="a"),
        questionary.Choice(title="beta", value="b"),
        questionary.Choice(title="gamma", value="c"),
    ]
    question = tui._filterable_select("Test:", choices=choices)
    inquirer_control = tui._find_inquirer_control(question.application.layout.container)
    assert inquirer_control.pointed_at == 0

    processor = question.application.key_processor
    processor.feed(KeyPress("j", "j"))
    processor.process_keys()
    assert inquirer_control.pointed_at == 1

    processor.feed(KeyPress("a", "a"))
    processor.process_keys()
    assert inquirer_control.search_filter == "a"


def test_filterable_select_still_enables_search_filter_kwarg() -> None:
    """The wrapper passes ``use_search_filter=True`` to questionary.select."""
    import ai_harness.modules.wizard.tui as tui_mod

    captured: list[dict[str, object]] = []

    def fake_select(message: object, *args: object, **kwargs: object) -> object:
        captured.append(kwargs)

        class _Q:
            # No ``application`` attribute — the wrapper must handle this gracefully
            # and still pass the right kwargs (mirrors the existing _SelectSpy tests).

            def ask(self) -> None:
                return None

        return _Q()

    original = tui_mod.questionary.select
    tui_mod.questionary.select = fake_select  # type: ignore[assignment]
    try:
        tui_mod._filterable_select("Test:", choices=[])
    finally:
        tui_mod.questionary.select = original  # type: ignore[assignment]

    assert captured, "questionary.select was not called"
    assert captured[0].get("use_search_filter") is True
    assert captured[0].get("use_jk_keys") is False
    assert captured[0].get("use_arrow_keys") is True


# ---------------------------------------------------------------------------
# Wizard — selective override write (issue #45 fix-up)
#
# These tests drive ``run_claude_wizard`` end-to-end with monkey-patched
# pickers. They verify that the override store stays partial — the bug the
# validator flagged was that the wizard wrote every agent's current model
# into overrides.json even when the user had not changed anything, polluting
# the store with template defaults.
# ---------------------------------------------------------------------------


class _ScriptedSelect:
    """A questionary.select stub that returns a queued value from .ask().

    Each instance consumes one entry from ``responses`` (a list). When the
    list is exhausted, the spy returns ``"__continue__"`` — the wizard's
    sentinel for "advance to the next phase without editing" — which lets
    the test script a full happy-path flow without real terminal input.

    Each construction also appends ``(message, choices)`` to the
    class-level ``captures`` ring buffer (last 3 entries) so tests can
    assert on the prompt body — e.g. that the effort-phase agent list
    rows render ``agent: model / (unset)`` rather than the legacy
    ``agent -> effort`` shape.
    """

    instances: list[_ScriptedSelect] = []
    captures: list[tuple[object, object]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs
        self._responses: list[object] = []
        type(self).instances.append(self)
        # Snapshot the prompt body for prompt-body assertions.
        message = args[0] if args else ""
        choices = kwargs.get("choices", [])
        type(self).captures.append((message, choices))
        # Cap the ring at 3 entries so tests that drive many prompts do
        # not accumulate state; tests assert against the most recent.
        if len(type(self).captures) > 3:
            type(self).captures.pop(0)

    def queue(self, *values: object) -> _ScriptedSelect:
        """Schedule *values* to be returned by successive .ask() calls."""
        self._responses.extend(values)
        return self

    def ask(self) -> object:
        if self._responses:
            return self._responses.pop(0)
        # Default fall-through: simulate the user pressing Continue.
        return "__continue__"


class _ScriptedConfirm:
    """A questionary.confirm stub that returns ``True`` (the user pressed enter)."""

    instances: list[_ScriptedConfirm] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs
        self._response: bool = True
        type(self).instances.append(self)

    def queue(self, value: bool) -> _ScriptedConfirm:
        self._response = value
        return self

    def ask(self) -> bool:
        return self._response


def _override_file(home: Path) -> Path:
    return home / ".ai-harness" / "overrides.json"


def _capturing_select(scripted: _ScriptedSelect, captures: list[tuple[object, object]]):
    """Wrap a shared :class:`_ScriptedSelect` so every wizard ``select`` call appends to *captures*.

    The lambda pattern used elsewhere (``lambda *a, **kw: scripted``) makes
    ``_ScriptedSelect.__init__`` run only once for the shared instance, so
    capturing prompt bodies in ``__init__`` records at most one entry per
    test. This helper instead records the (message, choices) tuple on
    every invocation the wizard makes, while still routing responses
    through the shared instance so ``scripted.queue(...)`` keeps working.
    """

    def factory(message, *args: object, **kwargs: object) -> _ScriptedSelect:
        choices = kwargs.get("choices", [])
        captures.append((message, list(choices) if choices else []))
        # Update the shared instance's args/kwargs so ask()-time inspections
        # (if any) see the latest call.
        scripted.args = (message, *args)
        scripted.kwargs = kwargs
        return scripted

    return factory


def test_run_claude_wizard_no_changes_does_not_create_override_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opening the wizard and confirming without edits leaves overrides.json absent.

    Regression for the validator's CRITICAL finding on issue #45: the wizard
    used to write every agent's current model into the override store,
    polluting it with template defaults. A fresh HOME plus a confirm without
    edits must produce no override file at all.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)

    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True, "wizard ran to completion; True is correct even with no writes"
    assert not _override_file(tmp_path).exists(), (
        "confirming without edits must NOT create overrides.json — that would "
        "be the default-pollution bug the validator flagged."
    )


def test_run_claude_wizard_model_change_writes_only_changed_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editing one agent's model writes only that (agent, model) entry."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)

    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1 (model pass): agent-pick returns "change-implementor", model-pick
    # returns "opus", then the next agent-pick returns Continue.
    # Phase 2 (effort pass): agent-pick returns Continue immediately.
    # Phase 3 (confirm): yes.
    scripted = _ScriptedSelect()
    scripted.queue("change-implementor", "opus", "__continue__", "__continue__")

    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert overrides == {"change-implementor": {"model": {"claude": "opus"}}}


def test_run_claude_wizard_existing_override_kept_when_user_confirms_as_is(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pre-existing non-default override survives a wizard session that confirms without edits.

    This is the "existing override values that user leaves as current may
    remain only if already present" half of the validator's spec: the
    wizard must NOT overwrite the prior file with a default-only payload.
    """
    from ai_harness.modules.wizard import tui

    # Seed an existing override that differs from the template default.
    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps({"implementor": {"model": {"claude": "haiku"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # User does not pick any agent — both phases go straight to confirm.
    scripted = _ScriptedSelect()
    scripted.queue("__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # Existing haiku override must survive untouched.
    assert overrides["implementor"] == {"model": {"claude": "haiku"}}
    # No new default entries for other agents.
    assert set(overrides.keys()) == {"implementor"}


def test_run_claude_wizard_effort_change_from_unset_writes_only_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting an agent's effort where baseline was None writes only the effort field."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1 (model): continue immediately.
    # Phase 2 (effort): pick change-validator, set effort to "high", continue.
    scripted = _ScriptedSelect()
    scripted.queue("__continue__", "change-validator", "high", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert overrides == {"change-validator": {"effort": {"claude": "high"}}}
    # No model entry leaked in — that would be the default-pollution bug.
    assert "model" not in overrides["change-validator"]


def test_run_claude_wizard_back_from_model_picker_returns_to_agent_choice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Picking "Back" inside the model picker returns to the model phase's agent chooser.

    Issue #50, transition 1: there was no way to back out of the per-agent
    model picker. Backing out must NOT record "__back__" as a model value
    for that agent — it must re-show the agent chooser so the user can
    pick the real value (or another agent, or continue) without polluting
    the override store with the sentinel itself.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1 (model): pick change-implementor -> back out of its model picker ->
    # continue (no agent edited in this phase).
    # Phase 2 (effort): continue immediately.
    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "__back__",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    assert not _override_file(tmp_path).exists(), (
        "backing out of the model picker must not write '__back__' (or any "
        "other value) as the agent's model — no override should exist."
    )


def test_run_claude_wizard_back_from_effort_picker_returns_to_agent_choice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Picking "Back" inside the effort picker returns to the effort phase's agent chooser.

    Issue #50, transition 2: mirrors the model-picker back behaviour for
    effort. Backing out must not record "__back__" as an effort value.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1 (model): continue immediately.
    # Phase 2 (effort): pick change-validator -> back out of effort picker -> continue.
    scripted = _ScriptedSelect()
    scripted.queue(
        "__continue__",
        "change-validator",
        "__back__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    assert not _override_file(tmp_path).exists(), (
        "backing out of the effort picker must not write '__back__' as the agent's effort — no override should exist."
    )


def test_run_claude_wizard_back_from_effort_phase_returns_to_model_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Picking "← Back" on the effort phase's agent chooser re-enters the model phase.

    Issue #50, transition 3: there was no way to go back from the effort
    phase to the model phase. State must survive the round trip: the
    model edit made before backing out must still be in effect when the
    user continues forward again, and the user can further revise it.
    """
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1 (model): pick change-implementor -> opus -> continue.
    # Phase 2 (effort): back -> re-enters phase 1 (model).
    # Phase 1 again: continue (change-implementor stays "opus", the prior edit).
    # Phase 2 again: continue.
    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "opus",
        "__continue__",
        "__back__",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert overrides == {"change-implementor": {"model": {"claude": "opus"}}}


def test_run_claude_wizard_no_back_choice_in_first_model_phase_agent_chooser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The model phase's agent chooser must NOT offer "← Back" — there is no prior phase."""
    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    tui._ask_continue_or_agent("model", {})

    assert captured, "the agent chooser did not call _filterable_select"
    values = [choice.value for choice in captured[0]]
    assert "__back__" not in values


# ---------------------------------------------------------------------------
# Esc = back, Ctrl+C = quit (issue #55)
# ---------------------------------------------------------------------------


def test_ask_continue_or_agent_esc_is_ignored_on_first_model_phase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Esc on the model phase's agent chooser (no predecessor) is a no-op, not '__back__'."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(
        tui, "_filterable_select", lambda *a, **kw: type("_Q", (), {"ask": lambda self: tui.Nav.ESC_BACK})()
    )

    result = tui._ask_continue_or_agent("model", {})

    assert result == tui.Nav.ESC_BACK, "the first phase has no back target — Esc must surface the raw sentinel"


def test_ask_continue_or_agent_esc_maps_to_back_on_effort_phase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Esc on the effort phase's agent chooser maps to '__back__' (return to model phase)."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(
        tui, "_filterable_select", lambda *a, **kw: type("_Q", (), {"ask": lambda self: tui.Nav.ESC_BACK})()
    )

    result = tui._ask_continue_or_agent("effort", {})

    assert result == "__back__"


def test_ask_opencode_continue_or_agent_esc_ignored_on_first_phase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Esc on the OpenCode model phase's agent chooser is a no-op."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(
        tui, "_filterable_select", lambda *a, **kw: type("_Q", (), {"ask": lambda self: tui.Nav.ESC_BACK})()
    )

    result = tui._ask_opencode_continue_or_agent("model", {}, opencode_change_agents())

    assert result == tui.Nav.ESC_BACK


def test_run_claude_wizard_esc_at_model_phase_agent_chooser_redraws_same_screen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Esc at the model phase's agent chooser is ignored — the wizard re-shows the same screen."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1 (model): Esc (no-op, redraw) -> continue.
    # Phase 2 (effort): continue.
    scripted = _ScriptedSelect()
    scripted.queue(
        tui.Nav.ESC_BACK,
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    assert not _override_file(tmp_path).exists()


def test_run_claude_wizard_esc_in_model_picker_returns_to_agent_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Esc inside the per-agent model picker behaves exactly like '← Back'."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        tui.Nav.ESC_BACK,
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    assert not _override_file(tmp_path).exists(), (
        "Esc inside the model picker must not write any override for the agent it abandoned editing."
    )


def test_run_claude_wizard_esc_on_effort_phase_agent_chooser_returns_to_model_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Esc on the effort phase's agent chooser goes back to the model phase, like '← Back'."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1 (model): pick change-implementor -> opus -> continue.
    # Phase 2 (effort): Esc -> re-enters phase 1 (model).
    # Phase 1 again: continue.
    # Phase 2 again: continue.
    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "opus",
        "__continue__",
        tui.Nav.ESC_BACK,
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert overrides == {"change-implementor": {"model": {"claude": "opus"}}}


def test_run_claude_wizard_esc_on_confirm_screen_returns_to_effort_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Esc on the confirm screen returns to the effort phase without writing anything yet."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    _ScriptedSelect.instances = []

    # Phase 1 (model): continue.
    # Phase 2 (effort): continue.
    # Confirm: Esc -> back to effort phase.
    # Phase 2 again: continue.
    # Confirm again: confirm (True).
    scripted = _ScriptedSelect()
    scripted.queue(
        "__continue__",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)

    confirm_responses = [tui.Nav.ESC_BACK, True]

    class _ConfirmSeq:
        def ask(self) -> object:
            return confirm_responses.pop(0)

    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: _ConfirmSeq())

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    assert not confirm_responses, "confirm must have been asked twice (Esc back, then confirm)"


def test_run_claude_wizard_ctrl_c_at_confirm_screen_still_cancels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ctrl+C on the confirm screen still fully cancels the wizard (semantics unchanged by #55)."""
    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    _ScriptedSelect.instances = []

    scripted = _ScriptedSelect()
    scripted.queue("__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)

    class _CtrlCConfirm:
        def ask(self) -> None:
            return None  # questionary.confirm returns None on Ctrl+C in this codebase's usage

    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: _CtrlCConfirm())

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is False
    assert not _override_file(tmp_path).exists()


def test_run_claude_wizard_clears_screen_once_per_phase_render(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each phase render (model, effort, confirm) clears the screen exactly once.

    Regression guard for #51: moving between wizard parts used to stack
    output instead of starting fresh. A straight-through run (continue,
    continue, confirm) hits exactly three phase renders, so the terminal
    must be cleared exactly three times.
    """
    from unittest.mock import PropertyMock

    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    clear_calls: list[str] = []
    monkeypatch.setattr(type(tui._console), "is_terminal", PropertyMock(return_value=True))
    monkeypatch.setattr(tui._console, "clear", lambda: clear_calls.append("clear"))

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    assert clear_calls == ["clear", "clear", "clear"], (
        f"expected one clear per phase render (model, effort, confirm), got {clear_calls}"
    )


def test_run_claude_wizard_back_navigation_clears_screen_again(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backing from the effort phase to the model phase clears the screen again.

    Regression guard for #51: back-navigation must re-clear so the
    re-rendered model phase doesn't stack on top of the effort phase's
    prior output.
    """
    from unittest.mock import PropertyMock

    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1 (model): continue immediately.
    # Phase 2 (effort): back -> re-enters phase 1 (model).
    # Phase 1 again: continue.
    # Phase 2 again: continue.
    # Phase 3: confirm.
    scripted = _ScriptedSelect()
    scripted.queue(
        "__continue__",
        "__back__",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    clear_calls: list[str] = []
    monkeypatch.setattr(type(tui._console), "is_terminal", PropertyMock(return_value=True))
    monkeypatch.setattr(tui._console, "clear", lambda: clear_calls.append("clear"))

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    # model, effort (back), model (again), effort (again), confirm = 5 renders.
    assert clear_calls == ["clear"] * 5, f"expected 5 phase-render clears (back re-clears), got {clear_calls}"


def test_run_claude_wizard_preserves_existing_install_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wizard's Claude re-render must NOT drop other CLIs from ``installed.json``.

    Regression for the validator's BLOCKER on issue #45: the set-models
    re-render path used to call ``install_for_agent_clis([Claude], ...)``,
    which rewrote the install manifest to only contain Claude and silently
    dropped generic + copilot entries. With multiple CLIs installed, the
    manifest must survive the wizard intact.
    """
    from ai_harness.modules.harness import install_for_agent_clis
    from ai_harness.modules.wizard import tui

    # Install generic + claude + copilot first so the manifest has them all.
    install_for_agent_clis(
        [AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT],
        home=tmp_path,
    )
    manifest_path = tmp_path / ".ai-harness" / "installed.json"
    before = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(before["agent_clis"]) == {"generic", "claude", "copilot"}

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Edit change-implementor's model, then confirm.
    scripted = _ScriptedSelect()
    scripted.queue("change-implementor", "opus", "__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    after = json.loads(manifest_path.read_text(encoding="utf-8"))
    # All three CLIs survive — the re-render is scoped to Claude change agents only.
    assert set(after["agent_clis"]) == {"generic", "claude", "copilot"}
    assert set(after["files_by_agent_cli"]) == {"generic", "claude", "copilot"}
    # Generic and copilot paths are byte-identical to before.
    for cli in ("generic", "copilot"):
        assert sorted(after["files_by_agent_cli"][cli]) == sorted(before["files_by_agent_cli"][cli])


# ---------------------------------------------------------------------------
# Effort-phase context parity (issue #63)
#
# The effort phase renders ``agent: model / <state>`` — the same shape
# the confirm panel uses. Both call sites consume
# :func:`format_selection_label` so the wording can never drift.
# ---------------------------------------------------------------------------


def test_run_claude_wizard_effort_phase_shows_unset_for_untouched_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude: the effort-phase agent picker shows ``agent: model / (unset)`` for an untouched agent.

    After task 1's formatter and task 3's display wiring, an agent
    whose effort is still ``None`` renders the rich format with the
    ``(unset)`` placeholder — the same shape the confirm panel emits.
    """
    import questionary

    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedSelect.captures = []
    _ScriptedConfirm.instances = []

    # Phase 1: continue. Phase 2 (effort): inspect the prompt body, then continue.
    scripted = _ScriptedSelect()
    scripted.queue("__continue__", "__continue__")
    captures: list[tuple[object, object]] = []
    monkeypatch.setattr(tui.questionary, "select", _capturing_select(scripted, captures))
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    # Find the prompt whose message names the "effort" phase.
    effort_captures = [c for c in captures if "effort" in str(c[0])]
    assert effort_captures, "expected at least one questionary.select call during the effort phase"
    _, choices = effort_captures[0]
    titles = [c.title for c in choices if isinstance(c, questionary.Choice)]
    # The rich format with "(unset)" must appear for an untouched agent.
    # Single agent prefix: ``format_selection_label`` already supplies ``{agent}: ``,
    # so the prompt function must NOT prepend another ``{agent} - ``.
    assert "change-implementor: sonnet / (unset)" in titles
    assert "change-implementor - change-implementor: sonnet / (unset)" not in titles


def test_run_claude_wizard_effort_phase_never_shows_na(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude: the effort phase never renders ``(NA)`` for any agent row.

    Claude models are always effort-supporting, so the ``has_effort_support=True``
    constant in the effort phase's display comprehension guarantees the
    ``(NA)`` branch is unreachable here. Locks the contract that no
    future refactor accidentally threads a non-Claude path into the
    formatter for the Claude wizard.
    """
    import questionary

    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedSelect.captures = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    scripted.queue("__continue__", "__continue__")
    captures: list[tuple[object, object]] = []
    monkeypatch.setattr(tui.questionary, "select", _capturing_select(scripted, captures))
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    effort_captures = [c for c in captures if "effort" in str(c[0])]
    assert effort_captures
    for _, choices in effort_captures:
        titles = [c.title for c in choices if isinstance(c, questionary.Choice)]
        for title in titles:
            assert "(NA)" not in title, f"Claude effort phase must never render (NA); saw title {title!r}"


def test_run_opencode_wizard_effort_phase_shows_unset_for_reasoning_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: a reasoning-capable model with effort=None renders ``(unset)`` on the effort phase."""
    import questionary

    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedSelect.captures = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    # Phase 1: pick change-implementor -> reasoning model -> continue.
    # Phase 2 (effort): inspect the prompt body, then continue (no effort picked).
    scripted.queue("change-implementor", "openai/gpt-5.5", "__continue__", "__continue__")
    captures: list[tuple[object, object]] = []
    monkeypatch.setattr(tui.questionary, "select", _capturing_select(scripted, captures))
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    effort_captures = [c for c in captures if "effort" in str(c[0])]
    assert effort_captures
    _, choices = effort_captures[0]
    titles = [c.title for c in choices if isinstance(c, questionary.Choice)]
    # Single agent prefix — verbatim consumption of ``format_selection_label``.
    assert "change-implementor: openai/gpt-5.5 / (unset)" in titles
    assert "change-implementor - change-implementor: openai/gpt-5.5 / (unset)" not in titles


def test_run_opencode_wizard_effort_phase_shows_na_for_non_reasoning_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: a non-reasoning model renders ``(NA)`` on the effort phase and skips the prompt."""
    import questionary

    from ai_harness.modules.wizard import tui

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5", "openai/gpt-5.5-mini"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                    "openai/gpt-5.5-mini": {"reasoning": False, "cost": {"input": 0.1, "output": 0.2}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedSelect.captures = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    # Pick change-implementor -> non-reasoning model -> continue (effort phase skipped) -> continue.
    scripted.queue("change-implementor", "openai/gpt-5.5-mini", "__continue__", "__continue__")
    captures: list[tuple[object, object]] = []
    monkeypatch.setattr(tui.questionary, "select", _capturing_select(scripted, captures))
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    effort_captures = [c for c in captures if "effort" in str(c[0])]
    assert effort_captures
    _, choices = effort_captures[0]
    titles = [c.title for c in choices if isinstance(c, questionary.Choice)]
    # Single agent prefix for non-reasoning / (NA) branch.
    assert "change-implementor: openai/gpt-5.5-mini / (NA)" in titles
    assert "change-implementor - change-implementor: openai/gpt-5.5-mini / (NA)" not in titles


def test_run_opencode_wizard_effort_phase_mixed_agent_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: mixed agent set renders per-agent reasoning branch — X with effort, Y with ``(NA)``.

    Seeds ``change-implementor`` on a reasoning model with effort ``high``
    and ``change-validator`` on a non-reasoning model with no effort —
    so the FIRST render of the effort phase shows both branches
    simultaneously. The wizard only touches change-validator in the
    model phase (same-model pick, so no actual state change), and the
    user does not pick any agent in the effort phase.
    """
    import questionary

    from ai_harness.modules.wizard import tui

    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps(
            {
                "change-implementor": {
                    "model": {"opencode": "openai/gpt-5.5"},
                    "effort": {"opencode": "high"},
                },
                "change-validator": {
                    "model": {"opencode": "openai/gpt-5.5-mini"},
                },
            },
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5", "openai/gpt-5.5-mini"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                    "openai/gpt-5.5-mini": {"reasoning": False, "cost": {"input": 0.1, "output": 0.2}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedSelect.captures = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    # Phase 1: pick change-validator (already on the non-reasoning model, same-model pick — no model change).
    # Phase 2: continue (don't pick effort for change-implementor; display still shows the seeded "high").
    # Confirm.
    scripted.queue(
        "change-validator",
        "openai/gpt-5.5-mini",
        "__continue__",
        "__continue__",
    )
    captures: list[tuple[object, object]] = []
    monkeypatch.setattr(tui.questionary, "select", _capturing_select(scripted, captures))
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    effort_captures = [c for c in captures if "effort" in str(c[0])]
    assert effort_captures
    _, choices = effort_captures[0]
    titles = [c.title for c in choices if isinstance(c, questionary.Choice)]
    # Both branches must be present, driven by per-agent reasoning lookup.
    # Single agent prefix — verbatim consumption of ``format_selection_label``.
    assert "change-implementor: openai/gpt-5.5 / high" in titles
    assert "change-validator: openai/gpt-5.5-mini / (NA)" in titles
    assert "change-implementor - change-implementor:" not in " | ".join(titles)
    assert "change-validator - change-validator:" not in " | ".join(titles)


def test_ask_continue_or_agent_effort_phase_no_agent_dash_agent_substring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude: no effort-phase choice title may contain the duplicated ``{agent} - {agent}:`` prefix.

    Locks the fix for the effort-row-duplication bug. Even if a future
    refactor reorders the title assembly, the bare substring
    ``{agent} - {agent}:`` MUST NEVER appear in any effort-phase choice
    title. Captures the choice list through the same ``_filterable_select``
    shim pattern as ``test_ask_continue_or_agent_uses_dash_label_format``.
    """
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    # Build selections for every Claude wizard agent using the same
    # ``agent: model / <state>`` shape ``run_effort_phase`` passes in.
    effort_pairs = [
        ("change-implementor", "change-implementor: sonnet / high"),
        ("change-validator", "change-validator: sonnet / (unset)"),
        ("change-explorer", "change-explorer: opus / high"),
    ]
    selections = dict(effort_pairs)
    tui._ask_continue_or_agent("effort", selections)

    titles = [choice.title for choice in captured[0] if isinstance(choice, questionary.Choice)]
    for agent, label in effort_pairs:
        forbidden = f"{agent} - {agent}:"
        assert forbidden not in titles, (
            f"Claude effort phase must never duplicate the agent prefix; saw {forbidden!r} in titles {titles!r}"
        )
        # And the label the caller passed in must be present verbatim.
        assert label in titles, (
            f"Claude effort phase must consume selections[{agent!r}] verbatim; saw titles {titles!r}"
        )


def test_ask_opencode_continue_or_agent_effort_phase_no_agent_dash_agent_substring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: no effort-phase choice title may contain the duplicated ``{agent} - {agent}:`` prefix.

    Covers all three effort states — ``high`` (set), ``(unset)`` (no
    override), and ``(NA)`` (non-reasoning model). Mirrors the Claude
    regression test so the two wizards cannot drift on this contract.
    """
    import questionary

    from ai_harness.modules.wizard import tui

    captured: list[object] = []

    def fake_select(message, *, choices, **kwargs):
        captured.append(choices)

        class _Q:
            def ask(self) -> str:
                return "__continue__"

        return _Q()

    monkeypatch.setattr(tui, "_filterable_select", fake_select)
    # Build selections for every OpenCode wizard agent. Seeds all three
    # effort states — ``high``, ``(unset)``, and ``(NA)`` — so a future
    # phase-aware formatter change that re-introduces the duplicated
    # prefix on any of the three branches would fail this test.
    effort_pairs = [
        ("change-implementor", "change-implementor: openai/gpt-5.5 / high"),
        ("change-validator", "change-validator: openai/gpt-5.5-mini / (NA)"),
        ("change-explorer", "change-explorer: openai/gpt-5.5 / (unset)"),
    ]
    selections = dict(effort_pairs)
    tui._ask_opencode_continue_or_agent(
        "effort",
        selections,
        opencode_change_agents(),
    )

    titles = [choice.title for choice in captured[0] if isinstance(choice, questionary.Choice)]
    for agent, label in effort_pairs:
        forbidden = f"{agent} - {agent}:"
        assert forbidden not in titles, (
            f"OpenCode effort phase must never duplicate the agent prefix; saw {forbidden!r} in titles {titles!r}"
        )
        # And the label the caller passed in must be present verbatim.
        assert label in titles, (
            f"OpenCode effort phase must consume selections[{agent!r}] verbatim; saw titles {titles!r}"
        )


def test_format_selection_label_effort_phase_and_confirm_panel_match_for_none_effort() -> None:
    """Both call sites produce byte-identical labels for ``(agent, model, None)``.

    The effort phase (which passes ``has_effort_support=True`` per
    Claude / per OpenCode reasoning-capable model) and the confirm
    panel (which always passes ``has_effort_support=True``) render
    the same triple with the same wording. Locking the contract here
    makes a future divergence between the two displays a test failure.
    """
    effort_label = format_selection_label("change-implementor", "opus", None, True)
    confirm_rows = build_confirmation_rows({"change-implementor": ModelSelection("opus", None)})

    assert effort_label == confirm_rows[0].label


def test_format_selection_label_effort_phase_and_confirm_panel_match_for_set_effort() -> None:
    """Both call sites produce byte-identical labels for ``(agent, model, 'high')``."""
    effort_label = format_selection_label("change-implementor", "opus", "high", True)
    confirm_rows = build_confirmation_rows({"change-implementor": ModelSelection("opus", "high")})

    assert effort_label == confirm_rows[0].label


# ---------------------------------------------------------------------------
# Model-switch effort reset (issue #63)
#
# Every successful model pick clears the agent's previously selected
# effort immediately, regardless of whether the new model supports
# effort. The clear is unconditional (no new_model != models[pick] gate)
# and per-pick (only efforts[pick] is mutated).
# ---------------------------------------------------------------------------


def test_run_claude_wizard_same_model_pick_clears_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude: a same-model pick still clears the agent's effort.

    The clear is unconditional — it fires even when ``new_model ==
    models[pick]`` (the user picked the model the agent already had).
    Gating the clear on a model change would let a same-model pick leak
    a stale effort into the override payload.
    """
    from ai_harness.modules.wizard import tui

    # Seed baseline: change-implementor had effort="high" previously.
    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps({"change-implementor": {"effort": {"claude": "high"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Pick change-implementor → pick "sonnet" (same as the template default) → continue → continue.
    scripted = _ScriptedSelect()
    scripted.queue("change-implementor", "sonnet", "__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # Effort was cleared to None even though the model didn't change.
    assert overrides["change-implementor"]["effort"] == {"claude": None}
    # No model entry — same-model pick is not a model change.
    assert "model" not in overrides["change-implementor"]


def test_run_claude_wizard_switching_one_agent_leaves_others_efforts_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude: switching one agent's model only clears that agent's effort; others stay.

    The model-switch reset is per-pick — only ``efforts[pick]`` is mutated.
    Other agents' efforts survive untouched even when the user switches
    a sibling agent's model in the same wizard session.
    """
    from ai_harness.modules.wizard import tui

    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps(
            {
                "change-validator": {"effort": {"claude": "high"}},
                "change-implementor": {"effort": {"claude": "max"}},
            },
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Switch only change-implementor to opus.
    scripted = _ScriptedSelect()
    scripted.queue("change-implementor", "opus", "__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # change-validator's effort survives untouched (no per-agent cross-talk).
    assert overrides["change-validator"]["effort"] == {"claude": "high"}
    # change-implementor's effort cleared and model updated.
    assert overrides["change-implementor"]["effort"] == {"claude": None}
    assert overrides["change-implementor"]["model"] == {"claude": "opus"}


def test_run_claude_wizard_back_navigation_preserves_effort_clear(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude: back-navigation after a switch preserves the cleared effort.

    The model-switch reset mutates ``efforts[pick]`` in-place. Backing
    out of the effort phase and re-entering it (or going all the way
    forward to confirm) must observe the cleared value — the clear
    lives in the closure's state, not in the prompt-rendering layer.
    """
    from ai_harness.modules.wizard import tui

    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps({"change-implementor": {"effort": {"claude": "high"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1: pick implementor -> opus -> continue.
    # Phase 2: back (returns to phase 1).
    # Phase 1 again: continue (no agent picked; the model change persists).
    # Phase 2 again: continue.
    # Confirm.
    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "opus",
        "__continue__",
        "__back__",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # Effort remains cleared after the round trip — the back-nav didn't restore the old "high".
    assert overrides["change-implementor"]["effort"] == {"claude": None}
    assert overrides["change-implementor"]["model"] == {"claude": "opus"}


def test_run_opencode_wizard_switch_to_reasoning_leaves_effort_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: switching from a non-reasoning to a reasoning model leaves effort None.

    A non-reasoning baseline (no prior effort, since the model can't
    carry one) switched to a reasoning model leaves the wizard's
    ``efforts[pick]`` at ``None``. The override payload contains no
    ``effort`` entry — the renderer drops the field.
    """
    from ai_harness.modules.wizard import tui

    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps({"change-implementor": {"model": {"opencode": "openai/gpt-5.5-mini"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5", "openai/gpt-5.5-mini"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                    "openai/gpt-5.5-mini": {"reasoning": False, "cost": {"input": 0.1, "output": 0.2}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    scripted.queue("change-implementor", "openai/gpt-5.5", "__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert "effort" not in overrides["change-implementor"]
    assert overrides["change-implementor"]["model"] == {"opencode": "openai/gpt-5.5"}


def test_run_opencode_wizard_switch_between_reasoning_models_clears_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: switching between two reasoning-capable models clears the prior effort.

    The clear is unconditional — it fires whether the new model supports
    effort or not. Switching from one reasoning model to a DIFFERENT
    reasoning model still wipes the prior effort so the user must
    re-affirm it on the effort phase.
    """
    from ai_harness.modules.wizard import tui

    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps(
            {
                "change-implementor": {
                    "model": {"opencode": "openai/gpt-5.5"},
                    "effort": {"opencode": "high"},
                },
            },
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        # Two reasoning-capable models so the test can switch between them.
        return ["openai/gpt-5.5", "openai/gpt-5.5-pro"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                    "openai/gpt-5.5-pro": {"reasoning": True, "cost": {"input": 6, "output": 30}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "openai/gpt-5.5-pro",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # Effort cleared even though the new model is also reasoning-capable.
    assert overrides["change-implementor"]["effort"] == {"opencode": None}
    assert overrides["change-implementor"]["model"] == {"opencode": "openai/gpt-5.5-pro"}


def test_run_opencode_wizard_same_model_pick_clears_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: a same-model pick clears the agent's effort.

    Mirrors the Claude same-model test (2.2): the clear fires whether or
    not the model actually changed. Picking the model the agent already
    had is still a "switch" from the wizard's point of view — and the
    effort must be cleared so the user re-affirms it on the effort phase.
    """
    from ai_harness.modules.wizard import tui

    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps(
            {
                "change-implementor": {
                    "model": {"opencode": "openai/gpt-5.5"},
                    "effort": {"opencode": "high"},
                },
            },
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    scripted.queue("change-implementor", "openai/gpt-5.5", "__continue__", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert overrides["change-implementor"]["effort"] == {"opencode": None}
    # Model entry unchanged (same-model pick).
    assert overrides["change-implementor"]["model"] == {"opencode": "openai/gpt-5.5"}


def test_run_opencode_wizard_switching_one_agent_leaves_others_efforts_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: switching one agent's model only clears that agent's effort; others stay."""
    from ai_harness.modules.wizard import tui

    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps(
            {
                "change-validator": {"effort": {"opencode": "high"}},
                "change-implementor": {
                    "model": {"opencode": "openai/gpt-5.5"},
                    "effort": {"opencode": "max"},
                },
            },
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5", "openai/gpt-5.5-pro"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                    "openai/gpt-5.5-pro": {"reasoning": True, "cost": {"input": 6, "output": 30}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "openai/gpt-5.5-pro",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert overrides["change-validator"]["effort"] == {"opencode": "high"}
    assert overrides["change-implementor"]["effort"] == {"opencode": None}
    assert overrides["change-implementor"]["model"] == {"opencode": "openai/gpt-5.5-pro"}


def test_run_claude_wizard_repeated_identical_model_picks_keep_effort_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude: repeated identical model picks keep effort ``None`` (idempotent clear).

    The clear is a single ``efforts[pick] = None`` assignment; assigning
    ``None`` to a key that already holds ``None`` is a no-op. After the
    first clear the second identical pick leaves the cleared value
    cleared — the override payload still has no effective effort change
    beyond the original clear.
    """
    from ai_harness.modules.wizard import tui

    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps({"change-implementor": {"effort": {"claude": "high"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1: pick implementor -> sonnet (same as default) -> continue.  [first clear]
    # Phase 2: back -> re-enters Phase 1.
    # Phase 1 again: pick implementor -> sonnet (same model again) -> continue.  [idempotent clear]
    # Phase 2 again: continue.
    # Confirm.
    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "sonnet",
        "__continue__",
        "__back__",
        "change-implementor",
        "sonnet",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_claude_wizard(home=tmp_path)

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # Effort still cleared after the second identical model pick — clear is idempotent.
    assert overrides["change-implementor"]["effort"] == {"claude": None}
    # No model entry — both picks were same-model.
    assert "model" not in overrides["change-implementor"]


# ---------------------------------------------------------------------------
# Regression contracts — preserved OpenCode gate, selective-write semantics,
# renderer backstop.
#
# These tests lock in the contracts from specs
# ``unsupported-effort-agent-handling-preserved`` and
# ``selective-write-semantics-preserved``. The OpenCode non-reasoning
# gate stays as a defensive safety net even though the model-switch
# reset owns the invariant; the selective-write contract
# (``selection.<field> != base.<field>``) is unchanged; the renderer's
# ``omits_effort_when_unset`` contract is the load-bearing backstop.
# ---------------------------------------------------------------------------


def test_run_opencode_wizard_non_reasoning_gate_idempotent_when_effort_already_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: gate running on a non-reasoning agent with effort already ``None`` is idempotent.

    With the model-switch reset in place, every agent that comes through
    the model phase has ``efforts[pick] = None`` by the time the effort
    phase starts. The non-reasoning gate still runs as a safety net —
    it re-sets ``efforts[pick] = None`` (no observable change) and
    emits the skip message instead of prompting for effort.
    """
    from ai_harness.modules.wizard import tui

    # Seed: change-implementor is already on a non-reasoning model with no effort.
    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps({"change-implementor": {"model": {"opencode": "openai/gpt-5.5-mini"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5-mini"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5-mini": {"reasoning": False, "cost": {"input": 0.1, "output": 0.2}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    printed: list[str] = []
    monkeypatch.setattr(tui._console, "print", lambda *a, **kw: printed.append(str(a[0])))

    scripted = _ScriptedSelect()
    # Skip the model phase (no agent picked -> no model change), then in
    # the effort phase pick change-implementor. The gate should fire
    # with effort already None and skip the effort prompt.
    scripted.queue("__continue__", "change-implementor", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    # The skip message is still emitted by the safety-net gate.
    assert any("Skipping effort" in msg and "not a reasoning model" in msg for msg in printed), (
        "the non-reasoning gate must still emit the skip message even when effort was already None"
    )
    # No override entry for effort — the idempotent clear left selection.effort == baseline.effort.
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    assert "effort" not in overrides["change-implementor"]


def test_run_opencode_wizard_effort_only_change_writes_only_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: effort change without model change writes only the effort key.

    Companion to ``test_run_claude_wizard_effort_change_from_unset_writes_only_effort``
    — same selective-write contract, OpenCode side. User keeps the
    reasoning model and only sets an effort; the override payload
    surfaces ``{"effort": {"opencode": <value>}}`` with no model entry.
    """
    from ai_harness.modules.wizard import tui

    # Seed: change-implementor on a reasoning model (so the effort-phase
    # gate doesn't fire), no prior effort. We do NOT touch the model in
    # the wizard, so the model-switch reset never fires.
    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps({"change-implementor": {"model": {"opencode": "openai/gpt-5.5"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1 (model): continue (no model change — change-implementor stays on openai/gpt-5.5).
    # Phase 2 (effort): pick change-implementor -> "high" -> continue.
    # Confirm.
    scripted = _ScriptedSelect()
    scripted.queue("__continue__", "change-implementor", "high", "__continue__")
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # Only the effort key — the model stayed the same, so deep-merge
    # preserves the existing model entry unchanged.
    assert overrides["change-implementor"]["effort"] == {"opencode": "high"}
    assert overrides["change-implementor"]["model"] == {"opencode": "openai/gpt-5.5"}


def test_run_opencode_wizard_model_only_change_writes_only_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCode: model change without effort change writes only the model key.

    Mirrors ``test_run_claude_wizard_model_change_writes_only_changed_agent``
    — same selective-write contract, OpenCode side. User switches to a
    different reasoning model but skips the effort prompt; the override
    payload surfaces only ``{"model": {"opencode": <value>}}``.
    """
    from ai_harness.modules.wizard import tui

    # Seed: change-implementor on a reasoning model with no prior effort.
    _override_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _override_file(tmp_path).write_text(
        json.dumps({"change-implementor": {"model": {"opencode": "openai/gpt-5.5"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(tui, "_resolve_opencode_binary", lambda: "/fake/opencode")

    def fake_loader(home: Path, *, runner=None) -> tuple[list[str], dict]:
        return ["openai/gpt-5.5", "openai/gpt-5.5-pro"], {
            "alpha": {
                "models": {
                    "openai/gpt-5.5": {"reasoning": True, "cost": {"input": 3, "output": 15}},
                    "openai/gpt-5.5-pro": {"reasoning": True, "cost": {"input": 6, "output": 30}},
                },
            },
        }

    monkeypatch.setattr(tui, "_load_opencode_catalog", fake_loader)
    monkeypatch.setattr(tui.questionary, "select", _ScriptedSelect)
    monkeypatch.setattr(tui.questionary, "confirm", _ScriptedConfirm)
    _ScriptedSelect.instances = []
    _ScriptedConfirm.instances = []

    # Phase 1 (model): pick change-implementor -> openai/gpt-5.5-pro (different reasoning model).
    # Phase 2 (effort): continue (user skips effort — selection.effort stays None, baseline.effort was None).
    # Confirm.
    scripted = _ScriptedSelect()
    scripted.queue(
        "change-implementor",
        "openai/gpt-5.5-pro",
        "__continue__",
        "__continue__",
    )
    monkeypatch.setattr(tui.questionary, "select", lambda *a, **kw: scripted)
    confirm = _ScriptedConfirm().queue(True)
    monkeypatch.setattr(tui.questionary, "confirm", lambda *a, **kw: confirm)

    wrote = tui.run_opencode_wizard(home=tmp_path, agents=opencode_change_agents())

    assert wrote is True
    overrides = json.loads(_override_file(tmp_path).read_text(encoding="utf-8"))
    # Only the model key — selection.effort (None) matches baseline.effort (None).
    # The existing override already had the original model — deep-merge preserves it
    # only when the value matches; here it differs, so the new model replaces it.
    assert overrides["change-implementor"]["model"] == {"opencode": "openai/gpt-5.5-pro"}
    assert "effort" not in overrides["change-implementor"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect HOME to a tmp dir so commands don't touch the real user state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path
