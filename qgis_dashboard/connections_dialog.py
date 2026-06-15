# -*- coding: utf-8 -*-
"""Connections dialog — wire sources to targets.

ArcGIS source -> action -> target, made explicit and user-editable. Each
*source* element (chart / pie / selector) gets a group listing every candidate
*target* (any element that accepts a filter); ticking a target means "when this
source filters, that target re-queries". Unwired elements ignore each other.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QCheckBox, QLabel, QScrollArea,
    QWidget, QDialogButtonBox,
)


class ConnectionsDialog(QDialog):
    def __init__(self, bus, elements, parent=None):
        super().__init__(parent)
        self.bus = bus
        self.setWindowTitle("Element connections")
        self.resize(420, 520)

        self._checks = {}   # (source_id, target_id) -> QCheckBox

        sources = [e for e in elements if e.is_filter_source]
        targets = [e for e in elements if e.accepts_filter]

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        col = QVBoxLayout(inner)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        if not sources:
            col.addWidget(QLabel("No source elements yet.\nAdd a chart, pie or "
                                 "selector to drive other tiles."))
        for src in sources:
            box = QGroupBox('"{}" filters →'.format(src.display_name()))
            box_lay = QVBoxLayout(box)
            candidates = [t for t in targets if t.id != src.id]
            if not candidates:
                box_lay.addWidget(QLabel("(no eligible targets)"))
            for tgt in candidates:
                cb = QCheckBox(tgt.display_name())
                cb.setChecked(bus.is_connected(src.id, tgt.id))
                self._checks[(src.id, tgt.id)] = cb
                box_lay.addWidget(cb)
            col.addWidget(box)
        col.addStretch(1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._sources = sources

    def apply(self):
        """Write the ticked wiring back onto the bus."""
        for src in self._sources:
            chosen = [tid for (sid, tid), cb in self._checks.items()
                      if sid == src.id and cb.isChecked()]
            self.bus.set_targets(src.id, chosen)
