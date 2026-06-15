# -*- coding: utf-8 -*-
"""Dashboard window — a standalone top-level dashboard.

Per the redesign the dashboard is no longer docked inside QGIS: it is its own
window (``QMainWindow``). It holds a tab bar + a ``QStackedWidget`` of pages;
each page is a :class:`PageView` (a scroll area wrapping one free drag/resize
:class:`DashboardCanvas`). The window owns the one shared :class:`DashboardBus`
(theme + live ``iface`` are global; cross-filter wiring is page-local).

Persistence: the whole dashboard — every page's tiles and grid placement, the
per-page connection graph, the theme, the (global) grid resolution and the
window size — is serialized to JSON (schema v3) in the ``.qgz`` project file and
restored on open. ``migrate_layout`` upgrades the older v1 (bare list) and v2
(single page) blobs on load.
"""

import json
import uuid

from qgis.PyQt.QtWidgets import (
    QMainWindow, QToolBar, QLabel, QWidget, QSizePolicy,
    QTabBar, QStackedWidget, QVBoxLayout, QMessageBox, QInputDialog, QMenu,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.core import QgsProject

from .bus import DashboardBus
from .theme import Theme
from .dashboard_canvas import DashboardCanvas
from .page_view import PageView
from .elements import create_element
from .add_element_dialog import AddElementDialog
from .settings_dialog import GridSettingsDialog
from .appearance_dialog import AppearanceDialog
from .connections_dialog import ConnectionsDialog

PROJECT_SCOPE = "QgisDashboard"
PROJECT_KEY = "layout"
DEFAULT_COLS = 12
DEFAULT_ROWS = 8


def migrate_layout(raw):
    """Normalize any stored layout (v1 list / v2 dict / v3 dict) to v3.

    v3 shape::

        {version, grid:{cols,rows}, theme, window, active_page,
         pages:[{id, title, connections, elements:[...]}]}
    """
    if not raw:
        raw = {"elements": []}
    # v1: a bare list of element configs
    if isinstance(raw, list):
        raw = {"elements": raw}

    version = raw.get("version", 2)
    grid = raw.get("grid", {})
    out = {
        "version": 3,
        "grid": {"cols": grid.get("cols", DEFAULT_COLS),
                 "rows": grid.get("rows", DEFAULT_ROWS)},
        "theme": raw.get("theme") or {},
        "window": raw.get("window", {}),
    }

    if version >= 3 and isinstance(raw.get("pages"), list):
        pages = []
        for p in raw["pages"]:
            pages.append({
                "id": p.get("id") or uuid.uuid4().hex[:8],
                "title": p.get("title") or "Page",
                "connections": p.get("connections") or {},
                "elements": p.get("elements") or [],
            })
        if not pages:
            pages = [{"id": uuid.uuid4().hex[:8], "title": "Page 1",
                      "connections": {}, "elements": []}]
        out["pages"] = pages
        out["active_page"] = raw.get("active_page") or pages[0]["id"]
    else:
        # v1/v2: collapse into a single page
        page = {
            "id": uuid.uuid4().hex[:8],
            "title": "Page 1",
            "connections": raw.get("connections") or {},
            "elements": raw.get("elements") or [],
        }
        out["pages"] = [page]
        out["active_page"] = page["id"]
    return out


class DashboardPage:
    """One dashboard page: an id/title plus its PageView (and its canvas)."""

    def __init__(self, page_id, title, view):
        self.id = page_id
        self.title = title
        self.view = view
        self.canvas = view.canvas


class DashboardWindow(QMainWindow):
    closed = pyqtSignal()   # the window was hidden/closed by the user

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("QGIS Dashboard")
        self.setWindowFlags(Qt.Window)
        self.resize(1100, 720)

        self.bus = DashboardBus(iface, Theme.default(), self)

        # tab bar + stack of pages
        self._pages = []
        self._tab_bar = QTabBar()
        self._tab_bar.setMovable(True)
        self._tab_bar.setExpanding(False)
        self._stack = QStackedWidget()

        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._tab_bar)
        col.addWidget(self._stack, 1)
        self.setCentralWidget(container)

        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabBarDoubleClicked.connect(self._rename_page_at)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)
        self._tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tab_bar.customContextMenuRequested.connect(self._tab_context_menu)

        self._build_toolbar()
        self._apply_window_style()

        self.add_page("Page 1")

        # keep config combos / map mirror fresh as project layers change
        QgsProject.instance().layersAdded.connect(
            lambda *_: self.bus.layersChanged.emit())
        QgsProject.instance().layersRemoved.connect(
            lambda *_: self.bus.layersChanged.emit())
        self.bus.filtersChanged.connect(self._update_filter_label)
        self.bus.themeChanged.connect(self._apply_window_style)

    # ---- chrome ----

    def _build_toolbar(self):
        tb = QToolBar("Dashboard", self)
        tb.setMovable(False)
        self.addToolBar(tb)
        for text, slot in (
            ("Add element", self.add_element_dialog),
            ("Add page", self._add_page_interactive),
            ("Connections…", self.open_connections),
            ("Appearance…", self.open_appearance),
            ("Grid…", self.open_grid_settings),
            ("Clear filter", self.bus.clear_all_filters),
        ):
            tb.addAction(text).triggered.connect(slot)
        tb.addSeparator()
        tb.addAction("Zoom −").triggered.connect(
            lambda: self.current_view() and self.current_view().zoom_out())
        tb.addAction("100%").triggered.connect(
            lambda: self.current_view() and self.current_view().reset_zoom())
        tb.addAction("Zoom +").triggered.connect(
            lambda: self.current_view() and self.current_view().zoom_in())
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        self.filter_label = QLabel("No active filter")
        self.filter_label.setStyleSheet("color:#6b7682; padding:0 8px;")
        tb.addWidget(self.filter_label)

    def _apply_window_style(self):
        self.setStyleSheet(self.bus.theme.window_qss())
        cur = self.current_canvas()
        if cur is not None:
            cur.update()

    def _update_filter_label(self):
        n = self.bus.active_filter_count()
        self.filter_label.setText(
            "No active filter" if n == 0 else "Filters active: {}".format(n))

    # ---- pages ----

    def pages(self):
        return list(self._pages)

    def current_page(self):
        idx = self._tab_bar.currentIndex()
        return self._pages[idx] if 0 <= idx < len(self._pages) else None

    def current_canvas(self):
        page = self.current_page()
        return page.canvas if page else None

    def current_view(self):
        page = self.current_page()
        return page.view if page else None

    def canvas_cols(self):
        return self._pages[0].canvas.cols if self._pages else DEFAULT_COLS

    def canvas_rows(self):
        return self._pages[0].canvas.rows if self._pages else DEFAULT_ROWS

    def add_page(self, title, page_id=None, make_active=True):
        page_id = page_id or uuid.uuid4().hex[:8]
        canvas = DashboardCanvas(self.bus, self.canvas_cols(), self.canvas_rows())
        view = PageView(canvas)
        page = DashboardPage(page_id, title, view)
        self._pages.append(page)
        self._stack.addWidget(view)
        self._tab_bar.addTab(title)
        if make_active:
            self._tab_bar.setCurrentIndex(len(self._pages) - 1)
        return page

    def delete_page(self, page_id):
        if len(self._pages) <= 1:
            return
        idx = next((i for i, p in enumerate(self._pages)
                    if p.id == page_id), -1)
        if idx < 0:
            return
        page = self._pages[idx]
        if page.canvas.tiles():
            ok = QMessageBox.question(
                self, "Delete page",
                'Delete "{}" and its {} tile(s)?'.format(
                    page.title, len(page.canvas.tiles())))
            if ok != QMessageBox.Yes:
                return
        page.canvas.clear()
        self.bus.forget_page(page.id)
        self._pages.pop(idx)
        self._stack.removeWidget(page.view)
        page.view.deleteLater()
        self._tab_bar.removeTab(idx)

    def _add_page_interactive(self):
        self.add_page("Page {}".format(len(self._pages) + 1))

    def _on_tab_changed(self, idx):
        if 0 <= idx < len(self._pages):
            page = self._pages[idx]
            self._stack.setCurrentWidget(page.view)
            self.bus.set_active_page(page.id)

    def _on_tab_moved(self, frm, to):
        self._pages.insert(to, self._pages.pop(frm))
        view = self._stack.widget(frm)
        self._stack.removeWidget(view)
        self._stack.insertWidget(to, view)

    def _rename_page_at(self, idx):
        if not (0 <= idx < len(self._pages)):
            return
        page = self._pages[idx]
        text, ok = QInputDialog.getText(self, "Rename page",
                                        "Title:", text=page.title)
        if ok and text.strip():
            page.title = text.strip()
            self._tab_bar.setTabText(idx, page.title)

    def _tab_context_menu(self, pos):
        idx = self._tab_bar.tabAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        menu.addAction("Rename").triggered.connect(
            lambda: self._rename_page_at(idx))
        menu.addAction("Delete").triggered.connect(
            lambda: self.delete_page(self._pages[idx].id))
        menu.exec_(self._tab_bar.mapToGlobal(pos))

    def _apply_grid_to_all(self, cols, rows):
        for page in self._pages:
            page.canvas.set_grid(cols, rows)

    # ---- element management ----

    def elements(self):
        page = self.current_page()
        return [t.element for t in page.canvas.tiles()] if page else []

    def add_element_dialog(self):
        dlg = AddElementDialog(self)
        if dlg.exec_():
            type_name, cfg = dlg.result_config()
            self.add_element(type_name, cfg)

    def add_element(self, type_name, config, grid_rect=None):
        page = self.current_page()
        if page is None:
            page = self.add_page("Page 1")
        return self._add_element_to(page, type_name, config, grid_rect)

    def _add_element_to(self, page, type_name, config, grid_rect=None):
        element = create_element(type_name, self.bus, config, page.canvas)
        tile = page.canvas.add_tile(element, grid_rect)
        tile.styleRequested.connect(self._edit_tile_style)
        return tile

    def _edit_tile_style(self, element):
        seed = self.bus.theme.merged_with(element.config.get("style"))
        dlg = AppearanceDialog(seed, mode="element", parent=self)
        if dlg.exec_():
            override = dlg.result_override()   # None == cleared
            if override:
                element.config["style"] = override
            else:
                element.config.pop("style", None)
            element.apply_theme()

    # ---- dialogs ----

    def open_connections(self):
        dlg = ConnectionsDialog(self.bus, self.elements(), self)
        if dlg.exec_():
            dlg.apply()

    def open_appearance(self):
        original = self.bus.theme
        dlg = AppearanceDialog(original, mode="global",
                               on_apply=self.bus.set_theme, parent=self)
        if dlg.exec_():
            self.bus.set_theme(dlg.result_theme())
        else:
            self.bus.set_theme(original)   # revert live preview

    def open_grid_settings(self):
        cur = self.current_canvas()
        cols = cur.cols if cur else DEFAULT_COLS
        rows = cur.rows if cur else DEFAULT_ROWS
        dlg = GridSettingsDialog(cols, rows, self)
        if dlg.exec_():
            new_cols, new_rows = dlg.result_grid()
            self._apply_grid_to_all(new_cols, new_rows)

    # ---- lifecycle ----

    def closeEvent(self, event):
        # Hide rather than destroy so state survives a reopen; tell the plugin
        # so it can untick the toolbar action.
        self.closed.emit()
        super().closeEvent(event)

    def clear_all(self):
        for page in self._pages:
            page.canvas.clear()
            self._stack.removeWidget(page.view)
            page.view.deleteLater()
        self._pages = []
        while self._tab_bar.count():
            self._tab_bar.removeTab(0)
        self.bus.clear_all_filters()

    # ---- persistence into the .qgz project ----

    def save_to_project(self):
        pages = []
        for page in self._pages:
            elements = []
            for tile in page.canvas.tiles():
                d = tile.element.to_dict()
                gx, gy, gw, gh = tile.grid_rect()
                d["grid"] = {"x": gx, "y": gy, "w": gw, "h": gh}
                elements.append(d)
            pages.append({
                "id": page.id,
                "title": page.title,
                "connections": self.bus.connections_to_dict(page.id),
                "elements": elements,
            })
        cur = self.current_page()
        data = {
            "version": 3,
            "grid": {"cols": self.canvas_cols(), "rows": self.canvas_rows()},
            "theme": self.bus.theme.to_dict(),
            "window": {"w": self.width(), "h": self.height()},
            "active_page": cur.id if cur else None,
            "pages": pages,
        }
        QgsProject.instance().writeEntry(
            PROJECT_SCOPE, PROJECT_KEY, json.dumps(data))

    def load_from_project(self):
        raw, ok = QgsProject.instance().readEntry(
            PROJECT_SCOPE, PROJECT_KEY, "")
        self.clear_all()
        if not ok or not raw:
            self.bus.set_theme(Theme.default())
            self.add_page("Page 1")
            self._apply_grid_to_all(DEFAULT_COLS, DEFAULT_ROWS)
            return
        try:
            data = migrate_layout(json.loads(raw))
        except (ValueError, TypeError):
            self.add_page("Page 1")
            return

        self.bus.set_theme(Theme.from_dict(data.get("theme")))
        self._apply_window_style()
        grid = data.get("grid", {})
        cols = grid.get("cols", DEFAULT_COLS)
        rows = grid.get("rows", DEFAULT_ROWS)

        for p in data["pages"]:
            page = self.add_page(p["title"], page_id=p["id"], make_active=False)
            page.canvas.set_grid(cols, rows)
            self.bus.load_connections(p.get("connections", {}), p["id"])
            for cfg in p.get("elements", []):
                cfg = dict(cfg)
                t = cfg.pop("__type__", None)
                g = cfg.pop("grid", None)
                rect = None
                if isinstance(g, dict):
                    rect = (g.get("x", 0), g.get("y", 0),
                            g.get("w", 4), g.get("h", 3))
                if t:
                    self._add_element_to(page, t, cfg, rect)

        active = data.get("active_page")
        idx = next((i for i, pg in enumerate(self._pages)
                    if pg.id == active), 0)
        self._tab_bar.setCurrentIndex(idx)

        win = data.get("window", {})
        if win.get("w") and win.get("h"):
            self.resize(int(win["w"]), int(win["h"]))
