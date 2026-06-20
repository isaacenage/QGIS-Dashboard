# -*- coding: utf-8 -*-
"""Legend widget — a symbology-driven cross-filter source.

This tile mirrors the bound layer's *real* map legend: it reads the layer's
categorized or graduated renderer and lists one checkable row per class, each
with the class's symbol swatch and label. Unchecking a class drops it from the
filter the tile pushes onto the bus, so toggling legend classes filters every
connected tile (and, wired to the map, visibly subsets the rendered features).

It is a *pure* source (``accepts_filter = False``). The class-set → expression
translation lives in the Qt-free :mod:`legend_model` (unit-tested); this element
only does the QGIS-side renderer reading and the widget plumbing.

Limitation (v1): filtering assumes the renderer classifies on a *field*. A
renderer keyed by an expression still lists its classes but the pushed filter
double-quotes the classification string as a field reference.
"""

from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from qgis.core import (
    NULL,
    QgsCategorizedSymbolRenderer,
    QgsGraduatedSymbolRenderer,
    QgsSymbolLayerUtils,
)

from .base import DashboardElement
from . import legend_model

_SWATCH = QSize(16, 16)
_ROLE = Qt.ItemDataRole.UserRole


class LegendElement(DashboardElement):
    type_name = "legend"
    is_filter_source = True
    accepts_filter = False

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.itemChanged.connect(self._on_item_changed)
        self.body.addWidget(self.list)
        self._mode = None        # "categorized" | "graduated" | None
        self._field = None
        self._total = 0
        self._suppress = False
        self.apply_theme()
        self.refresh()

    # ---- interaction mode ----

    def set_interactive(self, on):
        super().set_interactive(on)
        # Build mode: checkboxes inert so arranging tiles can't push a filter.
        self.list.setEnabled(bool(on))

    # ---- appearance ----

    def _restyle(self):
        th = self.effective_theme()
        self.list.setStyleSheet(
            'QListWidget {{ background:transparent; border:none;'
            ' color:{c}; font-family:{f}; font-size:{px}px; }}'
            'QListWidget::item {{ padding:2px 0; }}'.format(
                c=th.text, f=th.font_stack(), px=th.font_size))

    # ---- data (QGIS-side renderer reading) ----

    def _classify(self, lyr):
        """Return (mode, field, items) where items is a list of dicts.

        Each item: ``{"label", "value"|"range", "symbol"}``. ``mode`` is one of
        ``"categorized"`` / ``"graduated"`` / ``None`` (unsupported renderer).
        """
        renderer = lyr.renderer() if lyr is not None else None
        if isinstance(renderer, QgsCategorizedSymbolRenderer):
            items = []
            for cat in renderer.categories():
                v = cat.value()
                items.append({"label": cat.label() or str(v),
                              "value": None if v == NULL else v,
                              "symbol": cat.symbol()})
            return "categorized", renderer.classAttribute(), items
        if isinstance(renderer, QgsGraduatedSymbolRenderer):
            items = []
            for rng in renderer.ranges():
                items.append({"label": rng.label(),
                              "range": (rng.lowerValue(), rng.upperValue()),
                              "symbol": rng.symbol()})
            return "graduated", renderer.classAttribute(), items
        return None, None, []

    def refresh(self):
        mode, field, items = self._classify(self.layer())
        self._mode, self._field, self._total = mode, field, len(items)
        self._suppress = True
        self.list.clear()
        if mode is None:
            placeholder = QListWidgetItem("No categories to filter")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(placeholder)
            self._suppress = False
            self._restyle()
            return
        for it in items:
            item = QListWidgetItem(it["label"])
            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                          | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Checked)
            if it.get("symbol") is not None:
                pix = QgsSymbolLayerUtils.symbolPreviewPixmap(it["symbol"], _SWATCH)
                item.setIcon(QIcon(pix))
            item.setData(_ROLE, it["range"] if mode == "graduated" else it["value"])
            self.list.addItem(item)
        self._suppress = False
        self._restyle()

    # ---- source behavior ----

    def _checked_data(self):
        out = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(item.data(_ROLE))
        return out

    def _on_item_changed(self, _item):
        if self._suppress or not self._interactive or self._mode is None:
            return
        checked = self._checked_data()
        if self._mode == "graduated":
            expr = legend_model.ranges_to_expression(
                self._field, checked, self._total)
        else:
            expr = legend_model.categories_to_expression(
                self._field, checked, self._total)
        self.bus.set_filter(self.id, expr)

    def _on_filters_cleared(self):
        self._suppress = True
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked)
        self._suppress = False
