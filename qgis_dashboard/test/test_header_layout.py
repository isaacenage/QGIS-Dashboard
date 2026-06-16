# coding=utf-8
"""Tests for the pure header-layout helpers (no QGIS runtime needed).

Run directly so the test package ``__init__`` (which imports qgis) is not
loaded::

    cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_header_layout.py
"""

__author__ = 'isaacenagework@gmail.com'
__date__ = '2026-06-16'
__copyright__ = 'Copyright 2026, Isaac Enage'

import os
import sys
import unittest

# Import the pure helper directly from the ``elements`` dir so the package
# ``__init__`` (which imports qgis) is not loaded.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "elements"))

from header_layout import banner_compose, box_direction, header_tile_placement


class BannerComposeTest(unittest.TestCase):
    """Geometry for flattening a docked banner + canvas into one export image."""

    def test_top_banner_stacks_above_canvas(self):
        total_w, total_h, banner_pos, banner_size, canvas_pos = banner_compose(
            "top", 80, 1000, 600)
        self.assertEqual((total_w, total_h), (1000, 680))
        self.assertEqual(banner_pos, (0, 0))
        self.assertEqual(banner_size, (1000, 80))      # spans full width
        self.assertEqual(canvas_pos, (0, 80))          # canvas pushed down

    def test_bottom_banner_sits_below_canvas(self):
        total_w, total_h, banner_pos, banner_size, canvas_pos = banner_compose(
            "bottom", 80, 1000, 600)
        self.assertEqual((total_w, total_h), (1000, 680))
        self.assertEqual(canvas_pos, (0, 0))
        self.assertEqual(banner_pos, (0, 600))         # below the canvas
        self.assertEqual(banner_size, (1000, 80))

    def test_left_banner_spans_height(self):
        total_w, total_h, banner_pos, banner_size, canvas_pos = banner_compose(
            "left", 120, 1000, 600)
        self.assertEqual((total_w, total_h), (1120, 600))
        self.assertEqual(banner_pos, (0, 0))
        self.assertEqual(banner_size, (120, 600))      # spans full height
        self.assertEqual(canvas_pos, (120, 0))         # canvas pushed right

    def test_right_banner_sits_right_of_canvas(self):
        total_w, total_h, banner_pos, banner_size, canvas_pos = banner_compose(
            "right", 120, 1000, 600)
        self.assertEqual((total_w, total_h), (1120, 600))
        self.assertEqual(canvas_pos, (0, 0))
        self.assertEqual(banner_pos, (1000, 0))        # right of the canvas
        self.assertEqual(banner_size, (120, 600))

    def test_unknown_anchor_falls_back_to_top(self):
        self.assertEqual(banner_compose("sideways", 50, 200, 100),
                         banner_compose("top", 50, 200, 100))
        # and matches box_direction's own fallback
        self.assertEqual(box_direction("sideways"), box_direction("top"))


class HeaderTilePlacementTest(unittest.TestCase):
    """Geometry for converting a docked legacy header into a canvas tile."""

    def test_top_places_band_and_shifts_tiles_down(self):
        rect, shift, region = header_tile_placement("top", 80, 1000, 600)
        self.assertEqual(rect, (0, 0, 1000, 80))      # full-width band at the top
        self.assertEqual(shift, (0, 80))              # existing tiles move down
        self.assertEqual(region, (1000, 680))         # region grows in height

    def test_bottom_places_band_and_leaves_tiles(self):
        rect, shift, region = header_tile_placement("bottom", 80, 1000, 600)
        self.assertEqual(rect, (0, 600, 1000, 80))    # band below the old region
        self.assertEqual(shift, (0, 0))               # tiles unchanged
        self.assertEqual(region, (1000, 680))

    def test_left_places_band_and_shifts_tiles_right(self):
        rect, shift, region = header_tile_placement("left", 120, 1000, 600)
        self.assertEqual(rect, (0, 0, 120, 600))      # full-height band at the left
        self.assertEqual(shift, (120, 0))             # tiles move right
        self.assertEqual(region, (1120, 600))         # region grows in width

    def test_right_places_band_and_leaves_tiles(self):
        rect, shift, region = header_tile_placement("right", 120, 1000, 600)
        self.assertEqual(rect, (1000, 0, 120, 600))   # band right of the old region
        self.assertEqual(shift, (0, 0))
        self.assertEqual(region, (1120, 600))

    def test_unknown_anchor_falls_back_to_top(self):
        self.assertEqual(header_tile_placement("sideways", 50, 200, 100),
                         header_tile_placement("top", 50, 200, 100))


if __name__ == "__main__":
    unittest.main()
