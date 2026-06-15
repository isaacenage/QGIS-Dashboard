# -*- coding: utf-8 -*-
"""Settings dialogs.

* :class:`SettingsDialog` — the gear-button hub on the rail. It gathers the
  configuration-style actions that don't belong on the always-visible rail
  (currently: Appearance) plus an "About" panel.
* :class:`GridSettingsDialog` — set how many columns and rows the snap grid
  has. More cells = finer placement and smaller default tiles; fewer cells =
  coarser, bigger tiles.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QFormLayout, QSpinBox, QLabel, QDialogButtonBox,
    QVBoxLayout, QPushButton, QFrame,
)

# The dramatic origin story, rendered as rich text in the About panel.
ABOUT_HTML = """
<p style="margin:0 0 10px 0;">It began with a single, innocent question.</p>
<p style="margin:0 0 10px 0;">A friend leaned over and asked Isaac Enage:
<i>&ldquo;Is ArcGIS&nbsp;Dashboards&nbsp;free?&rdquo;</i></p>
<p style="margin:0 0 10px 0;">It is not. It never was.</p>
<p style="margin:0 0 10px 0;">Where a lesser developer would have shrugged and
closed the tab, Isaac saw a gauntlet thrown at his feet. If the giants would
not give it away, then he would <b>build it himself</b> &mdash; tile by tile,
filter by filter, pixel by stubborn pixel &mdash; and hand it to his friend for
nothing.</p>
<p style="margin:0 0 10px 0;">Nights bled into mornings. Cross-filters were
wired by hand. A signal bus was born. And from that one slightly unreasonable
question rose <b>this</b>: a free, open dashboard for everyone who ever wanted
ArcGIS&nbsp;Dashboards without the invoice.</p>
<p style="margin:0;">Built with love, caffeine, and a little spite &mdash; by
<b>Isaac Enage</b>, for a friend.</p>
"""


class SettingsDialog(QDialog):
    """The rail's gear hub: configuration actions + an About panel.

    *on_appearance* is a no-arg callback that opens the Appearance dialog (the
    window owns the live-preview/revert logic, so we just delegate to it).
    *on_export* is an optional no-arg callback that runs the HTML export.
    """

    def __init__(self, on_appearance, parent=None, on_export=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self._on_appearance = on_appearance
        self._on_export = on_export

        border, muted = "#e2e6ec", "#55606d"
        if parent is not None and hasattr(parent, "bus"):
            border = parent.bus.theme.border
            muted = parent.bus.theme.text_muted

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(12)

        # ---- Appearance -------------------------------------------------
        appearance_caption = QLabel("Appearance")
        appearance_caption.setStyleSheet("font-weight:600;")
        root.addWidget(appearance_caption)

        appearance_hint = QLabel(
            "Theme the whole dashboard — background, text, accent, fonts and "
            "the chart color palette.")
        appearance_hint.setWordWrap(True)
        appearance_hint.setStyleSheet("color:%s;" % muted)
        root.addWidget(appearance_hint)

        appearance_btn = QPushButton("Open Appearance…")
        appearance_btn.setProperty("variant", "secondary")
        appearance_btn.setCursor(Qt.PointingHandCursor)
        appearance_btn.clicked.connect(self._open_appearance)
        root.addWidget(appearance_btn)

        # ---- Export ------------------------------------------------------
        if self._on_export is not None:
            root.addWidget(self._separator(border))
            export_caption = QLabel("Export")
            export_caption.setStyleSheet("font-weight:600;")
            root.addWidget(export_caption)

            export_hint = QLabel(
                "Save this dashboard as a single, self-contained HTML file — "
                "open it in any browser, offline, with live cross-filtering.")
            export_hint.setWordWrap(True)
            export_hint.setStyleSheet("color:%s;" % muted)
            root.addWidget(export_hint)

            export_btn = QPushButton("Export to HTML…")
            export_btn.setProperty("variant", "secondary")
            export_btn.setCursor(Qt.PointingHandCursor)
            export_btn.clicked.connect(self._open_export)
            root.addWidget(export_btn)

        root.addWidget(self._separator(border))

        # ---- About ------------------------------------------------------
        about_caption = QLabel("About QGIS Dashboard")
        about_caption.setStyleSheet("font-weight:600;")
        root.addWidget(about_caption)

        story = QLabel(ABOUT_HTML)
        story.setTextFormat(Qt.RichText)
        story.setWordWrap(True)
        story.setOpenExternalLinks(True)
        root.addWidget(story)

        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

    def _separator(self, color):
        line = QFrame(self)
        line.setFixedHeight(1)
        line.setStyleSheet("background:%s; border:none;" % color)
        return line

    def _open_appearance(self):
        if callable(self._on_appearance):
            self._on_appearance()

    def _open_export(self):
        if callable(self._on_export):
            self.accept()
            self._on_export()


class GridSettingsDialog(QDialog):
    def __init__(self, cols, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dashboard grid settings")
        form = QFormLayout(self)

        form.addRow(QLabel("The dashboard snaps tiles to an invisible grid.\n"
                           "Adjust its resolution below."))

        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 48)
        self.cols_spin.setValue(int(cols))
        form.addRow("Columns (horizontal)", self.cols_spin)

        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 48)
        self.rows_spin.setValue(int(rows))
        form.addRow("Rows (vertical)", self.rows_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def result_grid(self):
        return self.cols_spin.value(), self.rows_spin.value()
