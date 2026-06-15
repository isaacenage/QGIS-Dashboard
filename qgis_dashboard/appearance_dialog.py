# -*- coding: utf-8 -*-
"""Appearance dialog — edit the dashboard theme.

Two modes:
  - "global": edit the whole-dashboard theme (background, foreground, borders,
    chart colors, fonts, ...).
  - "element": edit one tile's override; only the keys a tile may override are
    shown, and the result is written to ``config["style"]``.

Fonts are chosen with ``QFontComboBox``, which lists every font available to
the QGIS/Qt application (including fonts QGIS itself has registered).
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QFormLayout, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
    QSpinBox, QFontComboBox, QLabel, QColorDialog, QDialogButtonBox,
    QScrollArea, QToolButton, QCheckBox,
)
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import Qt, pyqtSignal

from .theme import Theme, OVERRIDE_KEYS, DEFAULT_SERIES

# (key, label) for the simple color rows
GLOBAL_COLORS = [
    ("chrome_bg", "Window background"),
    ("window_bg", "Canvas background"),
    ("surface_bg", "Tile background"),
    ("chart_bg", "Chart background"),
    ("text", "Text (foreground)"),
    ("text_muted", "Secondary text"),
    ("accent", "Accent / highlight"),
    ("border", "Tile border"),
    ("grid_line", "Grid dots"),
]
ELEMENT_COLORS = [
    ("surface_bg", "Tile background"),
    ("chart_bg", "Chart background"),
    ("text", "Text (foreground)"),
    ("text_muted", "Secondary text"),
    ("accent", "Accent / highlight"),
]


class _ColorButton(QPushButton):
    """A swatch button that opens a color picker."""

    changed = pyqtSignal()

    def __init__(self, hex_color, parent=None):
        super().__init__(parent)
        self._color = hex_color or "#000000"
        self.setFixedSize(120, 24)
        self.clicked.connect(self._pick)
        self._refresh()

    def _refresh(self):
        c = QColor(self._color)
        text_color = "#ffffff" if c.lightness() < 140 else "#1b2733"
        self.setStyleSheet(
            "background:{}; color:{}; border:1px solid #b6bfc8; border-radius:4px;"
            .format(self._color, text_color))
        self.setText(self._color)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Pick color")
        if c.isValid():
            self._color = c.name()
            self._refresh()
            self.changed.emit()

    def color(self):
        return self._color


class _PaletteEditor(QWidget):
    """Editable row of series colors with add/remove."""

    changed = pyqtSignal()

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self._colors = list(colors) if colors else list(DEFAULT_SERIES)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._rebuild()

    def _rebuild(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, hexc in enumerate(self._colors):
            btn = _ColorButton(hexc)
            btn.setFixedSize(28, 24)
            btn.changed.connect(lambda i=i, b=btn: self._set(i, b.color()))
            self._lay.addWidget(btn)
        add = QToolButton()
        add.setText("+")
        add.clicked.connect(self._add)
        rem = QToolButton()
        rem.setText("−")
        rem.clicked.connect(self._remove)
        self._lay.addWidget(add)
        self._lay.addWidget(rem)
        self._lay.addStretch(1)

    def _set(self, i, hexc):
        if 0 <= i < len(self._colors):
            self._colors[i] = hexc
            self.changed.emit()

    def _add(self):
        nxt = DEFAULT_SERIES[len(self._colors) % len(DEFAULT_SERIES)]
        self._colors.append(nxt)
        self._rebuild()
        self.changed.emit()

    def _remove(self):
        if len(self._colors) > 1:
            self._colors.pop()
            self._rebuild()
            self.changed.emit()

    def colors(self):
        return list(self._colors)


class AppearanceDialog(QDialog):
    """Edit a Theme (global) or a tile override (element)."""

    def __init__(self, theme, mode="global", on_apply=None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self._on_apply = on_apply
        self._cleared = False
        self.setWindowTitle("Tile appearance" if mode == "element"
                            else "Dashboard appearance")
        self.resize(420, 520)

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        rows = ELEMENT_COLORS if mode == "element" else GLOBAL_COLORS
        self._color_btns = {}
        for key, label in rows:
            btn = _ColorButton(getattr(theme, key))
            btn.changed.connect(self._apply_live)
            self._color_btns[key] = btn
            form.addRow(label, btn)

        # series palette
        self._palette = _PaletteEditor(theme.series)
        self._palette.changed.connect(self._apply_live)
        form.addRow("Chart series colors", self._palette)

        # fonts
        self._font = QFontComboBox()
        if theme.font_family:
            self._font.setCurrentFont(QFont(theme.font_family))
        self._font.currentFontChanged.connect(self._apply_live)
        form.addRow("Font", self._font)
        self._use_font = QCheckBox("Use this font (otherwise QGIS default)")
        self._use_font.setChecked(bool(theme.font_family))
        self._use_font.stateChanged.connect(self._apply_live)
        form.addRow("", self._use_font)

        self._font_size = self._spin(theme.font_size, 6, 48)
        form.addRow("Base font size", self._font_size)
        self._title_size = self._spin(theme.title_size, 8, 48)
        form.addRow("Title font size", self._title_size)
        self._value_size = self._spin(theme.value_size, 10, 96)
        form.addRow("Indicator value size", self._value_size)

        if mode == "global":
            self._radius = self._spin(theme.radius, 0, 32)
            form.addRow("Tile corner radius", self._radius)
        else:
            self._radius = None

        # buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        if mode == "element":
            clear = btns.addButton("Clear overrides",
                                   QDialogButtonBox.ResetRole)
            clear.clicked.connect(self._clear)
        else:
            apply_btn = btns.addButton(QDialogButtonBox.Apply)
            apply_btn.clicked.connect(self._apply_live)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._base_theme = theme

    def _spin(self, value, lo, hi):
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(int(value))
        s.valueChanged.connect(self._apply_live)
        return s

    def _clear(self):
        self._cleared = True
        self.accept()

    def _font_family(self):
        return self._font.currentFont().family() if self._use_font.isChecked() else ""

    def result_theme(self):
        """Full Theme (global mode)."""
        data = self._base_theme.to_dict()
        for key, btn in self._color_btns.items():
            data[key] = btn.color()
        data["series"] = self._palette.colors()
        data["font_family"] = self._font_family()
        data["font_size"] = self._font_size.value()
        data["title_size"] = self._title_size.value()
        data["value_size"] = self._value_size.value()
        if self._radius is not None:
            data["radius"] = self._radius.value()
        return Theme.from_dict(data)

    def result_override(self):
        """Partial override dict (element mode). None if cleared."""
        if self._cleared:
            return None
        ov = {}
        for key, btn in self._color_btns.items():
            ov[key] = btn.color()
        ov["series"] = self._palette.colors()
        ov["font_family"] = self._font_family()
        ov["font_size"] = self._font_size.value()
        ov["title_size"] = self._title_size.value()
        ov["value_size"] = self._value_size.value()
        return {k: v for k, v in ov.items() if k in OVERRIDE_KEYS}

    def _apply_live(self, *_):
        if self.mode == "global" and self._on_apply:
            self._on_apply(self.result_theme())
