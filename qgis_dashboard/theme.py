# -*- coding: utf-8 -*-
"""Dashboard theme.

A single source of truth for every color, font and metric the dashboard
paints with. The global ``Theme`` is edited in the Appearance dialog and
persisted into the project; individual tiles may carry a partial override
dict (``config["style"]``) that is merged over the global theme via
``Theme.merged_with``.

Colors are stored as ``#rrggbb`` strings so the whole theme is trivially
JSON-serializable. Chart widgets read colors straight off a ``Theme``;
container chrome is styled through ``Theme.window_qss`` / ``tile_qss``.
"""

import copy

# "Modern analytics" default palette (Summarizer design system, blue brand).
# A cool neutral canvas, white surfaces, hairline borders, one strong accent.
DEFAULT_SERIES = [
    "#2b7de9", "#13a10e", "#c19c00", "#d13438", "#8764b8",
    "#00b7c3", "#ca5010", "#498205", "#a4262c", "#5c2e91",
]

_DEFAULTS = {
    "chrome_bg": "#ffffff",   # window / toolbar / tab-bar chrome (light by default,
                              # independent of the QGIS application theme)
    "window_bg": "#fafafa",   # canvas drawing-area background (editable)
    "surface_bg": "#ffffff",  # tile background
    "text": "#252b33",        # primary foreground
    "text_muted": "#55606d",  # secondary foreground
    "accent": "#2b7de9",      # brand: highlights, indicator value, primary buttons
                              # (the hover/pressed shade is derived from this)
    "border": "#e2e6ec",      # tile border / hairlines / grid lines
    "chart_bg": "#ffffff",    # plot area background
    "grid_line": "#c4ccd4",   # snap-grid dots
    "zebra": "#f6f8fb",       # alternating table row
    "selection": "#e5e7eb",   # selected table row / text selection
    "series": list(DEFAULT_SERIES),
    "font_family": "Inter",   # bundled UI body font (see fonts.py); falls back gracefully
    "heading_font": "",       # optional heading/display family (titles + indicator
                              # value). Empty == reuse font_family (no pairing).
    "font_size": 11,
    "title_size": 13,
    "value_size": 30,         # indicator big number
    "radius": 12,             # tile / surface corner radius (px)
}

# Keys a per-element override is allowed to set (a tile can't move the window).
OVERRIDE_KEYS = (
    "surface_bg", "text", "text_muted", "accent", "chart_bg",
    "series", "font_family", "heading_font", "font_size", "title_size",
    "value_size",
)


class Theme(object):
    """Immutable-ish bag of appearance values.

    Mutating helpers (:meth:`merged_with`, :meth:`with_values`) return new
    ``Theme`` instances rather than editing in place, per the project style.
    """

    __slots__ = tuple(_DEFAULTS.keys())

    def __init__(self, **values):
        for key, default in _DEFAULTS.items():
            val = values.get(key, default)
            # never share the mutable list between instances
            setattr(self, key, list(val) if key == "series" else val)

    # ---- construction ----

    @classmethod
    def default(cls):
        return cls()

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            return cls.default()
        clean = {k: data[k] for k in _DEFAULTS if k in data}
        return cls(**clean)

    def to_dict(self):
        return {k: (list(getattr(self, k)) if k == "series" else getattr(self, k))
                for k in _DEFAULTS}

    def with_values(self, **values):
        data = self.to_dict()
        data.update(values)
        return Theme.from_dict(data)

    def merged_with(self, overrides):
        """Return a Theme that layers a partial override dict on top of self."""
        if not overrides:
            return self
        data = self.to_dict()
        for key in OVERRIDE_KEYS:
            if key in overrides and overrides[key] not in (None, ""):
                data[key] = copy.copy(overrides[key])
        return Theme.from_dict(data)

    # ---- derived values ----

    def series_color(self, index):
        pal = self.series or DEFAULT_SERIES
        return pal[index % len(pal)]

    # Fallbacks appended after the chosen family so the UI degrades gracefully
    # when the bundled Inter font is unavailable.
    _FONT_FALLBACK = '"Segoe UI", "Helvetica Neue", Arial, sans-serif'

    def font_stack(self):
        """The CSS font-family stack: the chosen body family then safe fallbacks."""
        fam = self.font_family or "Inter"
        return '"{}", {}'.format(fam, self._FONT_FALLBACK)

    def heading_family(self):
        """The resolved heading family name (falls back to the body family)."""
        return self.heading_font or self.font_family or "Inter"

    def heading_stack(self):
        """CSS stack for headings: heading family, then the body family, then
        safe fallbacks — so a missing heading font degrades to the body font."""
        head = self.heading_font or self.font_family or "Inter"
        body = self.font_family or "Inter"
        if head == body:
            return self.font_stack()
        return '"{}", "{}", {}'.format(head, body, self._FONT_FALLBACK)

    def _font_rule(self, size=None):
        fam = "font-family:{};".format(self.font_stack())
        sz = "font-size:{}px;".format(size) if size else ""
        return fam + sz

    def _heading_rule(self, size=None):
        fam = "font-family:{};".format(self.heading_stack())
        sz = "font-size:{}px;".format(size) if size else ""
        return fam + sz

    # ---- stylesheets ----

    def window_qss(self):
        """Stylesheet for the whole dashboard window (and its child dialogs).

        Explicitly styles the chrome (window, rail, tab bar, scroll areas) plus
        every common control — buttons, inputs, tabs, tables, scrollbars,
        tooltips — with the theme's own light "modern analytics" colors, so the
        dashboard does **not** inherit the QGIS application palette (which may
        be dark). Adapted from the Summarizer design system.
        """
        return """
* {{ font-family:{font_family}; }}
QMainWindow, QDialog {{ background:{chrome_bg}; }}
QWidget {{ color:{text}; }}
QFrame {{ border:none; background:transparent; }}

/* Left navigation rail --------------------------------------------------- */
#dashSidebar {{ background:{chrome_bg}; border-right:1px solid {border}; }}
#dashSidebarLogo {{ background:transparent; }}
#dashRailSep {{ background:{border}; border:none; }}
QToolButton#dashRailButton {{
    background:transparent; border:1px solid transparent; border-radius:8px;
}}
QToolButton#dashRailButton:hover {{ background:{brand_soft}; border-color:{border}; }}
QToolButton#dashRailButton:pressed {{ background:{selection}; }}
QToolButton#dashRailButton:checked {{ background:{brand_soft}; border-color:{accent}; }}
QToolButton#dashRailButton:focus {{ border-color:{accent}; }}

/* Status bar ------------------------------------------------------------- */
QStatusBar {{ background:{chrome_bg}; border-top:1px solid {border}; }}
QStatusBar::item {{ border:none; }}
#dashFilterStatus {{ color:{muted}; {small_font} background:transparent; }}
#dashFilterDot {{ background:{accent}; border-radius:4px; }}

/* Page tab strip (tab bar + lock/export buttons) ------------------------- */
/* The single soft hairline lives on the whole strip — matching the rail's
   border, never a heavy/dark outline — so it spans under the buttons too. The
   native tab-bar base line is disabled in code (QTabBar.setDrawBase(False)). */
#dashTabStrip {{ background:{chrome_bg}; border-bottom:1px solid {border}; }}
QTabBar {{ background:transparent; }}
QTabBar::tab {{
    background:transparent; color:{muted}; padding:8px 16px; margin-right:2px;
    border:none; border-bottom:3px solid transparent; font-weight:500;
}}
QTabBar::tab:hover {{ color:{text}; }}
QTabBar::tab:selected {{
    color:{accent}; font-weight:600; border-bottom:3px solid {accent};
    background:{brand_soft};
    border-top-left-radius:8px; border-top-right-radius:8px;
}}
QStackedWidget {{ background:{chrome_bg}; }}
/* Generic scroll areas (dialogs, lists, ...) stay transparent so they inherit
   their container's chrome — the *canvas background* must never leak into them. */
QScrollArea {{ background:transparent; border:none; }}
/* The canvas drawing-area background is scoped to the canvas and the page view
   that holds it (so overflow when zoomed/panned matches the canvas), nowhere else. */
#dashPageView, #dashCanvas {{ background:{window_bg}; }}

/* Tiles ------------------------------------------------------------------ */
#dashboardElement {{
    background:{surface_bg}; border:1px solid {border};
    border-radius:{radius}px;
}}
/* full-bleed tiles (e.g. the live map) fill edge-to-edge: square corners so a
   rectangular child aligns with the frame, and no inner background bleed. */
#dashboardElement[fullBleed="true"] {{ border-radius:0; }}
#tileHeader {{ background:transparent; }}
#tileTitle {{ color:{text}; {heading_font} font-weight:600; }}
#tileClose {{ color:{muted}; border:none; background:transparent; }}
#tileClose:hover {{ color:{accent}; }}
#elementTitle {{ color:{text}; {heading_font} font-weight:600; }}
#elementDescription {{ color:{muted}; {small_font} }}
#indValue {{ color:{accent}; font-family:{heading_stack}; font-size:{value_size}px; font-weight:700; }}
#indTop, #indBottom {{ color:{muted}; {small_font} }}
QLabel {{ color:{text}; {base_font} background:transparent; }}
QLabel[connHint="true"] {{ color:{muted}; {small_font} }}

/* Buttons ---------------------------------------------------------------- */
QPushButton {{
    min-height:32px; padding:7px 16px; border-radius:10px;
    border:1px solid transparent; font-weight:600; {base_font}
    background:{accent}; color:#ffffff;
}}
QPushButton:hover {{ background:{accent_hover}; }}
QPushButton:pressed {{ background:{accent_hover}; border-color:{accent_hover}; }}
QPushButton:disabled {{ background:{border}; color:{muted}; }}
QPushButton[variant="secondary"] {{
    background:{surface_bg}; border:1px solid {border}; color:{text};
}}
QPushButton[variant="secondary"]:hover {{
    border-color:{accent}; background:{brand_soft};
}}
QPushButton[variant="ghost"] {{
    background:transparent; border:none; color:{accent};
}}
QPushButton[variant="ghost"]:hover {{ background:{brand_soft}; }}
/* In a dialog button box, only the default (e.g. OK) reads as primary; the
   rest (Cancel/Apply/Clear) fall back to a quiet secondary pill. */
QDialogButtonBox QPushButton {{
    background:{surface_bg}; border:1px solid {border}; color:{text};
}}
QDialogButtonBox QPushButton:hover {{ border-color:{accent}; background:{brand_soft}; }}
QDialogButtonBox QPushButton:default {{
    background:{accent}; border-color:{accent}; color:#ffffff;
}}
QDialogButtonBox QPushButton:default:hover {{
    background:{accent_hover}; border-color:{accent_hover};
}}

/* Inputs ----------------------------------------------------------------- */
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background:{surface_bg}; border:1px solid {border}; border-radius:8px;
    color:{text}; padding:5px 9px; min-height:28px;
    selection-background-color:{selection}; selection-color:{text};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{ border:1px solid {accent}; }}
QComboBox::drop-down {{ width:22px; border:none; background:transparent; }}
QComboBox QAbstractItemView {{
    background:{surface_bg}; color:{text}; border:1px solid {border};
    selection-background-color:{selection}; selection-color:{text};
}}
QToolButton {{ color:{text}; }}
QCheckBox, QRadioButton {{ color:{text}; {base_font} background:transparent; }}

/* Sliders (e.g. the global corner-radius control) ------------------------ */
QSlider::groove:horizontal {{
    height:4px; border-radius:2px; background:{border};
}}
QSlider::sub-page:horizontal {{ background:{accent}; border-radius:2px; }}
QSlider::handle:horizontal {{
    background:{accent}; border:2px solid {chrome_bg}; width:14px; height:14px;
    margin:-6px 0; border-radius:9px;
}}
QSlider::handle:horizontal:hover {{ background:{accent_hover}; }}

/* Group boxes (themed surface + hairline, never the dark app palette) ----- */
QGroupBox {{
    background:{surface_bg}; border:1px solid {border}; border-radius:10px;
    margin-top:14px; padding:14px 12px 10px 12px; {base_font} font-weight:600;
    color:{text};
}}
QGroupBox::title {{
    subcontrol-origin:margin; subcontrol-position:top left; left:12px;
    padding:0 6px; color:{muted}; background:{chrome_bg};
}}

/* Tables and lists ------------------------------------------------------- */
QTableWidget, QTableView {{
    background:{surface_bg}; color:{text}; gridline-color:{border};
    border:1px solid {border}; border-radius:10px; {base_font}
    selection-background-color:{selection}; selection-color:{text};
    alternate-background-color:{zebra};
}}
QTableView::item {{ padding:4px 8px; }}
QListView, QTreeView, QListWidget, QTreeWidget {{
    background:{surface_bg}; color:{text}; border:1px solid {border};
    border-radius:10px; alternate-background-color:{zebra};
}}
QListWidget::item, QTreeWidget::item {{ padding:5px 8px; }}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background:{selection}; color:{text};
}}
QHeaderView::section {{
    background:{zebra}; color:{text}; padding:6px 10px;
    border:none; border-right:1px solid {border}; border-bottom:1px solid {border};
    font-weight:600;
}}
QTableCornerButton::section {{ background:{zebra}; border:none; }}

/* Scrollbars (slim, rounded) --------------------------------------------- */
QScrollBar:vertical {{ background:transparent; width:12px; margin:2px; }}
QScrollBar::handle:vertical {{
    background:{selection}; border-radius:5px; min-height:30px;
}}
QScrollBar::handle:vertical:hover {{ background:{muted}; }}
QScrollBar:horizontal {{ background:transparent; height:12px; margin:2px; }}
QScrollBar::handle:horizontal {{
    background:{selection}; border-radius:5px; min-width:30px;
}}
QScrollBar::handle:horizontal:hover {{ background:{muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}

/* Splitter, menus, tooltip ----------------------------------------------- */
QSplitter::handle {{ background:{border}; }}
QMenu {{ background:{surface_bg}; color:{text}; border:1px solid {border};
    border-radius:8px; padding:4px; }}
QMenu::item {{ padding:6px 18px; border-radius:6px; color:{text}; }}
QMenu::item:selected {{ background:{brand_soft}; color:{accent}; }}
QToolTip {{
    background:#111827; color:#ffffff; border:none; border-radius:6px;
    padding:5px 8px; {small_font}
}}
""".format(
            chrome_bg=self.chrome_bg, window_bg=self.window_bg,
            surface_bg=self.surface_bg, border=self.border, radius=self.radius,
            text=self.text, muted=self.text_muted, accent=self.accent,
            accent_hover=self._accent_hover(), zebra=self.zebra,
            selection=self.selection, brand_soft=self._brand_soft(),
            value_size=self.value_size, font_family=self.font_stack(),
            heading_stack=self.heading_stack(),
            heading_font=self._heading_rule(self.title_size),
            small_font=self._font_rule(11),
            base_font=self._font_rule(self.font_size),
        )

    def _accent_rgb(self):
        c = self.accent.lstrip("#")
        if len(c) == 6:
            return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return 43, 125, 233   # fall back to the default blue

    def _accent_hover(self):
        """A slightly darker shade of the accent for hover/pressed states."""
        r, g, b = self._accent_rgb()
        return "#{:02x}{:02x}{:02x}".format(
            int(r * 0.86), int(g * 0.86), int(b * 0.86))

    def _brand_soft(self):
        """A faint translucent tint of the accent for hover fills."""
        r, g, b = self._accent_rgb()
        return "rgba({}, {}, {}, 0.10)".format(r, g, b)

    def tile_qss(self):
        """Per-tile override stylesheet (scoped to one tile via objectName)."""
        return """
#dashboardElement {{ background:{surface_bg}; }}
#elementTitle, #tileTitle {{ color:{text}; {heading_font} font-weight:600; }}
#indValue {{ color:{accent}; font-family:{heading_stack}; font-size:{value_size}px; font-weight:700; }}
QLabel {{ color:{text}; {base_font} }}
""".format(
            surface_bg=self.surface_bg, text=self.text, accent=self.accent,
            value_size=self.value_size, heading_stack=self.heading_stack(),
            heading_font=self._heading_rule(self.title_size),
            base_font=self._font_rule(self.font_size),
        )
