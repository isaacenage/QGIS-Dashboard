# -*- coding: utf-8 -*-
"""Map element — a live mirror of the QGIS map canvas.

The dashboard is now its own window, but a user may still want a map tile.
This element embeds a real ``QgsMapCanvas`` that tracks ``iface.mapCanvas()``:
it shows the same displayed layers and follows the main canvas as the user
pans/zooms or toggles layers. It also flashes/zooms to features broadcast on
the bus ``featureAction`` signal (e.g. a row picked in a list element).

It is not a filter target (``accepts_filter = False``) — it reflects what QGIS
displays rather than a per-feature subset. It *is* a filter **source**
(``is_filter_source = True``): panning/zooming the QGIS canvas pushes a spatial
filter (debounced) onto the bus so every connected tile re-queries to the
features visible in the map frame. Wiring is edited from the tile's
``Connections…`` menu like any other source; an ``extent_filter_enabled`` config
flag (default on) lets the user pause it without unwiring.
"""

from qgis.PyQt.QtCore import QTimer, Qt
from qgis.gui import QgsMapCanvas, QgsRubberBand
from qgis.core import QgsFeatureRequest, QgsRectangle
from .base import DashboardElement
from .map_filter import extent_filter_expression


class _TileMapCanvas(QgsMapCanvas):
    """Map mirror whose **left**-drag moves the host dashboard tile.

    The full-bleed map tile has no title strip to grab, so the whole canvas
    must be draggable. The embedded canvas has no left-button map tool — pan is
    the **middle** button and zoom is the **wheel** — so we safely repurpose the
    left button: a left press/drag drives the :class:`~dashboard_canvas.GridTile`
    move API, while every other button and the wheel fall through to QGIS's
    normal canvas behavior.
    """

    def __init__(self, tile_getter, parent=None):
        super().__init__(parent)
        self._tile_getter = tile_getter   # callable -> the host GridTile or None
        self._drag_origin = None

    def mousePressEvent(self, e):
        tile = self._tile_getter()
        if e.button() == Qt.MouseButton.LeftButton and tile is not None:
            self._drag_origin = e.globalPos()
            tile.begin_move()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_origin is not None:
            tile = self._tile_getter()
            if tile is not None:
                tile.move_by(e.globalPos() - self._drag_origin)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._drag_origin is not None and e.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = None
            tile = self._tile_getter()
            if tile is not None:
                tile.end_move()
            e.accept()
            return
        super().mouseReleaseEvent(e)


class MapElement(DashboardElement):
    type_name = "map"
    accepts_filter = False
    is_filter_source = True   # the visible extent drives connected tiles
    full_bleed = True   # the canvas fills the tile: no title/description, no padding

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        # left-drag anywhere on the canvas moves the tile (see _TileMapCanvas);
        # the GridTile sets `_grid_tile` on this element when it wraps it.
        self.canvas = _TileMapCanvas(lambda: getattr(self, "_grid_tile", None))
        self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
        self.body.addWidget(self.canvas)
        self._rubber = None

        # debounce: a pan/zoom drag emits many extentsChanged; coalesce them
        # into one filter push so connected tiles re-query once on settle.
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(200)
        self._filter_timer.timeout.connect(self._push_extent_filter)

        self._source = self._qgis_canvas()
        if self._source is not None:
            self._source.extentsChanged.connect(self._sync_extent)
            self._source.extentsChanged.connect(self._schedule_filter)
            self._source.layersChanged.connect(self.refresh)
            self._source.destinationCrsChanged.connect(self._sync_crs)
        # re-evaluate when the wiring graph changes (a target was (un)connected)
        self.bus.connectionsChanged.connect(self._schedule_filter)
        self.bus.featureAction.connect(self._zoom_to)
        self.apply_theme()
        self.refresh()

    def _qgis_canvas(self):
        iface = getattr(self.bus, "iface", None)
        return iface.mapCanvas() if iface is not None else None

    def teardown(self):
        self._filter_timer.stop()
        try:
            self.bus.connectionsChanged.disconnect(self._schedule_filter)
        except (TypeError, RuntimeError):
            pass
        src = self._source
        if src is None:
            return
        for sig, slot in ((src.extentsChanged, self._sync_extent),
                          (src.extentsChanged, self._schedule_filter),
                          (src.layersChanged, self.refresh),
                          (src.destinationCrsChanged, self._sync_crs)):
            try:
                sig.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._source = None

    def reconfigure(self):
        # full-bleed: no title chrome to update; just re-apply the extent filter
        # so toggling "filter by extent" takes effect immediately.
        self.apply_theme()
        self.refresh()
        self._push_extent_filter()

    def _restyle(self):
        self.canvas.setCanvasColor(self.canvas.canvasColor())
        self.canvas.refresh()

    # ---- spatial cross-filter source (filter connected tiles by extent) ----

    def _extent_enabled(self):
        return bool(self.config.get("extent_filter_enabled", True))

    def showEvent(self, event):
        # Becoming the active page's map: re-apply the current extent so the
        # filter belongs to this page (pushes are gated on visibility, below).
        super().showEvent(event)
        self._schedule_filter()

    def _schedule_filter(self):
        self._filter_timer.start()

    def _push_extent_filter(self):
        # Only the visible (active-page) map pushes, so its filter never lands
        # in another page's page-local filter state.
        if not self.isVisible():
            return
        if not self._extent_enabled() or self._source is None:
            self.bus.set_filter(self.id, None)
            return
        ext = self._source.extent()
        authid = self._source.mapSettings().destinationCrs().authid()
        expr = extent_filter_expression(
            ext.xMinimum(), ext.yMinimum(), ext.xMaximum(), ext.yMaximum(),
            authid or None)
        self.bus.set_filter(self.id, expr)

    # ---- mirror the main QGIS canvas ----

    def refresh(self):
        src = self._source
        if src is None:
            return
        self.canvas.setLayers(src.layers())
        self._sync_crs()
        self._sync_extent()

    def _sync_crs(self):
        if self._source is not None:
            self.canvas.setDestinationCrs(
                self._source.mapSettings().destinationCrs())
            self.canvas.refresh()

    def _sync_extent(self):
        if self._source is not None:
            self.canvas.setExtent(self._source.extent())
            self.canvas.refresh()

    # ---- feature action (zoom/flash) ----

    def _zoom_to(self, fids):
        lyr = self.layer()
        if lyr is None or not fids:
            return
        req = QgsFeatureRequest().setFilterFids(fids)
        rect = QgsRectangle()
        rect.setMinimal()
        for f in lyr.getFeatures(req):
            geom = f.geometry()
            if not geom.isEmpty():
                rect.combineExtentWith(geom.boundingBox())
        if not rect.isEmpty():
            rect.scale(1.5)
            self.canvas.setExtent(rect)
            self.canvas.refresh()
            self._flash(lyr, fids)

    def _flash(self, lyr, fids):
        if self._rubber:
            self.canvas.scene().removeItem(self._rubber)
        self._rubber = QgsRubberBand(self.canvas, lyr.geometryType())
        self._rubber.setWidth(3)
        req = QgsFeatureRequest().setFilterFids(fids)
        for f in lyr.getFeatures(req):
            self._rubber.addGeometry(f.geometry(), lyr)
        QTimer.singleShot(1200, self._clear_flash)

    def _clear_flash(self):
        if self._rubber:
            self.canvas.scene().removeItem(self._rubber)
            self._rubber = None
