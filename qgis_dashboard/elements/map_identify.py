# -*- coding: utf-8 -*-
"""Pure helpers for the map element's left-click *identify* (no QGIS / Qt).

The identify flow in :mod:`map_element` converts a click to map coordinates,
builds a small tolerance square to search the bound layer, and renders the first
matching feature's attributes in a small popup. The geometry + row-shaping math
lives here so it can be unit-tested without a QGIS environment; the popup widget
and the QGIS feature query stay in :mod:`map_element`.
"""


def search_rect(map_x, map_y, tol):
    """A square search box of half-width *tol* (map units) around a point.

    Returns ``(xmin, ymin, xmax, ymax)``. *tol* is clamped non-negative so a
    zero/garbage tolerance degenerates to the point itself rather than an
    inverted rectangle.
    """
    t = max(0.0, float(tol))
    return (map_x - t, map_y - t, map_x + t, map_y + t)


def feature_summary(field_names, values, limit=12):
    """Pair field names with display strings for the identify popup.

    Returns a list of ``(name, text)`` rows, at most *limit* of them. ``None``
    (a cleaned QGIS NULL) renders as an empty string; everything else is
    stringified. Extra values beyond the field names are ignored.
    """
    rows = []
    for name, val in zip(field_names, values):
        if len(rows) >= max(0, int(limit)):
            break
        rows.append((name, "" if val is None else str(val)))
    return rows
