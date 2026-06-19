# -*- coding: utf-8 -*-
"""Base element.

ArcGIS Dashboards elements share an anatomy: a title area, a visualization
area, and a description area, plus a data source (a layer) and an optional
filter. This base class encodes that so indicator / chart / list elements only
implement their visualization.

Identity & wiring:
  - every element carries a stable ``id`` (persisted in ``config``) so the
    user-defined connection graph on the bus can route filters source->target.
  - a target's live filter is ``bus.combined_filter_for(self.id)`` AND-ed with
    the element-local ``base_filter``.

Appearance:
  - the effective theme is the global ``bus.theme`` merged with this element's
    optional per-tile override (``config["style"]``); ``apply_theme`` restyles
    the tile and lets subclasses repaint custom views.
"""

import uuid

from qgis.PyQt.QtGui import QPainterPath, QRegion
from qgis.PyQt.QtWidgets import QFrame, QVBoxLayout, QLabel
from qgis.core import (
    QgsProject,
    QgsFeatureRequest,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
)


class DashboardElement(QFrame):
    """A single dashboard tile. Subclass and implement refresh()."""

    type_name = "element"
    is_filter_source = False   # pushes filters onto the bus
    accepts_filter = True      # re-queries when a connected source filters
    full_bleed = False         # when True the visualization fills the tile
                               # edge-to-edge: no title/description chrome and
                               # no internal padding (e.g. the live map mirror)
    handles_own_body_drag = False   # when True the element drives its own
                               # body drag in Build mode (e.g. the map), so the
                               # tile keeps a thin top drag strip instead of the
                               # full-tile drag overlay every other tile gets

    def __init__(self, bus, config=None, parent=None):
        super().__init__(parent)
        self.bus = bus
        self.config = config or {}
        self.id = self.config.get("id") or uuid.uuid4().hex[:8]
        self.config["id"] = self.id
        # content-interaction mode (Use vs Build): True == Use mode, contents
        # react to the user (cross-filter clicks, map pan/identify); False ==
        # Build mode, contents inert so tiles can be moved/resized/configured.
        # The hosting GridTile drives this from the layout lock via
        # ``set_interactive``; the initial value is overwritten when the tile is
        # placed (DashboardCanvas.add_tile -> GridTile.set_locked).
        self._interactive = True
        self.setObjectName("dashboardElement")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # full-bleed tiles fill edge-to-edge; their rectangular child is clipped
        # to the theme's rounded corners in _update_fullbleed_mask so the map /
        # image follow the global corner radius like every other tile
        self.setProperty("fullBleed", bool(self.full_bleed))

        self._outer = QVBoxLayout(self)
        if self.full_bleed:
            self._outer.setContentsMargins(0, 0, 0, 0)
            self._outer.setSpacing(0)
        else:
            self._outer.setContentsMargins(12, 8, 12, 10)
            self._outer.setSpacing(6)

        # --- title area (omitted entirely for full-bleed tiles) ---
        self.title_label = QLabel(self.config.get("title", self.type_name.title()))
        self.title_label.setObjectName("elementTitle")
        if self.full_bleed:
            self.title_label.hide()
        else:
            self._outer.addWidget(self.title_label)

        # --- visualization area (subclasses fill this) ---
        self.body = QVBoxLayout()
        self.body.setSpacing(0 if self.full_bleed else 4)
        self._outer.addLayout(self.body, stretch=1)

        # --- description area (optional; omitted for full-bleed tiles) ---
        desc = self.config.get("description")
        self.desc_label = QLabel(desc or "")
        self.desc_label.setObjectName("elementDescription")
        self.desc_label.setWordWrap(True)
        if self.full_bleed:
            self.desc_label.hide()
        else:
            self.desc_label.setVisible(bool(desc))
            self._outer.addWidget(self.desc_label)

        # subscribe to the cross-filter bus + appearance
        self.bus.filtersChanged.connect(self._on_filters_changed)
        self.bus.layersChanged.connect(self.refresh)
        self.bus.themeChanged.connect(self.apply_theme)
        self.bus.filtersCleared.connect(self._on_filters_cleared)

    # ---- identity / metadata ----

    def display_name(self):
        from ..elements import ELEMENT_LABELS
        title = self.config.get("title")
        return title or ELEMENT_LABELS.get(self.type_name, self.type_name)

    # ---- appearance ----

    def effective_theme(self):
        return self.bus.theme.merged_with(self.config.get("style"))

    def apply_theme(self):
        self.setStyleSheet(self.effective_theme().tile_qss())
        self._update_fullbleed_mask()
        self._restyle()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_fullbleed_mask()

    def _update_fullbleed_mask(self):
        """Clip a full-bleed tile to the theme's rounded corners.

        A normal tile gets its rounded corners from the QSS ``border-radius`` on
        ``#dashboardElement``. A full-bleed tile holds a rectangular child that
        paints over those corners — most notably the map's ``QgsMapCanvas`` (a
        ``QGraphicsView`` whose viewport ignores stylesheet rounding). To make
        the map and image follow the global corner radius we mask the whole tile
        to a rounded region (re-applied on resize / theme change). Non-full-bleed
        tiles need no mask — their QSS rounding already shows.
        """
        if not self.full_bleed:
            return
        w, h = self.width(), self.height()
        r = self.effective_theme().radius
        if w <= 0 or h <= 0:
            return
        if r <= 0:
            self.clearMask()
            return
        r = min(float(r), w / 2.0, h / 2.0)
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(w), float(h), r, r)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _restyle(self):
        """Hook for subclasses with custom-painted views; default repaint."""
        self.update()

    def reconfigure(self):
        """Re-read ``config`` after an in-place edit (the Configure dialog).

        Updates the shared title/description chrome and re-applies appearance +
        data so a configuration change is reflected without recreating the tile.
        Subclasses that cache config in ``__init__`` override to extend this.
        """
        self.title_label.setText(self.config.get("title", self.type_name.title()))
        desc = self.config.get("description")
        self.desc_label.setText(desc or "")
        if not self.full_bleed:
            self.desc_label.setVisible(bool(desc))
        self.apply_theme()
        self.refresh()

    # ---- data helpers shared by every data-driven element ----

    def layer(self):
        lid = self.config.get("layer_id")
        if not lid:
            return None
        return QgsProject.instance().mapLayer(lid)

    def _combined_filter(self):
        """AND the element's own filter with its connected sources' filter."""
        parts = [p for p in (self.config.get("base_filter"),
                             self.bus.combined_filter_for(self.id)) if p]
        if not parts:
            return None
        return " AND ".join("({})".format(p) for p in parts)

    def iter_features(self):
        """Yield features honoring the combined filter. Safe if no layer."""
        lyr = self.layer()
        if lyr is None:
            return
        req = QgsFeatureRequest()
        expr_str = self._combined_filter()
        if expr_str:
            req.setFilterExpression(expr_str)
        for f in lyr.getFeatures(req):
            yield f

    def evaluate(self, expression_str):
        """Evaluate an aggregate-style QgsExpression against the layer.

        QGIS aggregate functions ignore the feature-request filter, so the
        live dashboard filter is exposed as the ``@dashboard_filter`` variable;
        use the aggregate ``filter:=`` argument to opt in, e.g.
        ``count(1, filter:=@dashboard_filter)``.
        """
        lyr = self.layer()
        if lyr is None or not expression_str:
            return None
        expr = QgsExpression(expression_str)
        ctx = QgsExpressionContext()
        ctx.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(lyr))
        flt = self._combined_filter()
        if flt is not None and ctx.lastScope() is not None:
            ctx.lastScope().setVariable("dashboard_filter", flt)
        val = expr.evaluate(ctx)
        if expr.hasEvalError():
            return None
        return val

    # ---- interaction mode (Use vs Build) ----

    def set_interactive(self, on):
        """Enable/disable content interaction (Use mode vs Build mode).

        In **Use mode** (``on=True``) the element's contents react to the user
        (clicking a chart to cross-filter, selecting a list row, panning the
        map). In **Build mode** (``on=False``) contents are inert so the user
        can move / resize / configure tiles without firing filters. Presentational
        elements need nothing; interactive elements (chart, pivot, list, selector,
        text, map) override and act on the flag.
        """
        self._interactive = bool(on)

    def on_tile_double_click(self):
        """Double-click on the tile body (Build mode only).

        The Build-mode drag overlay covers the whole tile, so a double-click on
        the body is routed here instead of reaching the element directly. Most
        elements do nothing; the text tile overrides this to edit its text.
        """
        pass

    # ---- bus reaction ----

    def _on_filters_changed(self):
        if self.accepts_filter:
            self.refresh()

    def _on_filters_cleared(self):
        """Sources override to reset their own selection state."""
        pass

    def refresh(self):
        """Subclasses override to redraw from current data + filter."""
        raise NotImplementedError

    def teardown(self):
        """Release external signal connections before the tile is destroyed.

        Bus connections are auto-dropped when this QObject dies; subclasses
        that wire *long-lived external* signals (e.g. the QGIS map canvas)
        override this to disconnect them explicitly.
        """
        pass

    # ---- persistence ----

    def to_dict(self):
        d = dict(self.config)
        d["__type__"] = self.type_name
        d["id"] = self.id
        return d
