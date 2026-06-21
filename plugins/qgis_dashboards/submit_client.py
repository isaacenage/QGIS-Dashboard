# -*- coding: utf-8 -*-
"""Thin HTTP client that POSTs a dashboard submission to the public site.

Replaces the old direct-to-GitHub ``github_client``: the plugin no longer holds
a GitHub token. It sends the dashboard to the website's ``/api/submit`` endpoint
(see the design spec), which holds the only secret server-side and opens a
moderated Pull Request. Contributors need no account and no token.

The request goes through ``QgsNetworkAccessManager`` (so QGIS proxy/SSL settings
apply), blocked on a local event loop with a timeout — the same pattern the old
client used. Failures surface as :class:`PublishError` with a user-safe message.
"""

import json

from qgis.PyQt.QtCore import QUrl, QByteArray, QEventLoop, QTimer
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.core import QgsNetworkAccessManager

# The public intake endpoint and gallery (kept here so the plugin's only server
# coordinate lives in one place — no repo, branch or token anymore).
SUBMIT_URL = "https://qgis.byzenterra.org/api/submit"
GALLERY_URL = "https://qgis.byzenterra.org/qdashboards/gallery"

USER_AGENT = "QGIS-Dashboard-Plugin"
TIMEOUT_MS = 60000


class PublishError(Exception):
    """A submission failure with a message safe to show the user."""


def submit_dashboard(payload_bytes, url=SUBMIT_URL):
    """POST *payload_bytes* (UTF-8 JSON) to the intake endpoint.

    Returns the parsed JSON response dict on success (``{ok, slug, pr_url,
    view_url}``). Raises :class:`PublishError` on transport failure, timeout, or
    any non-2xx response (surfacing the server's ``message`` when present).
    """
    nam = QgsNetworkAccessManager.instance()
    request = QNetworkRequest(QUrl(url))
    request.setRawHeader(b"Content-Type", b"application/json")
    request.setRawHeader(b"Accept", b"application/json")
    request.setRawHeader(b"User-Agent", USER_AGENT.encode())

    reply = nam.post(request, QByteArray(payload_bytes))

    loop = QEventLoop()
    reply.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timed_out = {"value": False}

    def _on_timeout():
        timed_out["value"] = True
        reply.abort()

    timer.timeout.connect(_on_timeout)
    timer.start(TIMEOUT_MS)
    loop.exec()
    timer.stop()

    err = reply.error()
    status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
    data = bytes(reply.readAll())
    reply.deleteLater()

    if timed_out["value"]:
        raise PublishError("The gallery service didn't respond in time. Check "
                           "your connection and try again.")
    if err != QNetworkReply.NetworkError.NoError and status is None:
        raise PublishError(
            "Couldn't reach the gallery service. Check your internet connection "
            "or QGIS proxy settings.")

    status = int(status or 0)
    body = {}
    if data:
        try:
            body = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            body = {}

    if 200 <= status < 300 and body.get("ok"):
        return body

    # Prefer the server's own user-facing message when present.
    message = body.get("message") if isinstance(body, dict) else None
    if message:
        raise PublishError(message)
    # 413 is a size rejection, not a transient error — retrying never helps.
    if status == 413:
        raise PublishError(
            "This dashboard is too large for the gallery service. Try skipping "
            "or removing large layers, using lighter images, or splitting it "
            "into fewer pages, then publish again.")
    raise PublishError(
        "The gallery service rejected the submission (error {}). Please try "
        "again later.".format(status or "unknown"))
