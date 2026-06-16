# -*- coding: utf-8 -*-
"""Dashboard canvas — free-form drag/resize layout (no grid).

Modelled on the Summarizer plugin's canvas: tiles are absolutely-positioned
children of the canvas that remember their placement in **logical pixels**
(``x, y, w, h`` at zoom 1.0) — there are no cells, no ``cols``/``rows``, and no
``QGridLayout``. The canvas applies the page's zoom factor when placing a tile
(``display = logical x zoom``) and grows its own surface to contain every tile
so the surrounding scroll area can pan it.

The user drags a tile by its header strip and resizes via the 8 handles; on
release the rect is snapped to an 8px step, clamped so the origin stays on the
surface, and **reverts if it would overlap** another tile (the one spatial
constraint kept from the old grid). Zoom is owned per-page by :class:`PageView`,
which calls :meth:`DashboardCanvas.set_zoom`.
"""

from qgis.PyQt.QtCore import Qt, QPoint, QPointF, pyqtSignal
from qgis.PyQt.QtGui import QPainter, QColor, QPixmap, QRegion
from qgis.PyQt.QtWidgets import QWidget, QFrame, QVBoxLayout, QToolButton, QMenu

HEADER_H = 20        # px drag strip height
GRIP = 16            # px resize grip square
SNAP = 8             # px snap step applied on drag/resize release
MARGIN = 12          # px breathing room kept around content when growing
MIN_TILE = 120       # px minimum tile width/height (logical)
DEFAULT_W = 320      # px default new-tile size (logical)
DEFAULT_H = 240
MAP_W = 480          # px default size for the (larger) map tile
MAP_H = 380


def _snap(px, step=SNAP):
    step = step or 1
    return int(round(px / float(step))) * step


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
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip("Drag to move")
        self._origin = None

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
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
    "n": Qt.CursorShape.SizeVerCursor, "s": Qt.CursorShape.SizeVerCursor,
    "e": Qt.CursorShape.SizeHorCursor, "w": Qt.CursorShape.SizeHorCursor,
    "nw": Qt.CursorShape.SizeFDiagCursor, "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor, "sw": Qt.CursorShape.SizeBDiagCursor,
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
        if e.button() == Qt.MouseButton.LeftButton:
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
    """A draggable / resizable container wrapping one dashboard element.

    Stores its placement in logical pixels (``x_px, y_px, w_px, h_px``); the
    canvas scales these by the active zoom when placing the widget.
    """

    closeRequested = pyqtSignal(object)        # emits the wrapped element
    styleRequested = pyqtSignal(object)        # emits the wrapped element
    connectionsRequested = pyqtSignal(object)  # emits the wrapped element
    configureRequested = pyqtSignal(object)    # emits the wrapped element
    geometryCommitted = pyqtSignal()           # pixel rect changed (persist)

    def __init__(self, canvas, element, pixel_rect):
        super().__init__(canvas)
        self.canvas = canvas
        self.element = element
        # back-reference so full-bleed elements (e.g. the map) can drive their
        # own move via the tile API — see elements/map_element._TileMapCanvas
        setattr(element, "_grid_tile", self)
        self.x_px, self.y_px, self.w_px, self.h_px = pixel_rect
        self._prev = tuple(pixel_rect)
        self.setObjectName("tileWrap")
        self.setStyleSheet("#tileWrap { background:transparent; }")

        # the element fills the card; chrome is overlaid on top
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(element)
        self._content_lay = lay   # the global "element gap" is applied here

        self.header = _DragHandle(self)   # transparent top strip, drag to move

        self.close_btn = QToolButton(self)
        self.close_btn.setObjectName("tileClose")
        self.close_btn.setText("✕")
        self.close_btn.setAutoRaise(True)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Remove tile")
        self.close_btn.clicked.connect(lambda: self.closeRequested.emit(self.element))

        self.style_btn = QToolButton(self)
        self.style_btn.setObjectName("tileClose")
        self.style_btn.setText("⚙")
        self.style_btn.setAutoRaise(True)
        self.style_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.style_btn.setToolTip("Tile appearance")
        self.style_btn.clicked.connect(lambda: self.styleRequested.emit(self.element))

        self._handles = {edge: _ResizeHandle(self, edge)
                         for edge in ("n", "s", "e", "w",
                                      "nw", "ne", "sw", "se")}
        self._locked = False   # layout lock: when True, no move/resize
        self._active = False   # a move/resize gesture is in progress

    def contextMenuEvent(self, event):
        """Right-click a tile to configure / wire / restyle / remove it."""
        menu = QMenu(self)
        menu.addAction("Configure").triggered.connect(
            lambda: self.configureRequested.emit(self.element))
        menu.addAction("Connections").triggered.connect(
            lambda: self.connectionsRequested.emit(self.element))
        menu.addAction("Tile appearance").triggered.connect(
            lambda: self.styleRequested.emit(self.element))
        menu.addSeparator()
        menu.addAction("Remove tile").triggered.connect(
            lambda: self.closeRequested.emit(self.element))
        menu.exec(event.globalPos())

    def grid_rect(self):
        """The tile's logical pixel placement ``(x, y, w, h)``."""
        return (self.x_px, self.y_px, self.w_px, self.h_px)

    def set_inset(self, px):
        """Inset the element card within the tile footprint by *px* display px.

        This is how the global element-gap setting is rendered: the tile
        footprint is unchanged (drag / resize / overlap still act on it), but
        the card shrinks inside it, leaving transparent breathing room around
        every element so adjacent cards never visually touch. ``px`` is already
        scaled for the current zoom by the canvas (see ``DashboardCanvas``).
        """
        px = max(0, int(px))
        self._content_lay.setContentsMargins(px, px, px, px)

    def set_chrome_visible(self, on):
        """Show/hide the editing chrome (drag strip, buttons, resize handles).

        Hidden while the canvas is grabbed for a PNG/PDF export so the saved
        image shows only the clean tiles, not the editing affordances. When
        restoring, the move/resize affordances only reappear if the layout is
        not locked.
        """
        self.close_btn.setVisible(on)
        self.style_btn.setVisible(on)
        interactive = on and not self._locked
        self.header.setVisible(interactive)
        for h in self._handles.values():
            h.setVisible(interactive)

    def set_locked(self, locked):
        """Lock/unlock this tile's layout: hide the drag strip + resize handles.

        Locking only affects moving/resizing — the tile still renders and its
        element stays interactive (e.g. clicking a chart to cross-filter).
        """
        self._locked = bool(locked)
        interactive = not self._locked
        self.header.setVisible(interactive)
        for h in self._handles.values():
            h.setVisible(interactive)

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
    # ``_active`` gates the whole gesture so every entry point — the drag
    # handle *and* the map tile's own canvas (which calls these directly) —
    # respects the layout lock.

    def begin_move(self):
        if self._locked:
            self._active = False
            return
        self._active = True
        self._prev = self.grid_rect()
        self._start_pos = self.pos()
        self.raise_()
        self.canvas.show_guides(True)

    def move_by(self, delta):
        if not self._active:
            return
        # clamp the live drag so the tile can never leave the canvas surface —
        # it stops at the left/right/top/bottom edge instead of disappearing
        target = self._start_pos + delta
        max_x = max(self.canvas.width() - self.width(), 0)
        max_y = max(self.canvas.height() - self.height(), 0)
        self.move(min(max(target.x(), 0), max_x),
                  min(max(target.y(), 0), max_y))

    def end_move(self):
        if not self._active:
            return
        self._active = False
        z = self.canvas.zoom() or 1.0
        lw, lh = self.w_px, self.h_px
        lcw, lch = self.canvas.logical_size()
        max_lx = max(int(round(lcw - lw)), 0)
        max_ly = max(int(round(lch - lh)), 0)
        lx = min(max(_snap(self.x() / z), 0), max_lx)
        ly = min(max(_snap(self.y() / z), 0), max_ly)
        self._commit_or_revert((lx, ly, lw, lh))

    # ---- resize ----

    def begin_resize(self):
        if self._locked:
            self._active = False
            return
        self._active = True
        self._prev = self.grid_rect()
        self._start_geom = (self.x(), self.y(), self.width(), self.height())
        self.raise_()
        self.canvas.show_guides(True)

    def resize_by(self, edge, dx, dy):
        if not self._active:
            return
        # work in display pixels; floor at the tile minimum scaled by zoom
        z = self.canvas.zoom() or 1.0
        min_disp = max(GRIP, int(round(MIN_TILE * z)))
        x, y, w, h = _proposed_resize(edge, self._start_geom, dx, dy, min_px=min_disp)
        self.setGeometry(x, y, w, h)

    def end_resize(self):
        if not self._active:
            return
        self._active = False
        z = self.canvas.zoom() or 1.0
        lx = max(0, _snap(self.x() / z))
        ly = max(0, _snap(self.y() / z))
        lw = max(MIN_TILE, _snap(self.width() / z))
        lh = max(MIN_TILE, _snap(self.height() / z))
        self._commit_or_revert((lx, ly, lw, lh))

    def _commit_or_revert(self, new_rect):
        self.canvas.show_guides(False)
        if self.canvas.rect_free(new_rect, ignore=self):
            self.x_px, self.y_px, self.w_px, self.h_px = new_rect
            self.canvas.place(self)
            self.canvas.sync_size()
            if new_rect != self._prev:
                self.geometryCommitted.emit()
        else:
            self.canvas.place(self)   # snap back to current pixel rect


class DashboardCanvas(QWidget):
    """Holds GridTiles in a free-form (overlap-free) pixel layout."""

    layoutChanged = pyqtSignal()         # a tile moved/resized/added/removed

    def __init__(self, bus, cols=12, rows=8, parent=None):
        super().__init__(parent)
        self.bus = bus
        # ``cols``/``rows`` are no longer used for layout (tiles are free-form
        # pixels); they are retained only as harmless persisted metadata so the
        # save/restore plumbing and older signatures keep working.
        self.cols = max(int(cols), 1)
        self.rows = max(int(rows), 1)
        self._tiles = []
        self._guides = False
        self._zoom = 1.0
        self._locked = False
        # global element gap (logical px): transparent breathing room inset
        # around every tile's card. 0 == cards may sit edge to edge.
        self.gap = 0
        self.setObjectName("dashCanvas")
        self.setMinimumSize(480, 360)
        if bus is not None:
            bus.themeChanged.connect(self.update)

    # ---- layout lock ----

    def is_locked(self):
        return self._locked

    def set_locked(self, locked):
        """Lock/unlock moving + resizing of every tile on this canvas."""
        self._locked = bool(locked)
        for t in self._tiles:
            t.set_locked(self._locked)

    # ---- zoom ----

    def zoom(self):
        return self._zoom

    def set_zoom(self, z):
        self._zoom = max(0.05, float(z))
        self.reflow()
        self.sync_size()
        self.update()

    # ---- element gap (global spacing) ----

    def set_gap(self, px):
        """Set the global element gap (logical px) and re-apply it live.

        The gap is rendered as a transparent inset around each tile's card, so
        adjacent elements always keep this breathing room no matter how they
        are dragged. Re-placing every tile picks up the new inset.
        """
        self.gap = max(0, int(px))
        self.reflow()
        self.update()

    def _tile_inset(self):
        """The card inset in display pixels (the gap scaled by the zoom)."""
        return int(round(self.gap * (self._zoom or 1.0)))

    # ---- geometry helpers ----

    def tiles(self):
        return list(self._tiles)

    def _viewport_size(self):
        """Visible size to fill — the host scroll area's viewport when present."""
        p = self.parentWidget()
        if p is not None and p.width() > 0 and p.height() > 0:
            return p.width(), p.height()
        return max(self.width(), 800), max(self.height(), 600)

    def _logical_viewport(self):
        z = self._zoom or 1.0
        vw, vh = self._viewport_size()
        return vw / z, vh / z

    def logical_size(self):
        """The canvas surface size in logical (zoom-1.0) pixels.

        Used to clamp tile placement so a tile stays fully on the surface.
        """
        z = self._zoom or 1.0
        return self.width() / z, self.height() / z

    def _content_extent(self):
        """Right/bottom extent of all tiles, in logical pixels."""
        max_r = max_b = 0
        for t in self._tiles:
            x, y, w, h = t.grid_rect()
            max_r = max(max_r, x + w)
            max_b = max(max_b, y + h)
        return max_r, max_b

    def rect_free(self, rect, ignore=None):
        """True if *rect* (logical px) is on-surface and overlaps no other tile."""
        x, y, w, h = rect
        if x < 0 or y < 0:
            return False
        for t in self._tiles:
            if t is ignore:
                continue
            ox, oy, ow, oh = t.grid_rect()
            if x < ox + ow and ox < x + w and y < oy + oh and oy < y + h:
                return False
        return True

    def first_free(self, w, h):
        """Find a non-overlapping origin for a *w*x*h* tile (logical px)."""
        step = 20
        lvw, lvh = self._logical_viewport()
        max_x = max(int(lvw - w), 0)
        max_y = max(int(lvh - h), 0)
        y = 0
        while y <= max_y:
            x = 0
            while x <= max_x:
                if self.rect_free((x, y, w, h)):
                    return (x, y, w, h)
                x += step
            y += step
        # surface is packed: cascade from the origin so the new tile is visible
        n = len(self._tiles)
        off = MARGIN + (n * 28) % 240
        return (off, off, w, h)

    # ---- tile lifecycle ----

    def add_tile(self, element, pixel_rect=None):
        if pixel_rect is None:
            if getattr(element, "type_name", "") == "map":
                pixel_rect = self.first_free(MAP_W, MAP_H)
            else:
                pixel_rect = self.first_free(DEFAULT_W, DEFAULT_H)
        tile = GridTile(self, element, pixel_rect)
        tile.closeRequested.connect(self._on_close)
        tile.geometryCommitted.connect(self.layoutChanged)
        tile.set_locked(self._locked)   # honour the canvas's current lock state
        self._tiles.append(tile)
        tile.show()
        self.place(tile)
        self.sync_size()
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
                self.sync_size()
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
        """Position one tile at ``logical x zoom`` display pixels."""
        z = self._zoom or 1.0
        x, y, w, h = tile.grid_rect()
        tile.setGeometry(int(round(x * z)), int(round(y * z)),
                         max(int(round(w * z)), 1), max(int(round(h * z)), 1))
        tile.set_inset(self._tile_inset())

    def reflow(self):
        for t in self._tiles:
            self.place(t)

    def sync_size(self):
        """Grow the surface so it contains all tiles (and fills the viewport)."""
        z = self._zoom or 1.0
        max_r, max_b = self._content_extent()
        lvw, lvh = self._logical_viewport()
        lw = max(lvw, max_r + MARGIN)
        lh = max(lvh, max_b + MARGIN)
        w = int(round(lw * z))
        h = int(round(lh * z))
        if (self.minimumWidth(), self.minimumHeight()) != (w, h):
            self.setMinimumSize(w, h)
            self.resize(w, h)

    def set_grid(self, cols, rows):
        """Retained for compatibility: store metadata, re-place tiles.

        The grid no longer drives layout — tiles keep their pixel placement —
        so this only refreshes the stored ``cols``/``rows`` and reflows.
        """
        self.cols = max(int(cols), 1)
        self.rows = max(int(rows), 1)
        self.reflow()
        self.sync_size()
        self.update()
        self.layoutChanged.emit()

    def show_guides(self, on):
        self._guides = on
        self.update()

    # ---- export ----

    def export_pixmap(self, scale=2.0):
        """Render the whole content surface to a high-res QPixmap.

        Exports at the logical layout (zoom 1.0) regardless of the current
        view zoom, with the editing chrome hidden, so the result is a clean
        image of the dashboard at *scale*x device resolution (crisp for PNG /
        PDF). The live view's zoom and chrome are restored afterwards.
        """
        old_zoom = self._zoom
        zoom_changed = abs(old_zoom - 1.0) > 1e-6
        self.show_guides(False)
        for t in self._tiles:
            t.set_chrome_visible(False)
        try:
            if zoom_changed:
                self.set_zoom(1.0)   # reflows + grows the surface to content
            else:
                self.sync_size()
            max_r, max_b = self._content_extent()
            w = max(int(round(max_r + MARGIN)), 1)
            h = max(int(round(max_b + MARGIN)), 1)
            scale = max(0.5, float(scale))
            pm = QPixmap(int(round(w * scale)), int(round(h * scale)))
            pm.setDevicePixelRatio(scale)
            theme = self.bus.theme if self.bus is not None else None
            pm.fill(QColor(theme.window_bg) if theme else QColor("#f4f6f8"))
            self.render(pm, QPoint(0, 0), QRegion(0, 0, w, h))
            return pm
        finally:
            for t in self._tiles:
                t.set_chrome_visible(True)
            if zoom_changed:
                self.set_zoom(old_zoom)

    # ---- painting ----

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.reflow()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self.bus.theme if self.bus is not None else None
        # paint the canvas background ourselves (configurable via the theme's
        # "Canvas background" colour) so it never inherits the QGIS palette
        bg = QColor(theme.window_bg) if theme else QColor("#f4f6f8")
        p.fillRect(self.rect(), bg)
        # while a tile is being dragged/resized, hint the 8px snap with a faint
        # dot lattice (coarsely spaced) — otherwise the canvas stays clean
        if self._guides:
            dot = QColor(theme.grid_line) if theme else QColor("#c4ccd4")
            dot.setAlpha(150)
            step = SNAP * 5 * (self._zoom or 1.0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(dot)
            x = 0.0
            while x <= self.width():
                y = 0.0
                while y <= self.height():
                    p.drawEllipse(QPointF(x, y), 1.4, 1.4)
                    y += step
                x += step
        p.end()
