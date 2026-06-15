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

    def __init__(self, bus, config=None, parent=None):
        super().__init__(parent)
        self.bus = bus
        self.config = config or {}
        self.id = self.config.get("id") or uuid.uuid4().hex[:8]
        self.config["id"] = self.id
        self.setObjectName("dashboardElement")
        self.setFrameShape(QFrame.StyledPanel)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(12, 8, 12, 10)
        self._outer.setSpacing(6)

        # --- title area ---
        self.title_label = QLabel(self.config.get("title", self.type_name.title()))
        self.title_label.setObjectName("elementTitle")
        self._outer.addWidget(self.title_label)

        # --- visualization area (subclasses fill this) ---
        self.body = QVBoxLayout()
        self.body.setSpacing(4)
        self._outer.addLayout(self.body, stretch=1)

        # --- description area (optional) ---
        desc = self.config.get("description")
        self.desc_label = QLabel(desc or "")
        self.desc_label.setObjectName("elementDescription")
        self.desc_label.setWordWrap(True)
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
        self._restyle()

    def _restyle(self):
        """Hook for subclasses with custom-painted views; default repaint."""
        self.update()

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
