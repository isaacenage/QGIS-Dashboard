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
    QMainWindow, QLabel, QWidget, QFrame, QHBoxLayout,
    QTabBar, QStackedWidget, QVBoxLayout, QMessageBox, QInputDialog, QMenu,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.core import QgsProject

from .bus import DashboardBus
from .theme import Theme
from .fonts import ensure_fonts_registered
from .icons import logo_icon
from .sidebar import Sidebar
from .dashboard_canvas import DashboardCanvas
from .page_view import PageView
from .elements import create_element
from .add_element_dialog import AddElementDialog
from .settings_dialog import GridSettingsDialog, SettingsDialog
from .appearance_dialog import AppearanceDialog
from .connections_dialog import ElementConnectionsDialog

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
        ensure_fonts_registered()   # register bundled Inter before any QSS/font use
        self.iface = iface
        self.setWindowTitle("QGIS Dashboard")
        self.setWindowIcon(logo_icon())
        self.setWindowFlags(Qt.Window)
        self.resize(1100, 720)

        self.bus = DashboardBus(iface, Theme.default(), self)

        # tab bar + stack of pages
        self._pages = []
        self._tab_bar = QTabBar()
        self._tab_bar.setMovable(True)
        self._tab_bar.setExpanding(False)
        self._stack = QStackedWidget()

        # left icon rail + (tabs over page stack)
        self._build_sidebar()
        pages_col = QWidget()
        col = QVBoxLayout(pages_col)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._tab_bar)
        col.addWidget(self._stack, 1)

        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.sidebar)
        row.addWidget(pages_col, 1)
        self.setCentralWidget(container)

        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabBarDoubleClicked.connect(self._rename_page_at)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)
        self._tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tab_bar.customContextMenuRequested.connect(self._tab_context_menu)

        self._build_status_bar()
        self._apply_window_style()

        self.add_page("Page 1")

        # keep config combos / map mirror fresh as project layers change
        QgsProject.instance().layersAdded.connect(
            lambda *_: self.bus.layersChanged.emit())
        QgsProject.instance().layersRemoved.connect(
            lambda *_: self.bus.layersChanged.emit())
        self.bus.filtersChanged.connect(self._update_filter_label)
        self.bus.filtersCleared.connect(self._update_filter_label)
        self.bus.themeChanged.connect(self._on_theme_changed)

    # ---- chrome ----

    def _build_sidebar(self):
        """Vertical icon rail replacing the old horizontal toolbar."""
        self.sidebar = Sidebar(self.bus.theme, self)
        self.sidebar.add_action(
            "add_element", "Add element", self.add_element_dialog)
        self.sidebar.add_action(
            "add_page", "Add page", self._add_page_interactive)
        self.sidebar.add_separator()
        self.sidebar.add_action(
            "zoom_out", "Zoom out", self._zoom_out)
        self.sidebar.add_action(
            "zoom_reset", "Reset zoom (100%)", self._zoom_reset)
        self.sidebar.add_action("zoom_in", "Zoom in", self._zoom_in)
        self.sidebar.add_stretch()
        self.sidebar.add_action(
            "clear_filter", "Clear filter", self.bus.clear_all_filters)
        self.sidebar.add_separator()
        # Settings hub (Appearance, About) lives at the foot of the rail.
        self.sidebar.add_action("settings", "Settings", self.open_settings)

    def _build_status_bar(self):
        """Bottom status strip carrying the live cross-filter indicator."""
        bar = self.statusBar()
        self._filter_dot = QFrame()
        self._filter_dot.setObjectName("dashFilterDot")
        self._filter_dot.setFixedSize(8, 8)
        self._filter_dot.hide()
        self.filter_label = QLabel("No active filter")
        self.filter_label.setObjectName("dashFilterStatus")
        bar.addWidget(self._filter_dot)
        bar.addWidget(self.filter_label)

    # ---- zoom helpers (act on the current page's view) ----

    def _zoom_in(self):
        view = self.current_view()
        if view is not None:
            view.zoom_in()

    def _zoom_out(self):
        view = self.current_view()
        if view is not None:
            view.zoom_out()

    def _zoom_reset(self):
        view = self.current_view()
        if view is not None:
            view.reset_zoom()

    def _apply_window_style(self):
        self.setStyleSheet(self.bus.theme.window_qss())
        cur = self.current_canvas()
        if cur is not None:
            cur.update()

    def _on_theme_changed(self):
        self.sidebar.apply_theme(self.bus.theme)
        self._apply_window_style()

    def _update_filter_label(self):
        n = self.bus.active_filter_count()
        self.filter_label.setText(
            "No active filter" if n == 0 else "Filters active: {}".format(n))
        self._filter_dot.setVisible(n > 0)

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
        canvas.gridSettingsRequested.connect(self.open_grid_settings)
        view = PageView(canvas)
        page = DashboardPage(page_id, title, view)
        self._pages.append(page)
        self._stack.addWidget(view)
        self._tab_bar.addTab(title)
        if make_active:
            self._tab_bar.setCurrentIndex(len(self._pages) - 1)
        self._update_tabbar_visibility()
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
        self._update_tabbar_visibility()

    def _update_tabbar_visibility(self):
        """Hide the page tab bar unless there's more than one page.

        A single-page dashboard then reads as just the rail + canvas; the tab
        bar only appears once a second page exists (via "Add page").
        """
        self._tab_bar.setVisible(len(self._pages) > 1)

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
        tile.connectionsRequested.connect(self._edit_tile_connections)
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

    def _edit_tile_connections(self, element):
        dlg = ElementConnectionsDialog(self.bus, element, self.elements(), self)
        if dlg.exec_():
            dlg.apply()

    def open_settings(self):
        dlg = SettingsDialog(self.open_appearance, self,
                             on_export=self.export_to_html)
        dlg.exec_()

    def export_to_html(self):
        from .export_dialog import prompt_and_export
        prompt_and_export(self, self)

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
        self._update_tabbar_visibility()
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
