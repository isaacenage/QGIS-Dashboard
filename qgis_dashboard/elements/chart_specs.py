# -*- coding: utf-8 -*-
"""Chart-type registry — declarative metadata + pure helpers.

Each entry in :data:`CHART_SPECS` describes one chart type so that a single
:class:`~.chart.ChartElement` can render it and the Add-element dialog can build
the right config rows. Adding a chart type is: register a painter (see
``charts/painters.py``) and add one row here.

This module is intentionally Qt-free so the helpers can be unit-tested without a
QGIS/Qt runtime.
"""

# type -> metadata. ``painter`` is a key into charts.painters.PAINTERS.
CHART_SPECS = {
    "bar":   {"label": "Bar (vertical)",   "group": "Comparison",
              "painter": "bar",  "supports_statistic": True,
              "fold_other": False, "default_cap": 12, "inner": 0.0},
    "barh":  {"label": "Bar (horizontal)", "group": "Comparison",
              "painter": "barh", "supports_statistic": True,
              "fold_other": False, "default_cap": 12, "inner": 0.0},
    "line":  {"label": "Line",             "group": "Trend",
              "painter": "line", "supports_statistic": True,
              "fold_other": False, "default_cap": 20, "inner": 0.0},
    "area":  {"label": "Area",             "group": "Trend",
              "painter": "area", "supports_statistic": True,
              "fold_other": False, "default_cap": 20, "inner": 0.0},
    "pie":   {"label": "Pie",              "group": "Composition",
              "painter": "pie",  "supports_statistic": False,
              "fold_other": True,  "default_cap": 7,  "inner": 0.0},
    "donut": {"label": "Donut",            "group": "Composition",
              "painter": "pie",  "supports_statistic": False,
              "fold_other": True,  "default_cap": 7,  "inner": 0.55},
}

# Display order for the Add-element dialog combo.
CHART_TYPE_ORDER = ["bar", "barh", "line", "area", "pie", "donut"]

DEFAULT_CHART_TYPE = "bar"


def spec_for(chart_type):
    """Return the spec for ``chart_type`` (falling back to the default)."""
    return CHART_SPECS.get(chart_type, CHART_SPECS[DEFAULT_CHART_TYPE])


def _is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def filter_literal(field, value):
    """Build a ``"field" = value`` expression, quoting non-numeric values."""
    if _is_number(value):
        return '"{}" = {}'.format(field, value)
    return '"{}" = \'{}\''.format(field, value)


def fold_categories(items, cap, fold_other=False):
    """Cap an ordered ``[(category, value)]`` list.

    With ``fold_other`` the tail past ``cap`` is summed into an ``"Other"``
    bucket (pie/donut); otherwise the list is simply truncated (bars/lines).
    """
    if not cap or cap <= 0 or len(items) <= cap:
        return list(items)
    head = list(items[:cap])
    if fold_other:
        other = sum(float(v) for _, v in items[cap:])
        head.append(("Other", other))
    return head
