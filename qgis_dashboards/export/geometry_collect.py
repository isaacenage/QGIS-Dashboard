# -*- coding: utf-8 -*-
"""Collect per-feature geometry (reprojected to WGS84) for the export map.

Parallel to :func:`data_collect.collect_layer_data`: it walks the same
``getFeatures()`` order and returns one GeoJSON geometry dict per feature (or
``None``), so the geometry list index-aligns with the attribute ``features``
list the runtime already cross-filters by. Geometry is reprojected to EPSG:4326
(Leaflet's CRS) and rounded to 6 decimals. No vertex simplification is applied —
full geometry fidelity is preserved.
"""

import json

from qgis.core import (
    QgsGeometry, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsProject,
)

WGS84 = "EPSG:4326"
_PRECISION = 6


def collect_layer_geometry(layer, project=None):
    """Return a list of GeoJSON geometry dicts (or ``None``) for *layer*.

    The list is in ``layer.getFeatures()`` order so it index-aligns with
    :func:`data_collect.collect_layer_data`'s ``features``.
    """
    project = project or QgsProject.instance()
    dest = QgsCoordinateReferenceSystem(WGS84)
    src = layer.crs()
    transform = None
    if src.isValid() and dest.isValid() and src != dest:
        transform = QgsCoordinateTransform(src, dest, project)

    out = []
    for feat in layer.getFeatures():
        out.append(_feature_geojson(feat.geometry(), transform))
    return out


def _feature_geojson(geom, transform):
    """One feature's geometry -> a GeoJSON geometry dict, or ``None``."""
    if geom is None or geom.isNull() or geom.isEmpty():
        return None
    if transform is not None:
        geom = QgsGeometry(geom)   # copy: never mutate the source feature
        try:
            if geom.transform(transform) != 0:
                return None
        except Exception:
            return None
    try:
        text = geom.asJson(_PRECISION)
    except Exception:
        return None
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None
