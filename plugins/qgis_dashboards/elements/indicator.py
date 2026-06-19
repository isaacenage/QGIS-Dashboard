# -*- coding: utf-8 -*-
"""Indicator element.

Mirrors the ArcGIS indicator: a big value, optional reference value, and a
trend/delta. ArcGIS divides the visualization into top/middle/bottom text
areas; we expose the same three slots. The value comes from a QgsExpression
aggregate (e.g. sum("pop")), so it reacts to the dashboard filter.

Beyond the data binding the tile is configurable like a real dashboard card:

* an optional **icon** (PNG / JPG / SVG) placed left / right / above the value,
* an explicit **value text size**, and
* a value **animation** (odometer / rolling / typewriter / fade) played whenever
  the number changes — see :mod:`indicator_anim`.
"""

from qgis.PyQt.QtWidgets import QLabel, QWidget, QGridLayout
from qgis.PyQt.QtCore import Qt
from .base import DashboardElement
from .media import icon_pixmap
from .indicator_anim import IndicatorValue


class IndicatorElement(DashboardElement):
    type_name = "indicator"

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        self.top = QLabel("")
        self.bottom = QLabel("")
        for lbl, name in ((self.top, "indTop"), (self.bottom, "indBottom")):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setObjectName(name)

        # icon + animated value share a small grid so the icon can sit left,
        # right or above the value without rebuilding layouts.
        self.icon = QLabel()
        self.icon.setObjectName("indIcon")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value = IndicatorValue()
        self._value_host = QWidget()
        self._vgrid = QGridLayout(self._value_host)
        self._vgrid.setContentsMargins(0, 0, 0, 0)
        self._vgrid.setHorizontalSpacing(10)
        self._vgrid.setVerticalSpacing(6)

        self.body.addStretch(1)
        self.body.addWidget(self.top)
        self.body.addWidget(self._value_host)
        self.body.addWidget(self.bottom)
        self.body.addStretch(1)

        self.apply_theme()
        self.refresh()

    # ---- formatting ----

    def _fmt(self, v):
        if v is None:
            return self.config.get("no_value_text", "No data")
        if isinstance(v, float):
            dp = int(self.config.get("decimals", 0) or 0)
            v = round(v, dp)
            if dp == 0:
                v = int(v)
        prefix = self.config.get("prefix", "")
        suffix = self.config.get("suffix", "")
        if isinstance(v, (int, float)):
            return "{}{:,}{}".format(prefix, v, suffix)
        return "{}{}{}".format(prefix, v, suffix)

    # ---- appearance ----

    def _restyle(self):
        th = self.effective_theme()
        size = int(self.config.get("value_size") or th.value_size)
        self.value.apply_style(th.accent, size, th.heading_family())

    def _rebuild_value_host(self, position, has_icon):
        self._vgrid.removeWidget(self.icon)
        self._vgrid.removeWidget(self.value)
        if not has_icon:
            self.icon.hide()
            self._vgrid.addWidget(self.value, 0, 0, Qt.AlignmentFlag.AlignCenter)
            return
        self.icon.show()
        if position == "top":
            self._vgrid.addWidget(self.icon, 0, 0, Qt.AlignmentFlag.AlignCenter)
            self._vgrid.addWidget(self.value, 1, 0, Qt.AlignmentFlag.AlignCenter)
        elif position == "right":
            self._vgrid.addWidget(self.value, 0, 0, Qt.AlignmentFlag.AlignCenter)
            self._vgrid.addWidget(self.icon, 0, 1, Qt.AlignmentFlag.AlignCenter)
        else:   # left (default)
            self._vgrid.addWidget(self.icon, 0, 0, Qt.AlignmentFlag.AlignCenter)
            self._vgrid.addWidget(self.value, 0, 1, Qt.AlignmentFlag.AlignCenter)

    # ---- data ----

    def refresh(self):
        # keep value styling current (cheap; also covers theme/config changes)
        self._restyle()

        value = self.evaluate(self.config.get("value_expression", "count(1)"))
        text = self._fmt(value)

        # optional icon
        path = self.config.get("icon_path")
        pixmap = icon_pixmap(path, self.config.get("icon_size", 48)) if path else None
        has_icon = pixmap is not None
        if has_icon:
            self.icon.setPixmap(pixmap)
        self._rebuild_value_host(self.config.get("icon_position", "left"), has_icon)

        # animated value
        self.value.set_options(
            self.config.get("animation", ""),
            self.config.get("animation_duration_ms", 900),
            self._fmt)
        self.value.set_value(value if isinstance(value, (int, float)) else None, text)

        # reference value + delta, like ArcGIS reference/trend
        ref_expr = self.config.get("reference_expression")
        if ref_expr and value is not None:
            ref = self.evaluate(ref_expr)
            if ref is not None and isinstance(value, (int, float)):
                delta = value - ref
                arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "—")
                self.bottom.setText("{} {} vs ref".format(arrow, self._fmt(abs(delta))))
                self.bottom.setProperty(
                    "trend",
                    "up" if delta > 0 else "down" if delta < 0 else "flat")
        self.top.setText(self.config.get("top_text", ""))
        self.top.setVisible(bool(self.config.get("top_text")))
        self.bottom.setVisible(bool(ref_expr))
