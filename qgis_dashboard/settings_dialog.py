# -*- coding: utf-8 -*-
"""Settings dialogs.

* :class:`SettingsDialog` — the gear-button hub on the rail. A **two-column
  master/detail** dialog: a slim left nav lists the sections (*Appearance*,
  *Layout*, *About*) and the right pane shows that section's controls,
  descriptions and actions. It gathers the configuration-style actions that
  don't belong on the always-visible rail.
"""

from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtWidgets import (
    QDialog, QLabel, QDialogButtonBox, QVBoxLayout, QHBoxLayout,
    QFrame, QSlider, QWidget, QListWidget, QListWidgetItem, QStackedWidget,
    QToolButton,
)

from .icons import monochrome_icon, logo_pixmap

RADIUS_MIN = 0
RADIUS_MAX = 32

# Project description, rendered as rich text in the About panel.
ABOUT_HTML = """
<p style="margin:0 0 10px 0;">&ldquo;Are there any <i>free</i> dashboards in QGIS
that can be connected to a map?&rdquo; my friend Edgar asked one afternoon,
fully expecting a one-word answer.</p>
<p style="margin:0 0 10px 0;">I went looking. There were paid platforms, there
were &ldquo;just export to a web app&rdquo; suggestions, and there was a lot of
helpful silence. So instead of admitting defeat to Edgar, I did the reasonable
thing and built <b>QGIS&nbsp;Dashboard</b> &mdash; ArcGIS-Dashboards-style
interactive dashboards that live right inside QGIS, powered entirely by your
project's own vector layers.</p>
<p style="margin:0 0 10px 0;">You drop in data-driven tiles &mdash; indicators,
charts, lists, a live map, and selectors &mdash; and clicking a value in one
tile cross-filters every other tile in real time. The whole layout tucks itself
neatly inside the QGIS project file, so it's there when you come back.</p>
<p style="margin:0;">It's free, it's open, and it's yours. Edgar got his
dashboard. You get one too.</p>
"""


class SettingsDialog(QDialog):
    """The rail's gear hub: a two-column settings panel.

    *on_appearance* is a no-arg callback that opens the Appearance dialog (the
    window owns the live-preview/revert logic, so we just delegate to it).
    *on_radius* is an optional callback ``f(int)`` applied live as the corner-
    radius slider moves (the change is global and kept — no revert).
    (Export lives on the page tab strip, not here.)
    """

    def __init__(self, on_appearance, parent=None, on_radius=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(640, 460)
        self._on_appearance = on_appearance
        self._on_radius = on_radius

        border, muted = "#e2e6ec", "#55606d"
        accent, accent_hover, brand_soft = "#2b7de9", "#2569c6", "rgba(43,125,233,0.10)"
        radius = 12
        if parent is not None and hasattr(parent, "bus"):
            th = parent.bus.theme
            border = th.border
            muted = th.text_muted
            radius = int(th.radius)
            accent = th.accent
            accent_hover = th._accent_hover()
            brand_soft = th._brand_soft()
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

        self._add_section("Appearance", "style_guide", self._appearance_page())
        self._add_section("Layout", "layout",
                          self._layout_page(radius, muted))
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

    def _appearance_page(self):
        page, lay = self._page_shell("Appearance")

        hint = QLabel(
            "Theme the whole dashboard — background, text, accent, fonts and "
            "the chart color palette. Pick a ready-made preset or fine-tune "
            "every color by hand.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:%s;" % self._muted)
        lay.addWidget(hint)

        # Open Appearance is now an icon button (the Fluent "style guide" glyph)
        # with a text caption beside it for discoverability.
        row = QHBoxLayout()
        row.setSpacing(12)
        btn = QToolButton()
        btn.setObjectName("appearanceIconBtn")
        btn.setIcon(monochrome_icon("style_guide", "#ffffff"))
        btn.setIconSize(QSize(22, 22))
        btn.setFixedSize(44, 44)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Open Appearance")
        btn.setAccessibleName("Open Appearance")
        btn.setStyleSheet(
            "#appearanceIconBtn { background:%s; border:none; border-radius:12px; }"
            "#appearanceIconBtn:hover { background:%s; }"
            "#appearanceIconBtn:pressed { background:%s; }"
            % (self._accent, self._accent_hover, self._accent_hover))
        btn.clicked.connect(self._open_appearance)
        row.addWidget(btn)

        caption = QLabel("Open Appearance editor")
        caption.setStyleSheet("font-weight:600;")
        row.addWidget(caption)
        row.addStretch(1)
        lay.addLayout(row)

        lay.addStretch(1)
        return page

    def _layout_page(self, radius, muted):
        page, lay = self._page_shell("Layout")

        radius_hint = QLabel(
            "Corner roundness of every dashboard element. Slide to preview the "
            "change live on the dashboard behind this dialog.")
        radius_hint.setWordWrap(True)
        radius_hint.setStyleSheet("color:%s;" % muted)
        lay.addWidget(radius_hint)

        radius_row = QHBoxLayout()
        radius_row.setSpacing(10)
        radius_row.addWidget(QLabel("Corner radius"))
        self._radius_slider = QSlider(Qt.Orientation.Horizontal)
        self._radius_slider.setRange(RADIUS_MIN, RADIUS_MAX)
        self._radius_slider.setValue(max(RADIUS_MIN, min(RADIUS_MAX, radius)))
        self._radius_slider.setSingleStep(1)
        self._radius_slider.setPageStep(2)
        radius_row.addWidget(self._radius_slider, 1)
        self._radius_value = QLabel("%d px" % radius)
        self._radius_value.setMinimumWidth(42)
        self._radius_value.setAlignment(Qt.AlignmentFlag.AlignRight
                                        | Qt.AlignmentFlag.AlignVCenter)
        self._radius_value.setStyleSheet("color:%s;" % muted)
        radius_row.addWidget(self._radius_value)
        lay.addLayout(radius_row)
        self._radius_slider.valueChanged.connect(self._on_radius_changed)

        lay.addStretch(1)
        return page

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

    def _open_appearance(self):
        if callable(self._on_appearance):
            self._on_appearance()

    def _on_radius_changed(self, value):
        self._radius_value.setText("%d px" % value)
        if callable(self._on_radius):
            self._on_radius(value)
