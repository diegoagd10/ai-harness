# Design: Refactor Commands (Install/Uninstall)

## Technical Approach

Move commands into subpackages (`commands/sdd/`, `commands/artifacts/`). Extract a four-module `artifacts/` subsystem: `catalog.py` (slim, CLI-agnostic resource discovery), `manifest.py` (immutable descriptors), `installer.py` (generic I/O policy), and `installers/` (per-CLI target-layout classes composing their own asset dataclasses). Commands become thin orchestrators. `main.py` shrinks to ~30 lines.

## Architecture Decisions

| Option | Tradeoff | Verdict |
|--------|----------|---------|
| Keep I/O inline in commands | Low risk, zero depth, duplication across install/uninstall | Rejected |
| Per-CLI installers + generic installer + slim catalog (this design) | Medium effort, maximal depth, each decision one home | **Chosen** |
| Catalog with CLI-specific accessors (`get_opencode_assets()`) | Leaks CLI knowledge downward; one caller per method | Rejected (see below) |

### Decision: ArtifactCatalog — slim, CLI-agnostic, deep

**Choice**: 4 methods only — `get_root()`, `get_main_instructions()`, `get_skills()`, `get_resource_dir(relative)`. No CLI-specific accessors.

**Rationale** (general-purpose + information-hiding): The old design's `get_opencode_assets()` and `get_claude_assets()` each had one caller — the one-method-one-caller smell (`general-purpose.md`). They leaked CLI names into a general-purpose catalog and the returned dataclasses (`OpencodeAssets`, `ClaudeAssets`) were shallow wrappers around paths only their installer consumed. Moving those dataclasses to the installer modules means **each piece of CLI-specific knowledge has one home**: the installer that owns the target layout. The catalog now serves 2-3 callers per method (`get_main_instructions` called by all 3, `get_skills` by 2-3), which is the sweet spot of "somewhat general-purpose."

### Decision: OpencodeAssets / ClaudeAssets — owned by installer modules

**Choice**: Each asset dataclass lives next to its installer (`artifacts/installers/opencode.py`, `artifacts/installers/claude.py`). The catalog doesn't know about them.

**Rationale** (classes): `OpencodeAssets` is a data class consumed and assembled exclusively by `OpencodeInstaller`. Keeping it in `catalog.py` was temporal decomposition — the catalog "discovers" and the installer "uses" — but they share no knowledge invariant. The installer alone knows what constitutes an opencode asset; it composes its own dataclass from the catalog's general-purpose `get_resource_dir()` calls. This also eliminates the shallow modules: a dataclass that only one module uses doesn't belong in a shared catalog.

### Decision: Generic installer as module-level functions

**Choice**: `install(manifest, home, console)` and `uninstall(manifest, home, console)` — no class.

**Rationale** (deep-modules): Two functions hide ~120 lines of backup/restore/conflict-rotation/template-substitution policy. No shared mutable state — operate on immutable `ArtifactManifest` + `Path` + `Console`. A class would add interface cost with zero depth gain (classitis).

## Data Flow

```
ai-harness install
  commands/artifacts/install.py
    catalog = ArtifactCatalog(RESOURCES_DIR)
    for installer in (OpencodeInstaller(catalog), ClaudeInstaller(catalog), CopilotInstaller(catalog)):
        installer.install(home, console)
          → catalog.get_main_instructions()  (shared, 3 callers)
          → catalog.get_skills()             (shared, 2-3 callers)
          → catalog.get_resource_dir(Path("agent-clis/opencode/opencode.json"))  (generic helper)
          → builds own OpencodeAssets from catalog paths
          → builds FileArtifact/DirArtifact list internally
          → installer.install(manifest, home, console)
               for each FileArtifact: read → template-sub → compare → backup/rotate → write
               for each DirArtifact:  enumerate source → merge/replace at target
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_harness/commands/__init__.py` | Create | Package marker |
| `src/ai_harness/commands/sdd/__init__.py` | Create | Exports `register(app)` |
| `src/ai_harness/commands/sdd/status.py` | Create | `sdd-status` command |
| `src/ai_harness/commands/sdd/continue_cmd.py` | Create | `sdd-continue` command |
| `src/ai_harness/commands/sdd/_resolve.py` | Create | `_run_sdd_resolve` helper |
| `src/ai_harness/commands/artifacts/__init__.py` | Create | Exports `register(app)` |
| `src/ai_harness/commands/artifacts/install.py` | Create | Thin: catalog + 3 installers in loop |
| `src/ai_harness/commands/artifacts/uninstall.py` | Create | Thin: catalog + 3 installers in loop |
| `src/ai_harness/artifacts/__init__.py` | Create | Package marker |
| `src/ai_harness/artifacts/catalog.py` | Create | `ArtifactCatalog` (4 methods), `Skill` dataclass |
| `src/ai_harness/artifacts/manifest.py` | Create | `FileArtifact`, `DirArtifact`, `ArtifactManifest` |
| `src/ai_harness/artifacts/installer.py` | Create | `install()`, `uninstall()` — generic I/O policy |
| `src/ai_harness/artifacts/installers/__init__.py` | Create | Package marker |
| `src/ai_harness/artifacts/installers/opencode.py` | Create | `OpencodeInstaller` + `OpencodeAssets` |
| `src/ai_harness/artifacts/installers/claude.py` | Create | `ClaudeInstaller` + `ClaudeAssets` |
| `src/ai_harness/artifacts/installers/copilot.py` | Create | `CopilotInstaller` + `CopilotAssets` |
| `src/ai_harness/main.py` | Modify | Shrink to ~30 lines: app + callback + `main()` |
| `tests/test_install.py` | Modify | Import `app` from `ai_harness.main` |
| `tests/test_uninstall.py` | Modify | Same import update |
| `tests/test_cli_sdd.py` | Modify | `app` import unchanged (`ai_harness.main`) |
| `tests/test_installer.py` | Create | Unit tests: generic installer |
| `tests/test_catalog.py` | Create | Unit tests: catalog accessors |

## Interfaces / Contracts

### ArtifactCatalog (slim, CLI-agnostic — hides filesystem layout)

```python
@dataclass(frozen=True)
class Skill:
    name: str
    source_dir: Path
    skill_md: Path

class ArtifactCatalog:
    def __init__(self, root: Path) -> None: ...
    def get_root(self) -> Path: ...
    def get_main_instructions(self) -> Path: ...
    def get_skills(self) -> list[Skill]: ...
    def get_resource_dir(self, relative: Path) -> Path: ...
```

### OpencodeInstaller (composes own OpencodeAssets from catalog)

```python
# artifacts/installers/opencode.py

@dataclass(frozen=True)
class OpencodeAssets:
    config_path: Path
    config_template: dict[str, str]
    prompts_dir: Path

class OpencodeInstaller:
    def __init__(self, catalog: ArtifactCatalog) -> None: ...

    def install(self, home: Path, console: Console) -> None:
        assets = OpencodeAssets(
            config_path=self._catalog.get_resource_dir(Path("agent-clis/opencode/opencode.json")),
            config_template={"{{HOME}}": str(home)},
            prompts_dir=self._catalog.get_resource_dir(Path("prompts/sdd")),
        )
        manifest = self._build_manifest(home, assets)
        installer.install(manifest, home, console)

    def uninstall(self, home: Path, console: Console) -> None: ...
```

### Command layer (thin — no manifest logic)

```python
# commands/artifacts/install.py
def install() -> None:
    home = Path.home()
    console = Console()
    catalog = ArtifactCatalog(RESOURCES_DIR)
    for cli_installer in (OpencodeInstaller(catalog), ClaudeInstaller(catalog), CopilotInstaller(catalog)):
        cli_installer.install(home, console)
```

### Generic installer (module-level functions)

```python
def install(manifest: ArtifactManifest, home: Path, console: Console) -> None: ...
def uninstall(manifest: ArtifactManifest, home: Path, console: Console) -> None: ...
```

## Layer Validity

| Layer | Abstraction | Owns |
|-------|-------------|------|
| `main.py` | App assembly | Which command packages exist |
| `commands/artifacts/` | CLI activation | Which CLIs get installed; iteration order |
| `installers/*.py` | Per-CLI target layout + asset composition | Where each CLI's files go; what assets it needs |
| `catalog.py` | Project resource layout (CLI-agnostic) | Where source files live; generic path resolution |
| `installer.py` | I/O policy | Backup/restore/rotation/template substitution |
| `manifest.py` | Data contract | What an artifact is |

No pass-throughs. The catalog is general-purpose: 4 methods, no CLI-specific knowledge. Each CLI installer composes its own asset dataclass from catalog calls — the catalog doesn't know who calls it. Generic installer knows nothing about which CLI produced the manifest. Three installer classes share `install`/`uninstall` signatures with different implementations — the legitimate "interface, many implementations" case (`layers.md`).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Generic installer (unit) | Fresh install, backup-on-conflict, rotation, template, restore, idempotent | New `test_installer.py` using `tmp_path` |
| Catalog (unit) | Typed accessors return correct paths/shapes; no CLI-specific methods | New `test_catalog.py` |
| CLI (integration) | 18 existing tests: install, uninstall, SDD | Update imports only; `CliRunner(app)` unchanged |
| E2E | Full harness lifecycle | Update constant imports |

## Open Questions

- [ ] `CopilotInstaller` — install AGENTS.md only (no copilot-specific resources exist yet) or no-op until resources added? (Recommend: AGENTS.md only.)
- [ ] `DirArtifact.merge_mode="merge_preserve"` has no current caller — defer implementation? (Recommend: defer.)
