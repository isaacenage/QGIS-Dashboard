# -*- coding: utf-8 -*-
"""Grab the live QGIS map canvas as a base64 PNG for map tiles.

A double-click ``file://`` page cannot run an interactive web map (Web Workers
are blocked and online basemaps need the network), so a map tile is exported as
a static image of what QGIS currently displays — same extent, layers and
basemap. One snapshot of ``iface.mapCanvas()`` is shared by every map tile.
"""

from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice


def _pixmap_to_data_uri(pixmap):
    if pixmap is None or pixmap.isNull():
        return None
    buffer_bytes = QByteArray()
    buffer = QBuffer(buffer_bytes)
    buffer.open(QIODevice.WriteOnly)
    if not pixmap.save(buffer, "PNG"):
        return None
    encoded = bytes(buffer_bytes.toBase64()).decode("ascii")
    return "data:image/png;base64,{}".format(encoded)


def canvas_data_uri(iface):
    """Return a PNG ``data:`` URI of the current map canvas, or ``None``."""
    if iface is None:
        return None
    canvas = iface.mapCanvas()
    if canvas is None:
        return None
    try:
        pixmap = canvas.grab()
    except Exception:
        return None
    return _pixmap_to_data_uri(pixmap)
