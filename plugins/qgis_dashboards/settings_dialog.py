# -*- coding: utf-8 -*-
"""Settings dialogs.

* :class:`SettingsDialog` — the gear-button hub on the rail. A **two-column
  master/detail** dialog: a slim left nav lists the sections (*Themes*,
  *Layout*, *About*) and the right pane shows that section's controls,
  descriptions and actions. It gathers the configuration-style actions that
  don't belong on the always-visible rail.

  *Themes* edits the dashboard **theme** — the colors, chart palette and fonts
  that style the **canvas elements only** (the plugin chrome keeps a fixed
  System font). *Layout* gathers everything geometric — corner radius, element
  spacing and text sizes — so the two sections never overlap.
"""

from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtWidgets import (
    QDialog, QLabel, QDialogButtonBox, QVBoxLayout, QHBoxLayout,
    QFrame, QSlider, QWidget, QListWidget, QListWidgetItem, QStackedWidget,
    QSpinBox, QFormLayout, QComboBox,
)

from .icons import monochrome_icon, logo_pixmap
from .appearance_dialog import AppearanceForm
from .theme import Theme, SYSTEM_FONT_FAMILY, CHROME

RADIUS_MIN = 0
RADIUS_MAX = 32
GAP_MIN = 0
GAP_MAX = 48
CANVAS_DIM_MIN = 320
CANVAS_DIM_MAX = 8000

# Export/print region presets: (label, width, height). "Custom…" is appended in
# code; editing a spinner flips the combo to it.
CANVAS_PRESETS = [
    ("16:9 — 1280 × 720", 1280, 720),
    ("16:9 — 1920 × 1080", 1920, 1080),
    ("16:10 — 1280 × 800", 1280, 800),
    ("4:3 — 1024 × 768", 1024, 768),
    ("A4 Landscape — 1754 × 1240", 1754, 1240),
    ("A4 Portrait — 1240 × 1754", 1240, 1754),
    ("Letter Landscape — 1650 × 1275", 1650, 1275),
]
CUSTOM_LABEL = "Custom…"

# Project description, rendered as rich text in the About panel.
ABOUT_HTML = """
<p style="margin:0 0 10px 0;">&ldquo;Are there any <i>free</i> dashboards in
QGIS that can be connected to the map we make?&rdquo; my friend Edgar asked.</p>
<p style="margin:0 0 10px 0;">That simple question actually pointed out a pretty
big missing piece in QGIS. When you look around for options, you quickly realize
you either have to pay for a premium platform or go through the hassle of
exporting your data into a completely separate web app. Nothing just worked
natively inside the software for free. So, the <b>QGIS&nbsp;Dashboard</b> plugin
was built to fix exactly that.</p>
<p style="margin:0 0 10px 0;">It lets you create interactive dashboard layouts
that live right inside your QGIS project, using the vector layers you already
have set up. You can just drop in data-driven tiles like charts, lists,
indicators, selectors, and even a live map. The coolest part is that everything
is connected, so when you click a value in one tile, it instantly filters all
the other tiles in real time.</p>
<p style="margin:0;">On top of that, the whole layout saves automatically inside
your QGIS project file so you don't lose anything, and since it's completely
free and open-source, anyone can use it.</p>
"""


class SettingsDialog(QDialog):
    """The rail's gear hub: a two-column settings panel.

    The *Themes* section embeds the whole-dashboard theme editor inline (no
    extra dialog hop): *theme* seeds it and *on_appearance* — a callback
    ``f(Theme)`` — applies each edit live and keeps it. The theme styles the
    canvas elements only; the plugin chrome keeps a fixed System font.

    The *Layout* section gathers the geometric settings, all applied live:
    *on_canvas_size* ``f(w, h)`` (the export/print region — the page size),
    *on_radius* ``f(int)`` (corner radius), *on_gap* ``f(int)`` (element gap /
    spacing) and *on_size* ``f(key, int)`` where *key* is one of
    ``font_size`` / ``title_size`` / ``value_size`` (the text sizes). *gap*
    seeds the spacing slider; *canvas_size* ``(w, h)`` seeds the page-size
    controls; *theme* seeds the text-size spinners. (Export lives on the page
    tab strip, not here.)
    """

    def __init__(self, parent=None, theme=None, on_appearance=None,
                 on_radius=None, on_gap=None, on_size=None,
                 on_canvas_size=None, gap=0, canvas_size=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(680, 560)
        self._theme = theme
        self._on_appearance = on_appearance
        self._on_radius = on_radius
        self._on_gap = on_gap
        self._on_size = on_size
        self._on_canvas_size = on_canvas_size
        self._gap = int(gap)
        cw, ch = canvas_size or (CANVAS_PRESETS[0][1], CANVAS_PRESETS[0][2])
        self._canvas_w, self._canvas_h = int(cw), int(ch)
        # guard so programmatic spinner/combo updates don't re-enter the callback
        self._canvas_syncing = False

        # The Settings dialog is CHROME: its colors come from the fixed CHROME
        # palette, never the dashboard theme (a dark preset must not recolor the
        # nav or its text). Only the corner-radius value is read from the theme,
        # because it seeds the (canvas) radius slider on the Layout page.
        border, muted = CHROME["border"], CHROME["muted"]
        accent = CHROME["accent"]
        accent_hover, brand_soft = CHROME["accent_hover"], CHROME["brand_soft"]
        radius = 12
        if parent is not None and hasattr(parent, "bus"):
            radius = int(parent.bus.theme.radius)
        self._muted = muted
        self._accent = accent
        self._accent_hover = accent_hover
        self._brand_soft = brand_soft

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        # ---- left: section nav (master) --------------------------------
        self._nav = QListWidget()
        self._nav.setObjectName("settingsNav")
        self._nav.setFixedWidth(190)
        self._nav.setIconSize(QSize(18, 18))
        self._nav.setFrameShape(QFrame.Shape.NoFrame)
        self._nav.setStyleSheet(
            "#settingsNav { background:transparent; border:none;"
            " border-right:1px solid %s; padding:10px 8px; outline:none; }"
            "#settingsNav::item { padding:9px 12px; border-radius:8px;"
            " margin:2px 4px; color:%s; }"
            "#settingsNav::item:hover { background:%s; }"
            "#settingsNav::item:selected { background:%s; color:%s;"
            " font-weight:600; }"
            % (border, muted, brand_soft, brand_soft, accent))
        body.addWidget(self._nav)

        # ---- right: stacked detail panes --------------------------------
        self._stack = QStackedWidget()
        self._stack.setObjectName("settingsStack")
        body.addWidget(self._stack, 1)

        self._add_section("Themes", "style_guide", self._themes_page())
        self._add_section("Layout", "layout",
                          self._layout_page(radius, self._gap, muted))
        self._add_section("About", "info", self._about_page())

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav.setCurrentRow(0)

        # ---- footer -----------------------------------------------------
        footer = QFrame()
        footer.setStyleSheet("border-top:1px solid %s;" % border)
        frow = QHBoxLayout(footer)
        frow.setContentsMargins(22, 10, 22, 12)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        frow.addStretch(1)
        frow.addWidget(buttons)
        root.addWidget(footer)

    # ---- nav plumbing ---------------------------------------------------

    def _add_section(self, title, icon_name, page):
        item = QListWidgetItem(monochrome_icon(icon_name, self._muted), title)
        self._nav.addItem(item)
        self._stack.addWidget(page)

    # ---- pages ----------------------------------------------------------

    def _page_shell(self, title):
        """A blank detail page with a bold caption; returns (page, layout)."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(12)
        caption = QLabel(title)
        caption.setStyleSheet("font-size:16px; font-weight:600;")
        lay.addWidget(caption)
        return page, lay

    def _themes_page(self):
        page, lay = self._page_shell("Themes")

        hint = QLabel(
            "Theme the dashboard <b>canvas</b> — background, text, accent, "
            "fonts and the chart color palette. Pick a ready-made preset or "
            "fine-tune every color by hand. Changes apply live as you edit.")
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setWordWrap(True)
        hint.setStyleSheet("color:%s;" % self._muted)
        lay.addWidget(hint)

        # Make the canvas-only scope explicit: the surrounding plugin interface
        # always uses the fixed System font, never the theme's fonts.
        sys_note = QLabel(
            "The theme fonts style the dashboard elements only. The plugin "
            "interface uses a fixed <b>System font</b> ({}) that can't be "
            "changed.".format(SYSTEM_FONT_FAMILY))
        sys_note.setTextFormat(Qt.TextFormat.RichText)
        sys_note.setWordWrap(True)
        sys_note.setStyleSheet("color:%s; font-size:11px;" % self._muted)
        lay.addWidget(sys_note)

        # The whole-dashboard theme editor lives inline here (no extra dialog),
        # applying each edit live via on_appearance.
        theme = self._theme if self._theme is not None else Theme.default()
        self._appearance_form = AppearanceForm(
            theme, mode="global", on_apply=self._on_appearance)
        lay.addWidget(self._appearance_form, 1)
        return page

    def _layout_page(self, radius, gap, muted):
        page, lay = self._page_shell("Layout")

        intro = QLabel(
            "Page size, shape, spacing and text sizes for the dashboard. Every "
            "control previews live on the dashboard behind this dialog.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color:%s;" % muted)
        lay.addWidget(intro)

        # --- Canvas size (the export/print region) -------------------------
        self._add_subheading(lay, "Canvas size")
        canvas_hint = QLabel(
            "The page your dashboard is laid out on — shown as a framed "
            "rectangle on the canvas and the exact area that exports to "
            "PNG/PDF. Reset Zoom fits this page to the view.")
        canvas_hint.setWordWrap(True)
        canvas_hint.setStyleSheet("color:%s; font-size:11px;" % muted)
        lay.addWidget(canvas_hint)
        self._build_canvas_size_controls(lay, muted)

        # --- Corner radius -------------------------------------------------
        self._add_subheading(lay, "Shape")
        radius_hint = QLabel("Corner roundness of every dashboard element.")
        radius_hint.setWordWrap(True)
        radius_hint.setStyleSheet("color:%s; font-size:11px;" % muted)
        lay.addWidget(radius_hint)

        self._radius_slider, self._radius_value = self._slider_row(
            lay, "Corner radius", radius, RADIUS_MIN, RADIUS_MAX,
            page_step=2, muted=muted, on_change=self._on_radius_changed)

        # --- Element gap / spacing (below the corner-radius slider) --------
        self._add_subheading(lay, "Spacing")
        gap_hint = QLabel(
            "Breathing room around every dashboard element. At 0 px cards can "
            "sit edge to edge; slide right to inset each card so a consistent "
            "gap always shows between elements — no matter how you arrange "
            "them.")
        gap_hint.setWordWrap(True)
        gap_hint.setStyleSheet("color:%s; font-size:11px;" % muted)
        lay.addWidget(gap_hint)

        self._gap_slider, self._gap_value = self._slider_row(
            lay, "Element gap", int(gap), GAP_MIN, GAP_MAX,
            page_step=4, muted=muted, on_change=self._on_gap_changed)

        # --- Text sizes ----------------------------------------------------
        self._add_subheading(lay, "Text size")
        sizes_hint = QLabel("Type sizes used inside every dashboard element.")
        sizes_hint.setWordWrap(True)
        sizes_hint.setStyleSheet("color:%s; font-size:11px;" % muted)
        lay.addWidget(sizes_hint)

        theme = self._theme if self._theme is not None else Theme.default()
        sizes = QFormLayout()
        sizes.setContentsMargins(0, 0, 0, 0)
        sizes.setHorizontalSpacing(12)
        self._base_size_spin = self._size_spin(theme.font_size, 6, 48, "font_size")
        sizes.addRow("Base text", self._base_size_spin)
        self._title_size_spin = self._size_spin(theme.title_size, 8, 48, "title_size")
        sizes.addRow("Element title", self._title_size_spin)
        self._value_size_spin = self._size_spin(theme.value_size, 10, 96, "value_size")
        sizes.addRow("Indicator value", self._value_size_spin)
        lay.addLayout(sizes)

        lay.addStretch(1)
        return page

    # ---- layout-control builders ---------------------------------------

    def _add_subheading(self, lay, text):
        label = QLabel(text)
        label.setStyleSheet("font-weight:600; margin-top:6px;")
        lay.addWidget(label)

    def _slider_row(self, lay, label, value, lo, hi, page_step, muted,
                    on_change):
        """Build a labelled slider + live "N px" readout; returns (slider, lbl)."""
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel(label))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(max(lo, min(hi, int(value))))
        slider.setSingleStep(1)
        slider.setPageStep(page_step)
        row.addWidget(slider, 1)
        readout = QLabel("%d px" % int(value))
        readout.setMinimumWidth(42)
        readout.setAlignment(Qt.AlignmentFlag.AlignRight
                             | Qt.AlignmentFlag.AlignVCenter)
        readout.setStyleSheet("color:%s;" % muted)
        row.addWidget(readout)
        lay.addLayout(row)
        slider.valueChanged.connect(on_change)
        return slider, readout

    def _size_spin(self, value, lo, hi, key):
        spin = QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(int(value))
        spin.setSuffix(" px")
        spin.valueChanged.connect(lambda v, k=key: self._on_size_changed(k, v))
        return spin

    def _build_canvas_size_controls(self, lay, muted):
        """Preset combo + width/height spinners for the export/print region."""
        self._canvas_combo = QComboBox()
        for label, _w, _h in CANVAS_PRESETS:
            self._canvas_combo.addItem(label)
        self._canvas_combo.addItem(CUSTOM_LABEL)
        self._canvas_combo.currentIndexChanged.connect(self._on_canvas_preset)
        lay.addWidget(self._canvas_combo)

        row = QHBoxLayout()
        row.setSpacing(10)
        self._canvas_w_spin = QSpinBox()
        self._canvas_w_spin.setRange(CANVAS_DIM_MIN, CANVAS_DIM_MAX)
        self._canvas_w_spin.setSuffix(" px")
        self._canvas_w_spin.setValue(self._canvas_w)
        self._canvas_h_spin = QSpinBox()
        self._canvas_h_spin.setRange(CANVAS_DIM_MIN, CANVAS_DIM_MAX)
        self._canvas_h_spin.setSuffix(" px")
        self._canvas_h_spin.setValue(self._canvas_h)
        row.addWidget(QLabel("Width"))
        row.addWidget(self._canvas_w_spin, 1)
        sep = QLabel("×")
        sep.setStyleSheet("color:%s;" % muted)
        row.addWidget(sep)
        row.addWidget(QLabel("Height"))
        row.addWidget(self._canvas_h_spin, 1)
        lay.addLayout(row)

        self._canvas_w_spin.valueChanged.connect(self._on_canvas_spin)
        self._canvas_h_spin.valueChanged.connect(self._on_canvas_spin)
        self._sync_canvas_combo()   # preselect the matching preset (or Custom)

    def _about_page(self):
        page, lay = self._page_shell("About QGIS Dashboard")

        logo = QLabel()
        logo.setPixmap(logo_pixmap(48))
        lay.addWidget(logo)

        story = QLabel(ABOUT_HTML)
        story.setTextFormat(Qt.TextFormat.RichText)
        story.setWordWrap(True)
        story.setOpenExternalLinks(True)
        lay.addWidget(story)

        lay.addStretch(1)
        return page

    # ---- callbacks ------------------------------------------------------

    def _on_radius_changed(self, value):
        self._radius_value.setText("%d px" % value)
        if callable(self._on_radius):
            self._on_radius(value)

    def _on_gap_changed(self, value):
        self._gap_value.setText("%d px" % value)
        if callable(self._on_gap):
            self._on_gap(value)

    def _on_size_changed(self, key, value):
        if callable(self._on_size):
            self._on_size(key, value)

    # ---- canvas-size (export/print region) callbacks --------------------

    def _sync_canvas_combo(self):
        """Preselect the preset matching the current size, else ``Custom…``."""
        idx = next((i for i, (_l, w, h) in enumerate(CANVAS_PRESETS)
                    if w == self._canvas_w and h == self._canvas_h),
                   self._canvas_combo.count() - 1)   # last item is Custom…
        self._canvas_syncing = True
        self._canvas_combo.setCurrentIndex(idx)
        self._canvas_syncing = False

    def _on_canvas_preset(self, index):
        """A preset was picked — push its size into the spinners and apply."""
        if self._canvas_syncing or index < 0 or index >= len(CANVAS_PRESETS):
            return   # Custom… (or a programmatic sync) makes no size change
        _label, w, h = CANVAS_PRESETS[index]
        self._canvas_syncing = True
        self._canvas_w_spin.setValue(w)
        self._canvas_h_spin.setValue(h)
        self._canvas_syncing = False
        self._apply_canvas_size()

    def _on_canvas_spin(self, _value):
        """A width/height edit — flip the combo to Custom… and apply."""
        if self._canvas_syncing:
            return
        self._sync_canvas_combo()
        self._apply_canvas_size()

    def _apply_canvas_size(self):
        self._canvas_w = int(self._canvas_w_spin.value())
        self._canvas_h = int(self._canvas_h_spin.value())
        if callable(self._on_canvas_size):
            self._on_canvas_size(self._canvas_w, self._canvas_h)
