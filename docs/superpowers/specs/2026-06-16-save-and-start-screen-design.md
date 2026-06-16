# Save to `.qdash` + Start screen with recent-project cards

**Date:** 2026-06-16
**Status:** Approved (design)

## Problem

The dashboard's entire state is already serialized into a v3 JSON blob and stored
**inside the `.qgz`** (`window.save_to_project` / `load_from_project` /
`migrate_layout`), so reopening a QGIS project restores the dashboard you left.
But there is no way to:

1. Save a dashboard to a **portable, standalone file** that can be shared or
   reopened independently of the `.qgz`.
2. **Discover and reopen** previous dashboards quickly — the way QGIS shows recent
   projects as cards on startup, and the way the Summarizer plugin shows recent
   dashboards as cards.

This change adds a portable save file (`.qdash`), a **Start/Home screen of
recent-project cards shown inside the canvas area**, and tidies the sidebar.

## Goals

- Reorder the rail zoom buttons to (top→bottom) **Zoom in → Zoom out → Reset zoom**.
- Add a rail **Save** button that writes the whole dashboard to a `.qdash` file.
- Add a rail **Home** button that returns to the Start screen at any time.
- Show a **Start screen** (recent-project cards + "New Dashboard" + "Open from
  file…") inside the canvas area **when the current QGIS project has no dashboard
  yet**. When the `.qgz` already has a dashboard, open straight to it (unchanged).
- Maintain recents in `QSettings` (capped, deduped, auto-pruned), like Summarizer.

## Non-goals (YAGNI)

- Live thumbnail snapshots on cards — use a branded placeholder + name/path/date.
- Embedding layer **data** in `.qdash` — it stays a config/template file that
  references layers by `layer_id` (same contract as the `.qgz` embedding).
- An "Open" entry in the Settings hub — Open now lives on the Start screen cards
  (reachable any time via the Home rail button).

## File format: `.qdash`

- Extension **`.qdash`** (follows QGIS's `q*` family: `.qgz`, `.qlr`, `.qml`,
  `.qpt`, `.qmd`). Content is **JSON** — the same v3 layout dict written into the
  `.qgz`, plus a top-level `"_format": "qgis-dashboard"` marker.
- Older `.qdash` files load through the existing pure `migrate_layout`, so they
  auto-upgrade exactly like older `.qgz` blobs. `migrate_layout` ignores the extra
  `_format` key.

## Components

### `project_io.py` (new, pure — no QGIS/Qt)

The single source of truth for the `.qdash` format. Pure, unit-testable.

- Constants: `QDASH_SUFFIX = ".qdash"`, `QDASH_FILTER = "QGIS Dashboard (*.qdash)"`,
  `FORMAT_TAG = "qgis-dashboard"`.
- `ensure_suffix(path) -> str` — append `.qdash` if missing (case-insensitive).
- `write_layout_file(path, data)` — returns a **new** dict with `_format` set,
  `json.dump`s it (UTF-8, `indent=2`, `ensure_ascii=False`) to `ensure_suffix(path)`.
  Does not mutate `data`.
- `read_layout_file(path) -> dict` — reads + `json.loads`; raises `ValueError` if the
  content is not a JSON object. Caller runs `migrate_layout` on the result.

### `recent_store.py` (new) — recents persistence (ported from Summarizer's `DashboardProjectStore`)

- Pure helpers (testable without QGIS), operating on plain lists of
  `{path, name, updated_at}` dicts:
  - `prune_missing(items, exists=os.path.exists)` — drop entries whose file is gone.
  - `dedupe_insert(items, entry, max_items)` — remove any same-path entry, insert
    `entry` at the front, cap to `max_items`. Returns a **new** list.
- Thin `QSettings` wrapper class `RecentStore`:
  - Keys: `QgisDashboard/recent_projects`, `QgisDashboard/last_dir`. `MAX_RECENTS = 8`.
  - `load_recents() -> list` (JSON-decoded, pruned, capped; rewrites storage if it
    pruned anything).
  - `record(path, name=None)` — uses `dedupe_insert` with a fresh `updated_at`.
  - `clear()`.
  - `default_directory()` / `remember_dir(path)` — last-used save directory, falling
    back to `~/Documents` (or `~`).
- `updated_at` is captured at call time via `QDateTime.currentDateTime().toString(Qt.ISODate)`
  (avoids non-deterministic `datetime.now()` in pure code; the timestamp lives in the
  Qt wrapper, not the pure helpers).

### `start_view.py` (new) — the Start/Home screen

A `QWidget` shown in the canvas content area. Themed via `Theme`; restyled on
`themeChanged`. Lays cards out in a **wrapping `QGridLayout` inside a `QScrollArea`**.

- `_ActionCard(icon_key, title, subtitle)` — icon chip + title + subtitle; `clicked`
  signal. Two instances: **New Dashboard** (`add_element`/dashboard glyph) and
  **Open from file…** (`export`/folder glyph — a dedicated `open` glyph is added).
- `_RecentCard(name, path, updated_at)` — branded `logo_pixmap` preview on top, then
  name, **elided** path, and last-modified date; hover + soft `QGraphicsDropShadowEffect`;
  `clicked` signal carrying the path.
- All colors come from `Theme` (background, text, `text_muted`, `border` hairline,
  `brand_soft` hover). **No hardcoded dark borders** — `theme.border` only, per the
  codebase border rule.
- `StartView` signals: `newRequested()`, `openFileRequested()`, `openRecentRequested(str)`.
- `set_recents(list)` rebuilds the recent cards; an empty state shows a short hint
  ("No saved dashboards yet — create one with New Dashboard").

### `window.py` wiring

- **Content stack**: wrap the existing (tab-strip + pages `QStackedWidget`) column and
  a new `StartView` in a content-area `QStackedWidget`. `show_start()` refreshes recents
  from `RecentStore`, hides the tab strip, shows the StartView; `show_dashboard()` shows
  the pages column.
- **Refactor (no behavior change to `.qgz`)**:
  - `_build_layout_dict() -> dict` — the dict-building currently inline in
    `save_to_project()`. Both `save_to_project()` (writes to `QgsProject`) and
    `save_to_file()` call it.
  - `_apply_layout_dict(data)` — the UI-applying currently inline in
    `load_from_project()` (theme, header, grid, pages, elements, active tab, window
    size). Both `.qgz` load and file open call it.
- **New methods**:
  - `save_to_file()` — `QFileDialog.getSaveFileName` seeded from
    `RecentStore.default_directory()`, default suffix `.qdash`; `write_layout_file`;
    `RecentStore.record(...)` + `remember_dir(...)`; status-bar confirmation;
    `QMessageBox` on error.
  - `open_file_path(path)` — `read_layout_file` → `migrate_layout` → `_apply_layout_dict`
    → `show_dashboard()` → `RecentStore.record(...)`. Wrapped in try/except with a
    user-friendly `QMessageBox`; on failure the recent entry is left for `load_recents`
    to prune.
  - `open_from_file()` — `QFileDialog.getOpenFileName` → `open_file_path`.
  - `new_dashboard()` — clear, add a blank "Page 1", apply default grid, `show_dashboard()`.
- **`load_from_project()` change**: if the `.qgz` has an embedded dashboard → migrate +
  `_apply_layout_dict` + `show_dashboard()` (unchanged restore). If **empty** →
  `show_start()` instead of auto-creating "Page 1".
- **Sidebar**: reorder zoom actions; add **Save** (→ `save_to_file`) to the top group;
  add **Home** (→ `show_start`).
- Confirmation: opening a recent/file while a dashboard with content is loaded prompts a
  `QMessageBox` Yes/No before replacing it.

### `icons.py` (new glyphs)

Stroke-based, matching the existing `_stroke` style: `"save"` (floppy-disk outline),
`"home"` (house), and `"open"` (folder) for the Open-from-file action card.

## Data flow

```
QGIS opens .qgz ─► load_from_project()
    ├─ embedded dashboard? ─► migrate_layout ─► _apply_layout_dict ─► show_dashboard()
    └─ empty?              ─► RecentStore.load_recents ─► StartView.set_recents ─► show_start()

StartView card click
    ├─ New Dashboard      ─► new_dashboard() ─► show_dashboard()
    ├─ Open from file…    ─► open_from_file() ─► getOpenFileName ─► open_file_path()
    └─ Recent card        ─► open_file_path(path)
                                ─► read_layout_file ─► migrate_layout
                                ─► _apply_layout_dict ─► show_dashboard()
                                ─► RecentStore.record()

Rail Save ─► save_to_file()
    ─► _build_layout_dict ─► write_layout_file ─► RecentStore.record() + remember_dir()

QGIS saves .qgz ─► save_to_project() ─► _build_layout_dict ─► QgsProject.writeEntry (unchanged)
```

## Error handling

- `read_layout_file` raises `ValueError` for non-object or corrupt JSON; `open_file_path`
  catches it and any `OSError`, shows a `QMessageBox`, and stays on the current view.
- `write_layout_file` failures (`OSError`) surface as a `QMessageBox`; recents/last-dir are
  only recorded on success.
- Missing recent files never reach an open attempt during normal flow — `load_recents`
  prunes them — but `open_file_path` still guards against a file vanishing mid-session.

## Testing

- `test/test_project_io.py` — round-trip `write`→`read`, `ensure_suffix`, `_format`
  marker present, `data` not mutated, migrate-compat (a v2 blob written then read +
  migrated yields a v3 dict). Runnable without QGIS (run the file directly).
- `test/test_recent_store.py` — `prune_missing` with a fake `exists`, `dedupe_insert`
  dedupe/cap/order, immutability of inputs. Pure, no QGIS.

## Registration

Add `project_io.py`, `recent_store.py`, `start_view.py` to **both** `pb_tool.cfg`
(`python_files`) and `Makefile` (`PY_FILES` / `SOURCES`), per the codebase rule.

## Known limitation (carried, deliberate)

Tiles bind to layers by QGIS `layer_id`. A `.qdash` opened on the project it came from
restores fully; opened on a different project, layout/theme/config restore but tiles need
rebinding. Recent cards for moved/deleted files auto-drop from the list.
