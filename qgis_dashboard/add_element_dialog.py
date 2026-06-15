# -*- coding: utf-8 -*-
"""Add-element dialog.

Minimal config UI per element type. Uses QgsMapLayerComboBox /
QgsFieldComboBox where it helps. This is the MVP stand-in for ArcGIS's rich
configuration panels — enough to bind data and see the dashboard work.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QLineEdit, QDialogButtonBox, QCheckBox,
    QPlainTextEdit, QWidget, QHBoxLayout, QPushButton, QFileDialog,
)
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox
from qgis.core import QgsMapLayerProxyModel
from .elements import ELEMENT_LABELS
from .elements.chart_specs import CHART_SPECS, CHART_TYPE_ORDER

# element types that bind to no vector layer (the Layer row is hidden for them)
_LAYERLESS_TYPES = ("text", "image")

_IMAGE_FILTER = ("Images (*.png *.jpg *.jpeg *.svg *.gif *.bmp *.webp);;"
                 "All files (*)")


class _PathPicker(QWidget):
    """A read/write path field with a 'Browse…' button (image file chooser)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        browse = QPushButton("Browse…")
        browse.setProperty("variant", "secondary")
        browse.clicked.connect(self._browse)
        row.addWidget(self._edit, 1)
        row.addWidget(browse)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose image", self._edit.text(), _IMAGE_FILTER)
        if path:
            self._edit.setText(path)

    def path(self):
        return self._edit.text().strip()


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

    def _field_combo(self, allow_empty=False):
        c = QgsFieldComboBox()
        if allow_empty:
            c.setAllowEmptyFieldName(True)
        c.setLayer(self.layer_combo.currentLayer())
        return c

    def _set_layer_row_visible(self, visible):
        lbl = self.form.labelForField(self.layer_combo)
        self.layer_combo.setVisible(visible)
        if lbl:
            lbl.setVisible(visible)

    def _rebuild(self):
        self._clear_dynamic()
        t = self.type_combo.currentData()
        self._set_layer_row_visible(t not in _LAYERLESS_TYPES)
        if t == "text":
            self._add_dyn("text", "Text", QPlainTextEdit())
            align = QComboBox()
            align.addItem("Left", "left")
            align.addItem("Center", "center")
            align.addItem("Right", "right")
            self._add_dyn("align", "Alignment", align)
            heading = QCheckBox()
            self._add_dyn("heading", "Heading style", heading)
        elif t == "image":
            self._add_dyn("path", "Image file", _PathPicker())
            fit = QComboBox()
            fit.addItem("Fit (keep aspect)", "contain")
            fit.addItem("Stretch to fill", "stretch")
            self._add_dyn("fit", "Scaling", fit)
        elif t == "indicator":
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
        elif t == "pivot":
            self._add_dyn("row_field", "Row field", self._field_combo())
            self._add_dyn("col_field", "Column field (optional)",
                          self._field_combo(allow_empty=True))
            stat = QComboBox()
            stat.addItems(["count", "sum", "mean", "min", "max"])
            self._add_dyn("statistic", "Statistic", stat)
            self._add_dyn("value_field", "Value field (sum/mean/min/max)",
                          self._field_combo())
            chk = QCheckBox()
            chk.setChecked(True)
            self._add_dyn("show_totals", "Show totals", chk)
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
            elif isinstance(w, QCheckBox):
                cfg[key] = w.isChecked()
            elif isinstance(w, QComboBox):
                data = w.currentData()
                cfg[key] = data if data is not None else w.currentText()
            elif isinstance(w, _PathPicker):
                cfg[key] = w.path()
            elif isinstance(w, QPlainTextEdit):
                cfg[key] = w.toPlainText()
            elif isinstance(w, QLineEdit):
                val = w.text().strip()
                if val:
                    cfg[key] = ([s.strip() for s in val.split(",")]
                                if key == "display_fields" else val)
        return t, cfg
