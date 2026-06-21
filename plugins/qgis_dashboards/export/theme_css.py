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
    "font_family": "Inter", "heading_font": "", "font_size": 11,
    "title_size": 13, "value_size": 30, "radius": 12,
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


def heading_stack(heading, body):
    """Heading stack: heading family, then body family, then safe fallbacks.

    Mirrors :meth:`theme.Theme.heading_stack` so a missing heading font
    degrades to the body font rather than the generic sans-serif.
    """
    head = heading or body or "Inter"
    body = body or "Inter"
    if head == body:
        return font_stack(body)
    return '"{}", "{}", {}'.format(head, body, FONT_FALLBACK)


def referenced_families(theme, tile_styles=None):
    """Set of font family names referenced by a theme dict and tile overrides.

    Collects ``font_family`` + ``heading_font`` from the global *theme* dict and
    from every per-tile ``config["style"]`` dict in *tile_styles*. Empty / None
    names are dropped. Pure (no QGIS/Qt) so it can be unit-tested and shared by
    both the HTML export and the ``.qdash`` save path.
    """
    out = set()
    for src in [theme or {}] + list(tile_styles or []):
        if not isinstance(src, dict):
            continue
        for key in ("font_family", "heading_font"):
            name = src.get(key)
            if name:
                out.add(name)
    return out


# Maps a font ``format`` keyword to its data-URI MIME type.
_FONT_MIME = {"truetype": "font/ttf", "opentype": "font/otf"}


def font_face_css(entries):
    """Return an ``@font-face`` CSS block for embedded custom fonts.

    *entries* is a list of dicts ``{family, format, b64}`` where ``format`` is
    ``"truetype"`` or ``"opentype"`` and ``b64`` is the base64-encoded font
    file. The base64 may equivalently be under ``data`` (the shape produced by
    ``user_fonts.embedded_payload``). Emits one ``@font-face`` per entry with the
    bytes inlined as a data URI, so an exported dashboard renders with the font
    on any machine. Returns ``""`` for an empty list. Pure (no I/O)."""
    rules = []
    for e in entries or []:
        family = (e or {}).get("family")
        b64 = (e or {}).get("b64") or (e or {}).get("data")
        if not family or not b64:
            continue
        fmt = (e or {}).get("format") or "truetype"
        mime = _FONT_MIME.get(fmt, "font/ttf")
        rules.append(
            "@font-face {{ font-family:'{family}'; font-style:normal; "
            "font-weight:normal; src:url(data:{mime};base64,{b64}) "
            "format('{fmt}'); }}".format(
                family=family, mime=mime, b64=b64, fmt=fmt))
    return "\n".join(rules) + ("\n" if rules else "")


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
        "--heading-family: {};".format(
            heading_stack((theme or {}).get("heading_font"), val("font_family"))),
    ]
    for i, color in enumerate(series):
        lines.append("--series-{}: {};".format(i, color))

    return ":root {\n  " + "\n  ".join(lines) + "\n}\n"
