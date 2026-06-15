# -*- coding: utf-8 -*-
"""Element registry — factory + persistence lookup."""

from .indicator import IndicatorElement
from .chart import ChartElement
from .pivot import PivotElement
from .list_element import ListElement
from .map_element import MapElement
from .category_selector import CategorySelectorElement

ELEMENT_TYPES = {
    cls.type_name: cls for cls in (
        IndicatorElement,
        ChartElement,
        PivotElement,
        ListElement,
        MapElement,
        CategorySelectorElement,
    )
}

# Friendly labels for the "Add element" UI
ELEMENT_LABELS = {
    "indicator": "Indicator",
    "chart": "Chart",
    "pivot": "Pivot / matrix",
    "list": "List",
    "map": "Map (live canvas)",
    "category_selector": "Category selector",
}


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _migrate_legacy(type_name, config):
    """Map the former serial_chart / pie_chart element types onto ``chart``.

    Saved dashboards (v1/v2/v3) reference the old type names; rewrite them so
    they load on the generic ChartElement. They auto-upgrade to ``chart`` on
    the next save (``ChartElement.to_dict`` writes ``__type__: "chart"``).
    """
    if type_name == "serial_chart":
        config.setdefault("chart_type", "bar")
        return "chart"
    if type_name == "pie_chart":
        inner = _to_float(config.get("inner_radius"))
        config.setdefault("chart_type", "donut" if inner > 0 else "pie")
        if "max_slices" in config and "max_categories" not in config:
            config["max_categories"] = config["max_slices"]
        return "chart"
    return type_name


def create_element(type_name, bus, config=None, parent=None):
    config = dict(config or {})
    type_name = _migrate_legacy(type_name, config)
    cls = ELEMENT_TYPES.get(type_name)
    if cls is None:
        raise ValueError("Unknown element type: {}".format(type_name))
    return cls(bus, config, parent)
