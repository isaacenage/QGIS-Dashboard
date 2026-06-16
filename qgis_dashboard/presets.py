# -*- coding: utf-8 -*-
"""Preset appearance themes.

A curated gallery of ready-made dashboard looks — each one a coordinated
**color palette + font pairing** — surfaced in the Appearance dialog so a user
can restyle the whole dashboard in one click instead of tuning a dozen color
pickers. Palettes and pairings were drawn from the ``ui-ux-pro-max`` design
intelligence (analytics / SaaS / fintech color systems + professional Google
Font pairings) and tuned for WCAG-reasonable contrast in both light and dark.

Each preset is a *partial* dict of :data:`theme._DEFAULTS` keys; missing keys
(radius, font sizes) inherit the defaults, so a preset only carries what makes
it distinctive. :func:`theme_for` layers a preset over the default theme and
returns a fresh :class:`~theme.Theme`; :func:`match` reverse-maps a live theme
back to a preset name so the dialog can preselect it.

Font pairings name Google Fonts (e.g. *Poppins*, *IBM Plex Sans*). They render
if installed on the machine; otherwise the theme's font stack degrades to the
bundled Inter / the platform sans-serif — the colors always apply regardless.
"""

from .theme import Theme, _DEFAULTS, DEFAULT_SERIES

# Sentinel name for "none of the presets match the current theme".
CUSTOM = "Custom"


# Each entry: human name -> partial theme dict. Order is the gallery order.
# ``font_family`` = body, ``heading_font`` = display/title family (the pairing).
_PRESETS = [
    # ---- light ----------------------------------------------------------
    ("Summarizer Blue", {
        "chrome_bg": "#ffffff", "window_bg": "#fafafa", "surface_bg": "#ffffff",
        "text": "#252b33", "text_muted": "#55606d", "accent": "#2b7de9",
        "border": "#e2e6ec", "chart_bg": "#ffffff", "grid_line": "#c4ccd4",
        "zebra": "#f6f8fb", "selection": "#e5e7eb",
        "series": list(DEFAULT_SERIES),
        "font_family": "Inter", "heading_font": "",
    }),
    ("Slate Professional", {
        "chrome_bg": "#ffffff", "window_bg": "#f8fafc", "surface_bg": "#ffffff",
        "text": "#0f172a", "text_muted": "#475569", "accent": "#2563eb",
        "border": "#e2e8f0", "chart_bg": "#ffffff", "grid_line": "#cbd5e1",
        "zebra": "#f1f5f9", "selection": "#e2e8f0",
        "series": ["#2563eb", "#0ea5e9", "#14b8a6", "#f59e0b", "#8b5cf6",
                   "#ef4444", "#22c55e", "#ec4899"],
        "font_family": "Open Sans", "heading_font": "Poppins",
    }),
    ("Indigo SaaS", {
        "chrome_bg": "#ffffff", "window_bg": "#f5f3ff", "surface_bg": "#ffffff",
        "text": "#1e1b4b", "text_muted": "#4b5563", "accent": "#6366f1",
        "border": "#e5e1f5", "chart_bg": "#ffffff", "grid_line": "#cdc7f0",
        "zebra": "#faf8ff", "selection": "#ece9fe",
        "series": ["#6366f1", "#22c55e", "#f59e0b", "#ec4899", "#06b6d4",
                   "#8b5cf6", "#ef4444", "#14b8a6"],
        "font_family": "Plus Jakarta Sans", "heading_font": "Plus Jakarta Sans",
    }),
    ("Fintech Amber", {
        "chrome_bg": "#ffffff", "window_bg": "#f8fafc", "surface_bg": "#ffffff",
        "text": "#0f172a", "text_muted": "#475569", "accent": "#d97706",
        "border": "#e7e5e0", "chart_bg": "#ffffff", "grid_line": "#cbd5e1",
        "zebra": "#f8fafc", "selection": "#fef3c7",
        "series": ["#1e40af", "#d97706", "#0891b2", "#15803d", "#7c3aed",
                   "#b91c1c", "#0e7490", "#a16207"],
        "font_family": "IBM Plex Sans", "heading_font": "IBM Plex Sans",
    }),
    ("Teal Health", {
        "chrome_bg": "#ffffff", "window_bg": "#f0fdfa", "surface_bg": "#ffffff",
        "text": "#042f2e", "text_muted": "#3f6360", "accent": "#0f766e",
        "border": "#cdeae6", "chart_bg": "#ffffff", "grid_line": "#9be0d7",
        "zebra": "#ecfdf9", "selection": "#ccfbf1",
        "series": ["#0f766e", "#0891b2", "#22c55e", "#f59e0b", "#6366f1",
                   "#db2777", "#0e7490", "#65a30d"],
        "font_family": "Noto Sans", "heading_font": "Figtree",
    }),
    ("Emerald Corporate", {
        "chrome_bg": "#ffffff", "window_bg": "#f6fdf9", "surface_bg": "#ffffff",
        "text": "#052e1b", "text_muted": "#456155", "accent": "#059669",
        "border": "#d4ebe0", "chart_bg": "#ffffff", "grid_line": "#a7d8c4",
        "zebra": "#f0faf5", "selection": "#d1fae5",
        "series": ["#059669", "#0d9488", "#2563eb", "#f59e0b", "#7c3aed",
                   "#dc2626", "#0891b2", "#65a30d"],
        "font_family": "Source Sans 3", "heading_font": "Lexend",
    }),
    ("Rose Editorial", {
        "chrome_bg": "#ffffff", "window_bg": "#fdf7f9", "surface_bg": "#ffffff",
        "text": "#3f1d2e", "text_muted": "#7a5567", "accent": "#be185d",
        "border": "#f1d9e3", "chart_bg": "#ffffff", "grid_line": "#e8bfd0",
        "zebra": "#fdf2f6", "selection": "#fce7f0",
        "series": ["#be185d", "#9d174d", "#b45309", "#0f766e", "#6d28d9",
                   "#1e40af", "#db2777", "#ca8a04"],
        "font_family": "Inter", "heading_font": "Playfair Display",
    }),
    ("Graphite Gold", {
        "chrome_bg": "#ffffff", "window_bg": "#fafaf9", "surface_bg": "#ffffff",
        "text": "#171717", "text_muted": "#525252", "accent": "#a16207",
        "border": "#e7e5e4", "chart_bg": "#ffffff", "grid_line": "#d6d3d1",
        "zebra": "#f5f5f4", "selection": "#ede9e3",
        "series": ["#a16207", "#404040", "#0891b2", "#b45309", "#15803d",
                   "#7c3aed", "#be123c", "#525252"],
        "font_family": "Inter", "heading_font": "Space Grotesk",
    }),
    ("Sunset Coral", {
        "chrome_bg": "#ffffff", "window_bg": "#fff7ed", "surface_bg": "#ffffff",
        "text": "#431407", "text_muted": "#6b5547", "accent": "#ea580c",
        "border": "#f3e1d3", "chart_bg": "#ffffff", "grid_line": "#fbcfa8",
        "zebra": "#fff4e6", "selection": "#ffedd5",
        "series": ["#ea580c", "#f59e0b", "#e11d48", "#0d9488", "#7c3aed",
                   "#2563eb", "#d97706", "#65a30d"],
        "font_family": "Work Sans", "heading_font": "Outfit",
    }),
    # ---- dark -----------------------------------------------------------
    ("Midnight Slate", {
        "chrome_bg": "#0b1220", "window_bg": "#0f172a", "surface_bg": "#1e293b",
        "text": "#e2e8f0", "text_muted": "#94a3b8", "accent": "#38bdf8",
        "border": "#334155", "chart_bg": "#1e293b", "grid_line": "#334155",
        "zebra": "#18243a", "selection": "#334155",
        "series": ["#38bdf8", "#34d399", "#fbbf24", "#f87171", "#a78bfa",
                   "#22d3ee", "#fb923c", "#4ade80"],
        "font_family": "Inter", "heading_font": "Space Grotesk",
    }),
    ("Carbon Dark", {
        "chrome_bg": "#0a0a0a", "window_bg": "#111111", "surface_bg": "#1a1a1a",
        "text": "#f5f5f5", "text_muted": "#a3a3a3", "accent": "#f59e0b",
        "border": "#2a2a2a", "chart_bg": "#1a1a1a", "grid_line": "#333333",
        "zebra": "#161616", "selection": "#2e2e2e",
        "series": ["#f59e0b", "#60a5fa", "#34d399", "#f87171", "#a78bfa",
                   "#22d3ee", "#fbbf24", "#fb7185"],
        "font_family": "IBM Plex Sans", "heading_font": "IBM Plex Sans",
    }),
    ("Indigo Night", {
        "chrome_bg": "#0f0f23", "window_bg": "#1a1740", "surface_bg": "#27234f",
        "text": "#e0e7ff", "text_muted": "#a9b1e0", "accent": "#818cf8",
        "border": "#352f63", "chart_bg": "#27234f", "grid_line": "#3a3570",
        "zebra": "#221e47", "selection": "#3730a3",
        "series": ["#818cf8", "#34d399", "#fbbf24", "#f472b6", "#22d3ee",
                   "#a78bfa", "#fb923c", "#4ade80"],
        "font_family": "Plus Jakarta Sans", "heading_font": "Plus Jakarta Sans",
    }),
]

# Keys a preset is allowed to carry (everything else inherits the defaults).
_PRESET_KEYS = tuple(
    k for k in _DEFAULTS
    if k in {
        "chrome_bg", "window_bg", "surface_bg", "text", "text_muted", "accent",
        "border", "chart_bg", "grid_line", "zebra", "selection", "series",
        "font_family", "heading_font",
    }
)


def names():
    """Preset display names, in gallery order."""
    return [name for name, _ in _PRESETS]


def values_for(name):
    """The raw partial dict for *name* (empty dict if unknown)."""
    for n, values in _PRESETS:
        if n == name:
            return dict(values)
    return {}


def theme_for(name, base=None):
    """Return a :class:`~theme.Theme` for preset *name*.

    The preset is layered over *base* (or the default theme), so non-palette
    settings like corner radius / font sizes are preserved from *base*.
    """
    data = (base.to_dict() if base is not None else Theme.default().to_dict())
    values = values_for(name)
    for key in _PRESET_KEYS:
        if key in values:
            data[key] = (list(values[key]) if key == "series" else values[key])
    return Theme.from_dict(data)


def match(theme):
    """Return the preset name whose palette+fonts equal *theme*, else ``None``.

    Compares only the keys a preset defines, so a theme that differs solely in
    radius / font size still matches its preset.
    """
    if theme is None:
        return None
    current = theme.to_dict()
    for name, values in _PRESETS:
        if all(_eq(values.get(k), current.get(k)) for k in values):
            return name
    return None


def _eq(a, b):
    if isinstance(a, list) or isinstance(b, list):
        return list(a or []) == list(b or [])
    return a == b
