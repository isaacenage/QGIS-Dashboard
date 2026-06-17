# -*- coding: utf-8 -*-
"""Text / heading element.

A presentational container — no data binding, no cross-filtering — for free
text such as a dashboard heading, a caption or a note. The text is edited
in-place by **double-clicking** the tile (a multi-line prompt), and styled from
the active :class:`~theme.Theme`: an optional *heading* style renders it large
and bold, and the text can be left/centre/right aligned.

It is a pure container: ``is_filter_source = accepts_filter = False`` so it
never appears as a cross-filter source or target (the connections dialog shows
it the "doesn't take part" note).
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QLabel, QInputDialog
from qgis.core import QgsProject
from .base import DashboardElement

_ALIGN = {
    "left": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    "center": Qt.AlignmentFlag.AlignCenter,
    "right": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
}

_PLACEHOLDER = "Double-click to edit text"


class TextElement(DashboardElement):
    type_name = "text"
    is_filter_source = False
    accepts_filter = False

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        # this tile *is* its text — drop the base title / description chrome
        self.title_label.hide()
        self.desc_label.hide()

        self._label = QLabel("")
        self._label.setObjectName("textTile")
        self._label.setWordWrap(True)
        self._label.setMinimumSize(1, 1)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.body.addWidget(self._label, 1)

        self.apply_theme()
        self.refresh()

    # ---- content ----

    def refresh(self):
        text = self.config.get("text", "")
        align = self.config.get("align", "left")
        self._label.setAlignment(_ALIGN.get(align, _ALIGN["left"]))
        self._label.setText(text or _PLACEHOLDER)
        self._restyle()

    def _restyle(self):
        th = self.effective_theme()
        is_heading = bool(self.config.get("heading"))
        is_empty = not self.config.get("text")
        size = int(round(th.title_size * 1.7)) if is_heading else th.font_size
        weight = 700 if is_heading else 400
        # muted, lighter weight while empty so the placeholder reads as a hint
        color = th.text_muted if is_empty else th.text
        self._label.setStyleSheet(
            "color:{color}; font-family:{family}; font-size:{size}px;"
            "font-weight:{weight}; font-style:{style}; background:transparent;".format(
                color=color, family=th.font_stack(), size=size,
                weight=400 if is_empty else weight,
                style="italic" if is_empty else "normal"))

    # ---- in-place editing ----

    def on_tile_double_click(self):
        # Editing the text is a Build-mode action: in Use mode (locked) the tile
        # is fixed, so a double-click does nothing. Routed here both from the
        # Build-mode drag overlay (which covers the whole tile) and from a direct
        # double-click on the tile.
        if self._interactive:
            return
        current = self.config.get("text", "")
        text, ok = QInputDialog.getMultiLineText(
            self, "Edit text", "Text:", current)
        if ok:
            self.config["text"] = text
            self.refresh()
            QgsProject.instance().setDirty(True)   # capture the edit on next save

    def mouseDoubleClickEvent(self, event):
        self.on_tile_double_click()
        super().mouseDoubleClickEvent(event)
