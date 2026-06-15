# -*- coding: utf-8 -*-
"""Map element — a live mirror of the QGIS map canvas.

The dashboard is now its own window, but a user may still want a map tile.
This element embeds a real ``QgsMapCanvas`` that tracks ``iface.mapCanvas()``:
it shows the same displayed layers and follows the main canvas as the user
pans/zooms or toggles layers. It also flashes/zooms to features broadcast on
the bus ``featureAction`` signal (e.g. a row picked in a list element).

It is not a filter target (``accepts_filter = False``) — it reflects what QGIS
displays rather than a per-feature subset.
"""

from qgis.PyQt.QtCore import QTimer
from qgis.gui import QgsMapCanvas, QgsRubberBand
from qgis.core import QgsFeatureRequest, QgsRectangle
from .base import DashboardElement


class MapElement(DashboardElement):
    type_name = "map"
    accepts_filter = False

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        self.canvas = QgsMapCanvas()
        self.body.addWidget(self.canvas)
        self._rubber = None
        self._source = self._qgis_canvas()
        if self._source is not None:
            self._source.extentsChanged.connect(self._sync_extent)
            self._source.layersChanged.connect(self.refresh)
            self._source.destinationCrsChanged.connect(self._sync_crs)
        self.bus.featureAction.connect(self._zoom_to)
        self.apply_theme()
        self.refresh()

    def _qgis_canvas(self):
        iface = getattr(self.bus, "iface", None)
        return iface.mapCanvas() if iface is not None else None

    def teardown(self):
        src = self._source
        if src is None:
            return
        for sig, slot in ((src.extentsChanged, self._sync_extent),
                          (src.layersChanged, self.refresh),
                          (src.destinationCrsChanged, self._sync_crs)):
            try:
                sig.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._source = None

    def _restyle(self):
        self.canvas.setCanvasColor(self.canvas.canvasColor())
        self.canvas.refresh()

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
