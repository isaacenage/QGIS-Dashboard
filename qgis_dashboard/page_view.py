# -*- coding: utf-8 -*-
"""PageView — a scroll-area wrapper that adds zoom/pan to one DashboardCanvas.

Scale-on-fill: at zoom 1.0 the canvas fills the viewport (the original
responsive behavior). Above 1.0 the canvas is given a fixed size of
``viewport x zoom`` so it overflows the viewport and the scroll bars (plus
middle-mouse drag) let the user pan. Zoom is view-only and never persisted.
"""

from qgis.PyQt.QtCore import Qt, QPoint
from qgis.PyQt.QtWidgets import QScrollArea

ZOOM_MIN = 0.5
ZOOM_MAX = 3.0
ZOOM_STEP = 1.2


def clamp_zoom(z):
    return max(ZOOM_MIN, min(float(z), ZOOM_MAX))


class PageView(QScrollArea):
    """Holds one canvas; manages its zoom level and panning."""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setWidget(canvas)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self._zoom = 1.0
        self._pan_origin = None
        self._pan_scroll = None

    def zoom(self):
        return self._zoom

    def set_zoom(self, z):
        self._zoom = clamp_zoom(z)
        self._apply_zoom()
        return self._zoom

    def zoom_in(self):
        return self.set_zoom(self._zoom * ZOOM_STEP)

    def zoom_out(self):
        return self.set_zoom(self._zoom / ZOOM_STEP)

    def reset_zoom(self):
        return self.set_zoom(1.0)

    def _apply_zoom(self):
        vp = self.viewport().size()
        if abs(self._zoom - 1.0) < 1e-3:
            self.setWidgetResizable(True)
            self.canvas.setMinimumSize(0, 0)
            self.canvas.setMaximumSize(16777215, 16777215)
        else:
            self.setWidgetResizable(False)
            w = int(vp.width() * self._zoom)
            h = int(vp.height() * self._zoom)
            self.canvas.setMinimumSize(w, h)
            self.canvas.resize(w, h)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if abs(self._zoom - 1.0) >= 1e-3:
            self._apply_zoom()

    # ---- middle-mouse panning ----

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self._pan_origin = e.pos()
            self._pan_scroll = QPoint(
                self.horizontalScrollBar().value(),
                self.verticalScrollBar().value())
            self.setCursor(Qt.ClosedHandCursor)
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
        if e.button() == Qt.MiddleButton and self._pan_origin is not None:
            self._pan_origin = None
            self.unsetCursor()
            return
        super().mouseReleaseEvent(e)
