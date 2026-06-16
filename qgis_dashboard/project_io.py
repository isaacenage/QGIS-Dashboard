# -*- coding: utf-8 -*-
"""Read/write the standalone ``.qdash`` dashboard file.

A ``.qdash`` file is the *portable* twin of the layout blob that
:meth:`window.DashboardWindow.save_to_project` embeds inside the ``.qgz``: the
exact same v3 JSON dict, plus a top-level ``"_format"`` marker so the file is
self-identifying. Older files load through the existing pure
``window.migrate_layout`` helper, so they auto-upgrade just like older ``.qgz``
blobs (``migrate_layout`` ignores the extra ``_format`` key).

This module is deliberately **pure** — no QGIS/Qt imports — so it can be
unit-tested without a QGIS environment (see ``test/test_project_io.py``).
"""

import json
import os

QDASH_SUFFIX = ".qdash"
QDASH_FILTER = "QGIS Dashboard (*.qdash)"
FORMAT_TAG = "qgis-dashboard"


def ensure_suffix(path):
    """Return *path* with a ``.qdash`` extension (added if missing).

    The check is case-insensitive so ``foo.QDASH`` is left untouched.
    """
    text = str(path or "")
    if text.lower().endswith(QDASH_SUFFIX):
        return text
    return text + QDASH_SUFFIX


def write_layout_file(path, data):
    """Write the layout *data* dict to ``ensure_suffix(path)`` as JSON.

    Returns the final path written. Does **not** mutate *data*: the
    ``"_format"`` marker is added to a shallow copy.
    """
    final_path = ensure_suffix(path)
    payload = dict(data or {})
    payload["_format"] = FORMAT_TAG
    with open(final_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return final_path


def read_layout_file(path):
    """Read a ``.qdash`` file and return its raw layout dict.

    The caller is expected to run the result through ``migrate_layout``.
    Raises :class:`ValueError` if the file does not hold a JSON object, and
    propagates :class:`OSError` if the file cannot be read.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError("Not a QGIS Dashboard file: expected a JSON object.")
    return raw


def display_name(path):
    """A friendly dashboard name derived from the file name (no extension)."""
    base = os.path.basename(str(path or ""))
    return os.path.splitext(base)[0] or "Dashboard"
