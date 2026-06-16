# Header as a Canvas Element — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the dashboard header (brand banner) from an out-of-canvas docked banner into an ordinary canvas tile that obeys every canvas rule and is configured/persisted like any element; drop the global "show on all pages" scope.

**Architecture:** Two new *pure* helpers in `elements/header_layout.py` (`header_tile_placement`, `materialize_header_tiles`) do the geometry + the legacy-header→tile migration with no Qt/QGIS, so they are unit-tested directly. The desktop side (`window.py`, `page_view.py`, `dashboard_canvas.py`, `elements/header.py`, `add_element_dialog.py`) then routes the header through the normal tile path and deletes the docking machinery. The HTML export (`export/`) renders the header as a positioned tile instead of a docked banner. Dead dock helpers are removed last.

**Tech Stack:** Python 3 / PyQt5+PyQt6 (via `qgis.PyQt`), QGIS plugin. Pure tests run with `python test/<file>.py` (no QGIS). Browser runtime is vanilla JS verified with `node --check`.

**Context for the worker:** Today the header is special-cased in three places — the live `PageView` docks it outside the scrolling canvas; the window persists it at the top level (global) or per page; and the HTML export renders it as a per-page docked banner. The spec is `docs/superpowers/specs/2026-06-16-header-as-canvas-element-design.md`. After this plan the header is just a `GridTile` carrying `title`/`font_family`/`font_size`/`align`/`logo_path`/`logo_slot`/`logo_size`; the dock-only keys `anchor`/`thickness`/`scope_all_pages` are gone.

**Important repo conventions (do not violate):**
- Relative imports inside the package (`from .elements.header_layout import …`).
- Fully-scoped Qt enums only (`Qt.AlignmentFlag.AlignLeft`), `.exec()` not `.exec_()`.
- Soft hairline borders only (`theme.border`), never dark/heavy outlines.
- No new files are added, so `pb_tool.cfg` / `Makefile` need no edits.

---

## File structure

| File | Responsibility after this plan |
|---|---|
| `qgis_dashboard/elements/header_layout.py` | Pure helpers: `inner_box_direction`, `resolve_header`, **new** `header_tile_placement`, **new** `materialize_header_tiles`. `box_direction`/`banner_compose` removed. |
| `qgis_dashboard/elements/header.py` | `HeaderElement` renders title+logo inside a tile; no self-owned context menu / double-click / signals. |
| `qgis_dashboard/page_view.py` | Scroll wrapper + zoom delegation only; no header dock. |
| `qgis_dashboard/dashboard_canvas.py` | Header tiles get a banner-shaped default size. |
| `qgis_dashboard/window.py` | Header flows through the tile path; legacy headers materialized into tiles on load; no header-only methods. |
| `qgis_dashboard/add_element_dialog.py` | Header config form drops `anchor`/`thickness`/`scope_all_pages`. |
| `qgis_dashboard/export/html_export.py`, `export/serialize.py`, `export/assets/runtime.js`, `export/assets/runtime.css` | Header rendered as a positioned tile, not a docked banner. |
| `qgis_dashboard/test/test_header_layout.py` | Tests for the two new pure helpers; old `banner_compose` tests removed. |

---

## Task 1: Pure helper `header_tile_placement`

**Files:**
- Modify: `qgis_dashboard/elements/header_layout.py`
- Test: `qgis_dashboard/test/test_header_layout.py`

- [ ] **Step 1: Write the failing tests**

Add this new test class to `qgis_dashboard/test/test_header_layout.py` (keep the existing imports and `BannerComposeTest` for now — they are removed in Task 6). Update the import line at the top so it also imports the new helper:

Change line 23 from:
```python
from header_layout import banner_compose, box_direction
```
to:
```python
from header_layout import banner_compose, box_direction, header_tile_placement
```

Then add, above `if __name__ == "__main__":`:
```python
class HeaderTilePlacementTest(unittest.TestCase):
    """Geometry for converting a docked legacy header into a canvas tile."""

    def test_top_places_band_and_shifts_tiles_down(self):
        rect, shift, region = header_tile_placement("top", 80, 1000, 600)
        self.assertEqual(rect, (0, 0, 1000, 80))      # full-width band at the top
        self.assertEqual(shift, (0, 80))              # existing tiles move down
        self.assertEqual(region, (1000, 680))         # region grows in height

    def test_bottom_places_band_and_leaves_tiles(self):
        rect, shift, region = header_tile_placement("bottom", 80, 1000, 600)
        self.assertEqual(rect, (0, 600, 1000, 80))    # band below the old region
        self.assertEqual(shift, (0, 0))               # tiles unchanged
        self.assertEqual(region, (1000, 680))

    def test_left_places_band_and_shifts_tiles_right(self):
        rect, shift, region = header_tile_placement("left", 120, 1000, 600)
        self.assertEqual(rect, (0, 0, 120, 600))      # full-height band at the left
        self.assertEqual(shift, (120, 0))             # tiles move right
        self.assertEqual(region, (1120, 600))         # region grows in width

    def test_right_places_band_and_leaves_tiles(self):
        rect, shift, region = header_tile_placement("right", 120, 1000, 600)
        self.assertEqual(rect, (1000, 0, 120, 600))   # band right of the old region
        self.assertEqual(shift, (0, 0))
        self.assertEqual(region, (1120, 600))

    def test_unknown_anchor_falls_back_to_top(self):
        self.assertEqual(header_tile_placement("sideways", 50, 200, 100),
                         header_tile_placement("top", 50, 200, 100))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd qgis_dashboard && python test/test_header_layout.py`
Expected: FAIL — `ImportError: cannot import name 'header_tile_placement'`.

- [ ] **Step 3: Implement the helper**

Add to `qgis_dashboard/elements/header_layout.py`, after `banner_compose` (before `resolve_header`):
```python
def header_tile_placement(anchor, thickness, region_w, region_h):
    """Place a legacy docked header as a canvas tile on its old edge.

    Converts the out-of-canvas banner model into a free-placed tile: returns
    the header tile's logical rect, the ``(dx, dy)`` shift to apply to every
    existing tile so it does not overlap the band, and the grown region size
    that now includes the band. Unknown anchors fall back to ``top``.

    Returns ``(header_rect, (dx, dy), (new_w, new_h))`` where ``header_rect`` is
    an ``(x, y, w, h)`` tuple, all in logical (zoom-1.0) pixels.
    """
    orient, banner_first = box_direction(anchor)
    if orient == "v":                       # top / bottom -> full-width band
        if banner_first:                    # top
            return ((0, 0, region_w, thickness), (0, thickness),
                    (region_w, region_h + thickness))
        return ((0, region_h, region_w, thickness), (0, 0),     # bottom
                (region_w, region_h + thickness))
    # left / right -> full-height band
    if banner_first:                        # left
        return ((0, 0, thickness, region_h), (thickness, 0),
                (region_w + thickness, region_h))
    return ((region_w, 0, thickness, region_h), (0, 0),         # right
            (region_w + thickness, region_h))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd qgis_dashboard && python test/test_header_layout.py`
Expected: PASS (all `BannerComposeTest` and `HeaderTilePlacementTest` cases).

- [ ] **Step 5: Commit**

```bash
git add qgis_dashboard/elements/header_layout.py qgis_dashboard/test/test_header_layout.py
git commit -m "feat: header_tile_placement helper for header-as-tile migration"
```

---

## Task 2: Pure helper `materialize_header_tiles`

**Files:**
- Modify: `qgis_dashboard/elements/header_layout.py`
- Test: `qgis_dashboard/test/test_header_layout.py`

This is the migration: given a loaded layout's pages, the optional global header, and the resolved region size, it appends each page's resolved header to that page's `elements` list as a `header` tile, shifts existing tiles out of the band, strips the dock-only config keys, and returns the grown (uniform) region.

- [ ] **Step 1: Write the failing tests**

Update the import line at the top of `test/test_header_layout.py`:
```python
from header_layout import (banner_compose, box_direction,
                           header_tile_placement, materialize_header_tiles)
```

Add this test class above `if __name__ == "__main__":`:
```python
class MaterializeHeaderTilesTest(unittest.TestCase):
    """Legacy global/per-page headers become header tiles in each page."""

    def _page(self, header=None, elements=None):
        p = {"id": "p1", "title": "Page 1", "connections": {},
             "elements": elements if elements is not None else []}
        if header is not None:
            p["header"] = header
        return p

    def test_global_header_added_to_each_page_as_top_tile(self):
        pages = [self._page(elements=[{"__type__": "indicator",
                                       "grid": {"x": 0, "y": 0, "w": 200, "h": 150}}])]
        glob = {"title": "Brand", "anchor": "top", "thickness": 80,
                "font_size": 22, "logo_slot": "left"}
        new_pages, w, h = materialize_header_tiles(pages, glob, 1000, 600)
        els = new_pages[0]["elements"]
        # existing tile shifted down by the band thickness
        self.assertEqual(els[0]["grid"], {"x": 0, "y": 80, "w": 200, "h": 150})
        # header appended as a header tile spanning the band
        hdr = els[1]
        self.assertEqual(hdr["__type__"], "header")
        self.assertEqual(hdr["grid"], {"x": 0, "y": 0, "w": 1000, "h": 80})
        self.assertEqual(hdr["title"], "Brand")
        # dock-only keys are stripped from the tile config
        self.assertNotIn("anchor", hdr)
        self.assertNotIn("thickness", hdr)
        self.assertNotIn("scope_all_pages", hdr)
        # region grew in height; the original 'header' key is gone
        self.assertEqual((w, h), (1000, 680))
        self.assertNotIn("header", new_pages[0])

    def test_per_page_header_overrides_global(self):
        pages = [self._page(header={"title": "Local", "anchor": "top",
                                    "thickness": 50})]
        glob = {"title": "Global", "anchor": "top", "thickness": 80}
        new_pages, w, h = materialize_header_tiles(pages, glob, 1000, 600)
        hdr = new_pages[0]["elements"][-1]
        self.assertEqual(hdr["title"], "Local")
        self.assertEqual(hdr["grid"]["h"], 50)
        self.assertEqual((w, h), (1000, 650))

    def test_no_header_leaves_page_unchanged(self):
        pages = [self._page(elements=[{"__type__": "chart",
                                       "grid": {"x": 0, "y": 0, "w": 100, "h": 100}}])]
        new_pages, w, h = materialize_header_tiles(pages, None, 1000, 600)
        self.assertEqual(new_pages[0]["elements"],
                         [{"__type__": "chart",
                           "grid": {"x": 0, "y": 0, "w": 100, "h": 100}}])
        self.assertEqual((w, h), (1000, 600))

    def test_region_is_uniform_max_across_pages(self):
        # page A has a top header (grows height), page B has none
        page_a = {"id": "a", "title": "A", "connections": {}, "elements": [],
                  "header": {"title": "H", "anchor": "top", "thickness": 80}}
        page_b = {"id": "b", "title": "B", "connections": {}, "elements": []}
        new_pages, w, h = materialize_header_tiles([page_a, page_b], None, 1000, 600)
        self.assertEqual((w, h), (1000, 680))   # both pages share the grown region
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd qgis_dashboard && python test/test_header_layout.py`
Expected: FAIL — `ImportError: cannot import name 'materialize_header_tiles'`.

- [ ] **Step 3: Implement the helper**

Add to `qgis_dashboard/elements/header_layout.py`, after `header_tile_placement` (it uses `resolve_header`, defined later in the file — module-level functions resolve at call time, so define order does not matter):
```python
# config keys that belonged to the docked-banner model and do not survive onto
# a free-placed header tile
_DOCK_ONLY_KEYS = ("anchor", "thickness", "scope_all_pages", "id", "grid",
                   "__type__")


def materialize_header_tiles(pages, global_header, region_w, region_h):
    """Fold legacy headers into each page's tile list (pure migration).

    For every page, the resolved header (per-page over *global_header*) is
    appended to that page's ``elements`` as a ``header`` tile, existing tiles
    are shifted out of the band, and the dock-only config keys are dropped. The
    region grows to include the band; the returned size is the max across pages
    so the single global page size stays uniform.

    Returns ``(new_pages, new_region_w, new_region_h)``. Input is not mutated.
    """
    new_pages = []
    grown_w, grown_h = region_w, region_h
    for page in pages:
        resolved = resolve_header(page.get("header"), global_header)
        new_page = dict(page)
        new_page.pop("header", None)
        elements = [dict(e) for e in page.get("elements", [])]
        if resolved:
            anchor = resolved.get("anchor", "top")
            thickness = int(resolved.get("thickness", 80) or 80)
            rect, (dx, dy), (pw, ph) = header_tile_placement(
                anchor, thickness, region_w, region_h)
            if dx or dy:
                for el in elements:
                    g = el.get("grid")
                    if isinstance(g, dict) and all(
                            k in g for k in ("x", "y", "w", "h")):
                        el["grid"] = {"x": g["x"] + dx, "y": g["y"] + dy,
                                      "w": g["w"], "h": g["h"]}
            hdr = {k: v for k, v in resolved.items()
                   if k not in _DOCK_ONLY_KEYS}
            hdr["__type__"] = "header"
            hdr["grid"] = {"x": rect[0], "y": rect[1],
                           "w": rect[2], "h": rect[3]}
            elements.append(hdr)
            grown_w, grown_h = max(grown_w, pw), max(grown_h, ph)
        new_page["elements"] = elements
        new_pages.append(new_page)
    return new_pages, grown_w, grown_h
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd qgis_dashboard && python test/test_header_layout.py`
Expected: PASS (all four classes).

- [ ] **Step 5: Commit**

```bash
git add qgis_dashboard/elements/header_layout.py qgis_dashboard/test/test_header_layout.py
git commit -m "feat: materialize_header_tiles migrates legacy headers to tiles"
```

---

## Task 3: `HeaderElement` becomes a plain tile + config form trimmed

**Files:**
- Modify: `qgis_dashboard/elements/header.py`
- Modify: `qgis_dashboard/add_element_dialog.py:222-230`

The wrapping `GridTile` now provides the move/resize/menu chrome, so the element drops its own. The config form drops the dock-only rows.

- [ ] **Step 1: Strip the self-owned affordances from `HeaderElement`**

In `qgis_dashboard/elements/header.py`:

Change the imports (lines 22-24) from:
```python
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QPixmap, QImage, QPainter
from qgis.PyQt.QtWidgets import QLabel, QBoxLayout, QMenu
```
to:
```python
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap, QImage, QPainter
from qgis.PyQt.QtWidgets import QLabel, QBoxLayout
```

Remove the two signal class attributes (lines 54-55):
```python
    configureRequested = pyqtSignal(object)   # emits self
    removeRequested = pyqtSignal(object)       # emits self
```

Remove the two event-handler methods at the end of the class (lines 142-153):
```python
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("Configure…").triggered.connect(
            lambda: self.configureRequested.emit(self))
        menu.addSeparator()
        menu.addAction("Remove").triggered.connect(
            lambda: self.removeRequested.emit(self))
        menu.exec(event.globalPos())

    def mouseDoubleClickEvent(self, event):
        self.configureRequested.emit(self)
        super().mouseDoubleClickEvent(event)
```

Also update the module docstring's "It is **not** wrapped in a `GridTile`…" paragraph (lines 10-14) to reflect the new reality:
```python
It **is** wrapped in a :class:`~dashboard_canvas.GridTile` like every other
tile — the canvas hosts it free-form (drag / resize / snap) and the tile
provides the move/resize/menu chrome — so this element only renders its title +
logo. ``anchor``/``thickness`` are no longer used (a tile has free geometry).
```

And update the `config` keys line (lines 16-17) to drop `anchor`/`thickness`:
```python
``config`` keys: ``title``, ``font_family``, ``font_size``, ``align``,
``logo_path``, ``logo_slot``, ``logo_size``.
```

- [ ] **Step 2: Trim the header config form**

In `qgis_dashboard/add_element_dialog.py`, replace the header branch's dock rows. Change lines 222-230 from:
```python
            self._add_dyn("logo_size", "Logo size (px)", self._spin(12, 400, 40))
            anchor = QComboBox()
            anchor.addItem("Top", "top")
            anchor.addItem("Bottom", "bottom")
            anchor.addItem("Left", "left")
            anchor.addItem("Right", "right")
            self._add_dyn("anchor", "Dock edge", anchor)
            self._add_dyn("thickness", "Banner thickness (px)",
                          self._spin(40, 600, 80))
            self._add_dyn("scope_all_pages", "Show on all pages", QCheckBox())
```
to:
```python
            self._add_dyn("logo_size", "Logo size (px)", self._spin(12, 400, 40))
```

- [ ] **Step 3: Verify the files compile**

Run: `cd qgis_dashboard && python -m py_compile elements/header.py add_element_dialog.py`
Expected: no output (success).

> Note: `window.py` still references the removed signals/methods at this point; it is fixed in Task 4. Do not run the plugin between Task 3 and Task 4. (`py_compile` passes because the references are runtime calls, not imports.)

- [ ] **Step 4: Commit**

```bash
git add qgis_dashboard/elements/header.py qgis_dashboard/add_element_dialog.py
git commit -m "refactor: header element drops dock-only chrome and config rows"
```

---

## Task 4: Desktop switchover — window + page view + canvas

**Files:**
- Modify: `qgis_dashboard/page_view.py` (full rewrite — heavily stripped)
- Modify: `qgis_dashboard/dashboard_canvas.py`
- Modify: `qgis_dashboard/window.py`

This is the core change: the header routes through the normal tile path, legacy headers are materialized on load, and the docking machinery is deleted.

- [ ] **Step 1: Rewrite `page_view.py` to drop the header dock**

Replace the entire contents of `qgis_dashboard/page_view.py` with:
```python
# -*- coding: utf-8 -*-
"""PageView — a page surface: a scroll-area-wrapped DashboardCanvas that owns
the page's zoom/pan.

``PageView`` is a thin container around a private :class:`_CanvasScroll` (a
``QScrollArea`` wrapping one :class:`~dashboard_canvas.DashboardCanvas`). The
canvas surface is the export/print region scaled by zoom; the scroll area is
centred so a page smaller than the viewport sits framed and overflows to
scrollbars (or middle-mouse drag) when zoomed in. Zoom is view-only, never
persisted. The header is now an ordinary canvas tile, so this no longer docks a
banner around the canvas.
"""

from qgis.PyQt.QtCore import Qt, QPoint
from qgis.PyQt.QtWidgets import QScrollArea, QWidget, QVBoxLayout

from .zoom_fit import ZOOM_MIN, ZOOM_MAX, clamp_zoom, fit_zoom  # noqa: F401

ZOOM_STEP = 1.2


class _CanvasScroll(QScrollArea):
    """Scroll area wrapping one canvas; manages its zoom level and panning."""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        # Named so the canvas-background QSS rule can target this scroll area
        # (and only this one) — see Theme.window_qss.
        self.setObjectName("dashPageView")
        self.setWidget(canvas)
        # The canvas manages its own size (region/content extent x zoom), so we
        # never let the scroll area stretch it to the viewport.
        self.setWidgetResizable(False)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        # centre the page when it is smaller than the viewport (e.g. just after
        # a fit-to-region Reset Zoom), so the framed region sits centred.
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom = 1.0
        self._pan_origin = None
        self._pan_scroll = None

    def zoom(self):
        return self._zoom

    def set_zoom(self, z):
        self._zoom = clamp_zoom(z)
        self.canvas.set_zoom(self._zoom)
        return self._zoom

    def zoom_in(self):
        return self.set_zoom(self._zoom * ZOOM_STEP)

    def zoom_out(self):
        return self.set_zoom(self._zoom / ZOOM_STEP)

    def reset_zoom(self):
        """Fit the canvas's export/print region to the viewport.

        Reset Zoom frames the whole page (the region) in the viewport, so the
        user always lands on a view of the exact rectangle that will export.
        """
        region = self.canvas.region_size() if hasattr(self.canvas, "region_size") \
            else (self.canvas.width(), self.canvas.height())
        vp = self.viewport()
        z = fit_zoom(region, (vp.width(), vp.height()))
        return self.set_zoom(z)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # the viewport changed — let the canvas refill it (it reads our
        # viewport size) without altering any tile's logical placement
        if hasattr(self.canvas, "sync_size"):
            self.canvas.sync_size()

    # ---- middle-mouse panning ----

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.MiddleButton:
            self._pan_origin = e.pos()
            self._pan_scroll = QPoint(
                self.horizontalScrollBar().value(),
                self.verticalScrollBar().value())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._pan_origin is not None:
            d = e.pos() - self._pan_origin
            self.horizontalScrollBar().setValue(self._pan_scroll.x() - d.x())
            self.verticalScrollBar().setValue(self._pan_scroll.y() - d.y())
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.MiddleButton and self._pan_origin is not None:
            self._pan_origin = None
            self.unsetCursor()
            return
        super().mouseReleaseEvent(e)


class PageView(QWidget):
    """One page: a scrolling canvas with view-only zoom/pan."""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.setObjectName("dashPageWrap")
        # A custom QWidget subclass only paints a stylesheet background when this
        # attribute is set — see #dashPageWrap in Theme.window_qss.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._scroll = _CanvasScroll(canvas, self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._scroll, 1)

    # ---- zoom/pan delegation (preserves the original PageView API) ----

    @property
    def canvas(self):
        return self._scroll.canvas

    def zoom(self):
        return self._scroll.zoom()

    def set_zoom(self, z):
        return self._scroll.set_zoom(z)

    def zoom_in(self):
        return self._scroll.zoom_in()

    def zoom_out(self):
        return self._scroll.zoom_out()

    def reset_zoom(self):
        return self._scroll.reset_zoom()

    # ---- static export (PNG / PDF) ----

    def export_pixmap(self, scale=2.0):
        """Render the page to a high-res pixmap. The header is now a canvas
        tile, so this is exactly the canvas's region render."""
        return self.canvas.export_pixmap(scale)
```

- [ ] **Step 2: Give header tiles a banner-shaped default size**

In `qgis_dashboard/dashboard_canvas.py`, add a constant after `MAP_H = 380` (line 33):
```python
HEADER_BAND_H = 80   # px default height for a new header tile (spans the region width)
```

Then in `add_tile` (lines 649-654), replace:
```python
    def add_tile(self, element, pixel_rect=None):
        if pixel_rect is None:
            if getattr(element, "type_name", "") == "map":
                pixel_rect = self.first_free(MAP_W, MAP_H)
            else:
                pixel_rect = self.first_free(DEFAULT_W, DEFAULT_H)
```
with:
```python
    def add_tile(self, element, pixel_rect=None):
        if pixel_rect is None:
            tname = getattr(element, "type_name", "")
            if tname == "map":
                pixel_rect = self.first_free(MAP_W, MAP_H)
            elif tname == "header":
                # a banner-shaped default: spans the region width, short height
                pixel_rect = self.first_free(self.region_w, HEADER_BAND_H)
            else:
                pixel_rect = self.first_free(DEFAULT_W, DEFAULT_H)
```

- [ ] **Step 3: Route the header through the tile path in `window.py`**

In `qgis_dashboard/window.py`:

(a) Change the import on line 43 from:
```python
from .elements.header_layout import resolve_header
```
to:
```python
from .elements.header_layout import materialize_header_tiles
```

(b) In `_on_element_chosen` (lines 631-643), replace the body with:
```python
    def _on_element_chosen(self, type_name):
        if type_name == "header":
            # the title doubles as the banner text — start blank to configure
            config = {"title": ""}
        else:
            # seed a friendly default title
            config = {"title": ELEMENT_LABELS.get(type_name, type_name.title())}
        self.add_element(type_name, config)
```

(c) In `add_element` (lines 645-653), remove the header special case so it reads:
```python
    def add_element(self, type_name, config, grid_rect=None):
        page = self.current_page()
        if page is None:
            page = self.add_page("Page 1")
        return self._add_element_to(page, type_name, config, grid_rect)
```

(d) Delete `DashboardPage.header_config` — remove lines 128-130:
```python
        # optional per-page header (brand banner) config, or None. A global
        # header (window._global_header) is shown when this is None.
        self.header_config = None
```
so `DashboardPage.__init__` ends at `self.canvas = view.canvas`.

(e) Delete the `_global_header` init in `DashboardWindow.__init__`. Find and remove (around lines 165-167):
```python
        # global header (brand banner) config shown on every page that lacks
        # its own per-page header, or None when there is no global header.
        self._global_header = None
```

(f) Delete the entire header section — `header_for_page`, `_set_header_from_config`, `_refresh_all_headers`, `_configure_header`, `_remove_header` (lines 743-833, the block starting `# ---- header (brand banner) ----` through the end of `_remove_header`). Remove the whole block.

(g) In `_set_canvas_size` (lines 903-905), remove the per-page banner re-fit. Change:
```python
        for page in self._pages:
            page.canvas.set_region(int(w), int(h))
            page.view.sync_header_geometry()   # re-fit each page's banner
```
to:
```python
        for page in self._pages:
            page.canvas.set_region(int(w), int(h))
```

(h) In `clear_all` (line 996), remove `self._global_header = None`.

(i) In `_build_layout_dict` (lines 1018-1026 and 1039-1040), drop the header writes. Change:
```python
            page_data = {
                "id": page.id,
                "title": page.title,
                "connections": self.bus.connections_to_dict(page.id),
                "elements": elements,
            }
            if page.header_config:
                page_data["header"] = page.header_config
            pages.append(page_data)
```
to:
```python
            page_data = {
                "id": page.id,
                "title": page.title,
                "connections": self.bus.connections_to_dict(page.id),
                "elements": elements,
            }
            pages.append(page_data)
```
and remove the trailing:
```python
        if self._global_header:
            data["header"] = self._global_header
```
so `_build_layout_dict` ends with `return data`.

(j) In `_apply_layout_dict` (lines 1078-1108), materialize legacy headers into tiles and drop all header handling. Replace:
```python
        self.clear_all()
        self.bus.set_theme(Theme.from_dict(data.get("theme")))
        self._apply_window_style()
        self._global_header = data.get("header") or None
        grid = data.get("grid", {})
        cols = grid.get("cols", DEFAULT_COLS)
        rows = grid.get("rows", DEFAULT_ROWS)
        gap = int(data.get("gap", DEFAULT_GAP))
        region_w, region_h = self._resolve_canvas_size(data)

        for p in data["pages"]:
            page = self.add_page(p["title"], page_id=p["id"], make_active=False)
            page.header_config = p.get("header") or None
            page.canvas.set_grid(cols, rows)
            page.canvas.set_gap(gap)
            page.canvas.set_region(region_w, region_h)
            self.bus.load_connections(p.get("connections", {}), p["id"])
            for cfg in p.get("elements", []):
                cfg = dict(cfg)
                t = cfg.pop("__type__", None)
                g = cfg.pop("grid", None)
                rect = None
                # placement is a logical pixel rect; only honour it when fully
                # specified, otherwise let the canvas auto-place (first-free)
                if isinstance(g, dict) and all(
                        k in g for k in ("x", "y", "w", "h")):
                    rect = (g["x"], g["y"], g["w"], g["h"])
                if t:
                    self._add_element_to(page, t, cfg, rect)

        self._refresh_all_headers()

        active = data.get("active_page")
```
with:
```python
        self.clear_all()
        self.bus.set_theme(Theme.from_dict(data.get("theme")))
        self._apply_window_style()
        grid = data.get("grid", {})
        cols = grid.get("cols", DEFAULT_COLS)
        rows = grid.get("rows", DEFAULT_ROWS)
        gap = int(data.get("gap", DEFAULT_GAP))
        region_w, region_h = self._resolve_canvas_size(data)
        # legacy docked headers (top-level global + per-page) become header
        # tiles in each page; the region grows uniformly to include the band
        src_pages, region_w, region_h = materialize_header_tiles(
            data["pages"], data.get("header"), region_w, region_h)

        for p in src_pages:
            page = self.add_page(p["title"], page_id=p["id"], make_active=False)
            page.canvas.set_grid(cols, rows)
            page.canvas.set_gap(gap)
            page.canvas.set_region(region_w, region_h)
            self.bus.load_connections(p.get("connections", {}), p["id"])
            for cfg in p.get("elements", []):
                cfg = dict(cfg)
                t = cfg.pop("__type__", None)
                g = cfg.pop("grid", None)
                rect = None
                # placement is a logical pixel rect; only honour it when fully
                # specified, otherwise let the canvas auto-place (first-free)
                if isinstance(g, dict) and all(
                        k in g for k in ("x", "y", "w", "h")):
                    rect = (g["x"], g["y"], g["w"], g["h"])
                if t:
                    self._add_element_to(page, t, cfg, rect)

        active = data.get("active_page")
```

- [ ] **Step 4: Verify everything compiles**

Run:
```bash
cd qgis_dashboard && python -m py_compile window.py page_view.py dashboard_canvas.py
```
Expected: no output (success).

- [ ] **Step 5: Verify no stale header references remain in `window.py`**

Run: `cd qgis_dashboard && grep -nE "header_for_page|_set_header_from_config|_refresh_all_headers|_configure_header|_remove_header|_global_header|header_config|sync_header_geometry|set_header" window.py page_view.py`
Expected: **no matches** (empty output). If any line prints, remove that reference.

- [ ] **Step 6: Verify the pure suites still pass**

Run:
```bash
cd qgis_dashboard && python test/test_header_layout.py && python test/test_zoom_fit.py && python test/test_project_io.py
```
Expected: all PASS (`OK`).

- [ ] **Step 7: Commit**

```bash
git add qgis_dashboard/window.py qgis_dashboard/page_view.py qgis_dashboard/dashboard_canvas.py
git commit -m "feat: header is a canvas tile on the desktop; migrate legacy headers"
```

---

## Task 5: HTML export renders the header as a tile

**Files:**
- Modify: `qgis_dashboard/export/html_export.py`
- Modify: `qgis_dashboard/export/serialize.py`
- Modify: `qgis_dashboard/export/assets/runtime.js`
- Modify: `qgis_dashboard/export/assets/runtime.css`
- Test: `qgis_dashboard/test/test_html_export.py`

- [ ] **Step 1: Embed the header logo and drop the docked-banner build**

In `qgis_dashboard/export/html_export.py`:

(a) In `_build_tile` (lines 110-118), add a header branch. Change:
```python
    if element.type_name == "map":
        out["map_image"] = map_uri
    elif element.type_name == "image":
        out["image_uri"] = image_data_uri(element.config.get("path"))
    elif element.type_name == "indicator":
        out["indicator_value"] = _indicator_baseline(element)
        icon = element.config.get("icon_path")
        if icon:
            out["icon_uri"] = image_data_uri(icon)
    return out
```
to:
```python
    if element.type_name == "map":
        out["map_image"] = map_uri
    elif element.type_name == "image":
        out["image_uri"] = image_data_uri(element.config.get("path"))
    elif element.type_name == "header":
        logo = (element.config.get("logo_path") or "").strip()
        if logo:
            out["logo_uri"] = image_data_uri(logo)
    elif element.type_name == "indicator":
        out["indicator_value"] = _indicator_baseline(element)
        icon = element.config.get("icon_path")
        if icon:
            out["icon_uri"] = image_data_uri(icon)
    return out
```

(b) Delete `_build_header` (lines 122-134) entirely.

(c) In `export_dashboard`, drop the `header` key from the per-page dict. Change (lines 147-153):
```python
        pages.append({
            "id": page.id,
            "title": page.title,
            "connections": window.bus.connections_to_dict(page.id),
            "tiles": tiles,
            "header": _build_header(window, page),
        })
```
to:
```python
        pages.append({
            "id": page.id,
            "title": page.title,
            "connections": window.bus.connections_to_dict(page.id),
            "tiles": tiles,
        })
```

- [ ] **Step 2: Drop the `header` key from the export serializer**

In `qgis_dashboard/export/serialize.py`, update `build_page` (lines 68-82). Replace:
```python
def build_page(page):
    """Normalize one page (id/title/connections + its tiles).

    A resolved ``header`` dict (the docked brand banner, with its logo already
    embedded as ``logo_uri``) is carried through verbatim when present.
    """
    out = {
        "id": page["id"],
        "title": page.get("title") or "Page",
        "connections": page.get("connections") or {},
        "tiles": [build_tile(t) for t in page.get("tiles", [])],
    }
    if page.get("header"):
        out["header"] = page["header"]
    return out
```
with:
```python
def build_page(page):
    """Normalize one page (id/title/connections + its tiles).

    The header is an ordinary tile now, so it flows through ``build_tile`` like
    any element — there is no separate docked-banner key.
    """
    return {
        "id": page["id"],
        "title": page.get("title") or "Page",
        "connections": page.get("connections") or {},
        "tiles": [build_tile(t) for t in page.get("tiles", [])],
    }
```

- [ ] **Step 3: Render the header as a tile in `runtime.js`**

In `qgis_dashboard/export/assets/runtime.js`:

(a) Replace the docked-banner section (lines 671-714: the `bannerDir` + `buildBanner` functions and their header comment) with a tile renderer:
```javascript
  // ---- header (brand banner) tile --------------------------------------
  // Mirrors theme fallbacks so a chosen family degrades gracefully.
  var FONT_FALLBACK = '"Segoe UI", "Helvetica Neue", Arial, sans-serif';

  function renderHeader(body, tile) {
    var cfg = tile.config || {};
    var inner = el("div", "dash-banner-inner");
    var slot = cfg.logo_slot || "left";
    inner.style.flexDirection = (slot === "above" || slot === "below") ? "column" : "row";
    inner.style.height = "100%";
    var logoFirst = (slot === "left" || slot === "above");

    var logo = null;
    if (tile.logo_uri) {
      logo = el("img", "dash-banner-logo");
      logo.src = tile.logo_uri;
      var sz = Number(cfg.logo_size || 40);
      logo.style.width = sz + "px";
      logo.style.height = sz + "px";
    }
    var title = el("div", "dash-banner-title", cfg.title || "");
    if (cfg.font_family) title.style.fontFamily = '"' + cfg.font_family + '", ' + FONT_FALLBACK;
    title.style.fontSize = Number(cfg.font_size || 22) + "px";
    title.style.textAlign = cfg.align || "left";
    title.style.flex = "1 1 auto";

    if (logo && logoFirst) inner.appendChild(logo);
    inner.appendChild(title);
    if (logo && !logoFirst) inner.appendChild(logo);
    body.appendChild(inner);
  }
```

(b) In `renderTile` (lines 646-667), exclude the header from the generic tile title and add its branch. Change:
```javascript
    var showTitle = !FULL_BLEED[tile.type] && tile.type !== "text";
```
to:
```javascript
    var showTitle = !FULL_BLEED[tile.type] && tile.type !== "text" && tile.type !== "header";
```
and add a header branch in the type dispatch — change:
```javascript
    else if (tile.type === "text") renderText(body, tile);
    else if (tile.type === "image") renderImage(body, tile);
```
to:
```javascript
    else if (tile.type === "text") renderText(body, tile);
    else if (tile.type === "header") renderHeader(body, tile);
    else if (tile.type === "image") renderImage(body, tile);
```

(c) Simplify `renderPage` (lines 731-749) to drop the banner wrap. Replace:
```javascript
  function renderPage(page) {
    CHART_HOSTS = [];
    var area = document.getElementById("page-area");
    area.innerHTML = "";
    var wrap = el("div", "dash-pagewrap");
    var hdr = page.header;
    var dir = hdr ? bannerDir(hdr.anchor) : null;
    if (dir) wrap.style.flexDirection = dir.css;
    var scroll = el("div", "dash-scroll");
    scroll.appendChild(buildGrid(page));
    if (hdr && dir.bannerFirst) wrap.appendChild(buildBanner(hdr));
    wrap.appendChild(scroll);
    if (hdr && !dir.bannerFirst) wrap.appendChild(buildBanner(hdr));
    area.appendChild(wrap);
    // charts need their host measured after layout
    requestAnimationFrame(function () {
      CHART_HOSTS.forEach(function (c) { drawChart(c.host, c.tile, c.page); });
    });
  }
```
with:
```javascript
  function renderPage(page) {
    CHART_HOSTS = [];
    var area = document.getElementById("page-area");
    area.innerHTML = "";
    var wrap = el("div", "dash-pagewrap");
    var scroll = el("div", "dash-scroll");
    scroll.appendChild(buildGrid(page));
    wrap.appendChild(scroll);
    area.appendChild(wrap);
    // charts need their host measured after layout
    requestAnimationFrame(function () {
      CHART_HOSTS.forEach(function (c) { drawChart(c.host, c.tile, c.page); });
    });
  }
```

- [ ] **Step 4: Update the export CSS**

In `qgis_dashboard/export/assets/runtime.css`, remove the docked-banner rule (the `.dash-banner { … }` block at lines 61-69) and update the comment, but **keep** `.dash-banner-inner`, `.dash-banner-logo`, and `.dash-banner-title` (the header tile renderer still uses them). Change lines 49-69 from:
```css
/* ---- page area: optional docked header banner around the scrolling grid - */
.dash-page-area { flex: 1 1 auto; position: relative; overflow: hidden; }
.dash-pagewrap { position: absolute; inset: 0; display: flex; flex-direction: column; }
.dash-scroll {
  flex: 1 1 auto;
  overflow: auto;
  background: var(--window-bg);
  padding: 10px;
  min-width: 0;
  min-height: 0;
}

/* docked brand banner (theme-driven surface + soft hairline, like a tile) */
.dash-banner {
  flex: 0 0 auto;
  background: var(--surface-bg);
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  overflow: hidden;
}
.dash-banner-inner {
```
to:
```css
/* ---- page area: a scrolling grid of tiles ------------------------------- */
.dash-page-area { flex: 1 1 auto; position: relative; overflow: hidden; }
.dash-pagewrap { position: absolute; inset: 0; display: flex; flex-direction: column; }
.dash-scroll {
  flex: 1 1 auto;
  overflow: auto;
  background: var(--window-bg);
  padding: 10px;
  min-width: 0;
  min-height: 0;
}

/* header tile content: logo + title (used by the header tile renderer) */
.dash-banner-inner {
```

- [ ] **Step 5: Verify the runtime JS parses and the export tests pass**

Run:
```bash
node --check qgis_dashboard/export/assets/runtime.js
cd qgis_dashboard && python -m py_compile export/html_export.py export/serialize.py && python test/test_html_export.py
```
Expected: `node --check` prints nothing; `py_compile` prints nothing; `test/test_html_export.py` prints `OK`.

> If `test/test_html_export.py` has an assertion that a built page contains a `header` key, delete that assertion (the header is now a tile, exercised via `build_tile`). Re-run and confirm `OK`.

- [ ] **Step 6: Commit**

```bash
git add qgis_dashboard/export/html_export.py qgis_dashboard/export/serialize.py qgis_dashboard/export/assets/runtime.js qgis_dashboard/export/assets/runtime.css qgis_dashboard/test/test_html_export.py
git commit -m "feat: HTML export renders the header as a positioned tile"
```

---

## Task 6: Remove the dead dock helpers

**Files:**
- Modify: `qgis_dashboard/elements/header_layout.py`
- Modify: `qgis_dashboard/test/test_header_layout.py`

`box_direction` and `banner_compose` were only used by the live dock and the export's docked-banner path, both gone. `header_tile_placement` uses `box_direction` internally — inline that fallback so it can be removed.

- [ ] **Step 1: Confirm nothing else imports the dock helpers**

Run: `cd qgis_dashboard && grep -rnE "banner_compose|box_direction" --include=*.py .`
Expected: matches only in `elements/header_layout.py` and `test/test_header_layout.py`. (The JS mirror in `runtime.js` was already removed in Task 5.) If any other `.py` matches, stop and reconcile before continuing.

- [ ] **Step 2: Make `header_tile_placement` self-contained, then remove the dock helpers**

In `qgis_dashboard/elements/header_layout.py`:

(a) Replace `header_tile_placement`'s reliance on `box_direction`. Change its first line from:
```python
    orient, banner_first = box_direction(anchor)
    if orient == "v":                       # top / bottom -> full-width band
```
to:
```python
    # top/bottom -> full-width horizontal band; left/right -> full-height band
    orient, banner_first = _ANCHOR.get(anchor, _ANCHOR["top"])
    if orient == "v":                       # top / bottom -> full-width band
```

(b) Delete `box_direction` (the function at lines 35-40) and `banner_compose` (lines 51-78). Keep `_ANCHOR`, `_SLOT`, `inner_box_direction`, `header_tile_placement`, `_DOCK_ONLY_KEYS`, `materialize_header_tiles`, and `resolve_header`.

(c) Update the module docstring's bullet list (lines 3-14) to drop the removed helpers — replace the bullet describing `box_direction` with one for `header_tile_placement`:
```python
* :func:`inner_box_direction` — how the logo and title stack inside the header
  for a given logo slot.
* :func:`header_tile_placement` — where a legacy docked header lands as a free
  canvas tile (rect, tile shift, grown region).
* :func:`materialize_header_tiles` — fold legacy global/per-page headers into
  each page's tile list.
* :func:`resolve_header` — which header config a page renders (a per-page header
  overrides the global one).
```

- [ ] **Step 3: Remove the obsolete `banner_compose` tests**

In `qgis_dashboard/test/test_header_layout.py`:

(a) Change the import line back to only what remains:
```python
from header_layout import header_tile_placement, materialize_header_tiles
```

(b) Delete the entire `BannerComposeTest` class (lines 26-65 in the original file).

- [ ] **Step 4: Verify**

Run:
```bash
cd qgis_dashboard && python test/test_header_layout.py && python -m py_compile elements/header_layout.py page_view.py window.py
```
Expected: `test/test_header_layout.py` prints `OK` (two classes: `HeaderTilePlacementTest`, `MaterializeHeaderTilesTest`); `py_compile` prints nothing.

- [ ] **Step 5: Commit**

```bash
git add qgis_dashboard/elements/header_layout.py qgis_dashboard/test/test_header_layout.py
git commit -m "refactor: drop dead box_direction/banner_compose dock helpers"
```

---

## Task 7: Full syntax sweep + CLAUDE.md note

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Compile the whole plugin**

Run:
```bash
cd qgis_dashboard && python -m py_compile __init__.py qgis_dashboard.py window.py bus.py \
  theme.py icons.py sidebar.py dashboard_canvas.py page_view.py zoom_fit.py add_element_dialog.py \
  element_picker.py settings_dialog.py appearance_dialog.py connections_dialog.py export_dialog.py \
  project_io.py recent_store.py start_view.py export/*.py elements/*.py
```
Expected: no output (success).

- [ ] **Step 2: Run every pure test suite**

Run:
```bash
cd qgis_dashboard && python test/test_header_layout.py && python test/test_zoom_fit.py \
  && python test/test_project_io.py && python test/test_recent_store.py && python test/test_html_export.py
```
Expected: each prints `OK`.

- [ ] **Step 3: Update the architecture note in `CLAUDE.md`**

The header is described in CLAUDE.md as "**not a grid tile**" / "a brand banner docked to a page edge … *outside* the tile grid" in two places: the bullet-3 PageView paragraph and the elements table's `header` row. Update both to reflect that the header is now an ordinary canvas tile.

In the elements table row for `header`, replace its "Notes" text:
```
A **brand banner docked to a page edge** … It is **not** wrapped in a `GridTile` — `PageView` hosts it on an edge…
```
with:
```
A **brand banner that is now an ordinary canvas tile** (`GridTile`): free drag/resize/snap, region-cropped on export, configured via the inspector like any element. Carries a styled title (`font_family`/`font_size`/`align`) and one logo in an anchored slot (`logo_slot`/`logo_path`/`logo_size`). Legacy docked headers (the old top-level/per-page `header` blob keys, with `anchor`/`thickness`) are migrated into header tiles on load by `header_layout.materialize_header_tiles` (+ `header_tile_placement`).
```

In bullet 3 (the `PageView` paragraph), remove the sentences describing the docked banner (`set_header`, `sync_header_geometry`, banner following the region, `_render_header_pixmap`, `banner_compose`) and replace with a single sentence:
```
`PageView` is a thin container around a `_CanvasScroll` (a `QScrollArea` wrapping one `DashboardCanvas`) that owns the page's zoom/pan; the header is a normal canvas tile, so the page no longer docks a banner. `export_pixmap` is just the canvas region render.
```

Also in bullet 2, remove the description of the header editor opening in the inspector via `_configure_header` and the "Show on all pages" checkbox moving the banner between global/per-page slots — the header now uses the standard tile `Configure…` path. Replace that sentence with:
```
The header is configured through the standard per-tile `Configure…` inspector like any element (no global/per-page scope).
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: header is now a canvas tile in the architecture notes"
```

---

## Self-review checklist (completed during plan authoring)

- **Spec coverage:** HeaderElement strip (T3), canvas/window routing + default size (T4), PageView dock removal (T4), persistence + migration via pure helpers (T1/T2/T4), HTML export rework (T5), header_layout helper changes + tests (T1/T2/T6), CLAUDE.md (T7). All spec sections map to a task.
- **Type consistency:** `header_tile_placement(anchor, thickness, region_w, region_h) -> (rect, (dx,dy), (w,h))` defined in T1 and consumed in T2; `materialize_header_tiles(pages, global_header, region_w, region_h) -> (pages, w, h)` defined in T2 and consumed in T4. `HEADER_BAND_H` defined and used in T4. No name drift.
- **Ordering safety:** dock helpers are removed (T6) only after their last python caller (`page_view.py`, T4) and the JS mirror (T5) are gone. T3 leaves `window.py` referencing removed signals, explicitly flagged as fixed in T4 with a "don't run between T3 and T4" note.
- **No placeholders:** every code step shows full before/after content; every verification step has an exact command and expected output.
