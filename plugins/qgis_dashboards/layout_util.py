# -*- coding: utf-8 -*-
"""Pure layout helpers (no QGIS / Qt).

Small, unit-testable functions that operate on the serialized layout blob, kept
out of :mod:`window` so they can be exercised without a QGIS environment.
"""


def region_scale_factor(old_w, old_h, new_w, new_h):
    """Uniform factor to scale a layout from an old page region to a new one.

    Returns ``min(new_w/old_w, new_h/old_h)`` — the *fit* factor: the layout
    grows/shrinks to fit fully inside the new page, leaving even margin in the
    longer axis when the aspect ratio changes. This guarantees every tile stays
    within the region (``x*f <= old_w*(new_w/old_w) = new_w``), so nothing is
    ever cropped on PNG/PDF export. A single uniform factor (rather than
    independent x/y scaling) keeps every tile's own aspect ratio and preserves
    the no-overlap invariant. Old dimensions are floored at 1 to avoid division
    by zero; when both axes are unchanged the factor is exactly 1.0.
    """
    old_w = max(1, int(old_w))
    old_h = max(1, int(old_h))
    return min(new_w / float(old_w), new_h / float(old_h))


def scale_rect(rect, factor):
    """Scale a logical ``(x, y, w, h)`` rect by *factor*, top-left anchored.

    Coordinates are rounded to ints; width/height are floored at 1 so a tile
    never collapses to zero on an extreme shrink.
    """
    x, y, w, h = rect
    return (int(round(x * factor)), int(round(y * factor)),
            max(1, int(round(w * factor))), max(1, int(round(h * factor))))


def default_locked(blob):
    """Default lock (Use) mode for a migrated layout blob.

    A saved dashboard that already has tiles opens in **Use mode** (locked,
    interactive); an empty one opens in **Build mode** (unlocked, editable).
    Used when the stored blob carries no explicit ``locked`` flag (older blobs)
    so existing dashboards open ready to use, not ready to edit.
    """
    for page in blob.get("pages", []):
        if page.get("elements"):
            return True
    return False
