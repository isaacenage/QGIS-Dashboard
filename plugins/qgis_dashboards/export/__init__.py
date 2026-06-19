# -*- coding: utf-8 -*-
"""Interactive HTML export.

Turns a live :class:`~window.DashboardWindow` into a single self-contained
``index.html`` that reproduces the dashboard — multi-page layout, theme, and
**live cross-filtering** — offline, with no framework and no server.

The package is split so the bulk of it is Qt/QGIS-free and unit-testable:

* :mod:`.serialize`   — pure: assemble the export-model dict.
* :mod:`.theme_css`   — pure: ``Theme`` dict -> CSS custom properties.
* :mod:`.html_builder`— pure: inline CSS + runtime JS + embedded JSON -> HTML.
* :mod:`.data_collect`— QGIS: per-layer rows + base_filter masks + images.
* :mod:`.map_snapshot`— QGIS/Qt: grab the map canvas to a base64 PNG.
* :mod:`.html_export` — orchestrator that wires the above together.

Keep this ``__init__`` import-light (no QGIS imports) so the pure modules can be
imported in a test runner without a QGIS runtime.
"""
