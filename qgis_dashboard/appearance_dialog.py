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
    QScrollArea, QToolButton, QCheckBox, QComboBox,
)
from qgis.PyQt.QtGui import QColor, QFont, QPixmap, QPainter, QIcon
from qgis.PyQt.QtCore import Qt, pyqtSignal, QSize, QRectF

from .theme import Theme, OVERRIDE_KEYS, DEFAULT_SERIES
from . import presets

# (key, label) for the simple color rows.
# Note: ``chrome_bg`` (the window/tab/rail chrome) is intentionally NOT editable —
# it stays at the neutral default so dialogs and chrome read consistently. Only the
# canvas drawing-area background ("Canvas background" → ``window_bg``) is exposed.
GLOBAL_COLORS = [
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


def _swatch_icon(values, size=16, n=5):
    """A small multi-color pill summarizing a preset's palette for a combo row.

    Draws the accent plus the first few series colors as rounded chips on a
    surface-colored ground, so the dropdown reads as a visual gallery.
    """
    w, h = size * n + 6, size + 6
    px = QPixmap(w, h)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    colors = [values.get("accent", "#2b7de9")]
    colors += list(values.get("series", []))[:n - 1]
    x = 3.0
    for c in colors[:n]:
        p.setBrush(QColor(c))
        p.setPen(QColor(0, 0, 0, 28))
        p.drawRoundedRect(QRectF(x, 3.0, size - 3, size), 3, 3)
        x += size
    p.end()
    return QIcon(px)


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

    def set_color(self, hex_color):
        """Set the swatch silently (no ``changed`` emission)."""
        self._color = hex_color or "#000000"
        self._refresh()


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

    def set_colors(self, colors):
        """Replace the palette silently (no ``changed`` emission)."""
        self._colors = list(colors) if colors else list(DEFAULT_SERIES)
        self._rebuild()


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

        # Guards re-entrancy while a preset populates the controls below.
        self._loading = False

        root = QVBoxLayout(self)

        # ---- preset gallery (global mode only) --------------------------
        # Presets set window/chrome colors that an element override can't carry,
        # so the one-click gallery is shown for the whole-dashboard theme only.
        self._preset = None
        if mode == "global":
            self._preset = QComboBox()
            self._preset.setIconSize(QSize(90, 22))
            self._preset.addItem(presets.CUSTOM)
            for name in presets.names():
                self._preset.addItem(_swatch_icon(presets.values_for(name)), name)
            match = presets.match(theme)
            self._preset.setCurrentText(match or presets.CUSTOM)
            self._preset.currentIndexChanged.connect(self._on_preset_chosen)
            preset_row = QFormLayout()
            preset_row.addRow("Preset theme", self._preset)
            root.addLayout(preset_row)

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
            btn.changed.connect(self._mark_custom)
            self._color_btns[key] = btn
            form.addRow(label, btn)

        # series palette
        self._palette = _PaletteEditor(theme.series)
        self._palette.changed.connect(self._apply_live)
        self._palette.changed.connect(self._mark_custom)
        form.addRow("Chart series colors", self._palette)

        # fonts — body family + an optional separate heading family (a pairing)
        self._font = QFontComboBox()
        if theme.font_family:
            self._font.setCurrentFont(QFont(theme.font_family))
        self._font.currentFontChanged.connect(self._apply_live)
        self._font.currentFontChanged.connect(self._mark_custom)
        form.addRow("Body font", self._font)
        self._use_font = QCheckBox("Use this font (otherwise QGIS default)")
        self._use_font.setChecked(bool(theme.font_family))
        self._use_font.stateChanged.connect(self._apply_live)
        self._use_font.stateChanged.connect(self._mark_custom)
        form.addRow("", self._use_font)

        self._heading_font = QFontComboBox()
        if theme.heading_font:
            self._heading_font.setCurrentFont(QFont(theme.heading_font))
        elif theme.font_family:
            self._heading_font.setCurrentFont(QFont(theme.font_family))
        self._heading_font.currentFontChanged.connect(self._apply_live)
        self._heading_font.currentFontChanged.connect(self._mark_custom)
        form.addRow("Heading font", self._heading_font)
        self._use_heading = QCheckBox("Use a separate heading font (pairing)")
        self._use_heading.setChecked(bool(theme.heading_font))
        self._use_heading.stateChanged.connect(self._apply_live)
        self._use_heading.stateChanged.connect(self._mark_custom)
        form.addRow("", self._use_heading)

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
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        if mode == "element":
            clear = btns.addButton("Clear overrides",
                                   QDialogButtonBox.ButtonRole.ResetRole)
            clear.clicked.connect(self._clear)
        else:
            apply_btn = btns.addButton(QDialogButtonBox.StandardButton.Apply)
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
        s.valueChanged.connect(self._mark_custom)
        return s

    def _clear(self):
        self._cleared = True
        self.accept()

    def _font_family(self):
        return self._font.currentFont().family() if self._use_font.isChecked() else ""

    def _heading_family(self):
        if self._use_heading.isChecked():
            return self._heading_font.currentFont().family()
        return ""

    # ---- presets --------------------------------------------------------

    def _mark_custom(self, *_):
        """A manual edit means the live theme no longer equals any preset."""
        if self._loading or self._preset is None:
            return
        if self._preset.currentText() != presets.CUSTOM:
            self._preset.blockSignals(True)
            self._preset.setCurrentText(presets.CUSTOM)
            self._preset.blockSignals(False)

    def _on_preset_chosen(self, *_):
        name = self._preset.currentText()
        if name == presets.CUSTOM:
            return
        # Layer the preset over the current theme so radius/sizes are kept.
        self._populate_from_theme(presets.theme_for(name, self._base_theme))
        if self.mode == "global" and self._on_apply:
            self._on_apply(self.result_theme())

    def _populate_from_theme(self, theme):
        """Load every control from *theme* without re-triggering preset logic."""
        self._loading = True
        try:
            for key, btn in self._color_btns.items():
                btn.set_color(getattr(theme, key))
            self._palette.set_colors(theme.series)
            self._use_font.setChecked(bool(theme.font_family))
            if theme.font_family:
                self._font.setCurrentFont(QFont(theme.font_family))
            self._use_heading.setChecked(bool(theme.heading_font))
            head = theme.heading_font or theme.font_family
            if head:
                self._heading_font.setCurrentFont(QFont(head))
            self._font_size.setValue(int(theme.font_size))
            self._title_size.setValue(int(theme.title_size))
            self._value_size.setValue(int(theme.value_size))
            if self._radius is not None:
                self._radius.setValue(int(theme.radius))
        finally:
            self._loading = False

    def result_theme(self):
        """Full Theme (global mode)."""
        data = self._base_theme.to_dict()
        for key, btn in self._color_btns.items():
            data[key] = btn.color()
        data["series"] = self._palette.colors()
        data["font_family"] = self._font_family()
        data["heading_font"] = self._heading_family()
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
        ov["heading_font"] = self._heading_family()
        ov["font_size"] = self._font_size.value()
        ov["title_size"] = self._title_size.value()
        ov["value_size"] = self._value_size.value()
        return {k: v for k, v in ov.items() if k in OVERRIDE_KEYS}

    def _apply_live(self, *_):
        if self._loading:
            return
        if self.mode == "global" and self._on_apply:
            self._on_apply(self.result_theme())
