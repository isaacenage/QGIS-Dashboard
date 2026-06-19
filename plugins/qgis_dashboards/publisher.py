# -*- coding: utf-8 -*-
"""Orchestrates *Publish to public*: dashboard -> intake endpoint -> moderated PR.

Runs on the UI thread (it renders widgets and shows a progress dialog). Builds
the self-contained HTML (:mod:`export.html_export`) and an off-screen thumbnail,
then POSTs them (HTML gzipped) to the website's ``/api/submit`` endpoint via
:mod:`submit_client`. The endpoint holds the only secret server-side and opens a
Pull Request the maintainer reviews; nothing is committed from the plugin.
"""

from qgis.PyQt.QtCore import Qt, QByteArray, QBuffer, QIODevice

from .export.html_export import build_dashboard_html, oversize_layers, _project_title
from .submit_client import submit_dashboard, PublishError
from . import submit_payload

THUMB_WIDTH = 800
# Mirror the export-dialog large-data guard.
MAX_FEATURES = 100000
MAX_BYTES = 50 * 1024 * 1024


def _noop(_step, _frac):
    pass


def render_thumbnail_png(window):
    """Render the current page to PNG bytes (~THUMB_WIDTH wide), or ``None``.

    Uses the canvas's own ``export_pixmap`` (which hides editing chrome and the
    region frame and restores them after) so the thumbnail is the clean page.
    """
    view = window.current_view()
    if view is None:
        return None
    pixmap = view.export_pixmap(scale=2.0)
    if pixmap is None or pixmap.isNull():
        return None
    image = pixmap.toImage()
    image.setDevicePixelRatio(1.0)   # normalize: work in physical pixels
    if image.width() > THUMB_WIDTH:
        image = image.scaledToWidth(
            THUMB_WIDTH, Qt.TransformationMode.SmoothTransformation)
    buffer_bytes = QByteArray()
    buffer = QBuffer(buffer_bytes)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        return None
    return bytes(buffer_bytes)


def publish_dashboard(window, author, description=None, skip_layers=None,
                      progress=None):
    """Submit the current dashboard for review. Returns the endpoint response.

    On success the response is ``{"ok", "slug", "pr_url", "view_url"}`` — a
    moderated PR has been opened; the dashboard goes live once the maintainer
    merges it. Raises :class:`PublishError` (user-safe message) on any failure.
    """
    progress = progress or _noop

    # --- local work first (UI thread): build HTML + thumbnail -------------
    progress("Building dashboard…", 0.15)
    html = build_dashboard_html(window, skip_layers=skip_layers)

    progress("Rendering thumbnail…", 0.35)
    thumb_bytes = render_thumbnail_png(window)
    if not thumb_bytes:
        raise PublishError("Couldn't render a dashboard thumbnail. Make sure the "
                           "dashboard window is open with at least one page.")

    title = _project_title()

    # --- send to the moderated intake endpoint ----------------------------
    progress("Uploading…", 0.55)
    payload = submit_payload.build_payload(
        title, author, html, thumb_bytes, description=description)
    result = submit_dashboard(submit_payload.payload_bytes(payload))

    progress("Done", 1.0)
    return result


def oversize_referenced_layers(window):
    """Large bound layers, for the pre-publish warning (reuses the export guard)."""
    return oversize_layers(window, MAX_FEATURES, MAX_BYTES)
