# -*- coding: utf-8 -*-
"""Pure layout helpers for the Header (brand banner) element.

Qt-free and side-effect-free so the geometry decisions can be unit-tested on
plain values, following the :mod:`pivot_engine` / :mod:`export.serialize`
precedent. Three small functions:

* :func:`box_direction` — how the page container stacks ``[banner, scroll]``
  for a given dock edge.
* :func:`inner_box_direction` — how the logo and title stack inside the banner
  for a given logo slot.
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


def box_direction(anchor):
    """Return ``(orientation, banner_first)`` for a dock *anchor* edge.

    Unknown anchors fall back to ``top``.
    """
    return _ANCHOR.get(anchor, _ANCHOR["top"])


def inner_box_direction(logo_slot):
    """Return ``(orientation, logo_first)`` for a *logo_slot* inside the banner.

    Unknown slots fall back to ``left``.
    """
    return _SLOT.get(logo_slot, _SLOT["left"])


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
