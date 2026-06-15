# -*- coding: utf-8 -*-
"""Pure ``Theme`` dict -> CSS custom properties.

The browser runtime paints chrome and tiles from CSS variables, mirroring the
plugin's :meth:`theme.Theme.window_qss` so the exported dashboard matches the
live one. This module is the web analogue of that QSS: it takes a plain theme
dict (``Theme.to_dict()``) and emits a ``:root { --token: value; }`` block.

Qt-free and side-effect-free so it can be unit-tested without a QGIS runtime.
The accent hover/soft shades are derived exactly as ``Theme`` derives them.
"""

# Mirrors Theme._FONT_FALLBACK so the export degrades gracefully without Inter.
FONT_FALLBACK = '"Segoe UI", "Helvetica Neue", Arial, sans-serif'

# Fallback values matching theme._DEFAULTS, used when a key is absent.
_FALLBACK = {
    "chrome_bg": "#ffffff", "window_bg": "#fafafa", "surface_bg": "#ffffff",
    "text": "#252b33", "text_muted": "#55606d", "accent": "#2b7de9",
    "border": "#e2e6ec", "chart_bg": "#ffffff", "grid_line": "#c4ccd4",
    "zebra": "#f6f8fb", "selection": "#e5e7eb",
    "font_family": "Inter", "font_size": 11, "title_size": 13,
    "value_size": 30, "radius": 12,
}


def _rgb(hex_str):
    """Parse ``#rrggbb`` to an ``(r, g, b)`` tuple (default blue on failure)."""
    c = (hex_str or "").lstrip("#")
    if len(c) == 6:
        try:
            return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        except ValueError:
            pass
    return 43, 125, 233


def _darken(hex_str, factor=0.86):
    r, g, b = _rgb(hex_str)
    return "#{:02x}{:02x}{:02x}".format(
        int(r * factor), int(g * factor), int(b * factor))


def _soft(hex_str, alpha=0.10):
    r, g, b = _rgb(hex_str)
    return "rgba({}, {}, {}, {})".format(r, g, b, alpha)


def font_stack(family):
    return '"{}", {}'.format(family or "Inter", FONT_FALLBACK)


def theme_to_css_vars(theme):
    """Return a ``:root { ... }`` CSS block of custom properties for *theme*."""
    def val(key):
        v = (theme or {}).get(key)
        return _FALLBACK[key] if v in (None, "") else v

    accent = val("accent")
    series = (theme or {}).get("series") or []

    lines = [
        "--chrome-bg: {};".format(val("chrome_bg")),
        "--window-bg: {};".format(val("window_bg")),
        "--surface-bg: {};".format(val("surface_bg")),
        "--text: {};".format(val("text")),
        "--muted: {};".format(val("text_muted")),
        "--accent: {};".format(accent),
        "--accent-hover: {};".format(_darken(accent)),
        "--brand-soft: {};".format(_soft(accent)),
        "--border: {};".format(val("border")),
        "--chart-bg: {};".format(val("chart_bg")),
        "--grid-line: {};".format(val("grid_line")),
        "--zebra: {};".format(val("zebra")),
        "--selection: {};".format(val("selection")),
        "--radius: {}px;".format(val("radius")),
        "--font-size: {}px;".format(val("font_size")),
        "--title-size: {}px;".format(val("title_size")),
        "--value-size: {}px;".format(val("value_size")),
        "--font-family: {};".format(font_stack(val("font_family"))),
    ]
    for i, color in enumerate(series):
        lines.append("--series-{}: {};".format(i, color))

    return ":root {\n  " + "\n  ".join(lines) + "\n}\n"
