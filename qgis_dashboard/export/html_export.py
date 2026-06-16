# -*- coding: utf-8 -*-
"""Orchestrator: a live ``DashboardWindow`` -> a single ``index.html`` file.

Walks the window's pages and tiles, pulls each bound layer's rows and each
tile's ``base_filter`` mask via :mod:`data_collect`, snapshots the map canvas
via :mod:`map_snapshot`, assembles the export model via :mod:`serialize`, and
writes the inlined document via :mod:`html_builder`.
"""

from qgis.core import (
    QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
)

from .serialize import build_model
from .theme_css import theme_to_css_vars
from .html_builder import build_html, load_assets
from .data_collect import (
    collect_layer_data, base_pass_indices, image_data_uri, layer_size_info,
)
from .geometry_collect import collect_layer_geometry
from .basemap import detect_basemap
from .map_snapshot import canvas_data_uri


def referenced_layer_ids(window):
    """Set of layer ids bound by any tile on any page."""
    ids = set()
    for page in window.pages():
        for tile in page.canvas.tiles():
            lid = tile.element.config.get("layer_id")
            if lid:
                ids.add(lid)
    return ids


def oversize_layers(window, max_features, max_bytes):
    """Referenced layers exceeding either threshold.

    Returns a list of ``(layer_id, name, feature_count, est_bytes)`` for the
    pre-export warning dialog.
    """
    project = QgsProject.instance()
    out = []
    for lid in referenced_layer_ids(window):
        layer = project.mapLayer(lid)
        if layer is None:
            continue
        count, est = layer_size_info(layer)
        if count > max_features or est > max_bytes:
            out.append((lid, layer.name(), count, est))
    return out


def _indicator_baseline(element):
    """Server-computed fallback value for an indicator (unsupported exprs)."""
    try:
        from .data_collect import jsonify
        return jsonify(element.evaluate(
            element.config.get("value_expression", "count(1)")))
    except Exception:
        return None


def _project_title():
    project = QgsProject.instance()
    name = project.title() or ""
    if name:
        return name
    file_name = project.fileName() or ""
    if file_name:
        import os
        return os.path.splitext(os.path.basename(file_name))[0]
    return "Dashboard"


def _collect_layers(window, skip_layers):
    """Return ``(layers_model, fid_indexes)`` for referenced layers."""
    project = QgsProject.instance()
    layers_model = {}
    fid_indexes = {}
    for lid in referenced_layer_ids(window):
        layer = project.mapLayer(lid)
        if layer is None:
            continue
        if lid in skip_layers:
            layers_model[lid] = {
                "fields": [f.name() for f in layer.fields()],
                "features": [], "geometry": [], "skipped": True,
            }
            fid_indexes[lid] = {}
        else:
            data, fid_index = collect_layer_data(layer)
            data["geometry"] = collect_layer_geometry(layer, project)
            layers_model[lid] = data
            fid_indexes[lid] = fid_index
    return layers_model, fid_indexes


def _canvas_extent_4326(iface, project):
    """The current map-canvas extent as ``[west, south, east, north]`` (WGS84)."""
    if iface is None:
        return None
    canvas = iface.mapCanvas()
    if canvas is None:
        return None
    try:
        extent = canvas.extent()
        src = canvas.mapSettings().destinationCrs()
        dest = QgsCoordinateReferenceSystem("EPSG:4326")
        if src.isValid() and src != dest:
            transform = QgsCoordinateTransform(src, dest, project)
            extent = transform.transformBoundingBox(extent)
        return [extent.xMinimum(), extent.yMinimum(),
                extent.xMaximum(), extent.yMaximum()]
    except Exception:
        return None


def _build_map_block(window, layers_model):
    """The interactive-map descriptor: basemap, extent, drawable layers, fallback."""
    project = QgsProject.instance()
    iface = getattr(window, "iface", None)
    layer_ids = [lid for lid in sorted(referenced_layer_ids(window))
                 if lid in layers_model]
    return {
        "basemap": detect_basemap(project),
        "extent": _canvas_extent_4326(iface, project),
        "layer_ids": layer_ids,
        "fallback_image": canvas_data_uri(iface),
    }


def _build_tile(tile, fid_indexes, skip_layers, window, layers_model):
    element = tile.element
    gx, gy, gw, gh = tile.grid_rect()
    out = {
        "id": element.id,
        "type": element.type_name,
        "config": dict(element.config),
        "grid": {"x": gx, "y": gy, "w": gw, "h": gh},
    }
    lid = element.config.get("layer_id")
    if lid:
        out["layer_id"] = lid
        if lid in fid_indexes and lid not in skip_layers:
            out["base_pass"] = base_pass_indices(
                element.layer(), element.config.get("base_filter"),
                fid_indexes[lid])
    if element.type_name == "map":
        out["map"] = _build_map_block(window, layers_model)
    elif element.type_name == "image":
        out["image_uri"] = image_data_uri(element.config.get("path"))
    elif element.type_name == "header":
        logo = (element.config.get("logo_path") or "").strip()
        if logo:
            out["logo_uri"] = image_data_uri(logo)
    elif element.type_name == "indicator":
        out["indicator_value"] = _indicator_baseline(element)
        icon = element.config.get("icon_path")
        if icon:
            out["icon_uri"] = image_data_uri(icon)
    return out


def export_dashboard(window, out_path, skip_layers=None):
    """Write the dashboard to *out_path* as a single HTML file. Returns the path."""
    skip_layers = set(skip_layers or [])
    layers_model, fid_indexes = _collect_layers(window, skip_layers)

    pages = []
    for page in window.pages():
        tiles = [_build_tile(t, fid_indexes, skip_layers, window, layers_model)
                 for t in page.canvas.tiles()]
        pages.append({
            "id": page.id,
            "title": page.title,
            "connections": window.bus.connections_to_dict(page.id),
            "tiles": tiles,
        })

    current = window.current_page()
    model = build_model(
        (window.canvas_cols(), window.canvas_rows()),
        window.bus.theme.to_dict(),
        current.id if current else None,
        pages, layers_model,
        gap=window.canvas_gap())

    css_vars = theme_to_css_vars(model["theme"])
    runtime_css, runtime_js, leaflet_css, leaflet_js = load_assets()
    html = build_html(model, css_vars, runtime_css, runtime_js,
                      leaflet_css=leaflet_css, leaflet_js=leaflet_js,
                      title=_project_title())

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out_path
