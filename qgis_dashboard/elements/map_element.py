# -*- coding: utf-8 -*-
"""Map element — a live mirror of the QGIS map canvas.

The dashboard is its own window, but a user may still want a map tile. This
element embeds a real ``QgsMapCanvas`` that tracks ``iface.mapCanvas()``: it
shows the same displayed layers and, in **Build mode**, follows the main canvas
as the user pans/zooms or toggles layers.

The tile behaves differently in the two dashboard modes (driven by the layout
lock via :meth:`set_interactive`):

* **Build mode** (unlocked): the hosting :class:`~dashboard_canvas.GridTile` owns
  the mouse through its full-tile drag overlay (like every other tile), so a
  left-drag anywhere on the map moves the tile and a right-click opens the tile
  menu. The map itself is inert — it mirrors the QGIS extent and pushes no filter.
* **Use mode** (locked): a left-**drag** pans the map (a ``QgsMapToolPan``) and a
  left-**click** (no drag) **identifies** the bound layer's feature under the
  cursor in a small popup. Panning/zooming pushes a debounced spatial extent
  filter so connected
  tiles re-query to the visible frame (it is a filter **source**), and the map
  **flies** to the features matching its connected sources' filter (it is a
  fly-to **target**) — single feature → that feature's bounds, many → their union.
  Clearing the filter returns the map to mirroring the QGIS canvas.

Wiring (both as a source and as a fly-to target) is edited from the tile's
``Connections…`` menu like any other element; an ``extent_filter_enabled`` config
flag (default on) lets the user pause the extent push without unwiring.
"""

from html import escape

from qgis.PyQt.QtCore import QTimer, Qt
from qgis.PyQt.QtWidgets import QFrame, QVBoxLayout, QLabel
from qgis.gui import QgsMapCanvas, QgsMapToolPan, QgsRubberBand
from qgis.core import QgsFeatureRequest, QgsRectangle, NULL
from .base import DashboardElement
from .map_filter import extent_filter_expression
from .map_identify import search_rect, feature_summary

# a left press/release that moves under this many pixels counts as a click
# (identify) rather than a drag (pan).
CLICK_THRESHOLD = 4
# identify search box half-size, in screen pixels around the click.
IDENTIFY_TOL_PX = 6


class _PanIdentifyTool(QgsMapToolPan):
    """Use-mode map tool: a left-drag pans, a left-click (no drag) identifies.

    Panning is handled by :class:`QgsMapToolPan` (the canonical left-drag pan, so
    the user no longer needs the middle mouse button); we only add the
    click-to-identify on top. A press that moves less than ``CLICK_THRESHOLD`` px
    before release counts as a click rather than a pan.

    Build-mode moving is **not** handled here — the hosting ``GridTile``'s
    full-tile drag overlay owns the mouse in Build mode, and this tool is only
    installed while the tile is in Use mode (see ``MapElement.set_interactive``).
    """

    def __init__(self, canvas, on_identify):
        super().__init__(canvas)
        self._on_identify = on_identify   # callable(local_QPoint) -> identify
        self._press = None      # press pos (canvas px) for click/drag detection
        self._moved = 0         # cumulative movement (px) since press

    def canvasPressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.pos()
            self._moved = 0
        super().canvasPressEvent(e)

    def canvasMoveEvent(self, e):
        if self._press is not None:
            self._moved = max(self._moved,
                              (e.pos() - self._press).manhattanLength())
        super().canvasMoveEvent(e)

    def canvasReleaseEvent(self, e):
        super().canvasReleaseEvent(e)   # let QgsMapToolPan finish the pan
        click = (e.button() == Qt.MouseButton.LeftButton
                 and self._press is not None and self._moved <= CLICK_THRESHOLD)
        self._press = None
        if click:
            self._on_identify(e.pos())


class IdentifyPopup(QFrame):
    """A small themed popup of ``field: value`` rows shown near an identify click."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("identifyPopup")
        self.setVisible(False)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(10, 8, 10, 8)
        self._lay.setSpacing(2)

    def show_rows(self, point, rows, theme):
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if not rows:
            self.setVisible(False)
            return
        # soft hairline border + theme surface; never a heavy/dark outline
        self.setStyleSheet(
            "#identifyPopup{{background:{bg};border:1px solid {border};"
            "border-radius:6px;}}"
            "QLabel{{color:{text};background:transparent;"
            "font-family:{font};font-size:{size}px;}}".format(
                bg=theme.surface_bg, border=theme.border, text=theme.text,
                font=theme.font_stack(), size=theme.font_size))
        for name, val in rows:
            lab = QLabel("<b>{}</b>&nbsp;&nbsp;{}".format(
                escape(str(name)), escape(str(val))))
            lab.setTextFormat(Qt.TextFormat.RichText)
            self._lay.addWidget(lab)
        self.adjustSize()
        par = self.parentWidget()
        x, y = point.x() + 12, point.y() + 12
        if par is not None:
            x = min(x, max(par.width() - self.width(), 0))
            y = min(y, max(par.height() - self.height(), 0))
        self.move(max(x, 0), max(y, 0))
        self.setVisible(True)
        self.raise_()


class MapElement(DashboardElement):
    type_name = "map"
    accepts_filter = False    # never subsets its *displayed* layers
    is_filter_source = True   # the visible extent drives connected tiles
    full_bleed = True   # the canvas fills the tile: no title/description, no padding
    # handles_own_body_drag stays False (inherited): in Build mode the tile's
    # full-tile drag overlay moves the map and routes its right-click menu, just
    # like every other tile. Use-mode pan/identify run through _PanIdentifyTool.

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        # map tiles start inert; the hosting tile applies the real mode via
        # set_interactive once it is placed (honouring the layout lock).
        self._interactive = False
        self.canvas = QgsMapCanvas()
        self.body.addWidget(self.canvas)
        # Use-mode interaction tool: left-drag pans, left-click identifies. It is
        # installed only while the tile is in Use mode (set_interactive); in Build
        # mode the GridTile's drag overlay owns the mouse, so the map has no tool.
        self._tool = _PanIdentifyTool(self.canvas, self._identify_at)
        self._rubber = None
        self._identify_popup = None
        # the last combined-source filter we flew to, so the map's own extent
        # pushes (which don't change it) never trigger a re-fly / feedback loop.
        self._last_fly_expr = None

        # debounce: a pan/zoom drag emits many extentsChanged; coalesce them
        # into one filter push so connected tiles re-query once on settle.
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(200)
        self._filter_timer.timeout.connect(self._push_extent_filter)

        self._source = self._qgis_canvas()
        if self._source is not None:
            self._source.extentsChanged.connect(self._sync_extent)
            self._source.layersChanged.connect(self.refresh)
            self._source.destinationCrsChanged.connect(self._sync_crs)
        # the tile's own extent (driven by Use-mode pan/zoom/fly) is what we push
        self.canvas.extentsChanged.connect(self._schedule_filter)
        # any pan/zoom/fly moves the view out from under a popped identify result
        self.canvas.extentsChanged.connect(self._dismiss_identify)
        # re-evaluate when the wiring graph changes (a target was (un)connected)
        self.bus.connectionsChanged.connect(self._schedule_filter)
        self.bus.featureAction.connect(self._zoom_to)
        # fly-to target: react to any connected source's filter changing
        self.bus.filtersChanged.connect(self._fly_to_filtered)
        self.apply_theme()
        self.refresh()

    def _qgis_canvas(self):
        iface = getattr(self.bus, "iface", None)
        return iface.mapCanvas() if iface is not None else None

    def teardown(self):
        self._filter_timer.stop()
        for sig, slot in ((self.bus.connectionsChanged, self._schedule_filter),
                          (self.bus.filtersChanged, self._fly_to_filtered),
                          (self.canvas.extentsChanged, self._schedule_filter),
                          (self.canvas.extentsChanged, self._dismiss_identify)):
            try:
                sig.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
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

    def reconfigure(self):
        # full-bleed: no title chrome to update; just re-apply the extent filter
        # so toggling "filter by extent" takes effect immediately.
        self.apply_theme()
        self.refresh()
        self._push_extent_filter()

    def _restyle(self):
        self.canvas.setCanvasColor(self.canvas.canvasColor())
        self.canvas.refresh()

    # ---- interaction mode (Use vs Build) ----

    def set_interactive(self, on):
        super().set_interactive(on)
        self._dismiss_identify()
        if on:
            # entering Use mode: install the pan/identify tool (left-drag pans,
            # left-click identifies) and become a source (push extent if wired)
            self.canvas.setMapTool(self._tool)
            self._schedule_filter()
            self._last_fly_expr = None
            self._fly_to_filtered()
        else:
            # leaving Use mode: drop the tool (the tile overlay takes the mouse),
            # stop being a source and re-mirror the QGIS canvas
            self.canvas.unsetMapTool(self._tool)
            self.bus.set_filter(self.id, None)
            self._last_fly_expr = None
            self._sync_extent(force=True)

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
        # Only the visible (active-page) map in Use mode pushes, so its filter
        # never lands in another page's page-local filter state and a Build-mode
        # map never filters anything.
        if not self._interactive or not self.isVisible():
            return
        if not self._extent_enabled():
            self.bus.set_filter(self.id, None)
            return
        ext = self.canvas.extent()
        authid = self.canvas.mapSettings().destinationCrs().authid()
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

    def _sync_extent(self, force=False):
        # Mirror the QGIS extent only in Build mode; in Use mode the tile is
        # independently navigable, so a live pan must not be overwritten by an
        # iface extentsChanged. `force` re-mirrors on the way back to Build mode.
        if self._source is None:
            return
        if self._interactive and not force:
            return
        self.canvas.setExtent(self._source.extent())
        self.canvas.refresh()

    # ---- Use-mode identify ----

    def _identify_at(self, local_point):
        lyr = self.layer()
        if lyr is None:
            self._dismiss_identify()
            return
        transform = self.canvas.getCoordinateTransform()
        if transform is None:
            return
        map_pt = transform.toMapCoordinates(local_point.x(), local_point.y())
        tol = transform.mapUnitsPerPixel() * IDENTIFY_TOL_PX
        xmin, ymin, xmax, ymax = search_rect(map_pt.x(), map_pt.y(), tol)
        req = QgsFeatureRequest().setFilterRect(QgsRectangle(xmin, ymin, xmax, ymax))
        feat = next(iter(lyr.getFeatures(req)), None)
        if feat is None:
            self._dismiss_identify()
            return
        names = [f.name() for f in lyr.fields()]
        # convert QGIS NULLs to None so the pure summary renders them as blanks
        values = [None if v == NULL else v for v in feat.attributes()]
        rows = feature_summary(names, values, limit=12)
        if self._identify_popup is None:
            self._identify_popup = IdentifyPopup(self.canvas)
        self._identify_popup.show_rows(local_point, rows, self.effective_theme())

    def _dismiss_identify(self):
        if self._identify_popup is not None:
            self._identify_popup.setVisible(False)

    # ---- fly-to target (zoom to connected sources' filtered features) ----

    def _fly_to_filtered(self):
        if not self._interactive:
            return
        expr = self.bus.combined_filter_for(self.id)
        # the map's own extent pushes don't change this expression, so guarding
        # on it prevents a pan -> push -> fly feedback loop.
        if expr == self._last_fly_expr:
            return
        self._last_fly_expr = expr
        if expr is None:
            # filters cleared: return to mirroring the QGIS canvas extent
            self._sync_extent(force=True)
            return
        lyr = self.layer()
        if lyr is None:
            return
        req = QgsFeatureRequest().setFilterExpression(expr)
        rect = QgsRectangle()
        rect.setMinimal()
        fids = []
        for f in lyr.getFeatures(req):
            geom = f.geometry()
            if not geom.isEmpty():
                rect.combineExtentWith(geom.boundingBox())
                fids.append(f.id())
        if not rect.isEmpty():
            rect.scale(1.5)
            self.canvas.setExtent(rect)
            self.canvas.refresh()
            self._flash(lyr, fids)

    # ---- feature action (zoom/flash on a list-row pick) ----

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
