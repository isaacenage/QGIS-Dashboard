# Lock/Unlock modes + Map widget interactivity — design

Date: 2026-06-16
Status: Approved (pending spec review)

## Problem

Two coupled gaps in the dashboard window:

1. **Lock is half a feature.** Today the lock toggle (`window.py` → `_on_lock_toggled` →
   `DashboardCanvas.set_locked` → `GridTile.set_locked`) only hides each tile's drag strip and
   resize handles. Tile *contents* stay interactive in **both** states, and the ⚙/✕ buttons and
   right-click Configure/Connections/Remove menu stay available when locked. There is no clean
   separation between *building* a dashboard and *using* it. Lock is also view-only and not
   persisted.

2. **The map tile barely connects to the rest of the dashboard.** `map_element.py` mirrors
   `iface.mapCanvas()` and pushes a debounced extent filter (it is a filter **source**), but it is
   **not a filter target** (`accepts_filter = False`) — clicking a connected chart or table does not
   move the map. Pan is the middle mouse button and zoom is the wheel; left-drag is repurposed to
   move the tile. There is no identify-on-click.

## Goals

- Reframe the existing lock toggle into two coherent modes with **no new button**:
  - **Unlocked = Build mode** — tiles move/resize/configure/remove; contents are inert.
  - **Locked = Use mode** — geometry fixed; contents are fully interactive.
- Make the map a first-class interactive element in Use mode: left-drag pan, left-click identify,
  and automatic fly-to of connected-source filter results.
- Persist the mode in the saved file.

## Non-goals

- No change to the HTML export runtime (export remains a static, always-interactive snapshot;
  the map export stays a static image).
- No free-form overlap / z-ordering changes.
- No multi-layer identify (bound layer only), no QGIS native Identify Results dock.
- The map does not become a filter target in the *displayed-layers* sense — it never subsets the
  layers it shows; "target" here means **fly-to extent only**.

## Mode model

The existing toggle's meaning is preserved (locked = fixed geometry) and **extended**. The two
modes are exhaustive and mutually exclusive:

| Capability | Unlocked = Build | Locked = Use |
|---|---|---|
| Move / resize / drag tiles | enabled | fixed |
| Tile ⚙ / ✕ buttons | shown | hidden |
| Right-click Configure / Connections / Tile appearance / Remove | available | suppressed |
| Text-tile double-click-to-edit; header banner edit/remove | enabled | disabled |
| Chart click → filter, list select → featureAction, category selector, pivot click | inert | live |
| Map pan / identify / fly-to / extent-source push | inert | live |

### Persistence

- Add a top-level `locked: bool` to the **v3** layout blob, alongside `gap`, `canvas`, etc.
- `_build_layout_dict()` writes the window's current mode; `_apply_layout_dict(data)` restores it
  (applying it through the same path the toggle uses, so every canvas + the button icon/tooltip
  update).
- **Migration / default:** `migrate_layout()` (and `_apply_layout_dict` when the `locked` key is
  absent from any older blob) derives the default from content via a new pure helper
  `default_locked(blob) -> bool`: **non-empty `pages` with any tile → `True` (Use mode); otherwise
  `False`**. This realizes "a saved dashboard with tiles opens in Use mode; an empty one opens in
  Build mode." The Start-screen / no-dashboard path is unaffected (it shows the Start screen, not a
  locked empty page).

## Interaction gating — `set_interactive(on)` element contract (Approach A)

Chosen over a transparent event-eating overlay (which fights the full-bleed map's own mouse
handling and the drag-strip/handle z-order).

- Add `DashboardElement.set_interactive(on: bool)` to `elements/base.py`. Base implementation is a
  no-op (presentational elements — image, indicator — need nothing).
- The lock toggle already fans out to every tile. Extend the chain:
  - `GridTile.set_locked(locked)` (today hides strip + handles) **additionally**:
    - hides/shows the ⚙ and ✕ buttons (`locked` → hidden),
    - calls `self.element.set_interactive(locked)`,
    - makes `contextMenuEvent` inert while locked (the build-only menu is not shown in Use mode).
  - `DashboardCanvas.set_locked` continues to fan out to all tiles; newly-added tiles honor the
    current lock state (existing `place`/add path already calls `tile.set_locked(self._locked)`).
- Source/interactive elements override `set_interactive`:
  - **chart** (`chart.py`) — enable/disable the bar/point/slice click→`set_filter` handler.
  - **pivot** (`pivot.py`) — enable/disable the cell/row/column click→`set_filter` handler.
  - **list** (`list_element.py`) — enable/disable row-select → `featureAction`.
  - **category_selector** (`category_selector.py`) — enable/disable the combo (and suppress its
    `set_filter` push) when inert.
  - **text** (`text_element.py`) — gate double-click-to-edit on Build mode (`on == False`).
  - **map** (`map_element.py`) — store the flag; it drives pan/identify/fly/extent-push (below).
- **Header banner** (not a grid tile): the window disables the page header's
  `configureRequested` / `removeRequested` (double-click / right-click) while locked. Tracked by a
  window-level mode flag passed to each `PageView`.

The exact per-element on/off mechanism is "disconnect vs. connect the existing click handler" or a
local `self._interactive` guard checked at the top of the handler — whichever is least invasive per
element; both are equivalent in effect.

## Map mouse behavior — driven by the tile lock flag

`_TileMapCanvas` already reads `tile.is_locked()` via its `_tile_getter`. Behavior splits on it:

- **Build mode (unlocked):** left-press/drag/release drives `GridTile.begin_move`/`move_by`/
  `end_move` exactly as today. No fly, identify, or extent push.
- **Use mode (locked):**
  - left-**drag** pans the tile's **own** `QgsMapCanvas` (hand-rolled: shift the extent center by
    the dragged delta, or `panActionEnd`-style set-center on move), cursor = open/closed hand.
  - left-**click without drag** (cumulative movement under a small pixel threshold, decided on
    release) triggers **Identify** on the bound layer.

Implemented by extending `_TileMapCanvas`'s existing press/move/release handlers with a
mode branch — not by swapping `QgsMapTool`s (a tool swap would pop QGIS's native Identify Results
dock, which we explicitly do not want, and complicates click-vs-drag disambiguation).

## Map as fly-to target

- The element connects to `bus.filtersChanged`. The handler (`_fly_to_filtered`) runs only in Use
  mode:
  - `expr = bus.combined_filter_for(self.id)` — the AND of the map's **wired** sources only
    (respects the explicit-connection philosophy; the user wires chart/table → map via
    `Connections…`).
  - `expr is None` (filters cleared) → **re-sync to the QGIS canvas extent** (return to mirroring).
  - `expr` non-None → query the **bound layer** (`config["layer_id"]`) with
    `QgsFeatureRequest().setFilterExpression(expr)`, union the matching features' bounding boxes
    into one `QgsRectangle`, `setExtent` (scaled padding, reusing the existing `_zoom_to` logic),
    and flash them via the existing `_flash`. One feature → that feature's bbox; many → the combined
    bbox.
  - No bound layer configured → graceful no-op.
- Existing `featureAction` (list row → zoom/flash) is unchanged and continues to work in Use mode.

## Map as extent source (revised)

The map keeps its source role, now driven by direct navigation of the tile rather than mirroring
iface:

- Listen to the **tile canvas's own** `extentsChanged` → schedule the debounced push.
- `_push_extent_filter` is gated on `isVisible()` **and** Use mode; it reads
  `self.canvas.extent()` (the tile's own extent) and the tile canvas CRS. When not in Use mode or
  not visible, it pushes `None`.
- `_sync_extent` (mirror of the iface extent) runs **only in Build mode**, so a Use-mode pan is not
  immediately overwritten by an iface `extentsChanged`. Layers and CRS keep mirroring in both modes.

## Identify popup — new module `elements/map_identify.py`

- `IdentifyPopup(QFrame)` — a themed, frameless popup of `field: value` rows shown near the cursor,
  dismissed on the next click / pan / move-away. Styled from the active `Theme` (soft hairline
  border, chrome neutrals — never a dark outline).
- Pure, Qt-free helpers (unit-tested):
  - `search_rect(map_x, map_y, tol) -> (xmin, ymin, xmax, ymax)` — the tolerance square around a
    click in map units.
  - `feature_summary(field_names, attributes, limit) -> list[(name, value)]` — the rows to display
    (handles NULLs, truncation).
- `map_element.py` calls into this module on a Use-mode identify click: pixel → map coords →
  `search_rect` → `QgsFeatureRequest` on the bound layer → first/nearest match → `feature_summary`
  → show popup. No match → dismiss any open popup.

Keeping the popup + helpers in their own module keeps `map_element.py` focused on the canvas mirror
and source/target wiring.

## Files touched

- `window.py` — persist/restore `locked`; track a window mode flag; disable header edit when locked;
  apply mode on load/create.
- `dashboard_canvas.py` — `GridTile.set_locked` also hides ⚙/✕, calls `element.set_interactive`,
  and gates `contextMenuEvent`.
- `elements/base.py` — `set_interactive(on)` no-op contract.
- `elements/chart.py`, `pivot.py`, `list_element.py`, `category_selector.py`, `text_element.py` —
  override `set_interactive`.
- `elements/map_element.py` — Use-mode pan/identify, fly-to target, revised extent source,
  `set_interactive`.
- `elements/map_identify.py` — **new** (`IdentifyPopup` + pure helpers).
- `page_view.py` — accept/relay the mode flag to gate header edit.
- `pb_tool.cfg` + `Makefile` — register `elements/map_identify.py` (it ships under the `elements`
  extra dir already, but list it in `python_files` / `PY_FILES` / `SOURCES` for completeness/parity
  with sibling modules).

## Testing

- **Pure helpers, TDD (no QGIS needed):**
  - `default_locked(blob)` — empty → False; with-tiles → True; absent-key paths.
  - `map_identify.search_rect` — tolerance square math.
  - `map_identify.feature_summary` — NULL handling, row limit/truncation.
  - Run directly per the project convention (each test file run standalone so `test/__init__`'s
    QGIS import is skipped).
- **Manual (GUI, in QGIS):** lock-toggle fan-out (geometry frozen, chrome hidden, contents live);
  map left-drag pan; left-click identify popup; chart/table → map fly-to of single and multi
  features; extent push gated to Use mode; persistence round-trip (save in Use mode → reopen Use
  mode; empty → Build).

## Deliberate consequences

- In Use mode tiles cannot be reconfigured — unlock to edit. This matches the requested model.
- The map becomes independently navigable in Use mode; it stops mirroring the iface extent until
  filters are cleared or the user returns to Build mode (layers + CRS keep mirroring throughout).
