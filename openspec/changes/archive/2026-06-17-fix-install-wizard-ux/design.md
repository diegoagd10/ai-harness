# Design: Fix Install Wizard UX (marker-only rendering + ESC cancel)

## Technical Approach

Both defects live in `questionary.checkbox`'s internal defaults, which we never override. We take ownership of prompt construction inside `wizard.py` while keeping its public surface (`select_install_targets`, `select_uninstall_targets`, `Empty`, `Cancelled`) unchanged. A new private builder constructs a `questionary.Question` around our own `Application`, using (a) a subclassed `InquirerControl` that splits the selected marker and title into separate style tokens, and (b) a `KeyBindings` set mirroring questionary's checkbox defaults plus an explicit `Keys.Escape` binding. `install.py` / `uninstall.py` stay untouched — they already consume `Cancelled()`. Satisfies `install-wizard` and `uninstall-wizard` "Visual presentation" + "Terminal states" deltas.

## Architecture Decisions

| Decision | Choice | Rejected alternative | Rationale |
|---|---|---|---|
| Rendering fix | Subclass `InquirerControl`, override `_get_choice_tokens` so the selected glyph emits under `class:checkbox-selected` and the title under `class:text`/`class:highlighted` | Pure `style=` kwarg remap of `class:selected` | questionary emits glyph AND title under the same `class:selected` token (`common.py` ~450/463). No style string can color one without the other. A token split is the only true fix. |
| ESC fix | Build our own `Application`/`KeyBindings` (cloning checkbox defaults) and add `Keys.Escape → app.exit(result=None)` | Pass `key_bindings=` to `questionary.checkbox(**kwargs)` | `checkbox()` builds its OWN `KeyBindings` and forwards `**kwargs` only to `Application.__init__`; an external binding is never merged. ESC would still be swallowed by the `Keys.Any` no-op. |
| Prompt ownership | Reuse `common.create_inquirer_layout` + wrap in `questionary.Question(application)`; keep `.ask()` call site | Fork questionary; or drop questionary entirely | `Question.__init__(application)` is a thin wrapper; reusing it preserves the `None→Cancelled` / `[]→Empty` translation and `.ask()` contract with minimal new code. |
| Coupling mitigation | Pin `questionary==2.1.1`; add an upgrade-canary test | Accept silent drift | Internals (`InquirerControl`, `_get_choice_tokens`, `create_inquirer_layout`) are semi-private. The canary fails loudly when they move, converting an unknown-unknown into a visible test failure. |

## Data Flow

```
select_*_targets()
   └─ _build_question(title, choices)          # NEW — owns construction
        ├─ MarkerOnlyControl(choices)          # NEW InquirerControl subclass
        ├─ create_inquirer_layout(ic, header)  # reused from questionary
        ├─ _checkbox_bindings(ic) + ESC        # NEW KeyBindings builder
        └─ questionary.Question(Application(layout, bindings, style=_WIZARD_STYLE))
   └─ _run_checkbox(question)                  # .ask() → None|[]|list
        None → Cancelled() ;  [] → Empty() ;  list → list
```

## File Changes

| File | Action | Description |
|---|---|---|
| `src/ai_harness/artifacts/wizard.py` | Modify | Add `MarkerOnlyControl`, `_WIZARD_STYLE`, `_checkbox_bindings`, `_build_question`; `_run_checkbox` takes the built `Question`. Public functions unchanged. |
| `pyproject.toml` | Modify | Pin `questionary==2.1.1` (was `>=2.1.0`). |
| `tests/conftest.py` | Modify | Add a `pipe_input` fixture (`create_pipe_input`) driving real key events; keep `_StubCheckbox` for the translation tests. |
| `tests/test_wizard.py` | Modify | Add binding-level + pipe-driven ESC/space/enter tests. |
| `tests/test_rendering.py` | Modify | Add marker/title token-split assertions. |

## Interfaces / Contracts

```python
class MarkerOnlyControl(InquirerControl):
    """Selected state colors ONLY the marker glyph, not the title."""
    def _get_choice_tokens(self):
        # Reuse super() output, then re-class title tokens of selected rows:
        # selected glyph  -> ("class:checkbox-selected", "● ")
        # selected title  -> ("class:text", title)   # was class:selected
        # focused title   -> ("class:highlighted", title)  # unchanged

_WIZARD_STYLE = merge_styles_default([Style([
    ("checkbox-selected", "fg:#00FF00"),  # green marker glyph only
    ("selected", ""),                     # belt-and-suspenders: no row highlight
])])

def _checkbox_bindings(ic) -> KeyBindings:
    """Clone checkbox defaults (ControlC/Q abort, space/a/i toggle,
    arrows+jk+emacs move, ControlM confirm, Keys.Any no-op) PLUS:"""
    @kb.add(Keys.Escape, eager=True)
    def _cancel(event): event.app.exit(result=None)  # → Cancelled()

def _build_question(title, choices) -> questionary.Question: ...
```

The `Keys.Escape` binding uses `eager=True` so prompt_toolkit fires it immediately instead of waiting on the escape-sequence-prefix timeout; arrow keys arrive as their own complete `Keys.Up`/`Keys.Down` sequences and are matched independently, so bare-ESC does not swallow them.

## Testing Strategy (strict_tdd — RED first)

| Layer | What to test | Approach |
|---|---|---|
| Unit (binding) | ESC binding maps to `app.exit(result=None)`; defaults present (space/enter/arrows) | Build the `KeyBindings` via `_checkbox_bindings`; assert `get_bindings_for_keys((Keys.Escape,))` is non-empty and others exist |
| Unit (render) | Selected row → glyph token is `class:checkbox-selected`, title token is `class:text` (NOT `class:selected`); unselected/focused unchanged | Instantiate `MarkerOnlyControl`, toggle a value into `selected_options`, assert `_get_choice_tokens()` token classes |
| Integration (pipe) | ESC returns `None`→`Cancelled`; space+enter returns the toggled list; enter-only returns `[]`→`Empty` | `create_pipe_input()` feeds real bytes (`\x1b`, `" "`, `\r`) into the Application via `_build_question(...).ask()` under `DummyOutput` |
| Canary | questionary internals contract holds | Assert `hasattr(InquirerControl, "_get_choice_tokens")`, `create_inquirer_layout` signature, and that `INDICATOR_SELECTED == "●"`; fails loudly on upgrade |

The existing `_StubCheckbox` tests for choice construction and `None/[]/list` translation stay — they cover the wrapper's translation layer, which the pipe tests do not re-prove.

## Migration / Rollout

No migration. Single PR, single runtime module. Rollback = revert the `wizard.py` + `pyproject.toml` commit; install/uninstall command paths and the state file are untouched.

## Open Questions

- None blocking. (Confirm green `#00FF00` is acceptable on light terminals during apply; the token split is the load-bearing fix regardless of exact hue.)
