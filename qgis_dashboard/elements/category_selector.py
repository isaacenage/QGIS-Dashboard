# -*- coding: utf-8 -*-
"""Category selector.

The canonical ArcGIS selector: a dropdown of grouped values from a category
field. Picking a value pushes a filter onto the bus (tagged with this
element's id); picking "(All)" clears it. The cleanest action SOURCE.

It is a *pure* source: ``accepts_filter = False`` so it never filters itself
down to a single value when other elements drive the dashboard.
"""

from qgis.PyQt.QtWidgets import QComboBox
from .base import DashboardElement


class CategorySelectorElement(DashboardElement):
    type_name = "category_selector"
    is_filter_source = True
    accepts_filter = False

    ALL = "(All)"

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        self.combo = QComboBox()
        self.combo.currentTextChanged.connect(self._on_change)
        self.body.addWidget(self.combo)
        self.body.addStretch(1)
        self._suppress = False
        self.apply_theme()
        self.refresh()

    def set_interactive(self, on):
        # Build mode: disable the dropdown so it can't push a filter while the
        # user is arranging tiles. Use mode: live.
        super().set_interactive(on)
        self.combo.setEnabled(bool(on))

    def refresh(self):
        # Repopulate values WITHOUT applying the dashboard filter, otherwise the
        # selector would filter itself down to one value.
        field = self.config.get("category_field")
        lyr = self.layer()
        self._suppress = True
        current = self.combo.currentText()
        self.combo.clear()
        self.combo.addItem(self.ALL)
        if lyr and field:
            idx = lyr.fields().indexOf(field)
            if idx >= 0:
                values = sorted({str(v) for v in lyr.uniqueValues(idx)})
                self.combo.addItems(values)
        i = self.combo.findText(current)
        if i >= 0:
            self.combo.setCurrentIndex(i)
        self._suppress = False

    def _on_change(self, text):
        if self._suppress:
            return
        field = self.config.get("category_field")
        if text == self.ALL or not field:
            self.bus.set_filter(self.id, None)
        else:
            self.bus.set_filter(self.id, '"{}" = \'{}\''.format(field, text))

    def _on_filters_cleared(self):
        self._suppress = True
        i = self.combo.findText(self.ALL)
        if i >= 0:
            self.combo.setCurrentIndex(i)
        self._suppress = False
