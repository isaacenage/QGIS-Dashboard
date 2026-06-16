# -*- coding: utf-8 -*-
"""Map element — a live mirror of the QGIS map canvas.

The dashboard is its own window, but a user may still want a map tile. This
element embeds a real ``QgsMapCanvas`` that tracks ``iface.mapCanvas()``: it
shows the same displayed layers and, in **Build mode**, follows the main canvas
as the user pans/zooms or toggles layers.

The tile behaves differently in the two dashboard modes (driven by the layout
lock via :meth:`set_interactive`):

* **Build mode** (unlocked): a left-drag moves the host tile (the full-bleed map
  has no title strip to grab). The map is inert — it mirrors the QGIS extent and
  pushes no filter.
* **Use mode** (locked): a left-**drag** pans the tile's own map; a left-**click**
  (no drag) **identifies** the bound layer's feature under the cursor in a small
  popup. Panning/zooming pushes a debounced spatial extent filter so connected
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
from qgis.gui import QgsMapCanvas, QgsRubberBand
from qgis.core import QgsFeatureRequest, QgsRectangle, NULL
from .base import DashboardElement
from .map_filter import extent_filter_expression
from .map_identify import search_rect, feature_summary

# a left press/release that moves under this many pixels counts as a click
# (identify) rather than a drag (pan).
CLICK_THRESHOLD = 4
# identify search box half-size, in screen pixels around the click.
IDENTIFY_TOL_PX = 6


class _TileMapCanvas(QgsMapCanvas):
    """Map mirror whose left button is mode-dependent.

    In **Build mode** a left press/drag drives the host
    :class:`~dashboard_canvas.GridTile` move API (the full-bleed map has no title
    strip). In **Use mode** a left drag pans this canvas and a left click (no
    drag) identifies a feature. Other buttons and the wheel always fall through
    to QGIS's normal canvas behavior.
    """

    def __init__(self, tile_getter, on_pan, on_identify, parent=None):
        super().__init__(parent)
        self._tile_getter = tile_getter   # callable -> the host GridTile or None
        self._on_pan = on_pan             # callable(dx_px, dy_px) -> pan canvas
        self._on_identify = on_identify   # callable(local_QPoint) -> identify
        self._mode = None       # "move" (build) | "pan" (use) | None
        self._press = None      # press pos (global) for total-move detection
        self._press_local = None   # press pos (local) for identify
        self._last = None       # last global pos (incremental pan delta)
        self._moved = 0         # cumulative movement (px) since press

    def _locked(self):
        tile = self._tile_getter()
        return tile is not None and tile.is_locked()

    def mousePressEvent(self, e):
        tile = self._tile_getter()
        if e.button() == Qt.MouseButton.LeftButton and tile is not None:
            self._press = e.globalPos()
            self._press_local = e.pos()
            self._last = e.globalPos()
            self._moved = 0
            if self._locked():
                self._mode = "pan"
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            else:
                self._mode = "move"
                tile.begin_move()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._mode is not None:
            delta = e.globalPos() - self._press
            self._moved = max(self._moved, abs(delta.x()) + abs(delta.y()))
            if self._mode == "move":
                tile = self._tile_getter()
                if tile is not None:
                    tile.move_by(delta)
            else:   # pan
                step = e.globalPos() - self._last
                self._last = e.globalPos()
                self._on_pan(step.x(), step.y())
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._mode is not None and e.button() == Qt.MouseButton.LeftButton:
            mode, moved = self._mode, self._moved
            self._mode = None
            if mode == "move":
                tile = self._tile_getter()
                if tile is not None:
                    tile.end_move()
            else:   # pan released; a near-zero move is a click -> identify
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                if moved <= CLICK_THRESHOLD:
                    self._on_identify(self._press_local)
            e.accept()
            return
        super().mouseReleaseEvent(e)


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

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        # map tiles start inert; the hosting tile applies the real mode via
        # set_interactive once it is placed (honouring the layout lock).
        self._interactive = False
        # left-drag behaviour is mode-dependent (see _TileMapCanvas); the
        # GridTile sets `_grid_tile` on this element when it wraps it.
        self.canvas = _TileMapCanvas(
            lambda: getattr(self, "_grid_tile", None),
            self._pan_pixels, self._identify_at)
        self.canvas.setCursor(Qt.CursorShape.SizeAllCursor)
        self.body.addWidget(self.canvas)
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
                          (self.canvas.extentsChanged, self._schedule_filter)):
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
        # cursor hint: open hand to pan in Use mode, move affordance in Build
        self.canvas.setCursor(Qt.CursorShape.OpenHandCursor if on
                              else Qt.CursorShape.SizeAllCursor)
        self._dismiss_identify()
        if on:
            # entering Use mode: become a source (push current extent if wired)
            self._schedule_filter()
            self._last_fly_expr = None
            self._fly_to_filtered()
        else:
            # leaving Use mode: stop being a source and re-mirror the QGIS canvas
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

    # ---- Use-mode pan ----

    def _pan_pixels(self, dx, dy):
        """Shift the tile canvas extent by a screen-pixel drag delta.

        Grab-and-drag pan: the map content follows the cursor, so dragging right
        reveals the area to the west and dragging down reveals the area to the
        north.
        """
        self._dismiss_identify()
        w = self.canvas.width() or 1
        h = self.canvas.height() or 1
        ext = self.canvas.extent()
        mu_x = ext.width() / w
        mu_y = ext.height() / h
        self.canvas.setExtent(QgsRectangle(
            ext.xMinimum() - dx * mu_x, ext.yMinimum() + dy * mu_y,
            ext.xMaximum() - dx * mu_x, ext.yMaximum() + dy * mu_y))
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
