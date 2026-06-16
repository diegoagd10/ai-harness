# Design: Compose Claude SDD Phase Bodies at Install Time

## Goal

The current `ClaudeInstaller` copies frontmatter-only phase files verbatim via `DirArtifact`, leaving 8 SDD-phase subagents with empty bodies. This design introduces `ComposedFileArtifact` — a frozen dataclass that describes a target file produced at install time by concatenating a frontmatter source with a shared prompt body — and rewires `installers/claude.py` to emit 8 composed artifacts while keeping the 7 inline subagents and orchestrator as verbatim copies.

## ADR-1: New dataclass vs. extending FileArtifact

**Decision**: New `ComposedFileArtifact` dataclass (separate type).

| Option | Tradeoff |
|--------|----------|
| (a) New `ComposedFileArtifact` | Keeps `FileArtifact` interface untouched; composition opt-in by type; `isinstance` dispatch is straightforward; single-responsibility per type |
| (b) Optional `body_source: Path \| None` on `FileArtifact` | Fewer types but overloads `FileArtifact` with two modes; `template` semantics ambiguous (apply to frontmatter only? whole composed text?) |

**Why (a)**: From the deep-modules lens, `FileArtifact` is already a deep module — small interface, powerful backing behavior (backup, rotation, template substitution, uninstall-restore). Adding `body_source` widens its interface and forces every caller to understand two modes gated by an optional field. A separate type keeps each boundary narrow and focused. The interface cost of one new class in `manifest.py` is negligible; the benefit is zero ambiguity.

## ADR-2: Where composition happens

**Decision**: Inline in `installer.py` via a new `_prepare_composed_content()` private function.

| Option | Tradeoff |
|--------|----------|
| (a) New `composers.py` module | Would be a **shallow module** — its interface IS its implementation (just string concatenation). Violates the "reject classitis" rule. |
| (b) Inline in `installer.py` | All content-preparation lives in one place. `installer.py` already owns "how content is produced from artifact descriptors." Composition is the same responsibility with two sources. |
| (c) Inline in `claude.py` only | Hides a generic capability behind a Claude-specific wall. If another installer later needs composition, we'd duplicate. |

**Why (b)**: `installer.py` is the designated "how" module — it hides backup, rotation, template substitution, and file I/O. Composition (read two files, concatenate) is a natural extension of `_prepare_content`. A separate module would add an interface boundary that hides nothing real.

## ADR-3: Backup / rotation / uninstall parity

**Decision**: Duplicate the backup/rotation loop for `ComposedFileArtifact` — same logic, different content preparation.

The `install()` and `uninstall()` functions gain a second loop for `manifest.composed` entries. The backup path computation, conflict rotation (`_next_available_path`), and uninstall content-matching logic are duplicated verbatim from the `FileArtifact` loop (~15 lines). Extracting a shared helper now would be premature — two loops is not yet change amplification. If a third artifact type appears, extract then.

`ComposedFileArtifact` carries `backup_suffix` and `conflict_suffix` with the same defaults as `FileArtifact` (`.ai-harness-backup`, `.ai-harness-conflict-backup`).

## ADR-4: Mapping table location

**Decision**: Module-level `dict` constant in `installers/claude.py`.

```python
_PHASE_NAMES: list[str] = [
    "sdd-explore", "sdd-propose", "sdd-spec", "sdd-design",
    "sdd-tasks", "sdd-apply", "sdd-verify", "sdd-archive",
]
_INLINE_AGENTS: list[str] = [
    "jd-fix-agent", "jd-judge-a", "jd-judge-b",
    "review-readability", "review-reliability", "review-resilience", "review-risk",
]
```

No external config file (classitis for an 8-entry mapping that changes only when SDD phases change). Inline literal is fine; extracting a constant costs nothing and makes the intent obvious.

## ADR-5: Test placement

**Decision**: `tests/test_claude_install.py` (CLI-level, `CliRunner` + `tmp_path`) for RED-first; extend `tests/test_installer.py` for generic composed-file lifecycle.

The e2e harness (`e2e/test_harness_lifecycle.py`) is extended with a `_assert_claude_agents()` helper that asserts `.claude/agents/sdd-*.md` composition and orchestrator presence. This follows the existing pattern of `_assert_sdd_prompts()`, `_assert_skills_targets()`, etc.

## ADR-6: Inline agents — `FileArtifact` per file vs. filtered `DirArtifact`

**Decision**: 7 individual `FileArtifact` entries (one per inline agent), enumerated by `_INLINE_AGENTS`.

A filtered `DirArtifact` with an exclude list would be more code and less explicit. Individual `FileArtifact` entries make it obvious which files are installed and give each its own backup/uninstall lifecycle. The orchestrator stays as a `DirArtifact` (single directory, self-contained).

## Module Layout

```
src/ai_harness/artifacts/
├── manifest.py          # + ComposedFileArtifact dataclass, + composed field on ArtifactManifest
├── installer.py         # + _prepare_composed_content(), + composed loops in install/uninstall
└── installers/
    └── claude.py        # rewrite: _PHASE_NAMES + _INLINE_AGENTS constants, 8 composed + 7 file + 1 dir
tests/
├── test_claude_install.py         # NEW — RED-first: CliRunner + tmp_path, asserts composed bodies
├── test_installer.py              # MODIFIED — add ComposedFileArtifact install/uninstall/backup tests
└── test_install.py                # MODIFIED — assert Claude agents present and orchestrator survives
e2e/
└── test_harness_lifecycle.py      # MODIFIED — _assert_claude_agents() helper in run_install_tests
```

## Data Flow

```
ClaudeInstaller._build_manifest()
  │
  ├─ reads agents_dir/*.md ──→ 8 ComposedFileArtifact entries
  │     frontmatter_source = agents/sdd-<phase>.md
  │     body_source        = prompts/sdd/<phase>.md
  │     target_relative    = .claude/agents/sdd-<phase>.md
  │
  ├─ reads 7 inline agents ──→ 7 FileArtifact entries
  │
  └─ reads orchestrator_dir ──→ 1 DirArtifact

installer.install(manifest, home, console)
  │
  ├─ for each ComposedFileArtifact:
  │     _prepare_composed_content():
  │       frontmatter = frontmatter_source.read_text()
  │       body        = body_source.read_text()
  │       return frontmatter + "\n---\n" + body
  │     → same backup/rotation/uninstall as FileArtifact
  │
  ├─ for each FileArtifact:
  │     _prepare_content() → backup/rotation/uninstall
  │
  └─ for each DirArtifact:
        replace_matching copy
```

## Interface Specifications

```python
# manifest.py — new symbol

@dataclass(frozen=True)
class ComposedFileArtifact:
    """Target file produced by joining a frontmatter source with a body source.

    At install time, the two sources are read and concatenated as:
        frontmatter + "\\n---\\n" + body
    The composed result is then written to home/target_relative with the
    same backup, conflict-rotation, and uninstall-restore policy as FileArtifact.
    """
    frontmatter_source: Path   # absolute path; YAML frontmatter block ending with "---"
    body_source: Path          # absolute path; raw Markdown body, no frontmatter
    target_relative: Path      # relative to HOME, e.g. ".claude/agents/sdd-apply.md"
    backup_suffix: str = ".ai-harness-backup"
    conflict_suffix: str = ".ai-harness-conflict-backup"

# ArtifactManifest — new field

@dataclass(frozen=True)
class ArtifactManifest:
    files: list[FileArtifact]
    dirs: list[DirArtifact]
    composed: list[ComposedFileArtifact] = field(default_factory=list)
    # ^^^ default_factory=list preserves backward compat: all existing
    #     ArtifactManifest(files=..., dirs=...) calls still work.
```

```python
# installer.py — new private function

def _prepare_composed_content(artifact: ComposedFileArtifact) -> str:
    """Read frontmatter and body sources, return concatenated text.

    Precondition: both sources exist and are UTF-8 text.
    Postcondition: returns frontmatter + "\n---\n" + body verbatim.
    """
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit (test_installer.py) | `ComposedFileArtifact` install/uninstall/backup/rotation lifecycle | `tmp_path` as home, mock sources, assert target content and backup behavior |
| CLI (test_claude_install.py) | RED-first: 8 phase files composed, 7 inline agents verbatim, orchestrator present | `CliRunner` + monkeypatched `HOME`, invoke `app install`, assert `.claude/agents/sdd-*.md` content |
| CLI (test_install.py) | Regression: AGENTS.md targets, skills, opencode prompts still work | Existing tests run unchanged |
| E2E (test_harness_lifecycle.py) | Full lifecycle: install, reinstall, uninstall with Claude agents | `_assert_claude_agents()` helper in `run_install_tests()` and `run_uninstall_tests()` |

## Mapping to Requirements

| Spec Requirement | Satisfied by |
|---|---|
| ComposedFileArtifact Dataclass | ADR-1, `manifest.py` |
| Concatenation and verbatim body | ADR-2, `_prepare_composed_content()` in `installer.py` |
| Backup, rotation, uninstall lifecycle | ADR-3, composed loops in `install()` / `uninstall()` |
| 8 composed + 7 inline + 1 orchestrator | ADR-4, ADR-6, `_PHASE_NAMES` + `_INLINE_AGENTS` in `claude.py` |
| RED-first e2e | ADR-5, `test_claude_install.py` |
| No regression of archived spec | ADR-5, existing tests unmodified + new assertions |
| Phase body matches shared prompt | `_prepare_composed_content` uses `prompts/sdd/<phase>.md` verbatim |
| Reviewer read-only, phase write tools | Resource files unchanged; installer copies verbatim / composes with same frontmatter |

## Risk and Tradeoffs

- **Risk**: Double `---` separator — frontmatter files end with `---\n`, and the spec mandates appending `"\n---\n"`. Produces valid YAML (document separator) but visually unusual. **Mitigation**: this is the spec contract; documented here and in the spec scenario.
- **Risk**: 7 inline agent enumeration is explicit — adding a new agent requires updating `_INLINE_AGENTS`. **Mitigation**: the 15-agent graph is stable SDD infrastructure; documented in a comment above the constant.
- **Risk**: `ComposedFileArtifact` has no `template` field (unlike `FileArtifact`). If `{{HOME}}` substitution is needed later, it must be added. **Mitigation**: none of the 8 frontmatter files use `{{HOME}}`; YAGNI applies.

## Open Questions

None. The spec is the contract; all decisions are addressed above.
