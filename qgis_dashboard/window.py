# -*- coding: utf-8 -*-
"""Dashboard window — a standalone top-level dashboard.

Per the redesign the dashboard is no longer docked inside QGIS: it is its own
window (``QMainWindow``). It holds a tab bar + a ``QStackedWidget`` of pages;
each page is a :class:`PageView` (a scroll area wrapping one free-form
drag/resize :class:`DashboardCanvas`). The window owns the one shared
:class:`DashboardBus` (theme + live ``iface`` are global; cross-filter wiring
is page-local).

Persistence: the whole dashboard — every page's tiles and their pixel
placement, the per-page connection graph, the theme and the window size — is
serialized to JSON (schema v3) in the ``.qgz`` project file and restored on
open. ``migrate_layout`` upgrades the older v1 (bare list) and v2 (single page)
blobs on load.
"""

import json
import uuid

from qgis.PyQt.QtWidgets import (
    QMainWindow, QLabel, QWidget, QFrame, QHBoxLayout, QToolButton,
    QTabBar, QStackedWidget, QVBoxLayout, QMessageBox, QInputDialog, QMenu,
)
from qgis.PyQt.QtCore import Qt, QSize, pyqtSignal
from qgis.core import QgsProject

from .bus import DashboardBus
from .theme import Theme
from .fonts import ensure_fonts_registered
from .icons import logo_icon, monochrome_icon
from .sidebar import Sidebar
from .dashboard_canvas import DashboardCanvas
from .page_view import PageView
from .elements import create_element
from .elements.header_layout import resolve_header
from .add_element_dialog import AddElementDialog
from .settings_dialog import SettingsDialog
from .appearance_dialog import AppearanceDialog
from .connections_dialog import ElementConnectionsDialog

PROJECT_SCOPE = "QgisDashboard"
PROJECT_KEY = "layout"
DEFAULT_COLS = 12
DEFAULT_ROWS = 8
DEFAULT_GAP = 0   # global element gap (logical px): cards may touch by default


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
        "gap": int(raw.get("gap", DEFAULT_GAP)),
        "theme": raw.get("theme") or {},
        "window": raw.get("window", {}),
        # optional global header (brand banner); absent in v1/v2/older v3 blobs
        "header": raw.get("header") or None,
    }

    if version >= 3 and isinstance(raw.get("pages"), list):
        pages = []
        for p in raw["pages"]:
            pages.append({
                "id": p.get("id") or uuid.uuid4().hex[:8],
                "title": p.get("title") or "Page",
                "connections": p.get("connections") or {},
                "elements": p.get("elements") or [],
                "header": p.get("header") or None,
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
        # optional per-page header (brand banner) config, or None. A global
        # header (window._global_header) is shown when this is None.
        self.header_config = None


class DashboardWindow(QMainWindow):
    closed = pyqtSignal()   # the window was hidden/closed by the user

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        ensure_fonts_registered()   # register bundled Inter before any QSS/font use
        self.iface = iface
        self.setWindowTitle("QGIS Dashboard")
        self.setWindowIcon(logo_icon())
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(1100, 720)

        self.bus = DashboardBus(iface, Theme.default(), self)

        # tab bar + stack of pages
        self._pages = []
        self._tab_bar = QTabBar()
        self._tab_bar.setMovable(True)
        self._tab_bar.setExpanding(False)
        # Suppress the platform style's dark base line under the tabs; the
        # theme draws a single soft hairline (border-bottom) instead.
        self._tab_bar.setDrawBase(False)
        self._stack = QStackedWidget()

        # layout lock (view-only, not persisted): when on, tiles can't be
        # moved/resized. Off by default so the dashboard is editable on open.
        self._editing_locked = False

        # global header (brand banner) config shown on every page that lacks
        # its own per-page header, or None when there is no global header.
        self._global_header = None

        # left icon rail + (tab strip over page stack)
        self._build_sidebar()
        pages_col = QWidget()
        col = QVBoxLayout(pages_col)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._build_tab_strip())
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
        self._tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
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

    def _build_tab_strip(self):
        """The page tab bar plus right-aligned lock + export buttons.

        Lives in one row that carries the soft bottom hairline; the tab bar
        stretches and the action buttons sit at the right edge.
        """
        strip = QFrame()
        strip.setObjectName("dashTabStrip")
        row = QHBoxLayout(strip)
        row.setContentsMargins(0, 0, 8, 0)
        row.setSpacing(4)
        row.addWidget(self._tab_bar, 1)

        self._lock_btn = self._make_strip_button(
            "unlock", "Lock layout — prevent moving/resizing tiles",
            checkable=True)
        self._lock_btn.toggled.connect(self._on_lock_toggled)
        row.addWidget(self._lock_btn)

        self._export_btn = self._make_strip_button(
            "export", "Export dashboard (HTML / PNG / PDF)")
        self._export_btn.clicked.connect(self._open_export_menu)
        row.addWidget(self._export_btn)
        return strip

    def _make_strip_button(self, icon_name, tooltip, checkable=False):
        btn = QToolButton()
        btn.setObjectName("dashRailButton")   # reuse the rail's themed hover/focus
        btn.setIcon(monochrome_icon(icon_name, self.bus.theme.text_muted))
        btn.setIconSize(QSize(18, 18))
        btn.setFixedSize(30, 28)
        btn.setAutoRaise(True)
        btn.setCheckable(checkable)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        return btn

    def _on_lock_toggled(self, locked):
        self._editing_locked = bool(locked)
        self._lock_btn.setIcon(monochrome_icon(
            "lock" if locked else "unlock", self.bus.theme.text_muted))
        self._lock_btn.setToolTip(
            "Unlock layout — allow moving/resizing tiles" if locked
            else "Lock layout — prevent moving/resizing tiles")
        for page in self._pages:
            page.canvas.set_locked(locked)

    def _open_export_menu(self):
        menu = QMenu(self)
        menu.addAction("Export to HTML").triggered.connect(self.export_to_html)
        menu.addAction("Export to PNG").triggered.connect(self.export_to_png)
        menu.addAction("Export to PDF").triggered.connect(self.export_to_pdf)
        menu.exec(self._export_btn.mapToGlobal(
            self._export_btn.rect().bottomLeft()))

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
        # re-tint the tab-strip buttons to the new theme
        muted = self.bus.theme.text_muted
        self._lock_btn.setIcon(monochrome_icon(
            "lock" if self._editing_locked else "unlock", muted))
        self._export_btn.setIcon(monochrome_icon("export", muted))

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

    def canvas_gap(self):
        return self._pages[0].canvas.gap if self._pages else DEFAULT_GAP

    def add_page(self, title, page_id=None, make_active=True):
        page_id = page_id or uuid.uuid4().hex[:8]
        canvas = DashboardCanvas(self.bus, self.canvas_cols(), self.canvas_rows())
        canvas.set_locked(self._editing_locked)   # honour the current layout lock
        canvas.set_gap(self.canvas_gap())          # honour the current element gap
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
            if ok != QMessageBox.StandardButton.Yes:
                return
        page.canvas.clear()
        self.bus.forget_page(page.id)
        self._pages.pop(idx)
        self._stack.removeWidget(page.view)
        page.view.deleteLater()
        self._tab_bar.removeTab(idx)
        self._update_tabbar_visibility()

    def _update_tabbar_visibility(self):
        """Keep the page tab bar visible whenever there's at least one page.

        The tab bar is the place to rename (double-click / right-click) and
        delete pages, so it stays visible even for a single-page dashboard —
        otherwise that page could never be renamed.
        """
        self._tab_bar.setVisible(len(self._pages) >= 1)

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
        menu.exec(self._tab_bar.mapToGlobal(pos))

    def _apply_grid_to_all(self, cols, rows):
        for page in self._pages:
            page.canvas.set_grid(cols, rows)

    def _apply_gap_to_all(self, gap):
        for page in self._pages:
            page.canvas.set_gap(int(gap))

    # ---- element management ----

    def elements(self):
        page = self.current_page()
        return [t.element for t in page.canvas.tiles()] if page else []

    def add_element_dialog(self):
        dlg = AddElementDialog(self)
        if dlg.exec():
            type_name, cfg = dlg.result_config()
            self.add_element(type_name, cfg)

    def add_element(self, type_name, config, grid_rect=None):
        page = self.current_page()
        if page is None:
            page = self.add_page("Page 1")
        if type_name == "header":
            # the header is not a grid tile — it docks to a page edge
            self._set_header_from_config(page, config)
            return None
        return self._add_element_to(page, type_name, config, grid_rect)

    def _add_element_to(self, page, type_name, config, grid_rect=None):
        element = create_element(type_name, self.bus, config, page.canvas)
        tile = page.canvas.add_tile(element, grid_rect)
        tile.styleRequested.connect(self._edit_tile_style)
        tile.connectionsRequested.connect(self._edit_tile_connections)
        tile.configureRequested.connect(self._edit_tile_config)
        return tile

    def _edit_tile_config(self, element):
        """Reopen the per-type config form on a live tile (the Configure menu).

        Managed keys are replaced wholesale (a cleared field drops its key);
        unmanaged keys — id, per-tile style override, base_filter — are kept.
        """
        dlg = AddElementDialog(self, element=element)
        if not dlg.exec():
            return
        _type, cfg = dlg.result_config()
        new_config = dict(element.config)
        for key in dlg.managed_keys():
            if key in cfg:
                new_config[key] = cfg[key]
            else:
                new_config.pop(key, None)
        new_config["id"] = element.id
        element.config = new_config
        element.reconfigure()

    def _edit_tile_style(self, element):
        seed = self.bus.theme.merged_with(element.config.get("style"))
        dlg = AppearanceDialog(seed, mode="element", parent=self)
        if dlg.exec():
            override = dlg.result_override()   # None == cleared
            if override:
                element.config["style"] = override
            else:
                element.config.pop("style", None)
            element.apply_theme()

    # ---- header (brand banner) ----

    def header_for_page(self, page):
        """The resolved header config a page renders (per-page over global)."""
        return resolve_header(page.header_config, self._global_header)

    def _set_header_from_config(self, page, config):
        """Add/replace a header from a config dialog result.

        The dialog's ``scope_all_pages`` checkbox decides whether the header is
        global (shown on every page) or local to *page*; it is not persisted on
        the config itself.
        """
        cfg = dict(config)
        all_pages = bool(cfg.pop("scope_all_pages", False))
        cfg.pop("id", None)
        if all_pages:
            self._global_header = cfg
        else:
            page.header_config = cfg
        self._refresh_all_headers()

    def _refresh_all_headers(self):
        """Rebuild every page's docked banner from the resolved header config."""
        for page in self._pages:
            cfg = self.header_for_page(page)
            if not cfg:
                page.view.set_header(None)
                continue
            element = create_element("header", self.bus, dict(cfg), None)
            element._dash_page = page
            element._dash_scope = "page" if page.header_config else "global"
            element.configureRequested.connect(self._configure_header)
            element.removeRequested.connect(self._remove_header)
            page.view.set_header(element)

    def _configure_header(self, element):
        """Reopen the header config form; the checkbox can move it global<->page."""
        page = element._dash_page
        was_global = element._dash_scope == "global"
        dlg = AddElementDialog(self, element=element)
        chk = dlg._dyn.get("scope_all_pages")
        if chk is not None:
            chk.setChecked(was_global)
        if not dlg.exec():
            return
        _type, cfg = dlg.result_config()
        now_global = bool(cfg.pop("scope_all_pages", False))
        cfg.pop("id", None)
        # clear the slot it came from, then write to the chosen slot, so a
        # header is never left in both the global and per-page slots
        if was_global:
            self._global_header = None
        else:
            page.header_config = None
        if now_global:
            self._global_header = cfg
        else:
            page.header_config = cfg
        self._refresh_all_headers()

    def _remove_header(self, element):
        page = element._dash_page
        if element._dash_scope == "global":
            self._global_header = None
        else:
            page.header_config = None
        self._refresh_all_headers()

    # ---- dialogs ----

    def _edit_tile_connections(self, element):
        dlg = ElementConnectionsDialog(self.bus, element, self.elements(), self)
        if dlg.exec():
            dlg.apply()

    def open_settings(self):
        # Export now lives on the tab strip, not in Settings. Settings holds
        # the global controls (Appearance, element corner radius, About).
        dlg = SettingsDialog(self.open_appearance, self,
                             on_radius=self._set_global_radius,
                             on_gap=self._set_global_gap,
                             gap=self.canvas_gap())
        dlg.exec()

    def _set_global_radius(self, value):
        """Live-apply a new global corner radius to every dashboard element."""
        self.bus.set_theme(self.bus.theme.with_values(radius=int(value)))

    def _set_global_gap(self, value):
        """Live-apply a new global element gap (spacing) to every page."""
        self._apply_gap_to_all(int(value))

    def export_to_html(self):
        from .export_dialog import prompt_and_export
        prompt_and_export(self, self)

    def export_to_png(self):
        from .export.raster_export import export_png
        export_png(self, self)

    def export_to_pdf(self):
        from .export.raster_export import export_pdf
        export_pdf(self, self)

    def open_appearance(self):
        original = self.bus.theme
        dlg = AppearanceDialog(original, mode="global",
                               on_apply=self.bus.set_theme, parent=self)
        if dlg.exec():
            self.bus.set_theme(dlg.result_theme())
        else:
            self.bus.set_theme(original)   # revert live preview

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
        self._global_header = None
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
            page_data = {
                "id": page.id,
                "title": page.title,
                "connections": self.bus.connections_to_dict(page.id),
                "elements": elements,
            }
            if page.header_config:
                page_data["header"] = page.header_config
            pages.append(page_data)
        cur = self.current_page()
        data = {
            "version": 3,
            "grid": {"cols": self.canvas_cols(), "rows": self.canvas_rows()},
            "gap": self.canvas_gap(),
            "theme": self.bus.theme.to_dict(),
            "window": {"w": self.width(), "h": self.height()},
            "active_page": cur.id if cur else None,
            "pages": pages,
        }
        if self._global_header:
            data["header"] = self._global_header
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
        self._global_header = data.get("header") or None
        grid = data.get("grid", {})
        cols = grid.get("cols", DEFAULT_COLS)
        rows = grid.get("rows", DEFAULT_ROWS)
        gap = int(data.get("gap", DEFAULT_GAP))

        for p in data["pages"]:
            page = self.add_page(p["title"], page_id=p["id"], make_active=False)
            page.header_config = p.get("header") or None
            page.canvas.set_grid(cols, rows)
            page.canvas.set_gap(gap)
            self.bus.load_connections(p.get("connections", {}), p["id"])
            for cfg in p.get("elements", []):
                cfg = dict(cfg)
                t = cfg.pop("__type__", None)
                g = cfg.pop("grid", None)
                rect = None
                # placement is a logical pixel rect; only honour it when fully
                # specified, otherwise let the canvas auto-place (first-free)
                if isinstance(g, dict) and all(
                        k in g for k in ("x", "y", "w", "h")):
                    rect = (g["x"], g["y"], g["w"], g["h"])
                if t:
                    self._add_element_to(page, t, cfg, rect)

        self._refresh_all_headers()

        active = data.get("active_page")
        idx = next((i for i, pg in enumerate(self._pages)
                    if pg.id == active), 0)
        self._tab_bar.setCurrentIndex(idx)

        win = data.get("window", {})
        if win.get("w") and win.get("h"):
            self.resize(int(win["w"]), int(win["h"]))
