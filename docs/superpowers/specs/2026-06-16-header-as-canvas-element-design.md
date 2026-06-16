# Header as a Canvas Element — Design Spec

**Date:** 2026-06-16
**Status:** Approved (design), pending implementation plan

## Problem

The header (brand banner) is currently a `HeaderElement` that is **not** a canvas
tile. `PageView` docks it on a page edge (top/bottom/left/right) *outside* the
scrolling canvas, sizes it to follow the export region's displayed width, and the
window persists it at the top level (global "show on all pages") or per-page of the
v3 blob. Visually it reads as awkwardly separated from the canvas: it floats over
the framed region rather than living inside the page the user lays out and exports.

We want the header to be **inside the canvas and treated as an ordinary dashboard
element** — obeying every canvas rule (free drag/resize, magnetic snap, overlap
revert/slide, per-page zoom, region-cropped PNG/PDF export), configured through the
inspector panel like any tile, and persisted in the page's `elements` list.

## Decisions

- **Free placement, not edge-docking.** The header becomes a `GridTile` with free
  `x/y/w/h`. The dock-edge model (`anchor`) and its `thickness` are dropped.
- **Per-page scope; global "show on all pages" is removed.** A header lives on one
  page like every other tile. Existing global headers are migrated into a header
  tile on each page that displayed them.
- **HTML export stays consistent.** The export reworks the header from a per-page
  docked banner into a positioned tile, so the desktop canvas and the exported HTML
  render the header the same way.

## Architecture changes

The header is special-cased in three places today; all three collapse onto the
normal tile path.

### 1. `HeaderElement` (`elements/header.py`)

- Remains a `DashboardElement` subclass; keeps title (font family / size / align),
  logo (path / slot / size), and `_restyle()`.
- **Removes** its self-owned editing affordances: `contextMenuEvent`,
  `mouseDoubleClickEvent`, and the `configureRequested` / `removeRequested`
  signals. The wrapping `GridTile` now supplies the drag strip, ⚙/✕ buttons, and
  the right-click *Configure / Connections / Tile appearance / Remove* menu.
- The dock-edge keys `anchor` and `thickness` are no longer meaningful for a
  free-placed tile: dropped from new configs, ignored if present in old ones.
  `logo_slot` (logo position relative to the title *inside* the banner) is kept.
- Still hides the base title/description chrome and fills the tile with its own
  title+logo layout.
- Remains `is_filter_source = False`, `accepts_filter = False` (presentational).

### 2. Canvas / window wiring (`window.py`, `dashboard_canvas.py`)

- `_on_element_chosen`: header seed config becomes `{"title": ""}` (no
  `anchor`/`thickness`).
- `add_element`: delete the `type_name == "header"` branch — headers go through
  `_add_element_to` like any element, getting the standard tile signal wiring
  (`styleRequested` / `connectionsRequested` / `configureRequested` /
  `closeRequested` → inspector).
- `DashboardCanvas.add_tile`: give `header` a banner-shaped default rect — full
  region width × `HEADER_BAND_H` (80 px) placed via `first_free` — mirroring how
  `map` gets `MAP_W`/`MAP_H`.
- **Delete** the header-only machinery on the window: `header_for_page`,
  `_set_header_from_config`, `_refresh_all_headers`, `_configure_header`,
  `_remove_header`, the `_global_header` attribute, and `DashboardPage.header_config`.

### 3. `PageView` (`page_view.py`) — strip the dock

- Remove `set_header`, `header()`, `sync_header_geometry`, `_relayout`,
  `_render_header_pixmap`, and the banner-compositing path in `export_pixmap`
  (it becomes simply `return self.canvas.export_pixmap(scale)`).
- Remove `_CanvasScroll._notify_page` and the header re-fit calls in
  `set_zoom`/`resizeEvent`.
- `PageView` collapses to what it fundamentally is: the scroll wrapper plus zoom
  delegation. The `dashPageWrap` styled-background workaround that existed to paint
  the canvas color behind the docked banner is reviewed and removed if no longer
  needed.

### 4. Persistence + migration (`window.py`)

- `_build_layout_dict`: stop writing the top-level `header` and per-page `header`
  keys. Header tiles serialize through the normal element path (`base.to_dict()`
  → `__type__:"header"` + `config`, window adds `grid`).
- `_apply_layout_dict`: stop applying `header`/`_global_header`. Instead,
  **materialize legacy headers into tiles**:
  - `migrate_layout` continues to carry the old `header` keys through unchanged.
  - For each page, after its region size is resolved, compute the page's resolved
    header config with `resolve_header(page_header, global_header)`.
  - If present, convert it to a header tile using a new pure helper
    `header_tile_placement(anchor, thickness, region_w, region_h)` returning
    `(header_rect, (dx, dy), (new_w, new_h))`:
    - **top:** header at `(0, 0, region_w, thickness)`; existing tiles shift by
      `(0, thickness)`; region grows to `(region_w, region_h + thickness)`.
    - **bottom:** header at `(0, region_h, region_w, thickness)`; tiles unchanged;
      region grows to `(region_w, region_h + thickness)`.
    - **left:** header at `(0, 0, thickness, region_h)`; tiles shift by
      `(thickness, 0)`; region grows to `(region_w + thickness, region_h)`.
    - **right:** header at `(region_w, 0, thickness, region_h)`; tiles unchanged;
      region grows to `(region_w + thickness, region_h)`.
  - The header tile inherits `logo_slot`/`logo_path`/`logo_size`/`title`/font/align
    from the old config; `anchor`/`thickness` are not stored on the tile.
  - The region is kept uniform across pages (it is a single global page size): take
    the max grown region across all migrated pages and apply it to every page.

### 5. HTML export (`export/`)

- `export/html_export.py`: remove `_build_header` and the `window.header_for_page`
  call.
- `export/serialize.py`: remove the per-page `header` key. The header now appears
  in the page's tile list like any element (with its `grid` placement), so it flows
  through the existing tile serialization.
- `export/assets/runtime.css` + `runtime.js`: remove the docked-banner layout
  (the `page.header` flex container and `box_direction` mirror). Add a `header`
  **tile renderer** that draws the styled title + optional logo in the configured
  `logo_slot`, positioned in the same absolute grid as every other tile —
  repurposing the existing banner title/logo/slot logic.

### 6. Pure helpers + tests (`elements/header_layout.py`, `test/`)

- `header_layout.py`: `box_direction` and `banner_compose` become dead (dock-only)
  and are removed. `inner_box_direction` (logo slot inside the banner) and
  `resolve_header` (used during migration) are kept. Add the pure
  `header_tile_placement(anchor, thickness, region_w, region_h)` helper.
- `test/test_header_layout.py`: drop the `banner_compose` cases; add
  `header_tile_placement` cases (all four anchors: header rect, tile shift, grown
  region).
- Add a migration test: a legacy v3 blob carrying a top-level `header` and/or a
  per-page `header` upgrades to header **tiles** in each page's `elements` list,
  with shifted tile coordinates and grown region.
- Update `pb_tool.cfg` / `Makefile` only if files are added (none expected; all
  changes are to existing modules).

## Out of scope / accepted trade-offs

- A header tile shows a *Connections…* menu item that does nothing (it is neither a
  filter source nor target) — the same harmless situation as `text` and `image`
  tiles today.
- Dropping global scope means a multi-page dashboard that wants the banner on every
  page needs one header per page. Migration does this automatically for existing
  files; new dashboards add headers per page.
- The migration's region growth assumes the common case (the same header thickness
  across pages, typically from a single global header). Mixed per-page thicknesses
  still migrate correctly per page but share the single max region; any extra space
  on a thinner page reads as empty margin.

## Affected files

- `qgis_dashboard/elements/header.py` — strip dock affordances.
- `qgis_dashboard/elements/header_layout.py` — remove dock helpers, add
  `header_tile_placement`.
- `qgis_dashboard/page_view.py` — remove the header dock entirely.
- `qgis_dashboard/dashboard_canvas.py` — header default tile size.
- `qgis_dashboard/window.py` — route header through the tile path; migration;
  persistence; remove header-only methods.
- `qgis_dashboard/export/html_export.py`, `export/serialize.py`,
  `export/assets/runtime.js`, `export/assets/runtime.css` — header-as-tile in the
  export.
- `qgis_dashboard/test/test_header_layout.py` (+ a migration test) — coverage.
