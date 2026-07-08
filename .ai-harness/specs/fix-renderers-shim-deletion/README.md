# Specs — fix-renderers-shim-deletion

1. `runtime-import-migration.md` — Wizard runtime imports `ADMINISTRATORS` from the administrator package.
2. `shim-deletion.md` — The deprecated `renderers.py` shim is deleted and unsupported in production code.
3. `test-import-migration.md` — Renderer and install tests collect through administrator package imports.
4. `mock-target-migration.md` — Monkeypatches target `administrators.base` or the owning provider module.
5. `legacy-shim-test-removal.md` — Shim-only public-surface and `render_agents` parity tests are removed.
6. `documentation-cleanup.md` — README, docstrings, and comments identify administrators as the rendering/metadata home.
7. `wizard-assertion-alignment.md` — Wizard source-inspection tests expect the administrator import boundary.
