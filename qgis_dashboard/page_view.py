# -*- coding: utf-8 -*-
"""PageView — a page surface: an optional docked header banner around a
scroll-area-wrapped DashboardCanvas (which owns the page's zoom/pan).

``PageView`` used to *be* the scroll area. It is now a thin container so it can
host a :class:`~elements.header.HeaderElement` banner docked on one edge of the
page (top / bottom / left / right) *outside* the scrolling canvas, with the
canvas filling the rest. The scroll/zoom/pan behavior lives unchanged in the
private :class:`_CanvasScroll`; ``PageView`` keeps the original public API
(``canvas``, ``zoom``/``set_zoom``/``zoom_in``/``zoom_out``/``reset_zoom``) by
delegating to it, and adds :meth:`set_header`.

The banner is outside the scroll area, so it stays fixed while the grid
zooms/pans — correct behavior for brand chrome. Zoom is view-only, never
persisted.
"""

from qgis.PyQt.QtCore import Qt, QPoint
from qgis.PyQt.QtWidgets import QScrollArea, QWidget, QBoxLayout

from .elements.header_layout import box_direction

ZOOM_MIN = 0.5
ZOOM_MAX = 3.0
ZOOM_STEP = 1.2


def clamp_zoom(z):
    return max(ZOOM_MIN, min(float(z), ZOOM_MAX))


class _CanvasScroll(QScrollArea):
    """Scroll area wrapping one canvas; manages its zoom level and panning."""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        # Named so the canvas-background QSS rule can target this scroll area
        # (and only this one) — see Theme.window_qss.
        self.setObjectName("dashPageView")
        self.setWidget(canvas)
        # The canvas manages its own size (content extent x zoom), so we never
        # let the scroll area stretch it to the viewport.
        self.setWidgetResizable(False)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self._zoom = 1.0
        self._pan_origin = None
        self._pan_scroll = None

    def zoom(self):
        return self._zoom

    def set_zoom(self, z):
        self._zoom = clamp_zoom(z)
        self.canvas.set_zoom(self._zoom)
        return self._zoom

    def zoom_in(self):
        return self.set_zoom(self._zoom * ZOOM_STEP)

    def zoom_out(self):
        return self.set_zoom(self._zoom / ZOOM_STEP)

    def reset_zoom(self):
        return self.set_zoom(1.0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # the viewport changed — let the canvas refill it (it reads our
        # viewport size) without altering any tile's logical placement
        if hasattr(self.canvas, "sync_size"):
            self.canvas.sync_size()

    # ---- middle-mouse panning ----

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.MiddleButton:
            self._pan_origin = e.pos()
            self._pan_scroll = QPoint(
                self.horizontalScrollBar().value(),
                self.verticalScrollBar().value())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._pan_origin is not None:
            d = e.pos() - self._pan_origin
            self.horizontalScrollBar().setValue(self._pan_scroll.x() - d.x())
            self.verticalScrollBar().setValue(self._pan_scroll.y() - d.y())
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.MiddleButton and self._pan_origin is not None:
            self._pan_origin = None
            self.unsetCursor()
            return
        super().mouseReleaseEvent(e)


class PageView(QWidget):
    """One page: an optional docked header banner around a scrolling canvas."""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.setObjectName("dashPageWrap")
        self._scroll = _CanvasScroll(canvas, self)
        self._header = None
        self._lay = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        self._lay.addWidget(self._scroll, 1)

    # ---- zoom/pan delegation (preserves the original PageView API) ----

    @property
    def canvas(self):
        return self._scroll.canvas

    def zoom(self):
        return self._scroll.zoom()

    def set_zoom(self, z):
        return self._scroll.set_zoom(z)

    def zoom_in(self):
        return self._scroll.zoom_in()

    def zoom_out(self):
        return self._scroll.zoom_out()

    def reset_zoom(self):
        return self._scroll.reset_zoom()

    # ---- docked header banner ----

    def header(self):
        return self._header

    def set_header(self, element):
        """Dock *element* (a HeaderElement) on the page edge from its config,
        or remove the current banner when *element* is ``None``."""
        if self._header is not None:
            self._lay.removeWidget(self._header)
            self._header.setParent(None)
            self._header.deleteLater()
            self._header = None
        anchor = "top"
        if element is not None:
            cfg = getattr(element, "config", {}) or {}
            anchor = cfg.get("anchor", "top")
            thickness = int(cfg.get("thickness", 80) or 80)
            element.setParent(self)
            orient, _first = box_direction(anchor)
            if orient == "v":
                element.setFixedHeight(thickness)
            else:
                element.setFixedWidth(thickness)
            self._header = element
        self._relayout(anchor)

    def _relayout(self, anchor):
        lay = self._lay
        lay.removeWidget(self._scroll)
        if self._header is not None:
            lay.removeWidget(self._header)
        orient, banner_first = box_direction(anchor)
        lay.setDirection(QBoxLayout.Direction.TopToBottom if orient == "v"
                         else QBoxLayout.Direction.LeftToRight)
        if self._header is not None and banner_first:
            lay.addWidget(self._header, 0)
        lay.addWidget(self._scroll, 1)
        if self._header is not None and not banner_first:
            lay.addWidget(self._header, 0)
