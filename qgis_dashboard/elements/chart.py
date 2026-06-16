# -*- coding: utf-8 -*-
"""Generic chart element.

One element renders every category chart type (bar / barh / line / area /
pie / donut). ``config["chart_type"]`` selects the painter from the registry
(``charts/painters.py``); the binding and behavior are shared: group features
by a category field, aggregate a statistic per group, and act as a filter
SOURCE — clicking a bar/point/slice pushes ``"category = X"`` tagged with this
element's id; clicking the same one again clears it.

This replaces the former ``serial_chart`` and ``pie_chart`` element classes;
their saved configs are migrated to ``chart`` in ``elements/__init__.py``.
"""

from collections import defaultdict

from .base import DashboardElement
from .chart_specs import (
    spec_for, fold_categories, filter_literal, DEFAULT_CHART_TYPE,
)
from .charts.painters import PAINTERS


class ChartElement(DashboardElement):
    type_name = "chart"
    is_filter_source = True

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        spec = self._spec()
        painter_cls = PAINTERS.get(spec["painter"], PAINTERS["bar"])
        self.view = painter_cls()
        self.view.categoryClicked.connect(self._on_category)
        self.body.addWidget(self.view)
        self._selected = None
        self.apply_theme()
        self.refresh()

    # ---- spec / appearance ----

    def _chart_type(self):
        return self.config.get("chart_type", DEFAULT_CHART_TYPE)

    def _spec(self):
        return spec_for(self._chart_type())

    def _restyle(self):
        self.view.set_theme(self.effective_theme())

    # ---- data ----

    def _aggregate(self):
        """Return ordered (category, value) pairs under the current filter."""
        cat_field = self.config.get("category_field")
        if not cat_field:
            return []
        spec = self._spec()
        stat = self.config.get("statistic", "count")
        if not spec.get("supports_statistic"):
            stat = "count"
        value_field = self.config.get("value_field")

        buckets = defaultdict(list)
        for f in self.iter_features():
            key = f[cat_field]
            if stat == "count":
                buckets[str(key)].append(1)
            else:
                # QGIS NULL is a null QVariant (not None) and breaks sum();
                # coerce and drop non-numerics.
                try:
                    buckets[str(key)].append(float(f[value_field]))
                except (TypeError, ValueError):
                    continue

        out = []
        for k, vals in buckets.items():
            if stat == "count":
                out.append((k, len(vals)))
            elif stat == "sum":
                out.append((k, sum(vals)))
            elif stat == "mean":
                out.append((k, sum(vals) / len(vals) if vals else 0))
        out.sort(key=lambda x: x[1], reverse=True)

        cap = self.config.get("max_categories") or spec.get("default_cap", 12)
        return fold_categories(out, int(cap), spec.get("fold_other", False))

    def refresh(self):
        data = self._aggregate()
        self.view.set_data(data, self._selected, self._spec().get("inner", 0.0))

    # ---- bus reaction ----

    def _on_filters_cleared(self):
        self._selected = None

    def _on_category(self, cat):
        if not self._interactive:   # Build mode: clicks don't cross-filter
            return
        if cat == "Other":
            return
        cat_field = self.config.get("category_field")
        if not cat_field:
            return
        if self._selected == cat:                # toggle off
            self._selected = None
            self.bus.set_filter(self.id, None)
        else:
            self._selected = cat
            self.bus.set_filter(self.id, filter_literal(cat_field, cat))
