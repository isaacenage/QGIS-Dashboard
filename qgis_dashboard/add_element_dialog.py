# -*- coding: utf-8 -*-
"""Add-element dialog.

Minimal config UI per element type. Uses QgsMapLayerComboBox /
QgsFieldComboBox where it helps. This is the MVP stand-in for ArcGIS's rich
configuration panels — enough to bind data and see the dashboard work.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QLineEdit, QDialogButtonBox, QCheckBox,
    QPlainTextEdit, QWidget, QHBoxLayout, QPushButton, QFileDialog, QSpinBox,
    QFontComboBox,
)
from qgis.PyQt.QtGui import QFont
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox
from qgis.core import QgsMapLayerProxyModel
from .elements import ELEMENT_LABELS
from .elements.chart_specs import CHART_SPECS, CHART_TYPE_ORDER

# element types that bind to no vector layer (the Layer row is hidden for them)
_LAYERLESS_TYPES = ("text", "image", "header")

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

    def set_path(self, value):
        self._edit.setText(value or "")


class AddElementDialog(QDialog):
    """Add a new element, or — when *element* is given — reconfigure one.

    In **configure** mode the element type is locked and every row is prefilled
    from the existing ``config`` so the same per-type form re-edits a live tile
    (opened from the tile's ``Configure…`` menu).
    """

    def __init__(self, parent=None, element=None):
        super().__init__(parent)
        self._element = element
        self.setWindowTitle("Configure element" if element else
                            "Add dashboard element")
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

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.form.addRow(self.buttons)

        if element is not None:
            idx = self.type_combo.findData(element.type_name)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
            self.type_combo.setEnabled(False)   # type is fixed when editing
            self.title_edit.setText(element.config.get("title", ""))
            lyr = element.layer()
            if lyr is not None:
                self.layer_combo.setLayer(lyr)

        self._rebuild()
        if element is not None:
            self._load_values(element.config)

    def _spin(self, lo, hi, value):
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(value)
        return s

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
        elif t == "header":
            # the top-level "Title" row doubles as the banner text
            self._add_dyn("font_family", "Font", QFontComboBox())
            self._add_dyn("font_size", "Font size (px)", self._spin(8, 200, 22))
            align = QComboBox()
            align.addItem("Left", "left")
            align.addItem("Center", "center")
            align.addItem("Right", "right")
            self._add_dyn("align", "Text alignment", align)
            self._add_dyn("logo_path", "Logo image (opt)", _PathPicker())
            slot = QComboBox()
            slot.addItem("Left of title", "left")
            slot.addItem("Right of title", "right")
            slot.addItem("Above title", "above")
            slot.addItem("Below title", "below")
            self._add_dyn("logo_slot", "Logo position", slot)
            self._add_dyn("logo_size", "Logo size (px)", self._spin(12, 400, 40))
            anchor = QComboBox()
            anchor.addItem("Top", "top")
            anchor.addItem("Bottom", "bottom")
            anchor.addItem("Left", "left")
            anchor.addItem("Right", "right")
            self._add_dyn("anchor", "Dock edge", anchor)
            self._add_dyn("thickness", "Banner thickness (px)",
                          self._spin(40, 600, 80))
            self._add_dyn("scope_all_pages", "Show on all pages", QCheckBox())
        elif t == "indicator":
            self._add_dyn("value_expression", "Value expression",
                          QLineEdit("count(1)"))
            self._add_dyn("reference_expression", "Reference expr (opt)",
                          QLineEdit(""))
            self._add_dyn("top_text", "Top label (opt)", QLineEdit(""))
            self._add_dyn("prefix", "Value prefix", QLineEdit(""))
            self._add_dyn("suffix", "Value suffix", QLineEdit(""))
            self._add_dyn("decimals", "Decimal places", self._spin(0, 6, 0))
            self._add_dyn("no_value_text", "No-data text", QLineEdit("No data"))
            self._add_dyn("value_size", "Value text size (px)",
                          self._spin(8, 200, 30))
            self._add_dyn("icon_path", "Icon image (opt)", _PathPicker())
            icon_pos = QComboBox()
            icon_pos.addItem("Left of value", "left")
            icon_pos.addItem("Right of value", "right")
            icon_pos.addItem("Above value", "top")
            self._add_dyn("icon_position", "Icon position", icon_pos)
            self._add_dyn("icon_size", "Icon size (px)", self._spin(12, 256, 48))
            anim = QComboBox()
            anim.addItem("None", "none")
            anim.addItem("Odometer count-up", "odometer")
            anim.addItem("Rolling digits", "rolling")
            anim.addItem("Typewriter", "typewriter")
            anim.addItem("Fade / flash", "fade")
            self._add_dyn("animation", "Value animation", anim)
        elif t == "map":
            extent = QCheckBox()
            extent.setChecked(True)
            self._add_dyn("extent_filter_enabled",
                          "Filter connected tiles to visible extent", extent)
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

    def _load_values(self, config):
        """Prefill the dynamic rows from an existing element's config."""
        for key, w in self._dyn.items():
            if key not in config:
                continue
            val = config[key]
            if isinstance(w, QgsFieldComboBox):
                w.setField(val or "")
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(val))
            elif isinstance(w, QSpinBox):
                try:
                    w.setValue(int(val))
                except (TypeError, ValueError):
                    pass
            elif isinstance(w, QFontComboBox):
                # QFontComboBox subclasses QComboBox — must precede it here
                if val:
                    w.setCurrentFont(QFont(val))
            elif isinstance(w, QComboBox):
                i = w.findData(val)
                if i >= 0:
                    w.setCurrentIndex(i)
            elif isinstance(w, _PathPicker):
                w.set_path(val or "")
            elif isinstance(w, QPlainTextEdit):
                w.setPlainText(val if isinstance(val, str) else "")
            elif isinstance(w, QLineEdit):
                if key == "display_fields" and isinstance(val, list):
                    w.setText(", ".join(val))
                else:
                    w.setText("" if val is None else str(val))

    def managed_keys(self):
        """Config keys this dialog owns — so a configure-edit can drop the ones
        the user cleared (an absent key removes, rather than keeps, the old)."""
        keys = set(self._dyn.keys())
        keys.update({"title", "layer_id"})
        return keys

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
            elif isinstance(w, QSpinBox):
                cfg[key] = w.value()
            elif isinstance(w, QFontComboBox):
                # QFontComboBox subclasses QComboBox — must precede it here
                cfg[key] = w.currentFont().family()
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
