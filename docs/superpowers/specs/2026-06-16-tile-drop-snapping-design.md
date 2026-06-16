# Tile drop snapping & drag feedback

**Date:** 2026-06-16
**Status:** Approved

## Problem

In `dashboard_canvas.py`, tiles are free-form pixel rectangles. While dragging, the
canvas shows only a faint dot lattice — no feedback about where a tile can land. On
release, `GridTile._commit_or_revert()` reverts the tile **all the way back to its
drag-start position** whenever the dropped rectangle overlaps another tile or falls
off the page. Dropping a tile into the visible gap between two others fails and the
tile flies back to where it came from, with no indication of why.

## Goal

Make dropping feel magnetic and forgiving:

1. **Never revert to origin.** A dropped tile lands at (or near) where it was released.
2. **Edge snapping (keep size).** The tile keeps its current width/height and snaps
   its edges flush against neighboring tiles and the page edges, spaced by the global
   **Element Gap** (`canvas.gap`, set in Settings → Layout).
3. **Live drag feedback.** While dragging, paint the landing zone:
   - **Yellow** translucent rectangle at the snapped landing position when it fits.
   - **Red** translucent overlay over the tile's current spot when it does not fit.
4. **No-fit fallback.** If the release position cannot fit anywhere at the cursor, the
   tile snaps to the *nearest* free space — it never returns to the far origin.

Out of scope: resize gestures keep today's behavior (revert on overlap). Auto-resize
to fill a gap was considered and rejected in favor of keep-size edge-snapping.

## Design

### New pure module `tile_snap.py` (Qt-free, unit-tested)

Mirrors the `zoom_fit.py` pattern: pure functions on plain tuples, tested without QGIS.

- `rects_overlap(a, b)` — helper, `(x, y, w, h)` overlap test.
- `snap_rect(rect, others, region, gap, threshold)` → `(x, y, w, h)`
  - `rect`: the dragged tile's proposed logical rect (already 8px-snapped by caller).
  - `others`: list of the other tiles' logical rects.
  - `region`: `(region_w, region_h)` page size.
  - `gap`: Element Gap in logical px (spacing kept between snapped neighbors/edges).
  - `threshold`: max logical-px distance for an edge to be pulled to a snap line.
  - Builds candidate snap lines per axis:
    - left edge → `0`, each `other.right + gap`, each `other.left`
    - right edge → `region_w`, each `other.left - gap`, each `other.right`
    - top edge → `0`, each `other.bottom + gap`, each `other.top`
    - bottom edge → `region_h`, each `other.top - gap`, each `other.bottom`
  - For each axis, pick the nearest snap line within `threshold`. **Size is fixed**, so
    only one edge per axis can win — whichever candidate (left vs right / top vs bottom)
    is closer to its nearest line. Snapping the left/top moves the origin; snapping the
    right/bottom moves the origin so the far edge meets the line.
  - Returns the input rect unchanged when no edge is within `threshold`.
- `nearest_free(rect, others, region, step)` → `(x, y, w, h)`
  - If `rect` overlaps nothing and is in-bounds, return it.
  - Otherwise spiral-search the `step` grid outward from `rect`'s origin (clamped to the
    region) for the closest same-size placement that overlaps no `other`. Return the
    first hit; if none found within the region, return `rect` unchanged (caller still
    places it — never reverts).

### `dashboard_canvas.py` changes

`DashboardCanvas`:
- `set_drop_preview(rect_or_None, valid)` — store a live preview rect (logical) + validity
  flag and `update()`.
- `paintEvent` — when a preview is set, draw it: a translucent **yellow** fill + hairline
  when `valid`, a translucent **red** fill when not. Drawn in display px (logical × zoom,
  offset by `_pad()`), like tiles.
- Reuse existing `rect_free` for validity.

`GridTile`:
- `move_by` — after the existing clamp, compute the candidate logical rect, run it through
  `snap_rect(..., gap=self.canvas.gap, ...)`, and push it to `self.canvas.set_drop_preview`
  with `valid = canvas.rect_free(candidate, ignore=self)`. (The live widget keeps following
  the cursor; only the preview shows the snap target.)
- `end_move` — compute the snapped candidate the same way. If `rect_free`, commit it. Else
  `nearest_free` and commit that. Clear the preview. **Remove the revert path** for moves.
- `_commit_or_revert` stays for resize; a new `_commit_move(rect)` handles the no-revert
  move path (place + grow surface + emit `geometryCommitted` when changed).

### Tests

`test/test_tile_snap.py` (pure, run directly like `test_zoom_fit.py`):
- `snap_rect`: left edge pulls to a neighbor's `right + gap`; right edge pulls to page
  edge; no snap when outside threshold; closer-edge-wins when both sides are near.
- `nearest_free`: returns input when already free; finds the closest free slot when the
  drop overlaps; returns input when the region is fully packed.
- `rects_overlap`: touching edges do not count as overlap; true overlap detected.

Register `tile_snap.py` in `pb_tool.cfg` (`python_files`) and `Makefile`
(`PY_FILES` / `SOURCES`).

## Acceptance

- Dropping a tile into a gap between two tiles lands it there, snapped flush with the
  Element Gap as spacing — no revert.
- Dragging shows a yellow landing zone where it will land, red when it cannot fit.
- Dropping onto an occupied area slides the tile to the nearest free space.
- `python test/test_tile_snap.py` passes; `py_compile` clean.
