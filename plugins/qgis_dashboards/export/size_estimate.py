# -*- coding: utf-8 -*-
"""Pure byte-size estimate for a layer's embedded export payload.

Kept QGIS-free (and separate from :mod:`data_collect`, which imports QGIS) so
the size-guard math is unit-testable. The numbers are deliberately rough — they
only need to flag a layer that would bloat the single-file HTML export.
"""

_ATTR_CELL_BYTES = 24    # avg JSON bytes per attribute cell
_GEOM_FEATURE_BYTES = 120  # avg JSON bytes per feature's WGS84 geometry


def estimate_layer_bytes(feature_count, field_count, include_geometry=False):
    """Estimate embedded bytes for *feature_count* features.

    Attribute cost is ``features * max(fields, 1) * 24``; geometry adds a flat
    ~120 bytes per feature when included.
    """
    count = max(int(feature_count or 0), 0)
    cols = max(int(field_count or 0), 1)
    total = count * cols * _ATTR_CELL_BYTES
    if include_geometry:
        total += count * _GEOM_FEATURE_BYTES
    return total
