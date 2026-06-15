# -*- coding: utf-8 -*-
"""SVG icon assets + rendering helpers for the dashboard chrome.

Icons are rendered to **crisp** ``QPixmap``\\ s via ``QSvgRenderer``. Two
flavours:

* **Monochrome action icons** for the left rail. Their artwork is embedded
  directly in the ``ICONS`` table below — no external files — and every glyph
  is re-tinted to one color with ``CompositionMode_SourceIn`` so the rail
  follows the active :class:`~theme.Theme` (light or dark). Because the tint
  recolors every opaque pixel, the stroke/fill colors baked into each glyph are
  irrelevant; only its shape matters.
* **The app logo** (``LOGO_SVG``) keeps its own pastel gradients and is rendered
  untouched — used for the window title-bar icon, the QGIS toolbar action, and
  the rail header.

**Crispness.** Every icon is supersampled (rendered at ``size × _SS``) and the
resulting pixmap is tagged with ``setDevicePixelRatio(_SS)``. Qt then *down*\\
scales it to whatever physical size the screen needs — and downscaling is
always sharp — so the icons stay crisp at 125/150/200 % Windows display
scaling instead of being upscaled from a too-small raster (the old blur).

``QtSvg`` ships with QGIS, but the import is still guarded: if it is somehow
absent every helper degrades to an empty / blank icon and callers fall back to
text, so the plugin never fails to load over a missing icon.
"""

from qgis.PyQt.QtCore import QByteArray, QRectF, Qt
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPixmap

try:
    from qgis.PyQt.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:                       # pragma: no cover - QtSvg always present in QGIS
    _HAS_SVG = False

# Supersample factor: render this many times larger, then let Qt downscale.
# 4× keeps icons sharp up to 4.0 device-pixel-ratio screens.
_SS = 4

# --- embedded, stroke-based icons (24×24) ----------------------------------

def _stroke(body):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="#000000" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">{}</svg>'
    ).format(body)


ICONS = {
    # add a tile to the canvas
    "add_element": _stroke(
        '<rect x="3" y="3" width="18" height="18" rx="2.5"/>'
        '<line x1="12" y1="8" x2="12" y2="16"/>'
        '<line x1="8" y1="12" x2="16" y2="12"/>'),
    # add a dashboard page (tab)
    "add_page": _stroke(
        '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
        '<polyline points="14 3 14 9 20 9"/>'
        '<line x1="12" y1="11.5" x2="12" y2="17.5"/>'
        '<line x1="9" y1="14.5" x2="15" y2="14.5"/>'),
    # cross-filter wiring (two interlocking chain links) — tinted to one color
    "connections": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2048 1280">'
        '<path d="m 1536,384 v 128 q 76,0 145,17 69,17 123,56 54,39 84,99 '
        '30,60 32,148 0,66 -25,124 -25,58 -69,101 -44,43 -102,69 -58,26 -124,26 '
        'h -512 q -66,0 -124,-25 -58,-25 -101,-69 -43,-44 -69,-102 -26,-58 -26,-124 '
        '0,-87 31,-147 31,-60 85,-99 54,-39 122,-56 68,-17 146,-18 V 384 h -64 '
        'q -93,0 -174,35 -81,35 -142,96 -61,61 -96,142 -35,81 -36,175 0,93 35,174 '
        '35,81 96,142 61,61 142,96 81,35 175,36 h 512 q 93,0 174,-35 81,-35 142,-96 '
        '61,-61 96,-142 35,-81 36,-175 0,-93 -35,-174 -35,-81 -96,-142 -61,-61 -142,-96 '
        '-81,-35 -175,-36 z M 896,896 V 768 q 76,0 145,-17 69,-17 123,-56 54,-39 84,-99 '
        '30,-60 32,-148 0,-66 -25,-124 -25,-58 -69,-101 -44,-43 -102,-69 -58,-26 -124,-26 '
        'H 448 q -66,0 -124,25 -58,25 -101,69 -43,44 -69,102 -26,58 -26,124 0,87 31,147 '
        '31,60 85,99 54,39 122,56 68,17 146,18 V 896 H 448 Q 355,896 274,861 193,826 132,765 '
        '71,704 36,623 1,542 0,448 0,355 35,274 70,193 131,132 192,71 273,36 354,1 448,0 '
        'h 512 q 93,0 174,35 81,35 142,96 61,61 96,142 35,81 36,175 0,93 -35,174 -35,81 -96,142 '
        '-61,61 -142,96 -81,35 -175,36 z"/>'
        '</svg>'),
    # appearance / theme (half-filled circle) — tinted to one color
    "appearance": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
        '<path d="M12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C7.02944 3 '
        '3 7.02944 3 12C3 16.9706 7.02944 21 12 21Z" stroke="#000" stroke-width="1.6"/>'
        '<path d="M12 5.25V18.75C15.7279 18.75 18.75 15.7279 18.75 12C18.75 8.27208 '
        '15.7279 5.25 12 5.25Z" fill="#000"/>'
        '</svg>'),
    # clear the active cross-filter (funnel + slash)
    "clear_filter": _stroke(
        '<path d="M3 4h18l-7 8.2V19l-4 2v-8.8z"/>'
        '<line x1="3.5" y1="3.5" x2="20.5" y2="20.5"/>'),
    # settings hub (gear) — opens the Settings dialog
    "settings": _stroke(
        '<circle cx="12" cy="12" r="3.1"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83'
        'l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0'
        'v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83'
        'l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4'
        'h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83'
        'l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0'
        'v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83'
        'l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4'
        'h-.09a1.65 1.65 0 0 0-1.51 1z"/>'),
    "zoom_out": _stroke(
        '<circle cx="11" cy="11" r="7"/>'
        '<line x1="20.5" y1="20.5" x2="16" y2="16"/>'
        '<line x1="8" y1="11" x2="14" y2="11"/>'),
    # fit / reset (corner brackets + center dot) — tinted to one color
    "zoom_reset": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#000" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4.5 9V4.5H9"/>'
        '<path d="M15 4.5H19.5V9"/>'
        '<path d="M4.5 15V19.5H9"/>'
        '<path d="M15 19.5H19.5V15"/>'
        '<circle cx="12" cy="12" r="2.1" stroke-width="1.5"/>'
        '</svg>'),
    "zoom_in": _stroke(
        '<circle cx="11" cy="11" r="7"/>'
        '<line x1="20.5" y1="20.5" x2="16" y2="16"/>'
        '<line x1="8" y1="11" x2="14" y2="11"/>'
        '<line x1="11" y1="8" x2="11" y2="14"/>'),
}


# --- the gradient app logo (pastel blue / orange / green branding) ---------
#
# Three ascending parallelogram "bars", each a soft pastel: blue (bottom),
# orange (middle), green (top) — the analytics palette ui-ux-pro-max returns
# for a dashboard (blue data + amber highlight + green categorical).
#
# The source art is drawn in a y-up space and flipped with ``matrix(1,0,0,-1)``;
# we keep the flip on an inner <g> and shift the viewBox to
# ``0 -492.481 … 492.481`` so the flipped geometry lands inside the rendered
# area while the userSpace gradients stay correct. (Transforms on the root
# <svg> are unreliable across renderers.)
LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 -492.481 492.481 492.481">'
    '<linearGradient id="dl1" gradientUnits="userSpaceOnUse" '
    'x1="-36.6002" y1="621.3422" x2="-17.2782" y2="547.7642" '
    'gradientTransform="matrix(7.8769 0 0 -7.8769 404.0846 4917.9966)">'
    '<stop offset="0" style="stop-color:#A7D2F5"/>'
    '<stop offset="1" style="stop-color:#5E97D0"/></linearGradient>'
    '<linearGradient id="dl2" gradientUnits="userSpaceOnUse" '
    'x1="-27.0735" y1="620.7541" x2="-11.7045" y2="560.3241" '
    'gradientTransform="matrix(7.8769 0 0 -7.8769 404.0846 4917.9966)">'
    '<stop offset="0" style="stop-color:#F8CDA6"/>'
    '<stop offset="1" style="stop-color:#E89A5C"/></linearGradient>'
    '<linearGradient id="dl3" gradientUnits="userSpaceOnUse" '
    'x1="14.0324" y1="554.688" x2="-10.4176" y2="584.028" '
    'gradientTransform="matrix(7.8769 0 0 -7.8769 404.0846 4917.9966)">'
    '<stop offset="0" style="stop-color:#A9DCC2"/>'
    '<stop offset="1" style="stop-color:#6FB890"/></linearGradient>'
    '<g transform="matrix(1,0,0,-1,0,0)">'
    '<polygon style="fill:url(#dl1);" '
    'points="25.687,297.141 135.735,0 271.455,0 161.398,297.141"/>'
    '<polygon style="fill:url(#dl2);" '
    'points="123.337,394.807 233.409,97.674 369.144,97.674 259.072,394.807"/>'
    '<polygon style="fill:url(#dl3);" '
    'points="221.026,492.481 331.083,195.348 466.794,195.348 356.746,492.481"/>'
    '</g></svg>'
)


# --- rendering -------------------------------------------------------------

def _render_px(svg_text, logical_size, tint=None, supersample=1):
    """Render *svg_text* into a transparent pixmap, crisp on hiDPI screens.

    The pixmap is drawn at ``logical_size × supersample`` physical pixels and
    tagged with that device-pixel-ratio, so it reports ``logical_size`` to
    layouts but carries enough resolution for Qt to downscale sharply. When
    *tint* is given every opaque pixel is recolored to it (monochrome rail
    glyphs); otherwise the artwork's own colors are kept (the logo).
    """
    size = max(1, int(round(logical_size * supersample)))
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    if _HAS_SVG:
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        painter = QPainter(px)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        vb = renderer.viewBoxF()
        if vb.isValid() and vb.width() > 0 and vb.height() > 0:
            scale = min(size / vb.width(), size / vb.height())
            w = vb.width() * scale
            h = vb.height() * scale
            renderer.render(painter, QRectF((size - w) / 2.0, (size - h) / 2.0, w, h))
        else:
            renderer.render(painter)
        if tint is not None:
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(px.rect(), QColor(tint))
        painter.end()
    if supersample != 1:
        px.setDevicePixelRatio(float(supersample))
    return px


def monochrome_icon(name, color, size=22):
    """A crisp single-color :class:`QIcon` for one rail glyph."""
    if not _HAS_SVG:
        return QIcon()
    svg = ICONS.get(name)
    if not svg:
        return QIcon()
    return QIcon(_render_px(svg, size, tint=color, supersample=_SS))


def logo_pixmap(size=64):
    """The gradient logo as a crisp ``QPixmap`` (for the rail header label)."""
    return _render_px(LOGO_SVG, size, tint=None, supersample=_SS)


def logo_icon(sizes=(16, 24, 32, 48, 64, 128, 256)):
    """The gradient logo as a multi-resolution :class:`QIcon`.

    Returns an empty icon when ``QtSvg`` is unavailable so callers can fall
    back (``QIcon.isNull()`` is reliable in that case). Pixmaps are rendered at
    their exact native sizes — the window system picks the best one — so the
    title-bar / taskbar icon stays sharp.
    """
    if not _HAS_SVG:
        return QIcon()
    icon = QIcon()
    for s in sizes:
        icon.addPixmap(_render_px(LOGO_SVG, s, tint=None, supersample=1))
    return icon
