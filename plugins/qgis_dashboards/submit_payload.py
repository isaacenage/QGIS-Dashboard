# -*- coding: utf-8 -*-
"""Pure (Qt-free) helpers for the *Publish to public* submission payload.

The plugin no longer commits to GitHub directly. Instead it POSTs a finished
dashboard to the website's ``/api/submit`` endpoint, which moderates it into a
Pull Request (see ``submit_client`` for the QGIS-touching POST and
``docs/superpowers/specs/2026-06-20-public-gallery-submissions-design.md``).

The HTML is **gzipped** before sending: Vercel serverless functions cap request
bodies at ~4.5 MB, and self-contained dashboards routinely exceed that
uncompressed. HTML compresses ~5–10×, so this keeps typical dashboards within
the wire budget. Everything here is plain Python so it unit-tests under a bare
``PYTHONPATH`` (run ``test/test_submit_payload.py`` directly).
"""

import base64
import gzip
import json

# Vercel serverless functions reject request bodies larger than ~4.5 MB with
# HTTP 413. We refuse client-side a little under that (leaving headroom for
# request headers / framing) so the user gets an actionable message instead of
# an opaque server rejection. See ``exceeds_size_limit`` and the publisher's
# preflight check.
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024  # 4 MB


def gzip_b64(html):
    """Return base64(gzip(utf-8 *html*)) as an ASCII ``str``."""
    if isinstance(html, str):
        html = html.encode("utf-8")
    compressed = gzip.compress(html)
    return base64.b64encode(compressed).decode("ascii")


def b64(data_bytes):
    """Return base64 of raw bytes as an ASCII ``str``."""
    return base64.b64encode(data_bytes).decode("ascii")


def build_payload(title, author, html, thumb_bytes, description=None):
    """Build the JSON-serializable submission body for ``/api/submit``.

    The endpoint expects ``{title, author, description?, html_gz_b64, thumb_b64}``.
    *description* is omitted when empty so the server treats it as absent.
    """
    payload = {
        "title": title or "",
        "author": author or "",
        "html_gz_b64": gzip_b64(html),
        "thumb_b64": b64(thumb_bytes),
    }
    desc = (description or "").strip()
    if desc:
        payload["description"] = desc
    return payload


def payload_bytes(payload):
    """Encode a payload dict as UTF-8 JSON bytes ready to POST."""
    return json.dumps(payload).encode("utf-8")


def exceeds_size_limit(raw):
    """True if *raw* (the POST body bytes) is over the gallery's request cap.

    The boundary is inclusive: a body exactly at :data:`MAX_PAYLOAD_BYTES` is
    still accepted; only strictly larger bodies are rejected.
    """
    return len(raw) > MAX_PAYLOAD_BYTES
