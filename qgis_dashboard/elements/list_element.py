# -*- coding: utf-8 -*-
"""List element.

ArcGIS list shows features as rows and can be a selector — clicking a row
filters/zooms other elements. Here each row is a feature; selecting a row
emits a featureAction so the map element can zoom/flash to it.
"""

from qgis.PyQt.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView
from .base import DashboardElement


class ListElement(DashboardElement):
    type_name = "list"

    def __init__(self, bus, config=None, parent=None):
        super().__init__(bus, config, parent)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_row)
        self.body.addWidget(self.table)
        self._fids = []
        self.apply_theme()
        self.refresh()

    def refresh(self):
        fields = self.config.get("display_fields", [])
        lyr = self.layer()
        if lyr and not fields:
            fields = [f.name() for f in lyr.fields()][:3]
        self.table.clear()
        self.table.setColumnCount(len(fields))
        self.table.setHorizontalHeaderLabels(fields)
        rows = list(self.iter_features())
        limit = self.config.get("max_rows", 200)
        rows = rows[:limit]
        self._fids = [f.id() for f in rows]
        self.table.setRowCount(len(rows))
        for r, feat in enumerate(rows):
            for c, fld in enumerate(fields):
                self.table.setItem(r, c, QTableWidgetItem(str(feat[fld])))
        self.table.resizeColumnsToContents()

    def _on_row(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if 0 <= idx < len(self._fids):
            self.bus.featureAction.emit([self._fids[idx]])
