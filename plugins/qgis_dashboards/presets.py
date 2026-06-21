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
    # Lavender glassmorphism, white cards, violet/pink accents, from the
    # "Omagie" project-management dashboard reference.
    ("Omagie Glass", {
        "chrome_bg": "#ffffff", "window_bg": "#ede7f9", "surface_bg": "#ffffff",
        "text": "#3a2e5c", "text_muted": "#8a7fa6", "accent": "#9b5de5",
        "border": "#e4dcf4", "chart_bg": "#fbf8fe", "grid_line": "#ddd2f0",
        "zebra": "#f7f3fd", "selection": "#ece3fb",
        "series": ["#9b5de5", "#f15bb5", "#c77dff", "#7b6cf0", "#d8a3ff",
                   "#ff8fc7", "#a98bf2", "#6a5acd"],
        "font_family": "Poppins", "heading_font": "Poppins",
    }),
    # Warm mauve-grey canvas with cream cards and a muted purple accent, from
    # the "Smartech" student dashboard reference.
    ("Smartech Mauve", {
        "chrome_bg": "#ffffff", "window_bg": "#c9b7c5", "surface_bg": "#f3efe9",
        "text": "#4a3a47", "text_muted": "#8e7e8a", "accent": "#8c6a9e",
        "border": "#e4dbe0", "chart_bg": "#f3efe9", "grid_line": "#d8cbd3",
        "zebra": "#efe9f1", "selection": "#e7dcea",
        "series": ["#8c6a9e", "#d96aa0", "#e8a23d", "#5fa39a", "#b07ac0",
                   "#e0739a", "#c79a4a", "#7a8fce"],
        "font_family": "Quicksand", "heading_font": "Quicksand",
    }),
    # Soft warm-grey clinical canvas, white cards, chartreuse-yellow accent,
    # from the "Cardiology" medical-records dashboard reference.
    ("Cardio Lime", {
        "chrome_bg": "#ffffff", "window_bg": "#e7e4dd", "surface_bg": "#ffffff",
        "text": "#1c1c18", "text_muted": "#7a786f", "accent": "#d4e614",
        "border": "#e0ddd5", "chart_bg": "#f4f2ec", "grid_line": "#d6d3ca",
        "zebra": "#f1efe9", "selection": "#eef0d4",
        "series": ["#d4e614", "#b9c70f", "#2b2b2b", "#8a9a3c", "#e3ee5e",
                   "#6f7d2a", "#a8b30c", "#444444"],
        "font_family": "Inter", "heading_font": "Inter",
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
    # Warm gold-on-charcoal, extracted from a dark amber admin-dashboard
    # reference (brown-charcoal canvas, cream text, signature amber accent).
    ("Amber Noir", {
        "chrome_bg": "#1a1613", "window_bg": "#1a1613", "surface_bg": "#272018",
        "text": "#f2ead9", "text_muted": "#9d927f", "accent": "#e8943a",
        "border": "#3a3128", "chart_bg": "#221c15", "grid_line": "#3a3128",
        "zebra": "#221c15", "selection": "#3d3327",
        "series": ["#e8943a", "#f3c178", "#d9a35c", "#c87f3c", "#ecdcb8",
                   "#b58a4e", "#a8662c", "#f0b765"],
        "font_family": "Poppins", "heading_font": "Poppins",
    }),
    # Purple-charcoal canvas with pink/violet accents, from the "CRAVEAT"
    # dark-theme admin dashboard reference.
    ("Violet Dusk", {
        "chrome_bg": "#2a2440", "window_bg": "#2a2440", "surface_bg": "#352e52",
        "text": "#f4f2fa", "text_muted": "#a99fc4", "accent": "#9d6bf5",
        "border": "#453d68", "chart_bg": "#2e2848", "grid_line": "#453d68",
        "zebra": "#2e2848", "selection": "#4a3f72",
        "series": ["#9d6bf5", "#ff7fd1", "#c77dff", "#6c63ff", "#4db6e8",
                   "#e0a3ff", "#8a5cf0", "#ff9ec7"],
        "font_family": "Poppins", "heading_font": "Poppins",
    }),
    # Deep teal "glass" canvas with spring-green + cyan accents, from the
    # "DATA CHEF" analytics dashboard reference.
    ("Mint Glass", {
        "chrome_bg": "#0c3431", "window_bg": "#0c3431", "surface_bg": "#18514a",
        "text": "#eafaf4", "text_muted": "#7fb0a3", "accent": "#2fe6a0",
        "border": "#1f6359", "chart_bg": "#134641", "grid_line": "#1f6359",
        "zebra": "#134641", "selection": "#256b60",
        "series": ["#2fe6a0", "#25c2c9", "#7ee06a", "#11b894", "#5ff0c0",
                   "#1f8f86", "#a8e85c", "#34d3b5"],
        "font_family": "Montserrat", "heading_font": "Montserrat",
    }),
    # Near-black canvas with a single chartreuse-lime accent, from the
    # "DWISON" overview dashboard reference.
    ("Lime Noir", {
        "chrome_bg": "#0b0d0b", "window_bg": "#0b0d0b", "surface_bg": "#14181b",
        "text": "#f3f5f4", "text_muted": "#8a928f", "accent": "#bef24d",
        "border": "#262b29", "chart_bg": "#101315", "grid_line": "#262b29",
        "zebra": "#101315", "selection": "#2c322f",
        "series": ["#bef24d", "#8fe04c", "#5dd39e", "#3ac77d", "#d4f06a",
                   "#6fb84a", "#a0e85a", "#2fb56a"],
        "font_family": "Inter", "heading_font": "Inter",
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
