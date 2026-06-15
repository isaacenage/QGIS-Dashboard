# Multi-page Dashboards + Canvas Zoom/Pan + Tile Resize Handles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multiple switchable dashboard pages (page-local cross-filtering), canvas zoom/pan, and 8-direction tile resize handles to the QGIS Dashboard plugin.

**Architecture:** A `QStackedWidget` of `PageView` (a `QScrollArea` wrapping one `DashboardCanvas`) per page, driven by a `QTabBar`. `DashboardBus` keeps theme/iface global but moves cross-filter state to per-page dicts exposed through properties. Persistence bumps to schema v3 (a `pages` list), still loading v1/v2.

**Tech Stack:** Python 3, `qgis.PyQt` (PyQt5), QGIS Python API, `unittest` (run under the QGIS-bootstrapped test harness in `test/`).

**Spec:** `docs/superpowers/specs/2026-06-15-multi-page-canvas-ux-design.md`

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `qgis_dashboard/bus.py` | Global theme/iface + **per-page** filter & connection state | Modify |
| `qgis_dashboard/dashboard_canvas.py` | Snap-grid canvas; `GridTile` with **8 resize handles**; pure `_proposed_resize` helper | Modify |
| `qgis_dashboard/page_view.py` | `PageView` — scroll-area wrapper owning **zoom/pan** for one canvas; pure `clamp_zoom` helper | Create |
| `qgis_dashboard/window.py` | Page **stack + tab bar**, zoom toolbar, persistence **v3** + `migrate_layout` pure helper | Modify |
| `qgis_dashboard/test/test_multipage.py` | All new tests (resize math, bus page-locality, zoom clamp, layout migration) | Create |
| `qgis_dashboard/pb_tool.cfg`, `qgis_dashboard/Makefile` | Register the new `page_view.py` module so it ships | Modify |

### Test runner

All test commands assume the plugin dir is on `PYTHONPATH` and a QGIS Python env is active (the harness bootstraps QGIS via `test/utilities.py`). From the repo root, in Git Bash:

```bash
cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py -v
```

If `pytest` is unavailable in the QGIS env, substitute `python -m unittest test.test_multipage -v` (same directory/PYTHONPATH).

---

## Task 1: 8-direction tile resize handles

Replace the single bottom-right grip with corner + edge handles. Extract a pure geometry helper so the math is unit-tested without mouse events.

**Files:**
- Modify: `qgis_dashboard/dashboard_canvas.py`
- Create: `qgis_dashboard/test/test_multipage.py`

- [ ] **Step 1: Write the failing test**

Create `qgis_dashboard/test/test_multipage.py`:

```python
# coding=utf-8
"""Tests for multi-page, zoom/pan, and resize-handle features."""

import unittest

from utilities import get_qgis_app

from dashboard_canvas import _proposed_resize

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()


class ResizeMathTest(unittest.TestCase):
    START = (100, 100, 200, 150)   # x, y, w, h

    def test_south_east_grows_size_only(self):
        self.assertEqual(_proposed_resize("se", self.START, 30, 40),
                         (100, 100, 230, 190))

    def test_east_changes_width_only(self):
        self.assertEqual(_proposed_resize("e", self.START, 30, 999),
                         (100, 100, 230, 150))

    def test_north_moves_top_and_changes_height(self):
        # dragging the north edge up by 40 (dy=-40) moves y up, grows height
        self.assertEqual(_proposed_resize("n", self.START, 0, -40),
                         (100, 60, 200, 190))

    def test_west_moves_left_and_changes_width(self):
        self.assertEqual(_proposed_resize("w", self.START, -30, 0),
                         (70, 100, 230, 150))

    def test_north_west_moves_both_origins(self):
        self.assertEqual(_proposed_resize("nw", self.START, -30, -40),
                         (70, 60, 230, 190))

    def test_min_size_clamps_and_pins_origin(self):
        # shrinking width past the floor from the west edge must not push x past
        # the original right edge
        x, y, w, h = _proposed_resize("w", self.START, 500, 0, min_px=40)
        self.assertEqual(w, 40)
        self.assertEqual(x, 260)   # original right edge (100+200) - 40


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py -v`
Expected: FAIL — `ImportError: cannot import name '_proposed_resize'`.

- [ ] **Step 3: Add the pure helper**

In `qgis_dashboard/dashboard_canvas.py`, add after the `_snap` function (around line 27):

```python
def _proposed_resize(edge, start_geom, dx, dy, min_px=40):
    """Return the new (x, y, w, h) for a tile dragged by ``(dx, dy)``.

    ``edge`` is a compass tag (n/s/e/w and the diagonals ne/nw/se/sw). Edges
    containing 'w'/'n' move the tile's origin; 'e'/'s' only grow size. Width
    and height are floored at ``min_px`` without letting a moving origin cross
    the opposite, fixed edge.
    """
    x, y, w, h = start_geom
    if "w" in edge:
        new_w = max(w - dx, min_px)
        x = x + (w - new_w)
        w = new_w
    if "e" in edge:
        w = max(w + dx, min_px)
    if "n" in edge:
        new_h = max(h - dy, min_px)
        y = y + (h - new_h)
        h = new_h
    if "s" in edge:
        h = max(h + dy, min_px)
    return (x, y, w, h)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py -v`
Expected: PASS (6 tests in `ResizeMathTest`).

- [ ] **Step 5: Replace the single grip with eight handles**

In `qgis_dashboard/dashboard_canvas.py`, replace the entire `_ResizeGrip` class (lines 58-88) with:

```python
EDGE_CURSORS = {
    "n": Qt.SizeVerCursor, "s": Qt.SizeVerCursor,
    "e": Qt.SizeHorCursor, "w": Qt.SizeHorCursor,
    "nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor,
    "ne": Qt.SizeBDiagCursor, "sw": Qt.SizeBDiagCursor,
}


class _ResizeHandle(QWidget):
    """A grab point on one side/corner of a tile; press-drag resizes it."""

    def __init__(self, tile, edge):
        super().__init__(tile)
        self._tile = tile
        self.edge = edge
        self.setCursor(EDGE_CURSORS[edge])
        self._origin = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._origin = e.globalPos()
            self._tile.begin_resize()

    def mouseMoveEvent(self, e):
        if self._origin is not None:
            d = e.globalPos() - self._origin
            self._tile.resize_by(self.edge, d.x(), d.y())

    def mouseReleaseEvent(self, e):
        if self._origin is not None:
            self._origin = None
            self._tile.end_resize()

    def paintEvent(self, _e):
        if self.edge != "se":
            return
        p = QPainter(self)
        p.setPen(QColor("#b6bfc8"))
        for off in (3, 7, 11):
            p.drawLine(self.width() - off, self.height() - 2,
                       self.width() - 2, self.height() - off)
        p.end()
```

- [ ] **Step 6: Build the handles and lay them out in `GridTile`**

In `GridTile.__init__`, replace `self.grip = _ResizeGrip(self)` (line 131) with:

```python
        self._handles = {edge: _ResizeHandle(self, edge)
                         for edge in ("n", "s", "e", "w",
                                      "nw", "ne", "sw", "se")}
```

In `GridTile.resizeEvent`, replace the grip line `self.grip.move(...)` and `self.grip.raise_()` (lines 142, 144) with handle placement. Replace the whole method body's handle/raise section so it reads:

```python
    def resizeEvent(self, e):
        super().resizeEvent(e)
        # drag strip spans the top, leaving room for the two corner buttons
        self.header.setGeometry(6, 2, max(self.width() - 52, 1), HEADER_H)
        self.close_btn.move(self.width() - 24, 3)
        self.style_btn.move(self.width() - 46, 3)
        self._place_handles()
        self.header.raise_()
        for h in self._handles.values():
            h.raise_()
        self.style_btn.raise_()
        self.close_btn.raise_()

    def _place_handles(self):
        w, h, t = self.width(), self.height(), GRIP
        mid_x, mid_y = (w - t) // 2, (h - t) // 2
        geom = {
            "nw": (0, 0), "n": (mid_x, 0), "ne": (w - t, 0),
            "w": (0, mid_y), "e": (w - t, mid_y),
            "sw": (0, h - t), "s": (mid_x, h - t), "se": (w - t, h - t),
        }
        for edge, (hx, hy) in geom.items():
            self._handles[edge].setGeometry(hx, hy, t, t)
```

- [ ] **Step 7: Generalize move/resize to full geometry in `GridTile`**

Replace `begin_resize`, `resize_by`, `end_resize` (lines 167-184) with:

```python
    def begin_resize(self):
        self._prev = self.grid_rect()
        self._start_geom = (self.x(), self.y(), self.width(), self.height())
        self.raise_()
        self.canvas.show_guides(True)

    def resize_by(self, edge, dx, dy):
        x, y, w, h = _proposed_resize(edge, self._start_geom, dx, dy)
        self.setGeometry(x, y, w, h)

    def end_resize(self):
        cw, ch = self.canvas.cell_size()
        gx = max(_snap(self.x(), cw), 0)
        gy = max(_snap(self.y(), ch), 0)
        gw = max(_snap(self.width(), cw), 1)
        gh = max(_snap(self.height(), ch), 1)
        gw = min(gw, self.canvas.cols - gx)
        gh = min(gh, self.canvas.rows - gy)
        self._commit_or_revert((gx, gy, gw, gh))
```

- [ ] **Step 8: Run the full suite to confirm no regressions**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py test/test_dashboard.py -v`
Expected: PASS (all resize-math tests + all existing dashboard tests).

- [ ] **Step 9: Commit**

```bash
git add qgis_dashboard/dashboard_canvas.py qgis_dashboard/test/test_multipage.py
git commit -m "feat: 8-direction tile resize handles"
```

---

## Task 2: Bus page-local cross-filter state

Move `_source_filters`/`_connections` to per-page dicts behind properties; add page lifecycle methods. A default page keeps all existing single-page usage working unchanged.

**Files:**
- Modify: `qgis_dashboard/bus.py`
- Modify: `qgis_dashboard/test/test_multipage.py`

- [ ] **Step 1: Write the failing test**

Append to `qgis_dashboard/test/test_multipage.py` (before the `if __name__` block):

```python
from bus import DashboardBus


class BusPageLocalTest(unittest.TestCase):
    def test_filter_is_isolated_per_page(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        bus.set_targets("src", ["tgt"])
        bus.set_filter("src", '"a" = 1')
        self.assertEqual(bus.combined_filter_for("tgt"), '("a" = 1)')

        bus.set_active_page("B")
        # page B has neither the connection nor the filter
        self.assertIsNone(bus.combined_filter_for("tgt"))

        bus.set_active_page("A")
        self.assertEqual(bus.combined_filter_for("tgt"), '("a" = 1)')

    def test_connections_round_trip_per_page(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        bus.set_targets("s1", ["t1", "t2"])
        data = bus.connections_to_dict("A")

        other = DashboardBus()
        other.set_active_page("A")
        other.load_connections(data, "A")
        self.assertEqual(other.targets_of("s1"), {"t1", "t2"})

    def test_forget_page_drops_state(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        bus.set_targets("src", ["tgt"])
        bus.set_filter("src", '"a" = 1')
        bus.forget_page("A")
        bus.set_active_page("A")   # recreated empty
        self.assertIsNone(bus.combined_filter_for("tgt"))

    def test_clear_all_filters_uses_in_place_clear(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        bus.set_targets("src", ["tgt"])
        bus.set_filter("src", '"a" = 1')
        bus.clear_all_filters()
        self.assertIsNone(bus.combined_filter_for("tgt"))
        self.assertEqual(bus.active_filter_count(), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py::BusPageLocalTest -v`
Expected: FAIL — `AttributeError: 'DashboardBus' object has no attribute 'set_active_page'`.

- [ ] **Step 3: Refactor the bus constructor and add properties**

In `qgis_dashboard/bus.py`, replace the `__init__` body's state lines (lines 47-48):

```python
        self._source_filters = {}   # source_id -> expression string
        self._connections = {}      # source_id -> set(target_id)
```

with:

```python
        self._active_page = "default"
        self._page_filters = {"default": {}}      # page_id -> {source_id: expr}
        self._page_connections = {"default": {}}  # page_id -> {source_id: set}
```

Then add these properties immediately after `__init__` (before the `# ---- theme ----` section):

```python
    # ---- page-local state (active page) ----

    @property
    def _source_filters(self):
        return self._page_filters.setdefault(self._active_page, {})

    @property
    def _connections(self):
        return self._page_connections.setdefault(self._active_page, {})

    def set_active_page(self, page_id):
        self._active_page = page_id or "default"
        self._page_filters.setdefault(self._active_page, {})
        self._page_connections.setdefault(self._active_page, {})
        self.connectionsChanged.emit()
        self.filtersChanged.emit()

    def forget_page(self, page_id):
        self._page_filters.pop(page_id, None)
        self._page_connections.pop(page_id, None)
```

- [ ] **Step 4: Update the methods that reassigned the dicts**

In `clear_all_filters` (lines 82-87), replace `self._source_filters = {}` with the in-place clear:

```python
    def clear_all_filters(self):
        had = bool(self._source_filters)
        self._source_filters.clear()
        self.filtersCleared.emit()
        if had:
            self.filtersChanged.emit()
```

Replace `connections_to_dict` and `load_connections` (lines 114-123) with page-aware versions:

```python
    def connections_to_dict(self, page_id=None):
        conns = (self._page_connections.get(page_id, {})
                 if page_id is not None else self._connections)
        return {src: sorted(tgts) for src, tgts in conns.items() if tgts}

    def load_connections(self, data, page_id=None):
        target = page_id if page_id is not None else self._active_page
        conns = {}
        if isinstance(data, dict):
            for src, tgts in data.items():
                if tgts:
                    conns[src] = set(tgts)
        self._page_connections[target] = conns
        self.connectionsChanged.emit()
```

(`set_filter`, `set_targets`, `forget_element` already mutate in place via the property — no change needed.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py test/test_dashboard.py -v`
Expected: PASS — new `BusPageLocalTest` passes **and** all 7 existing `DashboardBusTest` cases still pass (they use the implicit `"default"` page).

- [ ] **Step 6: Commit**

```bash
git add qgis_dashboard/bus.py qgis_dashboard/test/test_multipage.py
git commit -m "feat: page-local filter and connection state on the bus"
```

---

## Task 3: PageView — zoom/pan scroll wrapper

A `QScrollArea` that owns a `DashboardCanvas` and a zoom factor. At 100% the canvas fills the viewport (today's behavior); above 100% the canvas is enlarged and scroll/pan engage. Middle-mouse drag pans.

**Files:**
- Create: `qgis_dashboard/page_view.py`
- Modify: `qgis_dashboard/test/test_multipage.py`
- Modify: `qgis_dashboard/window.py` (use `PageView` as the central widget)

- [ ] **Step 1: Write the failing test**

Append to `qgis_dashboard/test/test_multipage.py`:

```python
from page_view import clamp_zoom, PageView


class ZoomTest(unittest.TestCase):
    def test_clamp_zoom_bounds(self):
        self.assertEqual(clamp_zoom(0.1), 0.5)
        self.assertEqual(clamp_zoom(9.0), 3.0)
        self.assertAlmostEqual(clamp_zoom(1.25), 1.25)

    def test_pageview_default_zoom_is_one(self):
        from dashboard_canvas import DashboardCanvas
        view = PageView(DashboardCanvas(None, 12, 8))
        self.assertAlmostEqual(view.zoom(), 1.0)

    def test_pageview_set_zoom_clamps(self):
        from dashboard_canvas import DashboardCanvas
        view = PageView(DashboardCanvas(None, 12, 8))
        view.set_zoom(10.0)
        self.assertEqual(view.zoom(), 3.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py::ZoomTest -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'page_view'`.

- [ ] **Step 3: Create `page_view.py`**

Create `qgis_dashboard/page_view.py`:

```python
# -*- coding: utf-8 -*-
"""PageView — a scroll-area wrapper that adds zoom/pan to one DashboardCanvas.

Scale-on-fill: at zoom 1.0 the canvas fills the viewport (the original
responsive behavior). Above 1.0 the canvas is given a fixed size of
``viewport x zoom`` so it overflows the viewport and the scroll bars (plus
middle-mouse drag) let the user pan. Zoom is view-only and never persisted.
"""

from qgis.PyQt.QtCore import Qt, QPoint
from qgis.PyQt.QtWidgets import QScrollArea

ZOOM_MIN = 0.5
ZOOM_MAX = 3.0
ZOOM_STEP = 1.2


def clamp_zoom(z):
    return max(ZOOM_MIN, min(float(z), ZOOM_MAX))


class PageView(QScrollArea):
    """Holds one canvas; manages its zoom level and panning."""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setWidget(canvas)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self._zoom = 1.0
        self._pan_origin = None
        self._pan_scroll = None

    def zoom(self):
        return self._zoom

    def set_zoom(self, z):
        self._zoom = clamp_zoom(z)
        self._apply_zoom()
        return self._zoom

    def zoom_in(self):
        return self.set_zoom(self._zoom * ZOOM_STEP)

    def zoom_out(self):
        return self.set_zoom(self._zoom / ZOOM_STEP)

    def reset_zoom(self):
        return self.set_zoom(1.0)

    def _apply_zoom(self):
        vp = self.viewport().size()
        if abs(self._zoom - 1.0) < 1e-3:
            self.setWidgetResizable(True)
            self.canvas.setMinimumSize(0, 0)
            self.canvas.setMaximumSize(16777215, 16777215)
        else:
            self.setWidgetResizable(False)
            w = int(vp.width() * self._zoom)
            h = int(vp.height() * self._zoom)
            self.canvas.setMinimumSize(w, h)
            self.canvas.resize(w, h)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if abs(self._zoom - 1.0) >= 1e-3:
            self._apply_zoom()

    # ---- middle-mouse panning ----

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self._pan_origin = e.pos()
            self._pan_scroll = QPoint(
                self.horizontalScrollBar().value(),
                self.verticalScrollBar().value())
            self.setCursor(Qt.ClosedHandCursor)
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
        if e.button() == Qt.MiddleButton and self._pan_origin is not None:
            self._pan_origin = None
            self.unsetCursor()
            return
        super().mouseReleaseEvent(e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py::ZoomTest -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Use `PageView` as the window's central widget + zoom toolbar**

In `qgis_dashboard/window.py`, add the import near the other local imports (after line 23 `from .dashboard_canvas import DashboardCanvas`):

```python
from .page_view import PageView
```

Replace the central-widget wiring in `__init__` (lines 48-49):

```python
        self.canvas = DashboardCanvas(self.bus, DEFAULT_COLS, DEFAULT_ROWS, self)
        self.setCentralWidget(self.canvas)
```

with:

```python
        self.canvas = DashboardCanvas(self.bus, DEFAULT_COLS, DEFAULT_ROWS)
        self.page_view = PageView(self.canvas, self)
        self.setCentralWidget(self.page_view)
```

In `_build_toolbar`, add zoom actions after the `("Clear filter", ...)` loop (after line 75, before the spacer):

```python
        tb.addSeparator()
        tb.addAction("Zoom −").triggered.connect(lambda: self.page_view.zoom_out())
        tb.addAction("100%").triggered.connect(lambda: self.page_view.reset_zoom())
        tb.addAction("Zoom +").triggered.connect(lambda: self.page_view.zoom_in())
```

- [ ] **Step 6: Run the full suite (import-safety regression check)**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py test/test_dashboard.py -v`
Expected: PASS (all tests; `window.py` still imports cleanly).

- [ ] **Step 7: Register the new module so it ships**

In `qgis_dashboard/pb_tool.cfg`, add `page_view.py` to the `python_files` list. In `qgis_dashboard/Makefile`, add `page_view.py` to `PY_FILES`. (Match the existing formatting of each list exactly — one entry alongside `bus.py`/`window.py`.)

- [ ] **Step 8: Commit**

```bash
git add qgis_dashboard/page_view.py qgis_dashboard/window.py \
        qgis_dashboard/pb_tool.cfg qgis_dashboard/Makefile \
        qgis_dashboard/test/test_multipage.py
git commit -m "feat: canvas zoom/pan via PageView scroll wrapper"
```

---

## Task 4: Persistence v3 + v1/v2 migration

Extract a pure `migrate_layout` that normalizes any stored blob (v1 list, v2 dict, v3 dict) into the canonical v3 shape. This lets the multi-page save/load in Task 5 stay simple and keeps migration unit-tested.

**Files:**
- Modify: `qgis_dashboard/window.py`
- Modify: `qgis_dashboard/test/test_multipage.py`

- [ ] **Step 1: Write the failing test**

Append to `qgis_dashboard/test/test_multipage.py`:

```python
from window import migrate_layout, DEFAULT_COLS, DEFAULT_ROWS


class MigrateLayoutTest(unittest.TestCase):
    def test_v1_bare_list_becomes_one_page(self):
        data = migrate_layout([{"__type__": "indicator", "id": "a"}])
        self.assertEqual(data["version"], 3)
        self.assertEqual(len(data["pages"]), 1)
        self.assertEqual(data["pages"][0]["title"], "Page 1")
        self.assertEqual(data["pages"][0]["elements"][0]["id"], "a")
        self.assertEqual(data["grid"], {"cols": DEFAULT_COLS,
                                        "rows": DEFAULT_ROWS})

    def test_v2_wraps_elements_and_connections(self):
        v2 = {
            "version": 2,
            "grid": {"cols": 10, "rows": 6},
            "theme": {"accent": "#123456"},
            "connections": {"s": ["t"]},
            "elements": [{"__type__": "serial_chart", "id": "s"}],
        }
        data = migrate_layout(v2)
        self.assertEqual(data["version"], 3)
        self.assertEqual(data["grid"], {"cols": 10, "rows": 6})
        self.assertEqual(data["theme"], {"accent": "#123456"})
        self.assertEqual(len(data["pages"]), 1)
        self.assertEqual(data["pages"][0]["connections"], {"s": ["t"]})
        self.assertEqual(data["pages"][0]["elements"][0]["id"], "s")

    def test_v3_passes_through(self):
        v3 = {
            "version": 3,
            "grid": {"cols": 12, "rows": 8},
            "theme": {},
            "active_page": "p2",
            "pages": [
                {"id": "p1", "title": "One", "connections": {},
                 "elements": []},
                {"id": "p2", "title": "Two", "connections": {"a": ["b"]},
                 "elements": [{"__type__": "list", "id": "a"}]},
            ],
        }
        data = migrate_layout(v3)
        self.assertEqual(data["active_page"], "p2")
        self.assertEqual(len(data["pages"]), 2)
        self.assertEqual(data["pages"][1]["connections"], {"a": ["b"]})

    def test_empty_input_yields_one_empty_page(self):
        data = migrate_layout(None)
        self.assertEqual(len(data["pages"]), 1)
        self.assertEqual(data["pages"][0]["elements"], [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py::MigrateLayoutTest -v`
Expected: FAIL — `ImportError: cannot import name 'migrate_layout'`.

- [ ] **Step 3: Add `migrate_layout` to `window.py`**

In `qgis_dashboard/window.py`, add this module-level function after the constants block (after line 33 `DEFAULT_ROWS = 8`):

```python
def migrate_layout(raw):
    """Normalize any stored layout (v1 list / v2 dict / v3 dict) to v3.

    v3 shape::

        {version, grid:{cols,rows}, theme, window, active_page,
         pages:[{id, title, connections, elements:[...]}]}
    """
    if not raw:
        raw = {"elements": []}
    # v1: a bare list of element configs
    if isinstance(raw, list):
        raw = {"elements": raw}

    version = raw.get("version", 2)
    grid = raw.get("grid", {})
    out = {
        "version": 3,
        "grid": {"cols": grid.get("cols", DEFAULT_COLS),
                 "rows": grid.get("rows", DEFAULT_ROWS)},
        "theme": raw.get("theme") or {},
        "window": raw.get("window", {}),
    }

    if version >= 3 and isinstance(raw.get("pages"), list):
        pages = []
        for p in raw["pages"]:
            pages.append({
                "id": p.get("id") or uuid.uuid4().hex[:8],
                "title": p.get("title") or "Page",
                "connections": p.get("connections") or {},
                "elements": p.get("elements") or [],
            })
        if not pages:
            pages = [{"id": uuid.uuid4().hex[:8], "title": "Page 1",
                      "connections": {}, "elements": []}]
        out["pages"] = pages
        out["active_page"] = raw.get("active_page") or pages[0]["id"]
    else:
        # v1/v2: collapse into a single page
        page = {
            "id": uuid.uuid4().hex[:8],
            "title": "Page 1",
            "connections": raw.get("connections") or {},
            "elements": raw.get("elements") or [],
        }
        out["pages"] = [page]
        out["active_page"] = page["id"]
    return out
```

Add the `uuid` import at the top of `window.py` (after `import json`, line 13):

```python
import uuid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py::MigrateLayoutTest -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add qgis_dashboard/window.py qgis_dashboard/test/test_multipage.py
git commit -m "feat: layout schema v3 migration helper"
```

---

## Task 5: Multi-page stack + tab bar (wire it all together)

Replace the single central `PageView` with a tab bar + `QStackedWidget` of `PageView`s, one per page. Route add-element / connections / clear-filter / zoom to the current page, and rewrite save/load to use `migrate_layout` and per-page bus state.

**Files:**
- Modify: `qgis_dashboard/window.py`
- Modify: `qgis_dashboard/test/test_multipage.py`

- [ ] **Step 1: Write the failing test**

Append to `qgis_dashboard/test/test_multipage.py`:

```python
from window import DashboardWindow


class MultiPageWindowTest(unittest.TestCase):
    def _win(self):
        return DashboardWindow(IFACE)

    def test_starts_with_one_page(self):
        win = self._win()
        self.assertEqual(len(win.pages()), 1)
        self.assertIs(win.current_canvas(), win.pages()[0].canvas)

    def test_add_page_creates_and_activates(self):
        win = self._win()
        page = win.add_page("Second")
        self.assertEqual(len(win.pages()), 2)
        self.assertEqual(page.title, "Second")
        self.assertIs(win.current_canvas(), page.canvas)
        self.assertEqual(win.bus._active_page, page.id)

    def test_add_element_lands_on_current_page(self):
        win = self._win()
        win.add_page("Second")
        win.add_element("indicator", {"title": "X"})
        self.assertEqual(len(win.current_canvas().tiles()), 1)
        self.assertEqual(len(win.pages()[0].canvas.tiles()), 0)

    def test_delete_page_keeps_at_least_one(self):
        win = self._win()
        first = win.pages()[0]
        win.add_page("Second")
        win.delete_page(first.id)
        self.assertEqual(len(win.pages()), 1)
        # cannot delete the final page
        last = win.pages()[0]
        win.delete_page(last.id)
        self.assertEqual(len(win.pages()), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py::MultiPageWindowTest -v`
Expected: FAIL — `AttributeError: 'DashboardWindow' object has no attribute 'pages'`.

- [ ] **Step 3: Add page data structures and imports**

In `qgis_dashboard/window.py`, extend the Qt import (lines 15-17) to add `QTabBar`, `QStackedWidget`, `QVBoxLayout`, `QMessageBox`, `QInputDialog`:

```python
from qgis.PyQt.QtWidgets import (
    QMainWindow, QToolBar, QLabel, QWidget, QSizePolicy,
    QTabBar, QStackedWidget, QVBoxLayout, QMessageBox, QInputDialog,
)
```

Add a tiny page record class after the `migrate_layout` function:

```python
class DashboardPage:
    """One dashboard page: an id/title plus its PageView (and its canvas)."""

    def __init__(self, page_id, title, view):
        self.id = page_id
        self.title = title
        self.view = view
        self.canvas = view.canvas
```

- [ ] **Step 4: Replace the central widget with the tab bar + stack**

In `DashboardWindow.__init__`, replace the central-widget block from Task 3:

```python
        self.canvas = DashboardCanvas(self.bus, DEFAULT_COLS, DEFAULT_ROWS)
        self.page_view = PageView(self.canvas, self)
        self.setCentralWidget(self.page_view)
```

with the stack scaffolding:

```python
        self._pages = []
        self._tab_bar = QTabBar()
        self._tab_bar.setMovable(True)
        self._tab_bar.setExpanding(False)
        self._stack = QStackedWidget()

        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._tab_bar)
        col.addWidget(self._stack, 1)
        self.setCentralWidget(container)

        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabBarDoubleClicked.connect(self._rename_page_at)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)

        self.add_page("Page 1")
```

> Note: `self.page_view`/`self.canvas` are no longer single attributes. Anything that referenced them now goes through `current_canvas()` / `current_view()` (handled in the steps below).

- [ ] **Step 5: Add page management methods**

Add these methods to `DashboardWindow` (place them after `_update_filter_label`):

```python
    # ---- pages ----

    def pages(self):
        return list(self._pages)

    def current_page(self):
        idx = self._tab_bar.currentIndex()
        return self._pages[idx] if 0 <= idx < len(self._pages) else None

    def current_canvas(self):
        page = self.current_page()
        return page.canvas if page else None

    def current_view(self):
        page = self.current_page()
        return page.view if page else None

    def add_page(self, title, page_id=None, make_active=True):
        page_id = page_id or uuid.uuid4().hex[:8]
        canvas = DashboardCanvas(self.bus, self.canvas_cols(), self.canvas_rows())
        canvas.layoutChanged.connect(self._on_layout_changed)
        view = PageView(canvas)
        page = DashboardPage(page_id, title, view)
        self._pages.append(page)
        self._stack.addWidget(view)
        self._tab_bar.addTab(title)
        if make_active:
            self._tab_bar.setCurrentIndex(len(self._pages) - 1)
        return page

    def delete_page(self, page_id):
        if len(self._pages) <= 1:
            return
        idx = next((i for i, p in enumerate(self._pages)
                    if p.id == page_id), -1)
        if idx < 0:
            return
        page = self._pages[idx]
        if page.canvas.tiles():
            ok = QMessageBox.question(
                self, "Delete page",
                'Delete "{}" and its {} tile(s)?'.format(
                    page.title, len(page.canvas.tiles())))
            if ok != QMessageBox.Yes:
                return
        page.canvas.clear()
        self.bus.forget_page(page.id)
        self._pages.pop(idx)
        self._stack.removeWidget(page.view)
        page.view.deleteLater()
        self._tab_bar.removeTab(idx)

    def _on_tab_changed(self, idx):
        if 0 <= idx < len(self._pages):
            page = self._pages[idx]
            self._stack.setCurrentWidget(page.view)
            self.bus.set_active_page(page.id)

    def _on_tab_moved(self, frm, to):
        self._pages.insert(to, self._pages.pop(frm))
        view = self._stack.widget(frm)
        self._stack.removeWidget(view)
        self._stack.insertWidget(to, view)

    def _rename_page_at(self, idx):
        if not (0 <= idx < len(self._pages)):
            return
        page = self._pages[idx]
        text, ok = QInputDialog.getText(self, "Rename page",
                                        "Title:", text=page.title)
        if ok and text.strip():
            page.title = text.strip()
            self._tab_bar.setTabText(idx, page.title)

    def canvas_cols(self):
        return self._pages[0].canvas.cols if self._pages else DEFAULT_COLS

    def canvas_rows(self):
        return self._pages[0].canvas.rows if self._pages else DEFAULT_ROWS

    def _on_layout_changed(self):
        pass
```

- [ ] **Step 6: Route existing actions through the current page**

In `_build_toolbar`, add an "Add page" action and a context menu for delete. After the existing action loop (after line 75), and adjust the zoom lambdas from Task 3 to use `current_view()`:

```python
        tb.addAction("Add page").triggered.connect(self._add_page_interactive)
        tb.addSeparator()
        tb.addAction("Zoom −").triggered.connect(
            lambda: self.current_view() and self.current_view().zoom_out())
        tb.addAction("100%").triggered.connect(
            lambda: self.current_view() and self.current_view().reset_zoom())
        tb.addAction("Zoom +").triggered.connect(
            lambda: self.current_view() and self.current_view().zoom_in())
```

Add the right-click delete wiring at the end of `__init__` (after `self.add_page("Page 1")`):

```python
        self._tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tab_bar.customContextMenuRequested.connect(self._tab_context_menu)
```

Add these helpers to the class:

```python
    def _add_page_interactive(self):
        self.add_page("Page {}".format(len(self._pages) + 1))

    def _tab_context_menu(self, pos):
        from qgis.PyQt.QtWidgets import QMenu
        idx = self._tab_bar.tabAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        menu.addAction("Rename").triggered.connect(
            lambda: self._rename_page_at(idx))
        menu.addAction("Delete").triggered.connect(
            lambda: self.delete_page(self._pages[idx].id))
        menu.exec_(self._tab_bar.mapToGlobal(pos))
```

Replace `elements`, `add_element`, and grid/connection routing. Update `elements` (lines 94-95) and `add_element` (lines 103-107):

```python
    def elements(self):
        page = self.current_page()
        return [t.element for t in page.canvas.tiles()] if page else []

    def add_element(self, type_name, config, grid_rect=None):
        canvas = self.current_canvas()
        element = create_element(type_name, self.bus, config, canvas)
        tile = canvas.add_tile(element, grid_rect)
        tile.styleRequested.connect(self._edit_tile_style)
        return tile
```

Update `open_grid_settings` (lines 136-140) to apply the new grid to **every** page's canvas:

```python
    def open_grid_settings(self):
        cur = self.current_canvas()
        dlg = GridSettingsDialog(cur.cols, cur.rows, self)
        if dlg.exec_():
            cols, rows = dlg.result_grid()
            for page in self._pages:
                page.canvas.set_grid(cols, rows)
```

(`open_connections` already calls `self.elements()`, which is now page-scoped — no change. `clear_all` is rewritten in Step 7.)

- [ ] **Step 7: Rewrite persistence for pages (v3)**

Replace `clear_all` (lines 150-153):

```python
    def clear_all(self):
        for page in self._pages:
            page.canvas.clear()
            self._stack.removeWidget(page.view)
            page.view.deleteLater()
        self._pages = []
        while self._tab_bar.count():
            self._tab_bar.removeTab(0)
        self.bus.clear_all_filters()
```

Replace `save_to_project` (lines 157-173):

```python
    def save_to_project(self):
        pages = []
        for page in self._pages:
            elements = []
            for tile in page.canvas.tiles():
                d = tile.element.to_dict()
                gx, gy, gw, gh = tile.grid_rect()
                d["grid"] = {"x": gx, "y": gy, "w": gw, "h": gh}
                elements.append(d)
            pages.append({
                "id": page.id,
                "title": page.title,
                "connections": self.bus.connections_to_dict(page.id),
                "elements": elements,
            })
        cur = self.current_page()
        data = {
            "version": 3,
            "grid": {"cols": self.canvas_cols(), "rows": self.canvas_rows()},
            "theme": self.bus.theme.to_dict(),
            "window": {"w": self.width(), "h": self.height()},
            "active_page": cur.id if cur else None,
            "pages": pages,
        }
        QgsProject.instance().writeEntry(
            PROJECT_SCOPE, PROJECT_KEY, json.dumps(data))
```

Replace `load_from_project` (lines 175-212):

```python
    def load_from_project(self):
        raw, ok = QgsProject.instance().readEntry(
            PROJECT_SCOPE, PROJECT_KEY, "")
        self.clear_all()
        if not ok or not raw:
            self.bus.set_theme(Theme.default())
            self.add_page("Page 1")
            self._apply_grid_to_all(DEFAULT_COLS, DEFAULT_ROWS)
            return
        try:
            data = migrate_layout(json.loads(raw))
        except (ValueError, TypeError):
            self.add_page("Page 1")
            return

        self.bus.set_theme(Theme.from_dict(data.get("theme")))
        self._apply_window_style()
        grid = data.get("grid", {})
        cols = grid.get("cols", DEFAULT_COLS)
        rows = grid.get("rows", DEFAULT_ROWS)

        for p in data["pages"]:
            page = self.add_page(p["title"], page_id=p["id"], make_active=False)
            page.canvas.set_grid(cols, rows)
            self.bus.load_connections(p.get("connections", {}), p["id"])
            for cfg in p.get("elements", []):
                cfg = dict(cfg)
                t = cfg.pop("__type__", None)
                g = cfg.pop("grid", None)
                rect = None
                if isinstance(g, dict):
                    rect = (g.get("x", 0), g.get("y", 0),
                            g.get("w", 4), g.get("h", 3))
                if t:
                    self._add_element_to(page, t, cfg, rect)

        active = data.get("active_page")
        idx = next((i for i, pg in enumerate(self._pages)
                    if pg.id == active), 0)
        self._tab_bar.setCurrentIndex(idx)

        win = data.get("window", {})
        if win.get("w") and win.get("h"):
            self.resize(int(win["w"]), int(win["h"]))
```

Add the two helpers used above:

```python
    def _apply_grid_to_all(self, cols, rows):
        for page in self._pages:
            page.canvas.set_grid(cols, rows)

    def _add_element_to(self, page, type_name, config, grid_rect=None):
        element = create_element(type_name, self.bus, config, page.canvas)
        tile = page.canvas.add_tile(element, grid_rect)
        tile.styleRequested.connect(self._edit_tile_style)
        return tile
```

- [ ] **Step 8: Run the full suite**

Run: `cd qgis_dashboard && PYTHONPATH="$(pwd)" python -m pytest test/test_multipage.py test/test_dashboard.py -v`
Expected: PASS — `MultiPageWindowTest` (4 tests) plus everything from Tasks 1-4 and the original `test_dashboard.py`.

- [ ] **Step 9: Commit**

```bash
git add qgis_dashboard/window.py qgis_dashboard/test/test_multipage.py
git commit -m "feat: multi-page dashboards with per-page tabs and persistence v3"
```

---

## Task 6: Manual smoke test in QGIS + docs

- [ ] **Step 1: Syntax-check the whole plugin**

Run (from repo root, Git Bash):

```bash
cd qgis_dashboard && python -m py_compile __init__.py qgis_dashboard.py window.py \
  bus.py theme.py dashboard_canvas.py page_view.py add_element_dialog.py \
  settings_dialog.py appearance_dialog.py connections_dialog.py elements/*.py
```

Expected: no output (clean compile).

- [ ] **Step 2: Manual test in QGIS**

Copy/symlink `qgis_dashboard/` into the QGIS plugins dir, enable the plugin, then verify:
- Add a page, rename it (double-click tab), reorder tabs by dragging, delete a page (last page cannot be deleted).
- Tiles added land on the current page only; a chart on page 1 does **not** filter a tile on page 2.
- Zoom +/− and 100% work; above 100% the canvas scrolls and middle-mouse drag pans.
- Drag each of the 8 resize handles; release snaps to grid and reverts on overlap.
- Save the `.qgz`, reopen it: pages, titles, tiles, and per-page connections are restored; active page is preserved.
- Open an **old** project saved before this change (v2): it loads as a single "Page 1" with its tiles and connections intact.

- [ ] **Step 3: Update CLAUDE.md architecture notes**

In `CLAUDE.md`, update the window/canvas description to mention: pages (`DashboardPage`, tab bar, `QStackedWidget` of `PageView`), page-local bus state, `PageView` zoom/pan, 8-handle resize, and persistence **v3** (still reading v1/v2). Add `page_view.py` to the "read these files together" list.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document multi-page, zoom/pan, resize handles in CLAUDE.md"
```

---

## Self-Review Notes

- **Spec coverage:** page stack (Task 5), page-local bus incl. theme-global (Task 2), persistence v3 + v1/v2 migration (Tasks 4-5), tab UX rename/delete/reorder/add (Task 5), zoom/pan scale-on-fill + controls (Task 3), 8-handle resize reusing snap/collision (Task 1), tests for every layer (Tasks 1-5), `page_view.py` registered in pb_tool.cfg/Makefile (Task 3). All spec sections map to a task.
- **Type/name consistency:** `migrate_layout`, `DashboardPage(id,title,view,canvas)`, `PageView.zoom()/set_zoom()/zoom_in()/zoom_out()/reset_zoom()`, bus `set_active_page/forget_page/connections_to_dict(page_id)/load_connections(data,page_id)`, canvas `_proposed_resize`, window `pages()/current_page()/current_canvas()/current_view()/add_page()/delete_page()` — used consistently across tasks.
- **Deviation from spec (intentional):** zoom lives on `PageView` (the scroll wrapper), not on `DashboardCanvas`, keeping the canvas almost untouched and the zoom logic self-contained. Behavior (scale-on-fill, scroll/pan, not persisted) matches the spec exactly.
```
