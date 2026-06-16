# coding=utf-8
"""Tests for the HTML export's pure (Qt/QGIS-free) modules.

Mirrors the pivot_engine testing pattern: the serialization, theme-to-CSS, and
HTML-assembly logic is exercised on plain dicts with no QGIS runtime. The
QGIS-touching collectors and the JS runtime are verified manually inside QGIS /
a browser (see the design spec's testing section).
"""

__author__ = 'isaacenagework@gmail.com'
__date__ = '2026-06-16'
__copyright__ = 'Copyright 2026, Isaac Enage'

import json
import unittest

from export.serialize import (
    build_model, build_tile, build_page, clean_config, EXPORT_VERSION,
)
from export.theme_css import theme_to_css_vars
from export.html_builder import build_html, embed_json


class CleanConfigTest(unittest.TestCase):
    def test_drops_id_keeps_rest(self):
        cfg = {"id": "abc", "title": "Pop", "layer_id": "L1", "chart_type": "bar"}
        out = clean_config(cfg)
        self.assertNotIn("id", out)
        self.assertEqual(out["title"], "Pop")
        self.assertEqual(out["chart_type"], "bar")

    def test_none_yields_empty(self):
        self.assertEqual(clean_config(None), {})


class BuildTileTest(unittest.TestCase):
    def test_minimal_tile(self):
        tile = {"id": "t1", "type": "chart",
                "grid": {"x": 0, "y": 0, "w": 4, "h": 3},
                "config": {"id": "t1", "category_field": "region"}}
        out = build_tile(tile)
        self.assertEqual(out["id"], "t1")
        self.assertEqual(out["type"], "chart")
        self.assertEqual(out["grid"], {"x": 0, "y": 0, "w": 4, "h": 3})
        self.assertEqual(out["config"], {"category_field": "region"})
        # absent optional keys are omitted entirely
        self.assertNotIn("layer_id", out)
        self.assertNotIn("base_pass", out)

    def test_optional_keys_passthrough(self):
        tile = {"id": "m", "type": "map", "grid": {},
                "map_image": "data:image/png;base64,AAAA",
                "layer_id": "L1", "base_pass": [0, 2]}
        out = build_tile(tile)
        self.assertEqual(out["map_image"], "data:image/png;base64,AAAA")
        self.assertEqual(out["layer_id"], "L1")
        self.assertEqual(out["base_pass"], [0, 2])

    def test_none_optional_is_omitted(self):
        tile = {"id": "i", "type": "indicator", "grid": {},
                "indicator_value": None}
        out = build_tile(tile)
        self.assertNotIn("indicator_value", out)

    def test_indicator_icon_uri_passthrough(self):
        tile = {"id": "i", "type": "indicator", "grid": {},
                "icon_uri": "data:image/png;base64,ZZ",
                "config": {"animation": "odometer", "value_size": 48}}
        out = build_tile(tile)
        self.assertEqual(out["icon_uri"], "data:image/png;base64,ZZ")
        self.assertEqual(out["config"]["animation"], "odometer")
        self.assertEqual(out["config"]["value_size"], 48)


class HeaderTileTest(unittest.TestCase):
    def test_header_is_a_normal_tile_with_logo_uri(self):
        # the header is a positioned tile now — no separate docked-banner key
        page = {"id": "p1", "title": "P", "connections": {},
                "tiles": [{"id": "h", "type": "header",
                           "grid": {"x": 0, "y": 0, "w": 1000, "h": 80},
                           "logo_uri": "data:image/png;base64,AA",
                           "config": {"title": "Brand", "logo_slot": "left"}}]}
        out = build_page(page)
        self.assertNotIn("header", out)
        hdr = out["tiles"][0]
        self.assertEqual(hdr["type"], "header")
        self.assertEqual(hdr["logo_uri"], "data:image/png;base64,AA")
        self.assertEqual(hdr["config"]["title"], "Brand")

    def test_no_header_key_on_a_plain_page(self):
        out = build_page({"id": "p1", "title": "P", "connections": {},
                          "tiles": []})
        self.assertNotIn("header", out)


class BuildModelTest(unittest.TestCase):
    def _page(self):
        return {"id": "p1", "title": "Page 1",
                "connections": {"s": ["t"]},
                "tiles": [{"id": "s", "type": "chart", "grid": {},
                           "config": {}}]}

    def test_top_level_shape(self):
        model = build_model((12, 8), {"accent": "#123456"}, "p1",
                            [self._page()], {"L1": {"fields": [], "features": []}})
        self.assertEqual(model["version"], EXPORT_VERSION)
        self.assertEqual(model["grid"], {"cols": 12, "rows": 8})
        self.assertEqual(model["theme"], {"accent": "#123456"})
        self.assertEqual(model["active_page"], "p1")
        self.assertEqual(len(model["pages"]), 1)
        self.assertEqual(model["pages"][0]["connections"], {"s": ["t"]})
        self.assertIn("L1", model["layers"])

    def test_gap_defaults_to_zero(self):
        model = build_model((12, 8), {}, "p1", [self._page()], {})
        self.assertEqual(model["gap"], 0)

    def test_gap_is_carried_through(self):
        model = build_model((12, 8), {}, "p1", [self._page()], {}, gap=16)
        self.assertEqual(model["gap"], 16)

    def test_round_trips_through_json(self):
        model = build_model((10, 6), {}, "p1", [self._page()], {})
        again = json.loads(json.dumps(model))
        self.assertEqual(again["grid"]["cols"], 10)


class ThemeCssTest(unittest.TestCase):
    def test_emits_core_variables(self):
        css = theme_to_css_vars({"accent": "#2b7de9", "surface_bg": "#ffffff"})
        self.assertIn(":root", css)
        self.assertIn("--accent: #2b7de9;", css)
        self.assertIn("--surface-bg: #ffffff;", css)

    def test_derives_accent_hover_darker(self):
        css = theme_to_css_vars({"accent": "#ffffff"})
        # 255 * 0.86 = 219 -> 0xdb
        self.assertIn("--accent-hover: #dbdbdb;", css)

    def test_series_become_indexed_vars(self):
        css = theme_to_css_vars({"series": ["#111111", "#222222"]})
        self.assertIn("--series-0: #111111;", css)
        self.assertIn("--series-1: #222222;", css)

    def test_missing_keys_fall_back(self):
        css = theme_to_css_vars({})
        self.assertIn("--accent: #2b7de9;", css)
        self.assertIn("Inter", css)

    def test_heading_family_defaults_to_body(self):
        css = theme_to_css_vars({"font_family": "Poppins"})
        # No separate heading font -> heading stack collapses to the body stack.
        self.assertIn('--heading-family: "Poppins",', css)

    def test_heading_family_pairing_leads_with_heading(self):
        css = theme_to_css_vars(
            {"font_family": "Open Sans", "heading_font": "Playfair Display"})
        self.assertIn('--heading-family: "Playfair Display", "Open Sans",', css)


class HtmlBuilderTest(unittest.TestCase):
    def test_embed_json_neutralizes_script_close(self):
        embedded = embed_json({"x": "</script><b>hi"})
        self.assertNotIn("</script>", embedded)
        self.assertIn("<\\/script>", embedded)

    def test_build_html_contains_data_css_and_js(self):
        model = build_model((12, 8), {"accent": "#abcdef"}, "p1",
                            [{"id": "p1", "title": "P", "connections": {},
                              "tiles": []}], {})
        html = build_html(model, ":root{--accent:#abcdef;}",
                          "/*css*/", "/*js*/", title="My Dash")
        self.assertIn("<!doctype html>", html)
        self.assertIn('id="dashboard-data"', html)
        self.assertIn("--accent:#abcdef;", html)
        self.assertIn("/*js*/", html)
        self.assertIn("<title>My Dash</title>", html)
        # the embedded JSON is real, parseable JSON
        marker = 'id="dashboard-data">'
        start = html.index(marker) + len(marker)
        end = html.index("</script>", start)
        parsed = json.loads(html[start:end])
        self.assertEqual(parsed["theme"]["accent"], "#abcdef")

    def test_build_html_escapes_title(self):
        model = build_model((1, 1), {}, None, [], {})
        html = build_html(model, "", "", "", title="<evil>")
        self.assertIn("&lt;evil&gt;", html)
        self.assertNotIn("<title><evil>", html)


if __name__ == "__main__":
    unittest.main()
