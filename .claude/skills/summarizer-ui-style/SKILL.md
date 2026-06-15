---
name: summarizer-ui-style
description: Use when building or restyling a PyQt5/QGIS plugin GUI (dialogs, dock/standalone windows, toolbars, tables, cards) and you want the "modern analytics" look from the Summarizer plugin — token-driven QSS, light/dark themes, bundled Inter font, and SVG icons. Keywords: QSS, stylesheet, theme, palette, design tokens, dark mode, Inter font, QIcon, card, button variant, themeMode.
---

# Summarizer UI Style

A reusable "modern analytics" design system for PyQt5 / QGIS-plugin GUIs, extracted from the Summarizer plugin. It gives a clean, light-or-dark, Power-BI-flavored look without hardcoding colors anywhere.

## Core principle

**One stylesheet template + one token dictionary.** Never put literal colors/sizes in widget code. Instead:

1. All colors, fonts, radii, and metrics live as **tokens** in a palette dict (light + dark variants).
2. A single `style.qss` uses `${token}` placeholders.
3. At startup you do `Template(qss).safe_substitute(palette_context(mode))` and apply it to the top-level window.
4. Per-widget *variants* are selected with **Qt dynamic properties** (`variant`, `card`, `role`, `themeMode`, `navIcon`), never with per-widget stylesheets.

This means: change a token → the whole app restyles; flip `themeMode` → dark mode; no widget hardcodes a hex value.

## The five pieces

| Piece | Source file | What it does |
|---|---|---|
| Tokens | `palette.py` | `COLORS`, `DARK_COLORS`, `TYPOGRAPHY`, `MISC` dicts + `palette_context(mode)` merges them into a `${...}` substitution map. |
| Stylesheet | `style.qss` | `string.Template` QSS with `${token}` placeholders + property-driven selectors. |
| Fonts | `fonts.py` | Registers bundled **Inter** TTFs via `QFontDatabase.addApplicationFont`; exposes `ui_font_family()` / `ui_font_stack()`. |
| Icons | `resources.py` | `svg_icon(name)` → `QIcon` from `resources/SVG/<name>`; tint helper recolors an SVG to a theme color. |
| Assets | `resources/` | `SVG/` (UI icons), `icons/` (data-source icons), `fonts/Inter/*.ttf`. |

Copyable templates live alongside this skill: **`palette.py`**, **`style.qss`**, **`fonts.py`**, **`resources.py`**. Drop them into a `resources/` + `utils/` layout and adapt the import paths.

## Color tokens

| Token | Light | Dark |
|---|---|---|
| `color_app_bg` | `#FAFAFA` | `#0B1020` |
| `color_surface` | `#FFFFFF` | `#0B1020` |
| `color_border` | `#E2E6EC` | `#334155` |
| `color_text_primary` | `#252B33` | `#F8FAFC` |
| `color_text_secondary` | `#55606D` | `#CBD5E1` |
| `color_primary` (brand) | `#5A3FE6` | `#7C6CFF` |
| `color_primary_hover` | `#4936C8` | `#6A5AE8` |
| `color_secondary` (accent/link) | `#2B7DE9` | `#60A5FA` |
| `color_success` / `warning` / `error` | `#2FB26A` / `#F2994A` / `#EB5757` | `#4ADE80` / `#FDBA74` / `#F87171` |
| `color_table_zebra` / `color_table_selection` | `#F6F8FB` / `#E5E7EB` | `#182230` / `#374151` |

## Typography & metrics

- Font: **Inter** (bundled), stack `"Inter", sans-serif`; mono `"Cascadia Mono", Consolas, monospace`.
- Sizes (px): page title `24`, section title `16`, body `13`, secondary `12`, caption/chip `11–12`, button `13`.
- Weights: regular `400`, medium `500`, semibold `600`.
- Radii: surface/card `12`, button `10`, table `10`, input `8`. Heights: button `36`, input `32`, tab `36`.

## Property-driven variants (the key idea)

Set a Qt dynamic property in code, and `style.qss` styles it — no inline stylesheet. After changing a property at runtime, **re-polish** the widget.

```python
btn.setProperty("variant", "secondary")   # primary (default) | secondary | ghost
frame.setProperty("card", True)            # white surface + border + 12px radius
label.setProperty("role", "title")         # appTitle | title | subtitle | helper | badge
navbtn.setProperty("navIcon", True)        # sidebar icon button
root.setProperty("themeMode", "dark")      # switches the whole subtree to dark tokens

# Re-apply style after a property changes at runtime:
w.style().unpolish(w); w.style().polish(w)
```

Recognized selectors in `style.qss`: `#headerBar`, `#sidebarContainer`, `#ribbonBar`, `#footerBar`, `[card="true"]`, `QPushButton[variant="secondary"|"ghost"]`, `QLabel[role="..."]`, `QToolButton[ribbonButton="true"]`, `[navIcon="true"]`, and a full `[themeMode="dark"]` overlay.

## Applying it

```python
import os
from string import Template
from .palette import palette_context
from .utils.fonts import ensure_ui_fonts_registered, attach_ui_font_enforcer

def apply_theme(window, mode="light"):
    ensure_ui_fonts_registered()                       # register Inter once
    qss_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
    with open(qss_path, "r", encoding="utf-8") as fh:
        qss = Template(fh.read()).safe_substitute(palette_context(mode))
    window.setStyleSheet(qss)
    if mode == "dark":                                 # property overlay drives dark mode
        window.setProperty("themeMode", "dark")
    attach_ui_font_enforcer(window)                    # keep Inter on dynamically-added widgets
```

For icons:

```python
from .utils.resources import svg_icon
btn.setIcon(svg_icon("Refresh.svg"))     # loads resources/SVG/Refresh.svg, empty QIcon if missing
```

## Adopting in a new widget

1. Give the widget an `objectName` (`headerBar`, `ribbonBar`, …) or a property (`card`, `variant`, `role`) — don't call `setStyleSheet` on it.
2. Use `svg_icon("Name.svg")` for any icon; add new SVGs under `resources/SVG/`.
3. Read colors you need in code (e.g. for QPainter charts) from `palette_context(mode)` — never hardcode hex.
4. To support dark mode, set `themeMode` on the root and re-polish.

## Common mistakes

- **Hardcoding hex in widget code or per-widget `setStyleSheet`.** Breaks theming and dark mode. Use a token + property selector.
- **Forgetting to re-polish** after changing a dynamic property at runtime — Qt won't restyle until `unpolish`/`polish`.
- **Forgetting `ensure_ui_fonts_registered()`** before applying QSS → Inter falls back to a system font.
- **Using `${token}` not present in the palette** — `safe_substitute` leaves it literal and Qt silently ignores the rule. Add the token to `palette.py`.
- **QtChart dependency for charts.** Summarizer/this project draw charts with plain `QPainter`; keep that — QtChart is absent from many QGIS builds.
