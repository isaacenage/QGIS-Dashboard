# -*- coding: utf-8 -*-
"""Small media-loading helpers shared by data-driven tiles.

Currently just an icon loader for the Indicator's optional symbol. Mirrors the
loading strategy of :mod:`image_element` (QPixmap for raster, QSvgRenderer for
SVG) but produces a square, aspect-preserving thumbnail at a target size rather
than filling a whole tile. Images are referenced by **file path** (the project
file stays small; the file must remain reachable on disk).
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap, QImage, QPainter

try:
    from qgis.PyQt.QtSvg import QSvgRenderer
except ImportError:          # QtSvg is optional on some builds
    QSvgRenderer = None


def icon_pixmap(path, size):
    """Return a ``QPixmap`` for *path* scaled to fit ``size``×``size``.

    Keeps aspect ratio; returns ``None`` when the path is empty, missing, or
    unreadable so the caller can simply skip the icon.
    """
    if not path or not os.path.isfile(path):
        return None
    size = max(int(size), 1)
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
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
