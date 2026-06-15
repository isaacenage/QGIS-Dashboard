# -*- coding: utf-8 -*-
"""Dashboard canvas — free drag/resize layout on a snap grid.

Replaces the old fixed wrapping ``QGridLayout``. Tiles are absolutely
positioned children of the canvas; each remembers its placement in *cell*
units (gx, gy, gw, gh). The pixel size of a cell is ``width/cols`` x
``height/rows``, so resizing the window (or changing the grid in Settings)
rescales every tile while preserving its grid placement.

The user drags a tile by its header strip and resizes via the bottom-right
grip; on release the tile snaps to the nearest cells, is clamped inside the
grid, and reverts if it would overlap another tile. Faint grid guides are
painted so the otherwise-invisible snap grid is discoverable.
"""

from qgis.PyQt.QtCore import Qt, QRect, QPoint, QPointF, pyqtSignal
from qgis.PyQt.QtGui import QPainter, QColor
from qgis.PyQt.QtWidgets import QWidget, QFrame, QVBoxLayout, QToolButton, QMenu

GAP = 4              # px gutter between tiles
HEADER_H = 20        # px drag strip height
GRIP = 16            # px resize grip square


def _snap(px, cell):
    return int(round(px / cell)) if cell else 0


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


class _DragHandle(QWidget):
    """Transparent overlay across the top of a tile; press-drag moves it.

    Sits on top of the element's own title area so the card stays clean — the
    handle is invisible, only the move cursor reveals it.
    """

    def __init__(self, tile):
        super().__init__(tile)
        self._tile = tile
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip("Drag to move")
        self._origin = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._origin = e.globalPos()
            self._tile.begin_move()

    def mouseMoveEvent(self, e):
        if self._origin is not None:
            self._tile.move_by(e.globalPos() - self._origin)

    def mouseReleaseEvent(self, e):
        if self._origin is not None:
            self._origin = None
            self._tile.end_move()


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


class GridTile(QFrame):
    """A draggable / resizable container wrapping one dashboard element."""

    closeRequested = pyqtSignal(object)        # emits the wrapped element
    styleRequested = pyqtSignal(object)        # emits the wrapped element
    connectionsRequested = pyqtSignal(object)  # emits the wrapped element
    geometryCommitted = pyqtSignal()           # grid rect changed (persist)

    def __init__(self, canvas, element, grid_rect):
        super().__init__(canvas)
        self.canvas = canvas
        self.element = element
        # back-reference so full-bleed elements (e.g. the map) can drive their
        # own move via the tile API — see elements/map_element._TileMapCanvas
        setattr(element, "_grid_tile", self)
        self.gx, self.gy, self.gw, self.gh = grid_rect
        self._prev = grid_rect
        self.setObjectName("tileWrap")
        self.setStyleSheet("#tileWrap { background:transparent; }")

        # the element fills the card; chrome is overlaid on top
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(element)

        self.header = _DragHandle(self)   # transparent top strip, drag to move

        self.close_btn = QToolButton(self)
        self.close_btn.setObjectName("tileClose")
        self.close_btn.setText("✕")
        self.close_btn.setAutoRaise(True)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setToolTip("Remove tile")
        self.close_btn.clicked.connect(lambda: self.closeRequested.emit(self.element))

        self.style_btn = QToolButton(self)
        self.style_btn.setObjectName("tileClose")
        self.style_btn.setText("⚙")
        self.style_btn.setAutoRaise(True)
        self.style_btn.setCursor(Qt.PointingHandCursor)
        self.style_btn.setToolTip("Tile appearance")
        self.style_btn.clicked.connect(lambda: self.styleRequested.emit(self.element))

        self._handles = {edge: _ResizeHandle(self, edge)
                         for edge in ("n", "s", "e", "w",
                                      "nw", "ne", "sw", "se")}

    def contextMenuEvent(self, event):
        """Right-click a tile to edit its connections / appearance / removal."""
        menu = QMenu(self)
        menu.addAction("Connections…").triggered.connect(
            lambda: self.connectionsRequested.emit(self.element))
        menu.addAction("Tile appearance…").triggered.connect(
            lambda: self.styleRequested.emit(self.element))
        menu.addSeparator()
        menu.addAction("Remove tile").triggered.connect(
            lambda: self.closeRequested.emit(self.element))
        menu.exec_(event.globalPos())

    def grid_rect(self):
        return (self.gx, self.gy, self.gw, self.gh)

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

    # ---- move ----

    def begin_move(self):
        self._prev = self.grid_rect()
        self._start_pos = self.pos()
        self.raise_()
        self.canvas.show_guides(True)

    def move_by(self, delta):
        self.move(self._start_pos + delta)

    def end_move(self):
        cw, ch = self.canvas.cell_size()
        gx = self.canvas.clamp(_snap(self.x(), cw), self.gw, self.canvas.cols)
        gy = self.canvas.clamp(_snap(self.y(), ch), self.gh, self.canvas.rows)
        self._commit_or_revert((gx, gy, self.gw, self.gh))

    # ---- resize ----

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

    def _commit_or_revert(self, new_rect):
        self.canvas.show_guides(False)
        if self.canvas.rect_free(new_rect, ignore=self):
            self.gx, self.gy, self.gw, self.gh = new_rect
            self.canvas.place(self)
            if new_rect != self._prev:
                self.geometryCommitted.emit()
        else:
            self.canvas.place(self)   # snap back to current grid rect


class DashboardCanvas(QWidget):
    """Holds GridTiles and enforces the snap grid."""

    layoutChanged = pyqtSignal()         # a tile moved/resized/added/removed
    gridSettingsRequested = pyqtSignal()  # user asked to edit the snap grid

    def __init__(self, bus, cols=12, rows=8, parent=None):
        super().__init__(parent)
        self.bus = bus
        self.cols = max(int(cols), 1)
        self.rows = max(int(rows), 1)
        self._tiles = []
        self._guides = False
        self.setObjectName("dashCanvas")
        self.setMinimumSize(480, 360)
        if bus is not None:
            bus.themeChanged.connect(self.update)

    # ---- context menu ----

    def contextMenuEvent(self, event):
        """Right-click the canvas to edit the (global) snap-grid resolution."""
        menu = QMenu(self)
        menu.addAction("Grid settings…").triggered.connect(
            self.gridSettingsRequested.emit)
        menu.exec_(event.globalPos())

    # ---- geometry helpers ----

    def cell_size(self):
        return (self.width() / float(self.cols), self.height() / float(self.rows))

    @staticmethod
    def clamp(value, span, total):
        return max(0, min(value, total - span))

    def tiles(self):
        return list(self._tiles)

    def rect_free(self, rect, ignore=None):
        x, y, w, h = rect
        if x < 0 or y < 0 or x + w > self.cols or y + h > self.rows:
            return False
        for t in self._tiles:
            if t is ignore:
                continue
            ox, oy, ow, oh = t.grid_rect()
            if x < ox + ow and ox < x + w and y < oy + oh and oy < y + h:
                return False
        return True

    def first_free(self, w, h):
        w = min(w, self.cols)
        h = min(h, self.rows)
        for y in range(self.rows):
            for x in range(self.cols):
                if self.rect_free((x, y, w, h)):
                    return (x, y, w, h)
        return (0, 0, w, h)   # last resort: overlap at origin

    # ---- tile lifecycle ----

    def add_tile(self, element, grid_rect=None):
        if grid_rect is None:
            default = (6, 5) if getattr(element, "type_name", "") == "map" else (4, 3)
            grid_rect = self.first_free(*default)
        tile = GridTile(self, element, grid_rect)
        tile.closeRequested.connect(self._on_close)
        tile.geometryCommitted.connect(self.layoutChanged)
        self._tiles.append(tile)
        tile.show()
        self.place(tile)
        self.layoutChanged.emit()
        return tile

    def _on_close(self, element):
        for t in list(self._tiles):
            if t.element is element:
                self._tiles.remove(t)
                element.teardown()
                t.setParent(None)
                t.deleteLater()
                if self.bus is not None:
                    self.bus.forget_element(getattr(element, "id", None))
                self.layoutChanged.emit()
                return

    def clear(self):
        for t in self._tiles:
            t.element.teardown()
            t.setParent(None)
            t.deleteLater()
        self._tiles = []
        self.layoutChanged.emit()

    def place(self, tile):
        cw, ch = self.cell_size()
        x = int(round(tile.gx * cw)) + GAP
        y = int(round(tile.gy * ch)) + GAP
        w = int(round(tile.gw * cw)) - 2 * GAP
        h = int(round(tile.gh * ch)) - 2 * GAP
        tile.setGeometry(x, y, max(w, 1), max(h, 1))

    def reflow(self):
        for t in self._tiles:
            self.place(t)

    def set_grid(self, cols, rows):
        self.cols = max(int(cols), 1)
        self.rows = max(int(rows), 1)
        # clamp any tile that now falls outside the smaller grid
        for t in self._tiles:
            gw = min(t.gw, self.cols)
            gh = min(t.gh, self.rows)
            gx = min(t.gx, self.cols - gw)
            gy = min(t.gy, self.rows - gh)
            t.gx, t.gy, t.gw, t.gh = gx, gy, gw, gh
        self.reflow()
        self.update()
        self.layoutChanged.emit()

    def show_guides(self, on):
        self._guides = on
        self.update()

    # ---- painting ----

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.reflow()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        theme = self.bus.theme if self.bus is not None else None
        # paint the canvas background ourselves (configurable via the theme's
        # "Canvas background" colour) so it never inherits the QGIS palette
        bg = QColor(theme.window_bg) if theme else QColor("#f4f6f8")
        p.fillRect(self.rect(), bg)
        # snap grid as faint dots at every cell intersection (bolder while a
        # tile is being dragged/resized)
        dot = QColor(theme.grid_line) if theme else QColor("#c4ccd4")
        dot.setAlpha(220 if self._guides else 130)
        radius = 2.0 if self._guides else 1.4
        p.setPen(Qt.NoPen)
        p.setBrush(dot)
        cw, ch = self.cell_size()
        for c in range(0, self.cols + 1):
            x = c * cw
            for r in range(0, self.rows + 1):
                p.drawEllipse(QPointF(x, r * ch), radius, radius)
        p.end()
