# -*- coding: utf-8 -*-
"""Pure layout helpers for the Header (brand banner) element.

Qt-free and side-effect-free so the geometry decisions can be unit-tested on
plain values, following the :mod:`pivot_engine` / :mod:`export.serialize`
precedent. Small functions:

* :func:`inner_box_direction` — how the logo and title stack inside the header
  for a given logo slot.
* :func:`header_tile_placement` — where a legacy docked header lands as a free
  canvas tile (rect, tile shift, grown region).
* :func:`materialize_header_tiles` — fold legacy global/per-page headers into
  each page's tile list.
* :func:`resolve_header` — which header config a page renders (a per-page header
  overrides the global one).
"""

# anchor -> (orientation, banner_first)
#   orientation: "v" (stack top/bottom) or "h" (side by side)
#   banner_first: banner comes before the scroll area in layout order
_ANCHOR = {
    "top": ("v", True),
    "bottom": ("v", False),
    "left": ("h", True),
    "right": ("h", False),
}

# logo slot -> (orientation, logo_first) inside the banner
_SLOT = {
    "left": ("h", True),
    "right": ("h", False),
    "above": ("v", True),
    "below": ("v", False),
}


def inner_box_direction(logo_slot):
    """Return ``(orientation, logo_first)`` for a *logo_slot* inside the banner.

    Unknown slots fall back to ``left``.
    """
    return _SLOT.get(logo_slot, _SLOT["left"])


def header_tile_placement(anchor, thickness, region_w, region_h):
    """Place a legacy docked header as a canvas tile on its old edge.

    Converts the out-of-canvas banner model into a free-placed tile: returns
    the header tile's logical rect, the ``(dx, dy)`` shift to apply to every
    existing tile so it does not overlap the band, and the grown region size
    that now includes the band. Unknown anchors fall back to ``top``.

    Returns ``(header_rect, (dx, dy), (new_w, new_h))`` where ``header_rect`` is
    an ``(x, y, w, h)`` tuple, all in logical (zoom-1.0) pixels.
    """
    # top/bottom -> full-width horizontal band; left/right -> full-height band
    orient, banner_first = _ANCHOR.get(anchor, _ANCHOR["top"])
    if orient == "v":                       # top / bottom -> full-width band
        if banner_first:                    # top
            return ((0, 0, region_w, thickness), (0, thickness),
                    (region_w, region_h + thickness))
        return ((0, region_h, region_w, thickness), (0, 0),     # bottom
                (region_w, region_h + thickness))
    # left / right -> full-height band
    if banner_first:                        # left
        return ((0, 0, thickness, region_h), (thickness, 0),
                (region_w + thickness, region_h))
    return ((region_w, 0, thickness, region_h), (0, 0),         # right
            (region_w + thickness, region_h))


# config keys that belonged to the docked-banner model and do not survive onto
# a free-placed header tile
_DOCK_ONLY_KEYS = ("anchor", "thickness", "scope_all_pages", "id", "grid",
                   "__type__")


def materialize_header_tiles(pages, global_header, region_w, region_h):
    """Fold legacy headers into each page's tile list (pure migration).

    For every page, the resolved header (per-page over *global_header*) is
    appended to that page's ``elements`` as a ``header`` tile, existing tiles
    are shifted out of the band, and the dock-only config keys are dropped. The
    region grows to include the band; the returned size is the max across pages
    so the single global page size stays uniform.

    Returns ``(new_pages, new_region_w, new_region_h)``. Input is not mutated.
    """
    new_pages = []
    grown_w, grown_h = region_w, region_h
    for page in pages:
        resolved = resolve_header(page.get("header"), global_header)
        new_page = dict(page)
        new_page.pop("header", None)
        elements = [dict(e) for e in page.get("elements", [])]
        if resolved:
            anchor = resolved.get("anchor", "top")
            thickness = int(resolved.get("thickness", 80) or 80)
            rect, (dx, dy), (pw, ph) = header_tile_placement(
                anchor, thickness, region_w, region_h)
            if dx or dy:
                for el in elements:
                    g = el.get("grid")
                    if isinstance(g, dict) and all(
                            k in g for k in ("x", "y", "w", "h")):
                        el["grid"] = {"x": g["x"] + dx, "y": g["y"] + dy,
                                      "w": g["w"], "h": g["h"]}
            hdr = {k: v for k, v in resolved.items()
                   if k not in _DOCK_ONLY_KEYS}
            hdr["__type__"] = "header"
            hdr["grid"] = {"x": rect[0], "y": rect[1],
                           "w": rect[2], "h": rect[3]}
            elements.append(hdr)
            grown_w, grown_h = max(grown_w, pw), max(grown_h, ph)
        new_page["elements"] = elements
        new_pages.append(new_page)
    return new_pages, grown_w, grown_h


def resolve_header(page_header, global_header):
    """Pick the header config to render for one page.

    A non-empty *page_header* wins (a per-page header overrides the global one);
    otherwise the *global_header*; otherwise ``None``.
    """
    if page_header:
        return page_header
    if global_header:
        return global_header
    return None
