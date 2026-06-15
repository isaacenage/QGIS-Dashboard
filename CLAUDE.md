# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A QGIS desktop plugin that builds **ArcGIS-Dashboards-style interactive dashboards** from a QGIS project's vector layers. The user adds data-driven tiles (indicators, charts, lists, a live map, selectors) into a dockable panel; selecting a value in one tile **cross-filters every other tile** in real time. Dashboard layout and configuration are saved inside the `.qgz` project file.

The shippable plugin lives in **`qgis_dashboard/`** — a QGIS Plugin Builder scaffold whose generated dialog skeleton was replaced with a real dashboard implementation (a dock widget + a signal bus + pluggable element types). Keep the Plugin Builder structure intact (it is what makes the plugin install cleanly and pass `plugins.qgis.org` validation); add features as new modules within it.

> Historical note: an earlier hand-written prototype lived in `qgisdashboardmvp/`. Its architecture worked but was not Plugin-Builder-shaped, so it failed to install cleanly. It has been folded into `qgis_dashboard/` and removed. Do not recreate a parallel plugin folder.

## Architecture (the big picture)

The dashboard is a **standalone top-level window** (not a dock) holding **multiple pages**. Read these files together — `bus.py`, `window.py`, `page_view.py`, `dashboard_canvas.py`, `theme.py`, `elements/base.py`, `qgis_dashboard.py` — before changing behavior.

1. **The bus / shared context (`bus.py` → `DashboardBus`)** is the one object every element shares. It carries the live `iface` (for the map mirror), the active `Theme` (both **global**), and **page-local** cross-filter state: each page has its own connection graph + per-source filters, keyed by the active page. The window calls `set_active_page(id)` on page switch; `set_filter`/`set_targets`/`combined_filter_for`/`connections_to_dict(page_id)`/`load_connections(data, page_id)` all operate on the active (or given) page. `forget_page(id)` drops a deleted page's state; `forget_element(id)` drops a tile from the active page. (`_source_filters`/`_connections` are properties returning the active page's dicts, so call sites are unchanged.) Cross-filtering follows ArcGIS *source → action → target*, but wiring is **explicit, user-editable, and only links tiles on the same page**. Signals:
   - `filtersChanged()` — any source filter changed; each target recomputes via `combined_filter_for(self.id)` (the AND of every *connected* source's expression, or `None`).
   - `filtersCleared()` — "Clear filter" pressed; sources reset their own selection state (highlighted bar, combo).
   - `connectionsChanged()` — the wiring graph changed.
   - `layersChanged()` — project layers added/removed.
   - `themeChanged()` — global theme changed; every tile re-applies appearance.
   - `featureAction(object)` — list of feature ids to zoom/flash; the map listens.

   Sources call `set_filter(self.id, expr_or_None)`. Wiring lives in `_connections` (`set_targets`, `targets_of`, `is_connected`, `connections_to_dict`/`load_connections`). `forget_element(id)` drops a removed tile from filters + graph.

2. **The window (`window.py` → `DashboardWindow`)** is a `QMainWindow` shown as its own OS window. Its toolbar exposes `Add element`, `Add page`, `Connections…`, `Appearance…`, `Grid…`, `Clear filter`, `Zoom −/100%/+`, and an active-filter label. The central widget is a `QTabBar` + a `QStackedWidget` of pages; each page is a `DashboardPage` (`{id, title, view}`) wrapping a `PageView`. Tabs add (`+`/`Add page`), rename (double-click), delete (right-click; the last page can't be deleted), and reorder (drag). `Connections…`/`Clear filter`/`Add element` act on the **current** page; `Grid…` applies one **global** grid to every page. It owns the `DashboardBus`, creates elements via the registry factory, and handles **persistence**: `save_to_project()` writes a **v3** JSON blob — `{version:3, grid:{cols,rows}, theme, window:{w,h}, active_page, pages:[{id, title, connections, elements:[…incl per-tile grid+style]}]}` — under project scope `QgisDashboard`/key `layout`. `load_from_project()` runs everything through the pure `migrate_layout()` helper, which upgrades the **v1** bare-list and **v2** single-page-with-top-level-connections blobs into v3 (collapsed into one "Page 1"). `closeEvent` emits `closed` so the toolbar action unticks.

3. **The page view (`page_view.py` → `PageView`)** is a `QScrollArea` wrapping one `DashboardCanvas` and owning that page's **zoom/pan** (scale-on-fill). At zoom 1.0 the canvas fills the viewport (original responsive behavior); above 1.0 the canvas is fixed at `viewport × zoom` so it overflows and the scrollbars (or middle-mouse drag) pan. Range 0.5–3.0 via `set_zoom`/`zoom_in`/`zoom_out`/`reset_zoom`; zoom is **view-only and never persisted**.

4. **The canvas (`dashboard_canvas.py` → `DashboardCanvas` + `GridTile`)** is the free drag/resize layout (one per page). Tiles are absolutely-positioned children remembering their placement in **cell units** (gx, gy, gw, gh); cell pixel size is `width/cols × height/rows`, so resizing/zooming or changing the grid rescales every tile. Drag a tile by its transparent top strip; resize via **8 handles** (4 corners + 4 edges — `_ResizeHandle`, geometry computed by the pure `_proposed_resize(edge, …)` helper). On release the tile **snaps to the grid**, is clamped in-bounds, and **reverts if it would overlap** another tile. Faint guides reveal the otherwise-invisible grid. Grid resolution is set in `settings_dialog.py → GridSettingsDialog`.

5. **The theme (`theme.py` → `Theme`)** is the single source of truth for every color/font/metric. The global theme is edited in `appearance_dialog.py → AppearanceDialog` (color pickers, a series-palette editor, and a `QFontComboBox` listing all QGIS/Qt fonts); a tile may carry a partial override in `config["style"]`, merged via `Theme.merged_with`. The window paints container chrome from `Theme.window_qss`; chart widgets read colors straight off the theme via each element's `_restyle()`.

6. **Elements (`elements/`)** are the dashboard tiles. `base.py → DashboardElement` (a `QFrame`) encodes the shared anatomy — title / body / description — a stable `id` (persisted in `config`, used by the connection graph), the **data-binding contract**, and appearance hooks:
   - `config["layer_id"]` — the bound `QgsVectorLayer` id (resolved lazily via `layer()`); `config["base_filter"]` — optional element-local expression.
   - `_combined_filter()` ANDs `base_filter` with `bus.combined_filter_for(self.id)`.
   - `iter_features()` yields features under the combined filter; `evaluate(expr)` runs an aggregate QgsExpression and exposes the combined filter as `@dashboard_filter`.
   - Class flags `is_filter_source` / `accepts_filter` declare an element's role. Subclasses implement `refresh()` (redraw) and optionally `_restyle()` (repaint custom views on theme change). Base wires `filtersChanged`/`layersChanged`/`themeChanged`/`filtersCleared` automatically.

### Source vs. target elements

| Element (`type_name`) | File | Role | Notes |
|---|---|---|---|
| `indicator` | `indicator.py` | target | Big value + optional reference/trend, via `evaluate()`. |
| `chart` | `chart.py` + `charts/painters.py` | source + target | One element, six QPainter chart types selected by `config["chart_type"]` — `bar`, `barh`, `line`, `area`, `pie`, `donut` — grouped by a category field with `count`/`sum`/`mean`. Clicking a bar/point/slice calls `set_filter`; clicking again clears. Pie/donut fold the long tail into an "Other" slice (not clickable). |
| `pivot` | `pivot.py` + `pivot_engine.py` | source + target | Cross-tab/matrix in a themed `QTableWidget`: rows = a row field, optional columns = a column field, cells aggregate a value field (`count`/`sum`/`mean`/`min`/`max`) with grand totals. The pandas-free `pivot_engine.compute_pivot` buckets `iter_features()` (testable on plain dicts). Clicking a data cell pushes `"row = r AND col = c"`; a row-header cell filters by row; a column header filters by column; clicking again clears. |
| `list` | `list_element.py` | target (featureAction source) | Feature table; selecting a row emits `featureAction` (it does not push a filter). |
| `map` | `map_element.py` | neither (`accepts_filter=False`) | A **live mirror of `iface.mapCanvas()`** — same displayed layers, follows pan/zoom; zooms + rubber-band flashes on `featureAction`. |
| `category_selector` | `category_selector.py` | source only (`accepts_filter=False`) | Dropdown of unique values; the cleanest source. A pure source must not react to filters — set `accepts_filter = False` (don't filter itself down to one value). |

The factory and labels live in `elements/__init__.py` (`ELEMENT_TYPES`, `ELEMENT_LABELS`, `create_element`). `create_element` also **migrates the legacy `serial_chart`/`pie_chart` element types onto `chart`** (with the right `chart_type`), so dashboards saved before the registry still load; they auto-upgrade to `__type__:"chart"` on the next save. The per-type configuration UI is `add_element_dialog.py → AddElementDialog`, which builds dynamic rows per selected type and returns `(type_name, config)`.

**Chart types are a declarative registry.** `elements/chart_specs.py → CHART_SPECS` maps each `chart_type` to its painter key, label, group, whether it takes a statistic/value field, "Other"-folding, and donut inner-radius (plus the Qt-free helpers `fold_categories` / `filter_literal`). `elements/charts/painters.py → PAINTERS` maps painter keys to `_ChartPainter` subclasses (all draw uniform `[(category, value)]` data and emit `categoryClicked`). **Adding a new chart type = one painter class + one `CHART_SPECS` row** — no change to `ChartElement` or the dialog.

### Plugin entry point

`__init__.py → classFactory(iface)` returns `qgis_dashboard.py → qgisdashboard`. That class keeps the Plugin Builder conventions (`tr()`, i18n loading, an `actions` list) but instead of opening a modal dialog it:
- registers one **checkable** toolbar + Plugins-menu action that shows/hides the standalone window;
- lazily creates the `DashboardWindow` on first toggle (`_ensure_window`) and unticks the action when the window's `closed` signal fires;
- connects `QgsProject.writeProject`, `iface.projectRead`, `iface.newProjectCreated` to save / load / clear the dashboard.

**Icon loading is intentionally resilient:** `from .resources import *` is wrapped in `try/except ImportError`. If `resources.py` was never compiled, the icon loads from the filesystem (`os.path.join(plugin_dir, 'icon.png')`) instead of the Qt resource path. This is what lets the plugin install without a build step — do not reintroduce a hard `from .resources import *`.

## Common commands

This is a QGIS/PyQt5 plugin; there is no app build. "Running" means loading it inside QGIS. The QGIS Python environment must be on `PYTHONPATH` for tests and imports (`qgis.core`, `qgis.gui`, `qgis.PyQt`).

```bash
# Syntax-check everything (no QGIS needed — catches typos fast)
cd qgis_dashboard && python -m py_compile __init__.py qgis_dashboard.py window.py bus.py \
  theme.py dashboard_canvas.py add_element_dialog.py settings_dialog.py \
  appearance_dialog.py connections_dialog.py elements/*.py

# Install for manual testing: copy (or symlink) the plugin folder into the
# QGIS plugins directory, then enable "QGIS Dashboard" in Plugins > Manage.
#   Windows: %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
#   Linux:   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
#   macOS:   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/

# Compile Qt resources (OPTIONAL — only if you want the :/plugins/... icon path)
cd qgis_dashboard && pyrcc5 -o resources.py resources.qrc

# Run the test suite (needs a sourced QGIS env; uses nose)
cd qgis_dashboard && make test
#   On Linux first: source scripts/run-env-linux.sh <path-to-qgis-install>
# Or run one module directly once QGIS is on PYTHONPATH:
cd qgis_dashboard && PYTHONPATH=$(pwd) python -m pytest test/test_dashboard.py -v

# Package a release zip (requires git + pb_tool or make)
cd qgis_dashboard && pb_tool zip        # or: make package VERSION=<tag>
```

Tests import plugin modules by bare name (e.g. `from bus import DashboardBus`), so they expect the plugin directory itself on `PYTHONPATH` (which `make test` sets). GUI-touching tests bootstrap QGIS through `test/utilities.py → get_qgis_app()`.

## Conventions specific to this codebase

- **Stay inside the Plugin Builder layout.** When you add a Python module or an `extra_dir`, register it in **both** `pb_tool.cfg` (`python_files` / `extra_dirs`) and `Makefile` (`PY_FILES` / `SOURCES` / `EXTRA_DIRS`), or it won't ship in the packaged zip.
- **Relative imports within the package** (`from .bus import …`, `from .elements import …`). The QGIS plugin loader imports the folder as a package; absolute imports break on install.
- **Qt comes through `qgis.PyQt`**, never bare `PyQt5`. **Do not use `qgis.PyQt.QtChart`** — the QtChart module is optional and is absent from many QGIS/PyQt builds (it raised `ModuleNotFoundError` on install). Charts are drawn with plain `QPainter` in a custom `QWidget` (see `elements/charts/painters.py`); follow that pattern for new visualizations.
- **Never mutate shared project layers** to apply a dashboard filter (no `setSubsetString` on project layers) — filtering is done per-element through `QgsFeatureRequest` so other plugins/views are unaffected.
- **Adding a new element type** (the most common extension):
  1. Create `elements/<type>.py` with a `DashboardElement` subclass, set `type_name`, set the `is_filter_source` / `accepts_filter` class flags, implement `refresh()`. To make it a *source*, call `self.bus.set_filter(self.id, expr_or_None)`; for a pure source set `accepts_filter = False` (see `category_selector.py`). For a theme-aware custom-painted view, override `_restyle()` and call `self.apply_theme()` in `__init__`.
  2. Register the class in `elements/__init__.py` (`ELEMENT_TYPES`) and add a label to `ELEMENT_LABELS`.
  3. Add its config rows in `AddElementDialog._rebuild` and read them in `result_config`.
  4. Persistence is automatic via `base.to_dict()` (whole `config` + `__type__` + `id`); the window adds `grid` placement. Ensure config values are JSON-serializable.
- **Theme everything through `Theme`.** New visualizations must read colors/fonts from `effective_theme()` (global merged with the tile's `config["style"]`), never hardcode — so the Appearance dialog and per-tile overrides keep working.

## Known limitations (deliberate, carried over)

- **No free-form overlap / z-ordering.** Tiles snap to the grid and may not overlap; placement reverts on collision. Resolution is set by the grid cols/rows.
- **Aggregates run on the UI thread.** For million-feature layers, move `_aggregate()` / `evaluate()` into a `QgsTask`.
- **QGIS aggregate functions ignore the feature-request filter**, so a bare `count(1)` in an indicator does not auto-fold the dashboard filter. `base.evaluate()` exposes the combined filter as the `@dashboard_filter` variable; use the aggregate `filter:=` argument to opt in. Charts/lists, which iterate `iter_features()`, *are* filter-aware.
- **Desktop only** — no web publishing; that is structural to any QGIS plugin.
