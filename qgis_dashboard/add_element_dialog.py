# -*- coding: utf-8 -*-
"""Add-element dialog.

Minimal config UI per element type. Uses QgsMapLayerComboBox /
QgsFieldComboBox where it helps. This is the MVP stand-in for ArcGIS's rich
configuration panels — enough to bind data and see the dashboard work.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QLineEdit, QDialogButtonBox
)
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox
from qgis.core import QgsMapLayerProxyModel
from .elements import ELEMENT_LABELS
from .elements.chart_specs import CHART_SPECS, CHART_TYPE_ORDER


class AddElementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add dashboard element")
        self.form = QFormLayout(self)

        self.type_combo = QComboBox()
        for key, label in ELEMENT_LABELS.items():
            self.type_combo.addItem(label, key)
        self.type_combo.currentIndexChanged.connect(self._rebuild)
        self.form.addRow("Element type", self.type_combo)

        self.title_edit = QLineEdit()
        self.form.addRow("Title", self.title_edit)

        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.layer_combo.layerChanged.connect(self._on_layer)
        self.form.addRow("Layer", self.layer_combo)

        # dynamic rows live in this dict so we can clear them on type change
        self._dyn = {}

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.form.addRow(self.buttons)

        self._rebuild()

    def _clear_dynamic(self):
        for w in self._dyn.values():
            lbl = self.form.labelForField(w)
            if lbl:
                lbl.deleteLater()
            w.deleteLater()
        self._dyn = {}

    def _add_dyn(self, key, label, widget):
        self._dyn[key] = widget
        # insert before the button row
        self.form.insertRow(self.form.rowCount() - 1, label, widget)

    def _field_combo(self):
        c = QgsFieldComboBox()
        c.setLayer(self.layer_combo.currentLayer())
        return c

    def _rebuild(self):
        self._clear_dynamic()
        t = self.type_combo.currentData()
        if t == "indicator":
            self._add_dyn("value_expression", "Value expression",
                          QLineEdit("count(1)"))
            self._add_dyn("reference_expression", "Reference expr (opt)",
                          QLineEdit(""))
        elif t == "chart":
            combo = QComboBox()
            for key in CHART_TYPE_ORDER:
                combo.addItem(CHART_SPECS[key]["label"], key)
            self._add_dyn("chart_type", "Chart type", combo)
            self._add_dyn("category_field", "Category field", self._field_combo())
            stat = QComboBox()
            stat.addItems(["count", "sum", "mean"])
            self._add_dyn("statistic", "Statistic", stat)
            self._add_dyn("value_field", "Value field (sum/mean)", self._field_combo())
        elif t == "category_selector":
            self._add_dyn("category_field", "Category field", self._field_combo())
        elif t == "list":
            self._add_dyn("display_fields", "Fields (comma sep)", QLineEdit(""))

    def _on_layer(self, _lyr):
        for w in self._dyn.values():
            if isinstance(w, QgsFieldComboBox):
                w.setLayer(self.layer_combo.currentLayer())

    def result_config(self):
        t = self.type_combo.currentData()
        cfg = {"title": self.title_edit.text() or ELEMENT_LABELS[t]}
        lyr = self.layer_combo.currentLayer()
        if lyr:
            cfg["layer_id"] = lyr.id()
        for key, w in self._dyn.items():
            if isinstance(w, QgsFieldComboBox):
                cfg[key] = w.currentField()
            elif isinstance(w, QComboBox):
                data = w.currentData()
                cfg[key] = data if data is not None else w.currentText()
            elif isinstance(w, QLineEdit):
                val = w.text().strip()
                if val:
                    cfg[key] = ([s.strip() for s in val.split(",")]
                                if key == "display_fields" else val)
        return t, cfg
