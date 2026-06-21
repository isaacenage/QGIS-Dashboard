# -*- coding: utf-8 -*-
"""Unit tests for submit_payload (pure, no QGIS).

Run directly so the test package __init__ (which imports qgis) is not loaded:
    PYTHONPATH=$(pwd) python test/test_submit_payload.py
"""
import base64
import gzip
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from submit_payload import (
    gzip_b64, b64, build_payload, payload_bytes,
    MAX_PAYLOAD_BYTES, exceeds_size_limit,
)


class TestGzipB64(unittest.TestCase):
    def test_round_trip_from_str(self):
        html = "<html>QGIS Dashboard, the quick brown fox</html>" * 50
        encoded = gzip_b64(html)
        # decode the way the server does: base64 -> gunzip -> utf-8
        restored = gzip.decompress(base64.b64decode(encoded)).decode("utf-8")
        self.assertEqual(restored, html)

    def test_round_trip_from_bytes(self):
        raw = b"\x00\x01binary-ish\xffdata"
        restored = gzip.decompress(base64.b64decode(gzip_b64(raw)))
        self.assertEqual(restored, raw)

    def test_actually_compresses_repetitive_html(self):
        html = "<div class='tile'></div>" * 1000
        compressed_len = len(base64.b64decode(gzip_b64(html)))
        self.assertLess(compressed_len, len(html.encode("utf-8")))

    def test_ascii_output(self):
        encoded = gzip_b64("héllo")
        encoded.encode("ascii")  # must not raise


class TestB64(unittest.TestCase):
    def test_round_trip(self):
        data = b"\x89PNG\r\n\x1a\n fake png bytes"
        self.assertEqual(base64.b64decode(b64(data)), data)


class TestBuildPayload(unittest.TestCase):
    def test_required_fields_present(self):
        p = build_payload("My Map", "Isaac", "<html>id=\"dashboard-data\"</html>",
                          b"PNGDATA")
        self.assertEqual(p["title"], "My Map")
        self.assertEqual(p["author"], "Isaac")
        self.assertIn("html_gz_b64", p)
        self.assertIn("thumb_b64", p)

    def test_html_field_is_gzip_b64(self):
        html = "<html>id=\"dashboard-data\"</html>"
        p = build_payload("T", "A", html, b"x")
        restored = gzip.decompress(base64.b64decode(p["html_gz_b64"])).decode("utf-8")
        self.assertEqual(restored, html)

    def test_thumb_field_is_b64(self):
        p = build_payload("T", "A", "<html></html>", b"THUMB")
        self.assertEqual(base64.b64decode(p["thumb_b64"]), b"THUMB")

    def test_description_included_when_present(self):
        p = build_payload("T", "A", "<html></html>", b"x", description="A summary")
        self.assertEqual(p["description"], "A summary")

    def test_description_omitted_when_empty(self):
        for desc in (None, "", "   "):
            p = build_payload("T", "A", "<html></html>", b"x", description=desc)
            self.assertNotIn("description", p)

    def test_none_title_author_become_empty_strings(self):
        p = build_payload(None, None, "<html></html>", b"x")
        self.assertEqual(p["title"], "")
        self.assertEqual(p["author"], "")


class TestSizeGuard(unittest.TestCase):
    def test_small_payload_is_within_limit(self):
        raw = payload_bytes(build_payload("T", "A", "<html></html>", b"x"))
        self.assertFalse(exceeds_size_limit(raw))

    def test_oversize_payload_flagged(self):
        self.assertTrue(exceeds_size_limit(b"x" * (MAX_PAYLOAD_BYTES + 1)))

    def test_boundary_exactly_at_limit_is_ok(self):
        self.assertFalse(exceeds_size_limit(b"x" * MAX_PAYLOAD_BYTES))

    def test_limit_stays_under_vercel_cap(self):
        # Vercel rejects request bodies over ~4.5 MB with HTTP 413; our
        # client-side guard must trip below that, with headroom to spare.
        self.assertLessEqual(MAX_PAYLOAD_BYTES, 4_500_000)


class TestPayloadBytes(unittest.TestCase):
    def test_is_utf8_json(self):
        p = build_payload("Café", "José", "<html></html>", b"x", description="ñ")
        raw = payload_bytes(p)
        self.assertIsInstance(raw, bytes)
        self.assertEqual(json.loads(raw.decode("utf-8")), p)


if __name__ == "__main__":
    unittest.main()
