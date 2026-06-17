# Rename plugin package to `qgis_dashboards` + scaffold cleanup

**Date:** 2026-06-17
**Status:** Approved

## Goal

Rename the plugin package folder `qgis_dashboard/` → `qgis_dashboards/` (a unique,
descriptive package identity), rename the main plugin module, and remove
Plugin-Builder scaffold cruft that is not needed for the plugin to run — while
keeping the packaging path (`pb_tool` / `make`) working.

The test of "removable": **if the file is deleted, the QGIS plugin still loads and
runs completely.**

## Scope of the rename

The folder name is the QGIS plugin's permanent package identity (install directory
under `.../python/plugins/<name>/` and uniqueness in the plugin registry). Because
package code uses **relative imports** and the test suite uses **bare-name imports
on `PYTHONPATH`** (with `_run_tests.py` deriving the package name via
`os.path.basename`), the rename is low-risk for Python imports — the folder name
surfaces in code only in `__init__.py`, and otherwise only in build config and docs.

### Renames
- `git mv qgis_dashboard/ qgis_dashboards/` (preserves history).
- `git mv qgis_dashboards/qgis_dashboard.py qgis_dashboards/main_plugin.py`.
- `__init__.py`: `from .qgis_dashboard import qgisdashboard` → `from .main_plugin import qgisdashboard`.

### Deliberately untouched
- The class name `qgisdashboard` (renaming it is out of scope).
- The QGIS project-scope key `QgisDashboard` / key `layout` — changing it would
  orphan dashboards already saved inside existing `.qgz` files. The rename is
  package-name-only.

## Cleanup (moderate tier)

Delete (plugin still runs without them):
- `README.html`, `README.txt`
- `pylintrc`
- `i18n/` (only `af.ts`, an unused translation stub; `LOCALES` is empty)
- `help/` (Sphinx docs scaffold)
- `scripts/` (translation build shell scripts)
- `plugin_upload.py` (QGIS-repo upload helper)

Kept — required at runtime:
- `resources/` — holds the bundled **Inter** fonts that `fonts.py` registers via
  `QFontDatabase.addApplicationFont`.

No Python modules are deleted: `fonts.py`, `form_util.py`, `minimized_bubble.py`,
and `tile_snap.py` are all actively imported.

## Config sync (so packaging keeps working)

The deletions strand several Makefile / pb_tool targets, so those are fixed rather
than left dangling.

- **`pb_tool.cfg`**: `name: qgis_dashboards`; `qgis_dashboard.py` → `main_plugin.py`
  in `python_files`; remove the `[help]` section.
- **`Makefile`**: `PLUGINNAME = qgis_dashboards`; `qgis_dashboard.py` →
  `main_plugin.py` in `SOURCES`/`PY_FILES`; remove now-dangling targets and refs
  (`doc`, `upload`/`PLUGIN_UPLOAD`, `transup`/`transcompile`/`transclean`,
  `pylint`) and drop `doc`+`transcompile` from the `deploy` chain. `compile`,
  `deploy`, `dclean`, `derase`, `zip`, `package`, `clean`, `pep8` keep working.
- **`resources.qrc`**: prefix `/plugins/qgis_dashboard` → `/plugins/qgis_dashboards`.

## Doc sync

- **`CLAUDE.md`**: update the `cd qgis_dashboard` command block and structural
  mentions to `qgis_dashboards`, and `qgis_dashboard.py` → `main_plugin.py`.
- **Test docstring comments**: `cd qgis_dashboard` → `cd qgis_dashboards` (cosmetic;
  tests work regardless of folder name).
- `docs/superpowers/specs|plans/*`: left as-is (dated historical records).

## Verification

- `python -m py_compile` over the renamed tree (catches the `__init__` import and
  any stragglers).
- Run the pure-module tests: `test_tile_snap`, `test_zoom_fit`, `test_project_io`,
  `test_recent_store`, `test_header_layout`, `test_layout_util`, `test_map_identify`.
- `grep -r qgis_dashboard` confirms no stray live references remain (excluding
  historical docs/specs).

## Non-goals

- No deeper module reorganization (e.g. `ui/` / `io/` / `core/` subpackages) — a
  separate, riskier refactor that can be specced later.
- The pre-existing uncommitted working-tree changes from a concurrent session
  (`dashboard.html` deletion, `painters.py` modification) are not authored here;
  `painters.py` rides along with the folder move with its content preserved.
