# coding=utf-8
"""Tests for the pivot engine and the PivotElement."""

__author__ = 'isaacenagework@gmail.com'
__date__ = '2026-06-16'
__copyright__ = 'Copyright 2026, Isaac Enage'

import unittest

from utilities import get_qgis_app

from bus import DashboardBus
from elements import create_element, ELEMENT_TYPES, ELEMENT_LABELS
from elements.pivot import PivotElement
from elements.pivot_engine import compute_pivot, NULL_KEY

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()

FEATS = [
    {"region": "East", "year": 2023, "sales": 10},
    {"region": "East", "year": 2023, "sales": 20},
    {"region": "East", "year": 2024, "sales": 5},
    {"region": "West", "year": 2023, "sales": 7},
    {"region": "West", "year": 2024, "sales": 3},
]


class PivotEngineTest(unittest.TestCase):
    def test_count_cross_tab(self):
        r = compute_pivot(FEATS, "region", "year", statistic="count")
        self.assertEqual(r.row_keys, ["East", "West"])        # by total desc
        self.assertEqual(r.col_keys, ["2023", "2024"])
        self.assertEqual(r.cells[("East", "2023")], 2)
        self.assertEqual(r.cells[("East", "2024")], 1)
        self.assertEqual(r.row_totals["East"], 3)
        self.assertEqual(r.col_totals["2023"], 3)
        self.assertEqual(r.grand_total, 5)

    def test_sum_without_column(self):
        r = compute_pivot(FEATS, "region", None, "sales", statistic="sum")
        self.assertEqual(r.col_keys, [])
        self.assertEqual(r.row_totals["East"], 35.0)
        self.assertEqual(r.row_totals["West"], 10.0)
        self.assertEqual(r.grand_total, 45.0)

    def test_mean_and_max(self):
        mean = compute_pivot(FEATS, "region", None, "sales", statistic="mean")
        self.assertAlmostEqual(mean.row_totals["West"], 5.0)
        mx = compute_pivot(FEATS, "region", None, "sales", statistic="max")
        self.assertEqual(mx.row_totals["East"], 20.0)

    def test_null_key_bucketed(self):
        feats = FEATS + [{"region": None, "year": 2023, "sales": 1}]
        r = compute_pivot(feats, "region", "year", statistic="count")
        self.assertIn(NULL_KEY, r.row_keys)

    def test_non_numeric_value_dropped_for_sum(self):
        feats = [{"region": "East", "sales": "n/a"},
                 {"region": "East", "sales": 4}]
        r = compute_pivot(feats, "region", None, "sales", statistic="sum")
        self.assertEqual(r.row_totals["East"], 4.0)

    def test_truncation_flag_and_caps(self):
        feats = [{"region": "R{}".format(i), "sales": i} for i in range(60)]
        r = compute_pivot(feats, "region", None, "sales",
                          statistic="count", max_rows=10)
        self.assertTrue(r.truncated)
        self.assertEqual(len(r.row_keys), 10)

    def test_no_row_field_is_empty(self):
        r = compute_pivot(FEATS, None, statistic="count")
        self.assertEqual(r.row_keys, [])


class PivotElementTest(unittest.TestCase):
    def _layer(self):
        from qgis.core import QgsVectorLayer, QgsFeature, QgsProject
        lyr = QgsVectorLayer(
            "None?field=region:string&field=year:integer&field=sales:double",
            "piv", "memory")
        feats = []
        for region, year, sales in [("East", 2023, 10), ("East", 2023, 20),
                                    ("East", 2024, 5), ("West", 2023, 7),
                                    ("West", 2024, 3)]:
            ft = QgsFeature(lyr.fields())
            ft.setAttributes([region, year, float(sales)])
            feats.append(ft)
        lyr.dataProvider().addFeatures(feats)
        lyr.updateExtents()
        QgsProject.instance().addMapLayer(lyr)
        return lyr

    def test_pivot_is_registered(self):
        self.assertIn("pivot", ELEMENT_TYPES)
        self.assertEqual(set(ELEMENT_TYPES), set(ELEMENT_LABELS))

    def test_create_without_layer_does_not_crash(self):
        bus = DashboardBus(IFACE)
        el = create_element("pivot", bus, {}, PARENT)
        self.assertIsInstance(el, PivotElement)
        self.assertEqual(el.table.rowCount(), 0)

    def test_populates_table_from_layer(self):
        bus = DashboardBus(IFACE)
        lyr = self._layer()
        el = create_element("pivot", bus, {
            "row_field": "region", "col_field": "year",
            "statistic": "count", "layer_id": lyr.id()}, PARENT)
        self.assertEqual(el._result.row_keys, ["East", "West"])
        self.assertEqual(el._result.col_keys, ["2023", "2024"])
        # header col + 2 col keys + Total = 4 columns; 2 rows + Total = 3
        self.assertEqual(el.table.columnCount(), 4)
        self.assertEqual(el.table.rowCount(), 3)

    def test_cell_click_filters_row_and_column(self):
        bus = DashboardBus(IFACE)
        lyr = self._layer()
        el = create_element("pivot", bus, {
            "row_field": "region", "col_field": "year",
            "statistic": "count", "layer_id": lyr.id()}, PARENT)
        bus.set_targets(el.id, ["t"])
        el._on_cell(0, 1)   # East x 2023
        expr = bus.combined_filter_for("t")
        self.assertIn('"region" = \'East\'', expr)
        self.assertIn('"year" = 2023', expr)
        el._on_cell(0, 1)   # toggle off
        self.assertIsNone(bus.combined_filter_for("t"))

    def test_row_header_click_filters_row_only(self):
        bus = DashboardBus(IFACE)
        lyr = self._layer()
        el = create_element("pivot", bus, {
            "row_field": "region", "col_field": "year",
            "statistic": "count", "layer_id": lyr.id()}, PARENT)
        bus.set_targets(el.id, ["t"])
        el._on_cell(0, 0)   # East row header
        self.assertEqual(bus.combined_filter_for("t"), '("region" = \'East\')')

    def test_column_header_click_filters_column_only(self):
        bus = DashboardBus(IFACE)
        lyr = self._layer()
        el = create_element("pivot", bus, {
            "row_field": "region", "col_field": "year",
            "statistic": "count", "layer_id": lyr.id()}, PARENT)
        bus.set_targets(el.id, ["t"])
        el._on_header(1)    # first column key = 2023
        self.assertEqual(bus.combined_filter_for("t"), '("year" = 2023)')


if __name__ == "__main__":
    unittest.main()
