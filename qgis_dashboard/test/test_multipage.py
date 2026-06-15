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

    def test_sources_of_is_reverse_lookup(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        bus.set_targets("s1", ["t", "x"])
        bus.set_targets("s2", ["t"])
        self.assertEqual(bus.sources_of("t"), {"s1", "s2"})
        self.assertEqual(bus.sources_of("x"), {"s1"})
        self.assertEqual(bus.sources_of("none"), set())

    def test_set_connected_toggles_single_edge(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        bus.set_targets("s", ["a", "b"])
        bus.set_connected("s", "c", True)
        self.assertEqual(bus.targets_of("s"), {"a", "b", "c"})
        bus.set_connected("s", "a", False)
        self.assertEqual(bus.targets_of("s"), {"b", "c"})
        bus.set_connected("s", "s", True)        # self-edge is ignored
        self.assertNotIn("s", bus.targets_of("s"))


class _FakeElement(object):
    """Minimal stand-in for a DashboardElement (the dialog only reads these)."""

    def __init__(self, eid, is_source, accepts):
        self.id = eid
        self.is_filter_source = is_source
        self.accepts_filter = accepts

    def display_name(self):
        return self.id


class ElementConnectionsDialogTest(unittest.TestCase):
    """The per-element connections dialog edits both directions in place."""

    def _setup(self, focus):
        from connections_dialog import ElementConnectionsDialog
        bus = DashboardBus()
        bus.set_active_page("A")
        # chart: both roles; selector: source only; indicator: target only
        chart = _FakeElement("chart", True, True)
        selector = _FakeElement("sel", True, False)
        indicator = _FakeElement("ind", False, True)
        elements = [chart, selector, indicator]
        focus_el = {"chart": chart, "sel": selector, "ind": indicator}[focus]
        dlg = ElementConnectionsDialog(bus, focus_el, elements)
        return bus, dlg

    def test_both_sections_present_for_dual_role_tile(self):
        bus, dlg = self._setup("chart")
        # outgoing target candidate: indicator; incoming source candidate: sel
        self.assertIn(("ind", "out"), dlg._checks)
        self.assertIn(("sel", "in"), dlg._checks)
        # chart never wires to itself
        self.assertNotIn(("chart", "out"), dlg._checks)

    def test_apply_writes_outgoing_and_incoming_edges(self):
        bus, dlg = self._setup("chart")
        dlg._checks[("ind", "out")].setChecked(True)   # chart filters indicator
        dlg._checks[("sel", "in")].setChecked(True)    # selector filters chart
        dlg.apply()
        self.assertTrue(bus.is_connected("chart", "ind"))
        self.assertTrue(bus.is_connected("sel", "chart"))

    def test_source_only_tile_shows_no_incoming_section(self):
        bus, dlg = self._setup("sel")
        self.assertTrue(any(d == "out" for _, d in dlg._checks))
        self.assertFalse(any(d == "in" for _, d in dlg._checks))

    def test_apply_can_clear_an_existing_edge(self):
        bus, dlg = self._setup("ind")
        bus.set_targets("sel", ["ind"])               # pre-existing sel → ind
        # rebuild so the checkbox reflects the existing edge
        from connections_dialog import ElementConnectionsDialog
        dlg = ElementConnectionsDialog(
            bus, _FakeElement("ind", False, True),
            [_FakeElement("sel", True, False), _FakeElement("ind", False, True)])
        self.assertTrue(dlg._checks[("sel", "in")].isChecked())
        dlg._checks[("sel", "in")].setChecked(False)
        dlg.apply()
        self.assertFalse(bus.is_connected("sel", "ind"))


class TextElementTest(unittest.TestCase):
    """The presentational text/heading container."""

    def _bus(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        return bus

    def test_factory_creates_text_element(self):
        from elements import create_element
        from elements.text_element import TextElement
        el = create_element("text", self._bus(), {"text": "Hi"})
        self.assertIsInstance(el, TextElement)

    def test_takes_no_part_in_cross_filtering(self):
        from elements import create_element
        el = create_element("text", self._bus(), {})
        self.assertFalse(el.is_filter_source)
        self.assertFalse(el.accepts_filter)

    def test_renders_text_and_alignment(self):
        from elements import create_element
        from qgis.PyQt.QtCore import Qt
        el = create_element("text", self._bus(),
                            {"text": "Heading", "align": "center"})
        self.assertEqual(el._label.text(), "Heading")
        self.assertTrue(el._label.alignment() & Qt.AlignHCenter)

    def test_empty_text_shows_placeholder(self):
        from elements import create_element
        from elements.text_element import _PLACEHOLDER
        el = create_element("text", self._bus(), {"text": ""})
        self.assertEqual(el._label.text(), _PLACEHOLDER)


class ImageElementTest(unittest.TestCase):
    def _bus(self):
        bus = DashboardBus()
        bus.set_active_page("A")
        return bus

    def test_is_full_bleed_presentational(self):
        from elements import create_element
        from elements.image_element import ImageElement
        el = create_element("image", self._bus(), {})
        self.assertIsInstance(el, ImageElement)
        self.assertTrue(el.full_bleed)
        self.assertFalse(el.is_filter_source)
        self.assertFalse(el.accepts_filter)

    def test_no_path_shows_placeholder(self):
        from elements import create_element
        el = create_element("image", self._bus(), {})
        self.assertIn("No image", el._label.text())

    def test_missing_file_is_reported(self):
        from elements import create_element
        el = create_element("image", self._bus(),
                            {"path": "/no/such/file.png"})
        self.assertIn("not found", el._label.text())


class AddElementDialogTest(unittest.TestCase):
    """Dynamic config rows for the new layerless tiles."""

    def _select(self, dlg, type_name):
        i = dlg.type_combo.findData(type_name)
        dlg.type_combo.setCurrentIndex(i)

    def test_text_hides_layer_row_and_returns_config(self):
        from add_element_dialog import AddElementDialog
        dlg = AddElementDialog()
        self._select(dlg, "indicator")
        self.assertFalse(dlg.layer_combo.isHidden())   # data tile shows layer
        self._select(dlg, "text")
        self.assertTrue(dlg.layer_combo.isHidden())     # layerless tile hides it
        dlg._dyn["text"].setPlainText("Title here")
        t, cfg = dlg.result_config()
        self.assertEqual(t, "text")
        self.assertEqual(cfg["text"], "Title here")
        self.assertIn("align", cfg)
        self.assertNotIn("layer_id", cfg)

    def test_image_returns_path_and_fit(self):
        from add_element_dialog import AddElementDialog
        dlg = AddElementDialog()
        self._select(dlg, "image")
        dlg._dyn["path"]._edit.setText("C:/pics/logo.svg")
        t, cfg = dlg.result_config()
        self.assertEqual(t, "image")
        self.assertEqual(cfg["path"], "C:/pics/logo.svg")
        self.assertEqual(cfg["fit"], "contain")


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
        # the horizontal toolbar was replaced by the left icon rail + status bar
        self.assertIn("#dashSidebar", qss)
        self.assertIn("QStatusBar", qss)

    def test_chrome_bg_round_trips(self):
        t = Theme.default().with_values(chrome_bg="#101010")
        self.assertEqual(Theme.from_dict(t.to_dict()).chrome_bg, "#101010")


if __name__ == "__main__":
    unittest.main()
