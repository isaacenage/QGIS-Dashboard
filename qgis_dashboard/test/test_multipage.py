# coding=utf-8
"""Tests for multi-page, zoom/pan, and resize-handle features."""

__author__ = 'isaacenagework@gmail.com'
__date__ = '2026-06-15'
__copyright__ = 'Copyright 2026, Isaac Enage'

import unittest

from utilities import get_qgis_app

from dashboard_canvas import _proposed_resize, DashboardCanvas
from bus import DashboardBus
from page_view import clamp_zoom, PageView
from window import migrate_layout, DashboardWindow, DEFAULT_COLS, DEFAULT_ROWS
from theme import Theme

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()


class ResizeMathTest(unittest.TestCase):
    START = (100, 100, 200, 150)   # x, y, w, h

    def test_south_east_grows_size_only(self):
        self.assertEqual(_proposed_resize("se", self.START, 30, 40),
                         (100, 100, 230, 190))

    def test_east_changes_width_only(self):
        self.assertEqual(_proposed_resize("e", self.START, 30, 999),
                         (100, 100, 230, 150))

    def test_north_moves_top_and_changes_height(self):
        self.assertEqual(_proposed_resize("n", self.START, 0, -40),
                         (100, 60, 200, 190))

    def test_west_moves_left_and_changes_width(self):
        self.assertEqual(_proposed_resize("w", self.START, -30, 0),
                         (70, 100, 230, 150))

    def test_north_west_moves_both_origins(self):
        self.assertEqual(_proposed_resize("nw", self.START, -30, -40),
                         (70, 60, 230, 190))

    def test_min_size_clamps_and_pins_origin(self):
        x, y, w, h = _proposed_resize("w", self.START, 500, 0, min_px=40)
        self.assertEqual(w, 40)
        self.assertEqual(x, 260)   # original right edge (100+200) - 40


class BusPageLocalTest(unittest.TestCase):
    def test_filter_is_isolated_per_page(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        bus.set_targets("src", ["tgt"])
        bus.set_filter("src", '"a" = 1')
        self.assertEqual(bus.combined_filter_for("tgt"), '("a" = 1)')

        bus.set_active_page("B")
        self.assertIsNone(bus.combined_filter_for("tgt"))

        bus.set_active_page("A")
        self.assertEqual(bus.combined_filter_for("tgt"), '("a" = 1)')

    def test_connections_round_trip_per_page(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        bus.set_targets("s1", ["t1", "t2"])
        data = bus.connections_to_dict("A")

        other = DashboardBus()
        other.set_active_page("A")
        other.load_connections(data, "A")
        self.assertEqual(other.targets_of("s1"), {"t1", "t2"})

    def test_forget_page_drops_state(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        bus.set_targets("src", ["tgt"])
        bus.set_filter("src", '"a" = 1')
        bus.forget_page("A")
        bus.set_active_page("A")   # recreated empty
        self.assertIsNone(bus.combined_filter_for("tgt"))

    def test_clear_all_filters_uses_in_place_clear(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        bus.set_targets("src", ["tgt"])
        bus.set_filter("src", '"a" = 1')
        bus.clear_all_filters()
        self.assertIsNone(bus.combined_filter_for("tgt"))
        self.assertEqual(bus.active_filter_count(), 0)


class ZoomTest(unittest.TestCase):
    def test_clamp_zoom_bounds(self):
        self.assertEqual(clamp_zoom(0.1), 0.5)
        self.assertEqual(clamp_zoom(9.0), 3.0)
        self.assertAlmostEqual(clamp_zoom(1.25), 1.25)

    def test_pageview_default_zoom_is_one(self):
        view = PageView(DashboardCanvas(None, 12, 8))
        self.assertAlmostEqual(view.zoom(), 1.0)

    def test_pageview_set_zoom_clamps(self):
        view = PageView(DashboardCanvas(None, 12, 8))
        view.set_zoom(10.0)
        self.assertEqual(view.zoom(), 3.0)


class MigrateLayoutTest(unittest.TestCase):
    def test_v1_bare_list_becomes_one_page(self):
        data = migrate_layout([{"__type__": "indicator", "id": "a"}])
        self.assertEqual(data["version"], 3)
        self.assertEqual(len(data["pages"]), 1)
        self.assertEqual(data["pages"][0]["title"], "Page 1")
        self.assertEqual(data["pages"][0]["elements"][0]["id"], "a")
        self.assertEqual(data["grid"], {"cols": DEFAULT_COLS,
                                        "rows": DEFAULT_ROWS})

    def test_v2_wraps_elements_and_connections(self):
        v2 = {
            "version": 2,
            "grid": {"cols": 10, "rows": 6},
            "theme": {"accent": "#123456"},
            "connections": {"s": ["t"]},
            "elements": [{"__type__": "serial_chart", "id": "s"}],
        }
        data = migrate_layout(v2)
        self.assertEqual(data["version"], 3)
        self.assertEqual(data["grid"], {"cols": 10, "rows": 6})
        self.assertEqual(data["theme"], {"accent": "#123456"})
        self.assertEqual(len(data["pages"]), 1)
        self.assertEqual(data["pages"][0]["connections"], {"s": ["t"]})
        self.assertEqual(data["pages"][0]["elements"][0]["id"], "s")

    def test_v3_passes_through(self):
        v3 = {
            "version": 3,
            "grid": {"cols": 12, "rows": 8},
            "theme": {},
            "active_page": "p2",
            "pages": [
                {"id": "p1", "title": "One", "connections": {},
                 "elements": []},
                {"id": "p2", "title": "Two", "connections": {"a": ["b"]},
                 "elements": [{"__type__": "list", "id": "a"}]},
            ],
        }
        data = migrate_layout(v3)
        self.assertEqual(data["active_page"], "p2")
        self.assertEqual(len(data["pages"]), 2)
        self.assertEqual(data["pages"][1]["connections"], {"a": ["b"]})

    def test_empty_input_yields_one_empty_page(self):
        data = migrate_layout(None)
        self.assertEqual(len(data["pages"]), 1)
        self.assertEqual(data["pages"][0]["elements"], [])


class MultiPageWindowTest(unittest.TestCase):
    def _win(self):
        return DashboardWindow(IFACE)

    def test_starts_with_one_page(self):
        win = self._win()
        self.assertEqual(len(win.pages()), 1)
        self.assertIs(win.current_canvas(), win.pages()[0].canvas)

    def test_add_page_creates_and_activates(self):
        win = self._win()
        page = win.add_page("Second")
        self.assertEqual(len(win.pages()), 2)
        self.assertEqual(page.title, "Second")
        self.assertIs(win.current_canvas(), page.canvas)
        self.assertEqual(win.bus._active_page, page.id)

    def test_add_element_lands_on_current_page(self):
        win = self._win()
        win.add_page("Second")
        win.add_element("indicator", {"title": "X"})
        self.assertEqual(len(win.current_canvas().tiles()), 1)
        self.assertEqual(len(win.pages()[0].canvas.tiles()), 0)

    def test_delete_page_keeps_at_least_one(self):
        win = self._win()
        first = win.pages()[0]
        win.add_page("Second")
        win.delete_page(first.id)
        self.assertEqual(len(win.pages()), 1)
        last = win.pages()[0]
        win.delete_page(last.id)
        self.assertEqual(len(win.pages()), 1)


class ThemeChromeTest(unittest.TestCase):
    def test_default_chrome_is_white(self):
        self.assertEqual(Theme.default().chrome_bg, "#ffffff")

    def test_window_qss_styles_chrome_not_just_canvas(self):
        qss = Theme.default().window_qss()
        self.assertIn("QMainWindow", qss)
        self.assertIn("QTabBar::tab", qss)
        self.assertIn("QToolBar", qss)

    def test_chrome_bg_round_trips(self):
        t = Theme.default().with_values(chrome_bg="#101010")
        self.assertEqual(Theme.from_dict(t.to_dict()).chrome_bg, "#101010")


if __name__ == "__main__":
    unittest.main()
