# -*- coding: utf-8 -*-
"""Header (brand banner) element.

A presentational banner — no data binding, no cross-filtering — that acts as
the dashboard's brand chrome. It carries a styled title (custom font family /
size / alignment chosen from the installed QGIS/Qt fonts) and a single logo
image in an anchored slot (left / right / above / below the title).

It **is** wrapped in a :class:`~dashboard_canvas.GridTile` like every other
tile — the canvas hosts it free-form (drag / resize / snap) and the tile
provides the move/resize/menu chrome and the Build/Use lock — so this element
only renders its title + logo. ``anchor``/``thickness`` are no longer used (a
tile has free geometry).

``config`` keys: ``title``, ``font_family``, ``font_size``, ``align``,
``logo_path``, ``logo_slot``, ``logo_size``.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap, QImage, QPainter
from qgis.PyQt.QtWidgets import QLabel, QBoxLayout

from .base import DashboardElement
from .header_layout import inner_box_direction

try:
    from qgis.PyQt.QtSvg import QSvgRenderer
except ImportError:          # QtSvg is optional on some builds
    QSvgRenderer = None

# Mirrors theme.Theme._FONT_FALLBACK so a chosen family degrades gracefully.
_FONT_FALLBACK = '"Segoe UI", "Helvetica Neue", Arial, sans-serif'

_ALIGN = {
    "left": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    "center": Qt.AlignmentFlag.AlignCenter,
    "right": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
}

_DIRECTION = {
    "h": QBoxLayout.Direction.LeftToRight,
    "v": QBoxLayout.Direction.TopToBottom,
}


class HeaderElement(DashboardElement):
    type_name = "header"
    is_filter_source = False
    accepts_filter = False

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        # the banner is its own content — drop the base title / description chrome
        self.title_label.hide()
        self.desc_label.hide()

        self._logo = QLabel("")
        self._logo.setObjectName("headerLogo")
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title = QLabel("")
        self._title.setObjectName("headerTitle")
        self._title.setWordWrap(False)

        self._inner = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._inner.setContentsMargins(0, 0, 0, 0)
        self._inner.setSpacing(12)
        self.body.addLayout(self._inner, 1)

        self.apply_theme()
        self.refresh()

    # ---- content ----

    def refresh(self):
        cfg = self.config
        size = int(cfg.get("logo_size", 40) or 40)
        pm = self._logo_pixmap((cfg.get("logo_path") or "").strip(), size)
        if pm is not None:
            self._logo.setPixmap(pm)
            self._logo.show()
        else:
            self._logo.clear()
            self._logo.hide()
        self._title.setText(cfg.get("title", "") or "")
        self._rebuild_inner(cfg.get("logo_slot", "left"))
        self._restyle()

    def _rebuild_inner(self, slot):
        lay = self._inner
        lay.removeWidget(self._logo)
        lay.removeWidget(self._title)
        orient, logo_first = inner_box_direction(slot)
        lay.setDirection(_DIRECTION[orient])
        if logo_first:
            lay.addWidget(self._logo, 0)
            lay.addWidget(self._title, 1)
        else:
            lay.addWidget(self._title, 1)
            lay.addWidget(self._logo, 0)

    def _restyle(self):
        th = self.effective_theme()
        family = self.config.get("font_family") or th.font_family
        size = int(self.config.get("font_size", 22) or 22)
        align = self.config.get("align", "left")
        self._title.setAlignment(_ALIGN.get(align, _ALIGN["left"]))
        self._title.setStyleSheet(
            'color:{c}; font-family:"{f}", {fb}; font-size:{s}px;'
            "font-weight:700; background:transparent;".format(
                c=th.text, f=family, fb=_FONT_FALLBACK, s=size))

    # ---- logo loading (raster + SVG; static is enough for a brand mark) ----

    def _logo_pixmap(self, path, size):
        if not path or not os.path.isfile(path):
            return None
        ext = os.path.splitext(path)[1].lower()
        if ext == ".svg" and QSvgRenderer is not None:
            renderer = QSvgRenderer(path)
            if not renderer.isValid():
                return None
            img = QImage(size, size, QImage.Format.Format_ARGB32)
            img.fill(Qt.GlobalColor.transparent)
            painter = QPainter(img)
            renderer.render(painter)
            painter.end()
            return QPixmap.fromImage(img)
        pm = QPixmap(path)
        if pm.isNull():
            return None
        return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)

