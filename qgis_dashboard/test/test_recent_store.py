# coding=utf-8
"""Tests for the pure recents helpers (no QGIS runtime needed).

Run directly::

    cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_recent_store.py
"""

__author__ = 'isaacenagework@gmail.com'
__date__ = '2026-06-16'
__copyright__ = 'Copyright 2026, Isaac Enage'

import unittest

from recent_store import prune_missing, dedupe_insert


class PruneMissingTest(unittest.TestCase):
    def test_keeps_only_existing(self):
        items = [{"path": "/keep"}, {"path": "/gone"}, {"path": "/keep2"}]
        present = {"/keep", "/keep2"}
        out = prune_missing(items, exists=lambda p: p in present)
        self.assertEqual([i["path"] for i in out], ["/keep", "/keep2"])

    def test_drops_blank_and_non_dict(self):
        items = [{"path": ""}, "nope", {"path": "/ok"}]
        out = prune_missing(items, exists=lambda p: True)
        self.assertEqual([i["path"] for i in out], ["/ok"])

    def test_handles_none(self):
        self.assertEqual(prune_missing(None), [])


class DedupeInsertTest(unittest.TestCase):
    def test_inserts_at_front(self):
        out = dedupe_insert([{"path": "/a"}], {"path": "/b"})
        self.assertEqual([i["path"] for i in out], ["/b", "/a"])

    def test_removes_existing_same_path(self):
        items = [{"path": "/a"}, {"path": "/b"}]
        out = dedupe_insert(items, {"path": "/b", "name": "B2"})
        self.assertEqual([i["path"] for i in out], ["/b", "/a"])
        self.assertEqual(out[0]["name"], "B2")

    def test_caps_to_max(self):
        items = [{"path": "/%d" % i} for i in range(8)]
        out = dedupe_insert(items, {"path": "/new"}, max_items=8)
        self.assertEqual(len(out), 8)
        self.assertEqual(out[0]["path"], "/new")

    def test_input_not_mutated(self):
        items = [{"path": "/a"}]
        dedupe_insert(items, {"path": "/b"})
        self.assertEqual([i["path"] for i in items], ["/a"])


if __name__ == "__main__":
    unittest.main()
