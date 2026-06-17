# -*- coding: utf-8 -*-
"""Pure layout helpers (no QGIS / Qt).

Small, unit-testable functions that operate on the serialized layout blob, kept
out of :mod:`window` so they can be exercised without a QGIS environment.
"""


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
