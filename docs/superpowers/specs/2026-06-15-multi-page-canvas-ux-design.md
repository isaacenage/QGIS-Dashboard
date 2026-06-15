# Design: Multi-page dashboards + canvas zoom/pan + tile resize handles

**Date:** 2026-06-15
**Status:** Approved (pending spec review)
**Origin:** §9 priority #4 from `SUMMARIZER_RESEARCH.md` ("Multi-page + canvas UX"), chosen as the first imitate-and-improve target.

## Goal

Add three user-facing capabilities to the QGIS Dashboard plugin, in one cohesive feature:

1. **Multi-page dashboards** — multiple pages of tiles, switchable via a tab bar.
2. **Canvas zoom/pan** — zoom the layout in/out and pan when zoomed.
3. **8-handle tile resize** — resize tiles from any corner or edge (currently bottom-right only).

## Non-goals (YAGNI)

- Per-page grid resolution (grid stays global; revisit later).
- Cross-page cross-filtering (filtering is page-local by design).
- Persisting zoom level (view-only; resets to 100% on open).
- Free-form overlap / z-ordering (tiles still snap and may not overlap — existing constraint preserved).
- Page duplication / templates (could be a later enhancement).

## Decisions (locked during brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Connections + active filters scope | **Page-local** (theme stays global) | Cross-filtering should only link tiles the user can see together. |
| Grid resolution scope | **Global** (one cols×rows for all pages) | Simplest; matches the single Grid… dialog. |
| Zoom/pan model | **Scale-on-fill** | Preserves current responsive-fill behavior at 100%; zoom is additive. |

## Architecture

### Page stack

Today `DashboardWindow` sets a single `DashboardCanvas` as its central widget. Insert a stack layer:

```
DashboardWindow
 ├─ QToolBar (existing) + zoom buttons
 ├─ QTabBar (NEW — one tab per page, "+" to add)
 └─ QStackedWidget (the "page stack")
     ├─ page 0: QScrollArea ▸ DashboardCanvas   (owns its tiles)
     ├─ page 1: QScrollArea ▸ DashboardCanvas
     └─ …
```

- Each page is its own `DashboardCanvas` (unchanged responsibilities — owns its tiles, enforces the snap grid). One canvas per page.
- The `QScrollArea` wrapper enables panning when zoomed.
- A lightweight `DashboardPage` record holds `{id, title, canvas, scroll_area}`. The window keeps an ordered `list[DashboardPage]` plus `active_page_id`.
- Page ids are generated like element ids (`uuid.uuid4().hex[:8]`).

### Bus refactor (page-local state)

`DashboardBus` keeps `iface` and `theme` **global**. The cross-filter state becomes **per-page**:

- Replace flat `_source_filters` / `_connections` with:
  - `_page_filters: dict[page_id, dict[source_id, expr]]`
  - `_page_connections: dict[page_id, dict[source_id, set[target_id]]]`
  - `_active_page: page_id | None`
- Expose `_source_filters` and `_connections` as **properties** returning the active page's dict, so existing in-place mutations (`pop`, item assignment, `discard`) keep working unchanged.
- `clear_all_filters` changes from reassigning `self._source_filters = {}` to `self._source_filters.clear()` (mutate the active page's dict in place).
- New methods:
  - `set_active_page(page_id)` — sets active page, `setdefault`s its dicts, emits `connectionsChanged` + `filtersChanged`.
  - `connections_to_dict(page_id=None)` — serialize a given (or active) page's connections.
  - `load_connections(data, page_id)` — load into a specific page.
  - `forget_page(page_id)` — drop a deleted page's filter + connection state.
  - `forget_element(id)` continues to operate on the active page.
- On page switch the window calls `set_active_page`; the emitted signals make the now-visible page recompute. Inactive pages' tiles still receive signals but resolve `combined_filter_for` to `None` (their ids aren't in the active page's connections) — harmless and cheap.

### Persistence — schema v3

`window.save_to_project` / `load_from_project`, backward compatible.

```json
{
  "version": 3,
  "grid": {"cols": 12, "rows": 8},
  "theme": { ... },
  "window": {"w": 1100, "h": 720},
  "active_page": "<page_id>",
  "pages": [
    {
      "id": "<page_id>",
      "title": "Page 1",
      "connections": { "<source_id>": ["<target_id>", ...] },
      "elements": [ { "__type__": "...", "id": "...", "grid": {"x","y","w","h"}, ... } ]
    }
  ]
}
```

**Backward compatibility on load:**
- **v1** (bare list of element configs) → wrap into a single page `{title:"Page 1", elements:list}`.
- **v2** (`{version:2, grid, theme, connections, window, elements}`) → wrap `elements` + `connections` into a single page named "Page 1".
- **v3** → read pages directly.

Theme and grid remain top-level (global) in all versions.

## Components & changes

| File | Change |
|---|---|
| `bus.py` | Page-local filter/connection state; properties + `set_active_page`, `forget_page`, page-scoped `connections_to_dict`/`load_connections`. |
| `dashboard_canvas.py` | Add `_zoom` (0.5–3.0); `cell_size` derives from scaled canvas size; size the canvas to `viewport × zoom`; spacebar / middle-mouse pan; `set_zoom`/`zoom_in`/`zoom_out`/`reset_zoom`. `GridTile`: replace single grip with 8 edge/corner handles. |
| `window.py` | Page stack (`QStackedWidget` of `QScrollArea ▸ DashboardCanvas`); `QTabBar` with add/rename/delete/reorder; zoom toolbar buttons + Ctrl+wheel; persistence v3 + v1/v2 migration; route Connections…/Clear filter to the active page. |
| `connections_dialog.py` | Operate on the current page's elements only; show page title in header (minor — likely already scoped to the elements passed in). |
| `test/test_dashboard.py` | New tests (see Testing). |

### Multi-page UX

- **Tab bar** (`QTabBar`) under the toolbar, one tab per page (title text), with a trailing **"+"** add button.
- **Switch:** click tab → `stack.setCurrentWidget(page.scroll_area)` + `bus.set_active_page(page.id)`.
- **Rename:** double-click tab → inline `QLineEdit` editor.
- **Delete:** right-click tab → "Delete page". Cannot delete the last remaining page; confirm if the page has tiles. Tears down the page's tiles and calls `bus.forget_page(id)`.
- **Reorder:** `QTabBar.setMovable(True)` → reorder the page list on `tabMoved`.
- **Connections…** dialog targets the current page's elements only. **Clear filter** clears the current page's filters.

### Zoom/pan (scale-on-fill)

- `DashboardCanvas._zoom` default `1.0`, clamped `[0.5, 3.0]`.
- At **zoom 1.0**: canvas fills the scroll-area viewport → identical to current behavior.
- At **zoom > 1.0**: canvas fixed size = `viewport × zoom`; `cell_size = canvas_width/cols`, so all tiles scale; scrollbars appear.
- **Pan:** scrollbars, spacebar-drag, or middle-mouse drag.
- **Controls:** toolbar **Zoom −**, **100%** (reset), **Zoom +**; **Ctrl + mouse wheel**.
- Grid/collision math is untouched — it already operates in cell units.
- Zoom is **not persisted**.

### Tile resize handles (8-handle)

- `GridTile`: replace the single bottom-right `_ResizeGrip` with **8 handles** — corners (`nw, ne, se, sw`) and edges (`n, s, e, w`), each with its matching resize cursor.
- Refactor `_ResizeGrip` to carry an `edge` spec and compute the proposed new pixel rect (origin may move for n/w/nw/ne/sw edges, not just size).
- On release, reuse the existing **snap → clamp → collision-revert** path (`end_resize` / `_commit_or_revert`), so commit behavior is unchanged; only the number of grab points grows. Min size stays 1×1 cell.

## Testing

Extend `test/test_dashboard.py` (pytest; logic-level tests need no GUI):

- **Bus / page-local state:**
  - A filter set on page A is invisible to page B (`combined_filter_for` on B returns `None`).
  - `set_active_page` swaps the active filter/connection dicts.
  - `forget_page` removes a page's state; `forget_element` only affects the active page.
  - Page-scoped `connections_to_dict` / `load_connections` round-trip.
- **Persistence / migration:**
  - v1 (bare list) load → one page "Page 1" with the elements.
  - v2 load → one page "Page 1" with elements + connections.
  - v3 round-trip preserves page ids, titles, per-page connections, and `active_page`.
  - Zoom is absent from saved JSON.
- **Canvas / tiles:**
  - `cell_size` scales proportionally with `_zoom`.
  - Resize-handle proposed-rect computation is correct per edge/corner.
  - Collision-revert still rejects an overlapping resize/move.

## Build order (for the implementation plan)

Bottom-up, each step independently testable:

1. **8-handle resize** in `GridTile` (contained; no schema/bus impact).
2. **Zoom/pan** in `DashboardCanvas` + scroll-area wrapper (contained).
3. **Bus page-local refactor** (properties + new methods + tests).
4. **Page stack + tab bar** in `window.py` (wire `set_active_page`).
5. **Persistence v3** + v1/v2 migration (tests).

## Risks / watch-points

- **Inactive-page signal churn:** all tiles (incl. hidden pages) receive bus signals. Acceptable for v1; if it ever matters, gate `refresh()` on the tile's page being active.
- **`clear_all_filters` semantics:** must mutate-in-place (`.clear()`), not reassign, or the property indirection breaks.
- **Map tile per page:** each `map` tile mirrors the global `iface` canvas; multiple map tiles across pages is fine (each mirrors the same QGIS canvas).
- **Scroll-area + theme:** ensure the `QScrollArea` viewport background matches the window theme (apply in `_apply_window_style`).
