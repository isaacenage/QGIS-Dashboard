# -*- coding: utf-8 -*-
"""QPainter chart painters.

Each painter is a ``QWidget`` that draws one chart type from uniform
``[(category, value)]`` data and emits :pyattr:`categoryClicked` when the user
clicks a bar / point / slice. They share a base that holds theme colors and the
data contract so :class:`~..chart.ChartElement` can swap painters by key.

Charts are drawn with plain QPainter rather than QtChart, because the QtChart
Qt module is optional and is not shipped with every QGIS/PyQt build.
"""

import math

from qgis.PyQt.QtCore import Qt, pyqtSignal, QRectF, QPointF
from qgis.PyQt.QtGui import QPainter, QColor, QPen, QPolygonF
from qgis.PyQt.QtWidgets import QWidget

from ...theme import DEFAULT_SERIES

EXPLODE_PX = 10.0


def fmt_num(v):
    if isinstance(v, float):
        if v == int(v):
            v = int(v)
        else:
            return "{:,.2f}".format(v)
    if isinstance(v, int):
        return "{:,}".format(v)
    return str(v)


class _ChartPainter(QWidget):
    """Base for all chart painters; holds data + theme, emits category clicks."""

    categoryClicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []            # list of (category, value)
        self._selected = None
        self._inner = 0.0          # pie/donut inner-radius fraction
        self._bg = QColor("#ffffff")
        self._palette = list(DEFAULT_SERIES)
        self._bar = QColor("#0f6cbd")
        self._bar_sel = QColor("#9aa7b4")
        self._text = QColor("#1b2733")
        self._muted = QColor("#6b7682")
        self._grid = QColor("#e3e8ee")
        self.setMinimumHeight(160)

    def set_theme(self, theme):
        self._bg = QColor(theme.chart_bg)
        self._palette = list(theme.series or DEFAULT_SERIES)
        self._bar = QColor(theme.series_color(0))
        self._bar_sel = QColor(theme.text_muted)
        self._text = QColor(theme.text)
        self._muted = QColor(theme.text_muted)
        self._grid = QColor(getattr(theme, "grid_line", "#e3e8ee"))
        self.update()

    def set_data(self, data, selected=None, inner=0.0):
        self._data = list(data)
        self._selected = selected
        self._inner = inner
        self.update()

    def _color(self, i):
        return QColor(self._palette[i % len(self._palette)])

    def _no_data(self, p, rect):
        p.setPen(self._muted)
        p.drawText(rect, Qt.AlignCenter, "No data")
        p.end()


class BarPainter(_ChartPainter):
    """Vertical bars with clickable columns and value labels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._geom = None   # (left, slot_w, n)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self._bg)
        rect = self.rect().adjusted(8, 8, -8, -8)
        self._geom = None
        if not self._data:
            return self._no_data(p, rect)

        n = len(self._data)
        max_v = max((float(v) for _, v in self._data), default=0) or 1.0
        fm = p.fontMetrics()
        label_h = fm.height() + 4
        top_pad = fm.height() + 4
        plot_bottom = rect.bottom() - label_h
        plot_top = rect.top() + top_pad
        plot_h = max(plot_bottom - plot_top, 1)
        slot_w = rect.width() / float(n)
        bar_w = slot_w * 0.6
        self._geom = (rect.left(), slot_w, n)

        for i, (cat, v) in enumerate(self._data):
            slot_left = rect.left() + i * slot_w
            h = plot_h * (float(v) / max_v)
            y = plot_bottom - h
            color = self._bar_sel if cat == self._selected else self._color(i)
            p.fillRect(QRectF(slot_left + (slot_w - bar_w) / 2, y, bar_w, h), color)
            p.setPen(self._text)
            p.drawText(QRectF(slot_left, y - top_pad, slot_w, top_pad),
                       Qt.AlignHCenter | Qt.AlignBottom, fmt_num(v))
            cat_txt = fm.elidedText(str(cat), Qt.ElideRight, int(slot_w))
            p.setPen(self._muted)
            p.drawText(QRectF(slot_left, plot_bottom + 2, slot_w, label_h),
                       Qt.AlignHCenter | Qt.AlignTop, cat_txt)
        p.end()

    def mousePressEvent(self, e):
        if not self._geom:
            return
        left, slot_w, n = self._geom
        idx = int((e.pos().x() - left) / slot_w)
        if 0 <= idx < n:
            self.categoryClicked.emit(str(self._data[idx][0]))


class BarHPainter(_ChartPainter):
    """Horizontal bars; category labels at the left."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._geom = None   # (top, slot_h, n, label_w)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self._bg)
        rect = self.rect().adjusted(8, 8, -8, -8)
        self._geom = None
        if not self._data:
            return self._no_data(p, rect)

        n = len(self._data)
        max_v = max((float(v) for _, v in self._data), default=0) or 1.0
        fm = p.fontMetrics()
        label_w = min(int(rect.width() * 0.32), 140)
        val_w = 52
        plot_left = rect.left() + label_w
        plot_w = max(rect.width() - label_w - val_w, 1)
        slot_h = rect.height() / float(n)
        bar_h = min(slot_h * 0.6, 26)
        self._geom = (rect.top(), slot_h, n, label_w)

        for i, (cat, v) in enumerate(self._data):
            slot_top = rect.top() + i * slot_h
            w = plot_w * (float(v) / max_v)
            y = slot_top + (slot_h - bar_h) / 2
            color = self._bar_sel if cat == self._selected else self._color(i)
            cat_txt = fm.elidedText(str(cat), Qt.ElideRight, label_w - 6)
            p.setPen(self._muted)
            p.drawText(QRectF(rect.left(), slot_top, label_w - 6, slot_h),
                       Qt.AlignLeft | Qt.AlignVCenter, cat_txt)
            p.fillRect(QRectF(plot_left, y, w, bar_h), color)
            p.setPen(self._text)
            p.drawText(QRectF(plot_left + w + 4, slot_top, val_w - 6, slot_h),
                       Qt.AlignLeft | Qt.AlignVCenter, fmt_num(v))
        p.end()

    def mousePressEvent(self, e):
        if not self._geom:
            return
        top, slot_h, n, _label_w = self._geom
        idx = int((e.pos().y() - top) / slot_h)
        if 0 <= idx < n:
            self.categoryClicked.emit(str(self._data[idx][0]))


class LinePainter(_ChartPainter):
    """Line connecting per-category values; markers are clickable."""

    fill = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []   # [(x, y, category)]

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self._bg)
        rect = self.rect().adjusted(8, 8, -8, -8)
        self._points = []
        if not self._data:
            return self._no_data(p, rect)

        n = len(self._data)
        max_v = max((float(v) for _, v in self._data), default=0) or 1.0
        fm = p.fontMetrics()
        label_h = fm.height() + 4
        top_pad = fm.height() + 4
        plot_bottom = rect.bottom() - label_h
        plot_top = rect.top() + top_pad
        plot_h = max(plot_bottom - plot_top, 1)
        slot_w = rect.width() / float(n)

        pts = []
        for i, (cat, v) in enumerate(self._data):
            x = rect.left() + slot_w * (i + 0.5)
            y = plot_bottom - plot_h * (float(v) / max_v)
            pts.append(QPointF(x, y))
            self._points.append((x, y, str(cat)))

        if self.fill and pts:
            poly = QPolygonF([QPointF(pts[0].x(), plot_bottom)] + pts +
                             [QPointF(pts[-1].x(), plot_bottom)])
            fill_c = QColor(self._color(0))
            fill_c.setAlpha(60)
            p.setPen(Qt.NoPen)
            p.setBrush(fill_c)
            p.drawPolygon(poly)

        p.setPen(QPen(self._color(0), 2))
        p.setBrush(Qt.NoBrush)
        for a, b in zip(pts, pts[1:]):
            p.drawLine(a, b)

        for i, (cat, v) in enumerate(self._data):
            x, y, _c = self._points[i]
            sel = (cat == self._selected)
            r = 5 if sel else 3
            p.setBrush(self._bar_sel if sel else self._color(0))
            p.setPen(QPen(self._bg, 1))
            p.drawEllipse(QPointF(x, y), r, r)
            cat_txt = fm.elidedText(str(cat), Qt.ElideRight, int(slot_w))
            p.setPen(self._muted)
            p.drawText(QRectF(x - slot_w / 2, plot_bottom + 2, slot_w, label_h),
                       Qt.AlignHCenter | Qt.AlignTop, cat_txt)
        p.end()

    def mousePressEvent(self, e):
        if not self._points:
            return
        px = e.pos().x()
        best, best_dx = None, None
        for x, _y, cat in self._points:
            dx = abs(px - x)
            if best_dx is None or dx < best_dx:
                best, best_dx = cat, dx
        if best is not None:
            self.categoryClicked.emit(best)


class AreaPainter(LinePainter):
    """Line chart with the area below the curve filled."""

    fill = True


class PiePainter(_ChartPainter):
    """Pie/donut with clickable slices and a legend (inner>0 == donut)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hit = None   # (cx, cy, radius, inner_r, [(label, start, span)])

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self._bg)
        rect = self.rect().adjusted(8, 8, -8, -8)
        self._hit = None
        total = sum(float(v) for _, v in self._data)
        if total <= 0:
            return self._no_data(p, rect)

        legend_w = 0
        if rect.width() > 260:
            legend_w = min(int(rect.width() * 0.4), 180)
        pie_area = rect.adjusted(0, 0, -legend_w, 0)
        diameter = max(min(pie_area.width(), pie_area.height()) - 4, 10)
        cx = pie_area.left() + pie_area.width() / 2.0
        cy = pie_area.top() + pie_area.height() / 2.0
        radius = diameter / 2.0
        inner_r = radius * self._inner if self._inner else 0.0

        slices = []
        start = 90.0
        for i, (label, value) in enumerate(self._data):
            span = 360.0 * float(value) / total
            ox, oy = 0.0, 0.0
            if label == self._selected:
                mid = math.radians(start + span / 2.0)
                ox = math.cos(mid) * EXPLODE_PX
                oy = -math.sin(mid) * EXPLODE_PX
            box = QRectF(cx - radius + ox, cy - radius + oy, diameter, diameter)
            p.setBrush(self._color(i))
            p.setPen(QColor("#ffffff"))
            p.drawPie(box, int(round(start * 16)), int(round(span * 16)))
            slices.append((label, start, span))
            start += span

        if inner_r > 0:
            p.setBrush(self._bg)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        self._hit = (cx, cy, radius, inner_r, slices)

        if legend_w:
            self._paint_legend(p, QRectF(rect.right() - legend_w, rect.top(),
                                         legend_w, rect.height()))
        p.end()

    def _paint_legend(self, p, area):
        fm = p.fontMetrics()
        row_h = fm.height() + 6
        y = area.top()
        for i, (label, value) in enumerate(self._data):
            if y + row_h > area.bottom():
                break
            p.setBrush(self._color(i))
            p.setPen(Qt.NoPen)
            p.drawRect(QRectF(area.left(), y + 3, 11, 11))
            p.setPen(self._text)
            txt = fm.elidedText("{} ({})".format(label, fmt_num(value)),
                                Qt.ElideRight, int(area.width() - 18))
            p.drawText(QRectF(area.left() + 18, y, area.width() - 18, row_h),
                       Qt.AlignLeft | Qt.AlignVCenter, txt)
            y += row_h

    def mousePressEvent(self, e):
        if not self._hit:
            return
        cx, cy, radius, inner_r, slices = self._hit
        dx = e.pos().x() - cx
        dy = e.pos().y() - cy
        dist = math.hypot(dx, dy)
        if dist > radius or (inner_r and dist < inner_r):
            return
        angle = math.degrees(math.atan2(-dy, dx)) % 360.0
        for label, start, span in slices:
            rel = (angle - (start % 360.0)) % 360.0
            if rel < span:
                self.categoryClicked.emit(str(label))
                return


PAINTERS = {
    "bar": BarPainter,
    "barh": BarHPainter,
    "line": LinePainter,
    "area": AreaPainter,
    "pie": PiePainter,
}
