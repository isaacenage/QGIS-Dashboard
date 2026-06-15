# -*- coding: utf-8 -*-
"""Orchestrator: a live ``DashboardWindow`` -> a single ``index.html`` file.

Walks the window's pages and tiles, pulls each bound layer's rows and each
tile's ``base_filter`` mask via :mod:`data_collect`, snapshots the map canvas
via :mod:`map_snapshot`, assembles the export model via :mod:`serialize`, and
writes the inlined document via :mod:`html_builder`.
"""

from qgis.core import QgsProject

from .serialize import build_model
from .theme_css import theme_to_css_vars
from .html_builder import build_html, load_assets
from .data_collect import (
    collect_layer_data, base_pass_indices, image_data_uri, layer_size_info,
)
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
                "features": [], "skipped": True,
            }
            fid_indexes[lid] = {}
        else:
            data, fid_index = collect_layer_data(layer)
            layers_model[lid] = data
            fid_indexes[lid] = fid_index
    return layers_model, fid_indexes


def _build_tile(tile, fid_indexes, skip_layers, map_uri):
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
        out["map_image"] = map_uri
    elif element.type_name == "image":
        out["image_uri"] = image_data_uri(element.config.get("path"))
    elif element.type_name == "indicator":
        out["indicator_value"] = _indicator_baseline(element)
    return out


def export_dashboard(window, out_path, skip_layers=None):
    """Write the dashboard to *out_path* as a single HTML file. Returns the path."""
    skip_layers = set(skip_layers or [])
    layers_model, fid_indexes = _collect_layers(window, skip_layers)
    map_uri = canvas_data_uri(getattr(window, "iface", None))

    pages = []
    for page in window.pages():
        tiles = [_build_tile(t, fid_indexes, skip_layers, map_uri)
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
        pages, layers_model)

    css_vars = theme_to_css_vars(model["theme"])
    runtime_css, runtime_js = load_assets()
    html = build_html(model, css_vars, runtime_css, runtime_js,
                      title=_project_title())

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out_path
