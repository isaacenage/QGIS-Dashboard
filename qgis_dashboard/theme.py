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

# Modern, clean default palette (Fluent-ish blues on a cool neutral canvas).
DEFAULT_SERIES = [
    "#0f6cbd", "#13a10e", "#c19c00", "#d13438", "#8764b8",
    "#00b7c3", "#ca5010", "#498205", "#a4262c", "#5c2e91",
]

_DEFAULTS = {
    "chrome_bg": "#ffffff",   # window / toolbar / tab-bar chrome (light by default,
                              # independent of the QGIS application theme)
    "window_bg": "#f4f6f8",   # canvas drawing-area background (editable)
    "surface_bg": "#ffffff",  # tile background
    "text": "#1b2733",        # primary foreground
    "text_muted": "#6b7682",  # secondary foreground
    "accent": "#0f6cbd",      # highlights, indicator value
    "border": "#d9dee3",      # tile border / grid lines
    "chart_bg": "#ffffff",    # plot area background
    "grid_line": "#c4ccd4",   # snap-grid dots
    "series": list(DEFAULT_SERIES),
    "font_family": "",        # "" => inherit the application default font
    "font_size": 11,
    "title_size": 13,
    "value_size": 30,         # indicator big number
    "radius": 8,              # tile corner radius (px)
}

# Keys a per-element override is allowed to set (a tile can't move the window).
OVERRIDE_KEYS = (
    "surface_bg", "text", "text_muted", "accent", "chart_bg",
    "series", "font_family", "font_size", "title_size", "value_size",
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

    def _font_rule(self, size=None):
        fam = 'font-family:"{}";'.format(self.font_family) if self.font_family else ""
        sz = "font-size:{}px;".format(size) if size else ""
        return fam + sz

    # ---- stylesheets ----

    def window_qss(self):
        """Stylesheet for the whole dashboard window.

        Explicitly styles the chrome (window, toolbar, tab bar, scroll areas)
        with the theme's own light colors so the dashboard does **not** inherit
        the QGIS application palette (which may be dark).
        """
        return """
QMainWindow {{ background:{chrome_bg}; }}
QToolBar {{ background:{chrome_bg}; border:none; spacing:2px; padding:3px; }}
QToolBar QToolButton {{
    color:{text}; background:transparent; padding:4px 9px; border-radius:5px;
}}
QToolBar QToolButton:hover {{ background:{window_bg}; }}
QToolBar::separator {{ background:{border}; width:1px; margin:4px 4px; }}
QTabBar {{ background:{chrome_bg}; }}
QTabBar::tab {{
    background:{window_bg}; color:{text}; padding:5px 12px;
    border:1px solid {border}; border-bottom:none;
    border-top-left-radius:6px; border-top-right-radius:6px; margin-right:2px;
}}
QTabBar::tab:selected {{ background:{surface_bg}; color:{accent}; }}
QStackedWidget {{ background:{chrome_bg}; }}
QScrollArea {{ background:{window_bg}; border:none; }}
#dashCanvas {{ background:{window_bg}; }}
#dashboardElement {{
    background:{surface_bg}; border:1px solid {border};
    border-radius:{radius}px;
}}
#tileHeader {{ background:transparent; }}
#tileTitle {{ color:{text}; {title_font} font-weight:600; }}
#tileClose {{ color:{muted}; border:none; background:transparent; }}
#tileClose:hover {{ color:{accent}; }}
#elementTitle {{ color:{text}; {title_font} font-weight:600; }}
#elementDescription {{ color:{muted}; {small_font} }}
#indValue {{ color:{accent}; font-size:{value_size}px; font-weight:700; }}
#indTop, #indBottom {{ color:{muted}; {small_font} }}
QLabel {{ color:{text}; {base_font} background:transparent; }}
QToolButton {{ color:{text}; }}
QTableWidget, QTableView {{
    background:{surface_bg}; color:{text}; gridline-color:{border};
    border:none; {base_font}
}}
QHeaderView::section {{
    background:{window_bg}; color:{text}; padding:3px 6px;
    border:none; border-right:1px solid {border}; border-bottom:1px solid {border};
}}
QTableCornerButton::section {{ background:{window_bg}; border:none; }}
""".format(
            chrome_bg=self.chrome_bg, window_bg=self.window_bg,
            surface_bg=self.surface_bg, border=self.border, radius=self.radius,
            text=self.text, muted=self.text_muted, accent=self.accent,
            value_size=self.value_size,
            title_font=self._font_rule(self.title_size),
            small_font=self._font_rule(11),
            base_font=self._font_rule(self.font_size),
        )

    def tile_qss(self):
        """Per-tile override stylesheet (scoped to one tile via objectName)."""
        return """
#dashboardElement {{ background:{surface_bg}; }}
#elementTitle, #tileTitle {{ color:{text}; {title_font} font-weight:600; }}
#indValue {{ color:{accent}; font-size:{value_size}px; font-weight:700; }}
QLabel {{ color:{text}; {base_font} }}
""".format(
            surface_bg=self.surface_bg, text=self.text, accent=self.accent,
            value_size=self.value_size,
            title_font=self._font_rule(self.title_size),
            base_font=self._font_rule(self.font_size),
        )
