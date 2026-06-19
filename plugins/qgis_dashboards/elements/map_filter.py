# -*- coding: utf-8 -*-
"""Pure builder for the map element's "filter by visible extent" expression.

The live map mirrors the QGIS canvas; when it acts as a cross-filter *source*
it pushes a spatial ``QgsExpression`` that keeps, in every connected target
layer, only the features whose geometry intersects the map's current visible
extent.

This is deliberately Qt/QGIS-free (a plain string builder) so it can be
unit-tested on its own, following the :mod:`pivot_engine` precedent.
"""


def _num(value):
    """Format a coordinate for WKT without locale/precision surprises."""
    return repr(float(value))


def extent_wkt(xmin, ymin, xmax, ymax):
    """A closed ``POLYGON`` WKT string for the given rectangle."""
    corners = [(xmin, ymin), (xmax, ymin), (xmax, ymax),
               (xmin, ymax), (xmin, ymin)]
    pts = ", ".join("{} {}".format(_num(x), _num(y)) for x, y in corners)
    return "POLYGON(({}))".format(pts)


def extent_filter_expression(xmin, ymin, xmax, ymax, authid=None):
    """Return a QgsExpression keeping features intersecting the extent.

    *authid* is the map canvas CRS auth id (e.g. ``"EPSG:3857"``). When given,
    each target feature's geometry is transformed from its own layer CRS into
    the map CRS before the intersection, so a single expression string works for
    every connected target regardless of its layer's projection.

    Robustness: the intersection is wrapped in ``coalesce(..., true)`` so a
    feature with no geometry — e.g. a non-spatial table wired by mistake — is
    *passed through* (the wiring becomes a harmless no-op) rather than dropped.
    """
    poly = "geom_from_wkt('{}')".format(extent_wkt(xmin, ymin, xmax, ymax))
    if authid:
        geom = ("transform($geometry, layer_property(@layer, 'crs'), '{}')"
                .format(authid))
    else:
        geom = "$geometry"
    return "coalesce(intersects({}, {}), true)".format(geom, poly)
