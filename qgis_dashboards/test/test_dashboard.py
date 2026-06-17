# coding=utf-8
"""Dashboard core tests — connection bus, theme, and element registry.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'isaacenagework@gmail.com'
__date__ = '2026-06-15'
__copyright__ = 'Copyright 2026, Isaac Enage'

import unittest

from utilities import get_qgis_app

from bus import DashboardBus
from theme import Theme
from elements import ELEMENT_TYPES, ELEMENT_LABELS, create_element

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()


class DashboardBusTest(unittest.TestCase):
    """The bus routes a source's filter only to its connected targets."""

    def test_unconnected_source_does_not_reach_target(self):
        bus = DashboardBus()
        bus.set_filter("src", '"region" = \'North\'')
        self.assertIsNone(bus.combined_filter_for("tgt"))

    def test_connected_source_reaches_target(self):
        bus = DashboardBus()
        bus.set_targets("src", ["tgt"])
        bus.set_filter("src", '"region" = \'North\'')
        self.assertEqual(bus.combined_filter_for("tgt"),
                         '("region" = \'North\')')

    def test_multiple_sources_are_anded(self):
        bus = DashboardBus()
        bus.set_targets("s1", ["tgt"])
        bus.set_targets("s2", ["tgt"])
        bus.set_filter("s1", '"a" = 1')
        bus.set_filter("s2", '"b" = 2')
        self.assertEqual(bus.combined_filter_for("tgt"),
                         '("a" = 1) AND ("b" = 2)')

    def test_clear_all_filters(self):
        bus = DashboardBus()
        bus.set_targets("src", ["tgt"])
        bus.set_filter("src", '"a" = 1')
        bus.clear_all_filters()
        self.assertIsNone(bus.combined_filter_for("tgt"))
        self.assertEqual(bus.active_filter_count(), 0)

    def test_empty_filter_is_dropped(self):
        bus = DashboardBus()
        bus.set_targets("src", ["tgt"])
        bus.set_filter("src", "")
        self.assertIsNone(bus.combined_filter_for("tgt"))

    def test_forget_element_removes_from_graph(self):
        bus = DashboardBus()
        bus.set_targets("src", ["tgt"])
        bus.set_filter("src", '"a" = 1')
        bus.forget_element("src")
        self.assertIsNone(bus.combined_filter_for("tgt"))
        self.assertEqual(bus.targets_of("src"), set())

    def test_connections_round_trip(self):
        bus = DashboardBus()
        bus.set_targets("s1", ["t1", "t2"])
        data = bus.connections_to_dict()

        other = DashboardBus()
        other.load_connections(data)
        self.assertEqual(other.targets_of("s1"), {"t1", "t2"})


class ThemeTest(unittest.TestCase):
    def test_dict_round_trip(self):
        t = Theme.default()
        self.assertEqual(Theme.from_dict(t.to_dict()).to_dict(), t.to_dict())

    def test_override_merge(self):
        base = Theme.default()
        merged = base.merged_with({"surface_bg": "#000000"})
        self.assertEqual(merged.surface_bg, "#000000")
        # global accent untouched
        self.assertEqual(merged.accent, base.accent)

    def test_empty_override_ignored(self):
        base = Theme.default()
        merged = base.merged_with({"font_family": ""})
        self.assertEqual(merged.font_family, base.font_family)


class ElementRegistryTest(unittest.TestCase):
    """Every registered type must be constructible from an empty config."""

    def test_labels_cover_every_type(self):
        self.assertEqual(set(ELEMENT_TYPES), set(ELEMENT_LABELS))

    def test_create_each_element(self):
        bus = DashboardBus(IFACE)
        for type_name in ELEMENT_TYPES:
            el = create_element(type_name, bus, {}, PARENT)
            self.assertEqual(el.type_name, type_name)
            self.assertTrue(el.id)
            d = el.to_dict()
            self.assertEqual(d.get("__type__"), type_name)
            self.assertEqual(d.get("id"), el.id)

    def test_unknown_type_raises(self):
        bus = DashboardBus()
        with self.assertRaises(ValueError):
            create_element("does_not_exist", bus, {}, PARENT)


if __name__ == "__main__":
    unittest.main()
