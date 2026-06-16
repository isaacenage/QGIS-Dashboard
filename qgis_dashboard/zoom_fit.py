# -*- coding: utf-8 -*-
"""Zoom math — pure, Qt-free helpers for the page view's zoom/fit behavior.

Kept separate from :mod:`page_view` (which imports ``qgis.PyQt``) so the
fit-to-region math can be unit-tested without a QGIS environment, mirroring the
other Qt-free helper modules (``header_layout``, ``map_filter``,
``pivot_engine``).
"""

ZOOM_MIN = 0.1
ZOOM_MAX = 4.0
FIT_MARGIN = 12   # px breathing room kept around the region when fitting


def clamp_zoom(z):
    """Clamp *z* into the allowed zoom range."""
    return max(ZOOM_MIN, min(float(z), ZOOM_MAX))


def fit_zoom(region, viewport, margin=FIT_MARGIN):
    """The zoom factor that fits *region* inside *viewport* (both ``(w, h)``).

    Returns the largest factor for which ``region x factor`` fits within the
    viewport less a *margin* on every side, clamped to the zoom range. Falls
    back to ``1.0`` for a degenerate region/viewport (so a not-yet-sized
    viewport never produces a zero or negative zoom).
    """
    rw, rh = float(region[0]), float(region[1])
    avail_w = float(viewport[0]) - 2 * margin
    avail_h = float(viewport[1]) - 2 * margin
    if rw <= 0 or rh <= 0 or avail_w <= 0 or avail_h <= 0:
        return 1.0
    return clamp_zoom(min(avail_w / rw, avail_h / rh))
