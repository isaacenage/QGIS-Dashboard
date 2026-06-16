# -*- coding: utf-8 -*-
"""Resolve the basemap for the interactive Leaflet export map.

The exported map is an online Leaflet slippy map. If the QGIS project already
contains an XYZ tile layer we reuse its URL template (so the export matches what
the user sees in QGIS); otherwise we fall back to OpenStreetMap.

``xyz_template_to_leaflet`` is pure (no QGIS) and unit-tested; ``detect_basemap``
scans the project and delegates to it.
"""

import re
from urllib.parse import unquote

OSM_BASEMAP = {
    "url_template": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "attribution": "© OpenStreetMap contributors",
    "subdomains": None,
    "max_zoom": 19,
    "tms": False,
}


def xyz_template_to_leaflet(url):
    """Convert a QGIS XYZ ``url=`` template into a Leaflet basemap dict.

    Returns ``None`` when *url* has no usable ``{x}/{y}/{z}`` tokens so the
    caller can fall back to OSM. ``{-y}`` (TMS addressing) sets ``tms=True`` and
    is normalized to ``{y}`` for Leaflet.
    """
    if not url:
        return None
    text = unquote(str(url)).strip()
    if "{x}" not in text or "{z}" not in text:
        return None
    tms = "{-y}" in text
    if tms:
        text = text.replace("{-y}", "{y}")
    if "{y}" not in text:
        return None
    return {
        "url_template": text,
        "attribution": "",
        "subdomains": None,
        "max_zoom": 19,
        "tms": tms,
    }


def detect_basemap(project):
    """Return a Leaflet basemap dict for *project* — its XYZ layer, else OSM."""
    try:
        layers = list(project.mapLayers().values())
    except Exception:
        return dict(OSM_BASEMAP)
    for layer in layers:
        try:
            source = layer.source() or ""
        except Exception:
            source = ""
        if "type=xyz" in source and "url=" in source:
            match = re.search(r"url=([^&]+)", source)
            if match:
                parsed = xyz_template_to_leaflet(match.group(1))
                if parsed:
                    return parsed
    return dict(OSM_BASEMAP)
