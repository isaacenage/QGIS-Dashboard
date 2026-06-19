# -*- coding: utf-8 -*-
"""Pure assembly of the HTML-export data model.

This module takes already-collected, JSON-safe Python structures (the layout,
the per-page connection graph, the theme dict, and the per-layer feature rows)
and produces the single dict that is embedded into ``index.html`` and read by
the browser runtime. It is intentionally free of any QGIS/Qt import so it can be
unit-tested on plain dicts, following the :mod:`pivot_engine` precedent.

The shape it produces (``EXPORT_VERSION`` 2)::

    {
      "version": 2,
      "grid": {"cols": 12, "rows": 8},
      "gap": 0,
      "theme": { ... Theme.to_dict() ... },
      "active_page": "<page id>",
      "pages": [
        {"id", "title", "connections": {src: [tgt, ...]},
         "tiles": [
           {"id", "type", "grid": {x,y,w,h}, "config": {...},
            "layer_id"?, "base_pass"?, "map"?, "image_uri"?,
            "indicator_value"?}
         ]}
      ],
      "layers": {"<layer id>": {"fields": [...], "features": [ {field: val} ],
                                "geometry": [ geojson_geom_or_null ]}}
    }
"""

EXPORT_VERSION = 2

# Optional per-tile keys copied through verbatim when present (and not None).
_OPTIONAL_TILE_KEYS = (
    "layer_id", "base_pass", "map", "image_uri", "indicator_value",
    "icon_uri", "logo_uri",
)


# The per-tile appearance system stores visual settings under ``config["style"]``
# (some renamed away from theme.OVERRIDE_KEYS). The browser runtime still reads
# the original top-level names, so hoist those values back up at export time —
# this keeps the existing export features working without touching runtime.js.
# (New per-role keys — colors/weights/per-role fonts/table styling — are not yet
# mirrored in the runtime; that parity is a deferred follow-up.)
_STYLE_TO_LEGACY = {
    "value_px": "value_size",
    "icon_size": "icon_size",
    "icon_position": "icon_position",
    "animation": "animation",
    "animation_duration_ms": "animation_duration_ms",
    "rows_shown": "max_rows",
    "cols_shown": "max_cols",
    "max_categories": "max_categories",
    "logo_size": "logo_size",
    "logo_slot": "logo_slot",
    "title_font": "font_family",
    "title_align": "align",
    "text_align": "align",
}


def _hoist_legacy_style(out):
    """Copy relocated style values back to the legacy top-level names the
    browser runtime reads (without overwriting an explicit top-level value)."""
    style = out.get("style")
    if not isinstance(style, dict):
        return
    for skey, ckey in _STYLE_TO_LEGACY.items():
        val = style.get(skey)
        if val not in (None, "") and ckey not in out:
            out[ckey] = val
    try:
        if int(style.get("text_weight", 0)) >= 600:
            out.setdefault("heading", True)
    except (TypeError, ValueError):
        pass


def clean_config(config):
    """Return a JSON-safe copy of an element config for embedding.

    ``id`` is dropped (it is carried on the tile itself); every other key is
    kept so the browser renderer sees the same binding the plugin used. Visual
    settings stored under ``style`` are also surfaced under their legacy
    top-level names for the browser runtime.
    """
    if not config:
        return {}
    out = {k: v for k, v in config.items() if k != "id"}
    _hoist_legacy_style(out)
    return out


def build_tile(tile):
    """Normalize one tile descriptor into its exported form.

    *tile* is a plain dict with at least ``id``, ``type`` and ``grid``; it may
    also carry any of :data:`_OPTIONAL_TILE_KEYS` and a ``config`` dict.
    """
    out = {
        "id": tile["id"],
        "type": tile["type"],
        "grid": dict(tile.get("grid") or {}),
        "config": clean_config(tile.get("config")),
    }
    for key in _OPTIONAL_TILE_KEYS:
        if tile.get(key) is not None:
            out[key] = tile[key]
    return out


def build_page(page):
    """Normalize one page (id/title/connections + its tiles).

    The header is an ordinary tile now, so it flows through ``build_tile`` like
    any element — there is no separate docked-banner key.
    """
    return {
        "id": page["id"],
        "title": page.get("title") or "Page",
        "connections": page.get("connections") or {},
        "tiles": [build_tile(t) for t in page.get("tiles", [])],
    }


def build_model(grid, theme, active_page, pages, layers, gap=0):
    """Assemble the final, embeddable export-model dict.

    *grid* is a ``(cols, rows)`` pair; *gap* is the global element gap (logical
    px) the browser insets each card by, mirroring the desktop spacing; *theme*
    is ``Theme.to_dict()``; *pages* is a list of page descriptors; *layers* maps
    layer id -> ``{fields, features}``.
    """
    cols, rows = grid
    return {
        "version": EXPORT_VERSION,
        "grid": {"cols": cols, "rows": rows},
        "gap": max(0, int(gap or 0)),
        "theme": theme or {},
        "active_page": active_page,
        "pages": [build_page(p) for p in pages],
        "layers": layers or {},
    }
