# -*- coding: utf-8 -*-
"""Unit tests for layout_util (pure, no QGIS).

Run directly so the test package __init__ (which imports qgis) is not loaded:
    PYTHONPATH=$(pwd) python test/test_layout_util.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layout_util import default_locked


class TestDefaultLocked(unittest.TestCase):
    def test_empty_blob_is_unlocked(self):
        self.assertFalse(default_locked({}))

    def test_pages_with_no_elements_is_unlocked(self):
        blob = {"pages": [{"id": "a", "elements": []},
                          {"id": "b", "elements": []}]}
        self.assertFalse(default_locked(blob))

    def test_any_page_with_elements_is_locked(self):
        blob = {"pages": [{"id": "a", "elements": []},
                          {"id": "b", "elements": [{"__type__": "chart"}]}]}
        self.assertTrue(default_locked(blob))

    def test_first_page_with_elements_is_locked(self):
        blob = {"pages": [{"id": "a", "elements": [{"__type__": "indicator"}]}]}
        self.assertTrue(default_locked(blob))


if __name__ == "__main__":
    unittest.main()
