# -*- coding: utf-8 -*-
"""Per-element connections dialog — wire one tile's cross-filter links.

ArcGIS source -> action -> target, made explicit and user-editable, but scoped
to a *single* element (opened from that tile's right-click menu). The dialog
shows the element's connections from its own perspective:

* if the element **is a filter source** (chart / pivot / selector), an outgoing
  section — "This filters →" — lists every candidate *target* (anything that
  accepts a filter); ticking one means "when this tile filters, that tile
  re-queries".
* if the element **accepts a filter** (indicator / chart / pivot / list), an
  incoming section — "← Filtered by" — lists every candidate *source*; ticking
  one wires that source onto this tile.

Dual-role tiles (chart, pivot) show both sections. A tile that neither sources
nor accepts filters (e.g. the map) shows an explanatory note.

All writes go through the bus edge-by-edge (:meth:`DashboardBus.set_connected`),
so editing one tile never disturbs links that don't involve it.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QCheckBox, QLabel, QScrollArea,
    QWidget, QDialogButtonBox,
)


class ElementConnectionsDialog(QDialog):
    """Edit the cross-filter links for a single *element*."""

    def __init__(self, bus, element, elements, parent=None):
        super().__init__(parent)
        self.bus = bus
        self.element = element
        self.setWindowTitle('Connections — {}'.format(element.display_name()))
        self.resize(380, 460)

        # (peer_id, direction) -> QCheckBox, where direction is "out" (this
        # element filters the peer) or "in" (the peer filters this element).
        self._checks = {}

        others = [e for e in elements if e.id != element.id]
        out_targets = ([e for e in others if e.accepts_filter]
                       if element.is_filter_source else [])
        in_sources = ([e for e in others if e.is_filter_source]
                      if element.accepts_filter else [])

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        col = QVBoxLayout(inner)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        if not out_targets and not in_sources:
            col.addWidget(QLabel(
                "This tile doesn't take part in cross-filtering.\n"
                "Add a chart, pivot or selector to drive other tiles."))

        if element.is_filter_source:
            col.addWidget(self._section(
                "This filters →", out_targets, "out",
                lambda peer: bus.is_connected(element.id, peer.id),
                "(no eligible targets)"))

        if element.accepts_filter:
            col.addWidget(self._section(
                "← Filtered by", in_sources, "in",
                lambda peer: bus.is_connected(peer.id, element.id),
                "(no eligible sources)"))

        col.addStretch(1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _section(self, title, peers, direction, is_on, empty_text):
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        if not peers:
            lay.addWidget(QLabel(empty_text))
        for peer in peers:
            cb = QCheckBox(peer.display_name())
            cb.setChecked(is_on(peer))
            self._checks[(peer.id, direction)] = cb
            lay.addWidget(cb)
        return box

    def apply(self):
        """Write the ticked wiring back onto the bus, edge by edge."""
        eid = self.element.id
        for (peer_id, direction), cb in self._checks.items():
            if direction == "out":      # this element → peer
                self.bus.set_connected(eid, peer_id, cb.isChecked())
            else:                       # peer → this element
                self.bus.set_connected(peer_id, eid, cb.isChecked())
