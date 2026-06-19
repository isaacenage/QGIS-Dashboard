# -*- coding: utf-8 -*-
"""Orchestrates *Publish to public*: dashboard -> GitHub -> public URL.

Runs on the UI thread (it renders widgets and shows a progress dialog). Ties
together the pure manifest logic (:mod:`github_publish`), the HTML build
(:mod:`export.html_export`), an off-screen thumbnail render, and the atomic Git
Data commit (:mod:`github_client`).
"""

import base64
import datetime

from qgis.PyQt.QtCore import Qt, QByteArray, QBuffer, QIODevice

from .export.html_export import build_dashboard_html, oversize_layers, _project_title
from .github_client import GitHubClient, PublishError
from . import github_publish as gp

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


def _b64(data_bytes):
    return base64.b64encode(data_bytes).decode("ascii")


def publish_dashboard(window, token, repo, branch, author,
                      description=None, skip_layers=None, progress=None):
    """Publish the current dashboard. Returns ``{"url", "slug", "is_update"}``.

    Raises :class:`PublishError` (user-safe message) on any failure.
    """
    progress = progress or _noop

    # --- local work first (UI thread): build HTML + thumbnail -------------
    progress("Building dashboard…", 0.05)
    html = build_dashboard_html(window, skip_layers=skip_layers)
    html_bytes = html.encode("utf-8")

    progress("Rendering thumbnail…", 0.15)
    thumb_bytes = render_thumbnail_png(window)
    if not thumb_bytes:
        raise PublishError("Couldn't render a dashboard thumbnail. Make sure the "
                           "dashboard window is open with at least one page.")

    title = _project_title()
    slug = gp.slugify(title)
    today = datetime.date.today().isoformat()
    entry = gp.build_entry(slug, title, author, today, description=description)

    # --- talk to GitHub (atomic Git Data commit) --------------------------
    client = GitHubClient(token, repo, branch)

    progress("Reading repository…", 0.30)
    head_sha = client.head_commit_sha()
    base_tree_sha = client.commit_tree_sha(head_sha)
    manifest_text = client.read_text_file(gp.MANIFEST_PATH)
    new_manifest_text, is_update = gp.merge_manifest(manifest_text, entry)

    progress("Uploading files…", 0.55)
    html_blob = client.create_blob_base64(_b64(html_bytes))
    thumb_blob = client.create_blob_base64(_b64(thumb_bytes))
    manifest_blob = client.create_blob_base64(
        _b64(new_manifest_text.encode("utf-8")))

    progress("Committing…", 0.80)
    items = gp.tree_items([
        (gp.asset_repo_path(slug, "index.html"), html_blob),
        (gp.asset_repo_path(slug, "thumb.png"), thumb_blob),
        (gp.MANIFEST_PATH, manifest_blob),
    ])
    tree_sha = client.create_tree(base_tree_sha, items)
    verb = "Update" if is_update else "Publish"
    commit_sha = client.create_commit(
        "{} dashboard: {}".format(verb, title), tree_sha, head_sha)
    client.update_branch_ref(commit_sha)

    progress("Done", 1.0)
    return {
        "url": gp.public_view_url(slug),
        "slug": slug,
        "is_update": is_update,
    }


def oversize_referenced_layers(window):
    """Large bound layers, for the pre-publish warning (reuses the export guard)."""
    return oversize_layers(window, MAX_FEATURES, MAX_BYTES)
