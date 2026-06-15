# -*- coding: utf-8 -*-
"""Indicator element.

Mirrors the ArcGIS indicator: a big value, optional reference value, and a
trend/delta. ArcGIS divides the visualization into top/middle/bottom text
areas; we expose the same three slots. The value comes from a QgsExpression
aggregate (e.g. sum("pop")), so it reacts to the dashboard filter.
"""

from qgis.PyQt.QtWidgets import QLabel
from qgis.PyQt.QtCore import Qt
from .base import DashboardElement


class IndicatorElement(DashboardElement):
    type_name = "indicator"

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        self.top = QLabel("")
        self.middle = QLabel("—")
        self.bottom = QLabel("")
        for lbl, name in ((self.top, "indTop"),
                          (self.middle, "indValue"),
                          (self.bottom, "indBottom")):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setObjectName(name)
            self.body.addWidget(lbl)
        self.apply_theme()
        self.refresh()

    def _fmt(self, v):
        if v is None:
            return self.config.get("no_value_text", "No data")
        if isinstance(v, float):
            dp = self.config.get("decimals", 0)
            v = round(v, dp)
            if dp == 0:
                v = int(v)
        prefix = self.config.get("prefix", "")
        suffix = self.config.get("suffix", "")
        if isinstance(v, (int, float)):
            return "{}{:,}{}".format(prefix, v, suffix)
        return "{}{}{}".format(prefix, v, suffix)

    def refresh(self):
        value_expr = self.config.get("value_expression", "count(1)")
        value = self.evaluate(value_expr)
        self.middle.setText(self._fmt(value))

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
