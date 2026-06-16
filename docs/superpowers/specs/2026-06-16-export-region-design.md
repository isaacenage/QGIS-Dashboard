# Export region + fit-to-region Reset Zoom + adjustable canvas size

**Date:** 2026-06-16
**Status:** Approved, implementing.

## Problem

- PNG/PDF export renders the surface from `(0,0)` out to `DashboardCanvas._content_extent()`
  (the outermost right/bottom edge of all tiles) + a small `MARGIN`. The exported image is
  therefore sized to the **ragged bounding box** of the tiles, not a predictable page.
- **Reset Zoom** just sets zoom to `1.0`, which makes the canvas fill the current viewport.
  It does not fit to any defined region.
- There is **no concept of a canvas/page size** — the canvas grows on demand to contain tiles
  and fill the viewport. The user cannot tell "how big is my dashboard."

## Decision

Introduce an explicit, global **export region** (a fixed page rectangle) that:

1. is the source of truth for the page the dashboard lives on (Option A — "the region is the canvas");
2. is drawn on the canvas as a light hairline rectangle with a faint scrim over the
   off-page area ("this is the page" reads clearly);
3. is what **Reset Zoom** fits the viewport to;
4. is adjustable from **Settings → Layout → Canvas size** (presets + custom pixels);
5. **drives export** — PNG/PDF render exactly the region rect (tiles outside are cropped,
   empty space inside becomes margin → always a clean rectangle).

Scope: **global** (one size for the whole dashboard, like `grid`/`gap`).

## Design

### Data model & persistence (`window.py`)
- Constants `DEFAULT_CANVAS_W = 1280`, `DEFAULT_CANVAS_H = 720` (16:9).
- v3 blob gains optional top-level `"canvas": {"w", "h"}`. **Version stays 3** (additive optional key).
  `migrate_layout` carries it: `out["canvas"] = raw.get("canvas") or None`.
- `_build_layout_dict` writes `"canvas"` from `self.canvas_size()` (mirrors `canvas_gap()`,
  reading `_pages[0].canvas.region_size()`).
- `_apply_layout_dict` reads it; when **absent** (old dashboards) it computes the region from the
  content bounding box across all pages, rounded up to a tidy step, falling back to the default
  when there are no tiles — so existing exports don't change on first open. Applies via
  `canvas.set_region(w, h)` to every page.
- `add_page` seeds new canvases with `set_region(*self.canvas_size())` (like it does for gap).

### Canvas / region model (`dashboard_canvas.py`)
- `DashboardCanvas` stores `region_w, region_h`; `set_region()` / `region_size()`.
- `sync_size()` → surface = `max(region, content extent)` (out-of-region tiles stay reachable).
  Drops the viewport-fill behavior (the region now defines the page).
- `paintEvent` draws the region: 1px **cosmetic** hairline in `theme.border` at
  `(pad, pad, region_w·zoom, region_h·zoom)`, plus a faint scrim over the area **outside** it.
- `export_pixmap` renders **exactly the region rect**: zoom 1.0, region-sized pixmap,
  `render(..., QRegion(pad, pad, region_w, region_h))`.

### Reset Zoom = fit (`page_view.py`)
- Pure `fit_zoom(region, viewport, margin)` helper (Qt-free, unit-tested).
- `_CanvasScroll.reset_zoom()` computes the fit factor from the viewport and `region_size()`
  and applies it (region framed + centered).
- Zoom clamp widens (`ZOOM_MIN 0.5→0.1`, `ZOOM_MAX 3.0→4.0`); `zoom_in/out` keep ×1.2.
- Reframe on first show and on region change.

### Settings → Layout "Canvas size" (`settings_dialog.py` + `window.py`)
- New top group on the *Layout* page: preset `QComboBox` + width/height `QSpinBox`es (px).
  Presets: `16:9 — 1280×720`, `16:9 — 1920×1080`, `16:10 — 1280×800`, `4:3 — 1024×768`,
  `A4 Landscape — 1754×1240`, `A4 Portrait — 1240×1754`, `Letter Landscape — 1650×1275`, `Custom…`.
  Editing a spinner flips combo to *Custom*; picking a preset sets the spinners.
- New ctor params `on_canvas_size=f(w,h)`, `canvas_size=(w,h)`; `open_settings` wires
  `self._set_canvas_size` / `self.canvas_size()`.
- `_set_canvas_size(w,h)` applies `set_region` to every page, repaints, reset-zooms current view.

### Docs & tests
- Update CLAUDE.md (v3 `canvas` key, region-bounded export, fit-to-region Reset Zoom, Layout control).
- No new module → no `pb_tool.cfg`/`Makefile` changes.
- Pure tests (run without QGIS): `fit_zoom()`; migration round-trip with/without `canvas`.

## Out of scope (v1)
- Hard-clamping tile drag to the region (tiles can still be dragged off-page; the rectangle
  shows what will be cropped).
- Per-page region sizes.
