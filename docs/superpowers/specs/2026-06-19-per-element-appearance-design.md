# Per-element Configure & Tile Appearance — design

**Date:** 2026-06-19
**Status:** Approved (design); implementation plan to follow.

## Problem

Every dashboard tile's **Tile Appearance** editor is identical. `_edit_tile_style`
(`window.py`) opens `AppearanceForm(mode="element")` (`appearance_dialog.py`),
which always shows the same controls regardless of element type:

- Tile background, **Chart background**, Text, Secondary text, Accent
- **Chart series colors**
- Body font, Heading font
- Base font size, Element title size, Indicator value size

This is wrong for most elements:

- A **List**, **Indicator**, **Map**, **Category selector**, **Text**, **Image**
  and **Header** tile have no chart, yet they get "Chart background" and
  "Chart series colors".
- The elements' *real* text roles have no dedicated control. The indicator's
  dynamic **value** is hard-wired to `theme.accent`; the **text** tile's body,
  the **header** title, **table** headers/cells, and the **selector** dropdown
  derive from a few global theme attributes with no per-tile, per-role control.

The Configure ⇄ Appearance split is also muddled: visual settings are scattered
into Configure today — `align`/`heading` (text); `font_family`/`font_size`/
`align`/`logo_*` (header); `value_size`/`icon_*`/`animation` (indicator); `fit`
(image) — mixed in with data binding.

### Root cause

Per-tile appearance is a single **global-shaped `Theme` slice**
(`config["style"]` filtered to a global `OVERRIDE_KEYS`, merged into a `Theme`,
applied via `Theme.tile_qss()`), not a **per-element-type schema**. There is no
notion of an element's distinct text/visual *roles*.

## Decisions (locked with the user)

1. **Full per-role control** — each text/visual role exposes family, size, color,
   weight, italic, and alignment where it makes sense.
2. **Clean split** — Tile Appearance owns *all* visual styling; Configure owns
   *only* data/content. `align`/`heading`/header-fonts/etc. move into Appearance.
3. **Tile size in pixels**, in a "Tile" group at the top of every Appearance panel.
4. **Scope: per-tile Appearance + Configure only.** The global theme / Settings
   hub is left as-is. HTML-export parity for the new per-role keys is a deferred
   follow-up.

## Approach (chosen)

A **declarative style-schema registry**, mirroring the existing `ELEMENT_TYPES`
and `chart_specs` registries. Rejected alternatives: nine hand-built bespoke
forms (heavy duplication, fights the small-files/registry ethos); minimal
cleanup (does not deliver the chosen "full per-role control").

## Architecture

### `elements/style_schema.py` (new, pure / Qt-free, unit-tested)

```
STYLE_SCHEMAS: dict[type_name] -> list[StyleSection]
StyleSection(title, [StyleField, ...])
StyleField(key, label, kind, default=<theme attr name or literal>, **opts)
```

Field **kinds**:

| kind | widget | value |
|---|---|---|
| `color` | swatch button (existing `_ColorButton`) | `#rrggbb` |
| `font` | `QFontComboBox` | family name |
| `size` | `QSpinBox` (px) | int |
| `weight` | combo: Normal/Medium/Semibold/Bold | int (400/500/600/700) |
| `italic` | checkbox | bool |
| `align` | combo or segmented: Left/Center/Right | `left`/`center`/`right` |
| `bool` | checkbox | bool |
| `choice` | combo (opts: `[(label, data), ...]`) | data |
| `palette` | `_PaletteEditor` (existing) | list[str] |
| `tile_size` | width+height px spinners | **geometry, not style** (see below) |

Each field declares a **default source**: a `Theme` attribute name (so the form
seeds from the *effective* theme) or a literal. A shared `tile_section()` helper
produces the generic Tile section reused by every type. Pure helpers:
`fields_for(type_name)`, `default_for(field, theme)`, `all_style_keys(type_name)`.

### `tile_style_form.py` → `TileStyleForm` (new)

A schema-driven `QWidget` replacing `AppearanceForm(mode="element")` for the
inspector. Built dynamically from `STYLE_SCHEMAS[element.type_name]` into
**collapsible sections** (Tile → Title → element-specific). Behavior:

- Emits `changed` on every edit so the inspector previews live (unchanged
  inspector commit model).
- Seeds each control from the **effective theme** value (global theme merged with
  the tile's current override) so controls show the real current appearance.
- Returns a **sparse override dict**: only fields whose value differs from the
  seed are written, so a tile keeps tracking the global theme for everything the
  user did not touch. (Today's form bakes the whole theme into the override.)
- Keeps a **"Clear all overrides"** button (drops `config["style"]` → tile
  follows the global theme) and a per-section **reset** affordance.
- The `tile_size` field reads `element._grid_tile.grid_rect()` and writes via
  `GridTile.set_size_px(w, h)`; it is **not** part of the override dict.

The legacy `AppearanceForm`/`AppearanceDialog` remain **only** for global-mode
Settings (Themes page) and are not changed.

### `config["style"]` — unchanged home, extended contents

`config["style"]` continues to hold all visual overrides and stays the only
persisted appearance state on a tile. It now carries:

- **Theme-shaped keys** (e.g. `surface_bg`, `border`) consumed by `tile_qss()`
  for the *baseline* tile look (background, border, base font). Mechanism
  unchanged — `Theme.merged_with` still copies these via `OVERRIDE_KEYS`.
- **New element-specific keys** (e.g. `value_color`, `value_weight`,
  `table_header_bg`, `text_align`) read **directly** by each element's
  `_restyle()`. `merged_with` ignores them harmlessly (it only copies
  `OVERRIDE_KEYS`).

All values stay JSON-serializable so persistence is automatic.

### Base helpers (`elements/base.py`)

- `style_get(key, default)` — read a value from `config["style"]`.
- `apply_text_role(label, prefix, defaults)` — resolve
  `{prefix}_color/_font/_size/_weight/_italic/_align` (falling back to the
  effective theme defaults) and apply one inline stylesheet + alignment to a
  `QLabel`. Keeps every element's role styling DRY.
- Base `apply_theme()` additionally applies per-tile **title** styling to
  `#elementTitle` from the `title_*` role (defaults = theme heading family /
  `title_size` / text color / weight 600), so titles honor per-tile overrides.
  Defaults reproduce today's look exactly when no override is set.

### `GridTile.set_size_px(w, h)` (`dashboard_canvas.py`)

Generalizes the existing `set_height_px`:

- **Height** keeps the existing accordion push (tiles below shift by the delta).
- **Width** is clamped to `[SNAP, region_width]`; if the new width overlaps
  another tile, the width change reverts (origin/height preserved).
- Emits `geometryCommitted`; Cancel in the inspector restores the snapshot size.

`set_height_px` becomes a thin wrapper (`set_size_px(self.w_px, h)` preserving
its accordion behavior) so the header's prior call contract is preserved.

## Per-element appearance schemas

Generic **Tile** section on every element: **Tile size** (w/h px), **Tile
background** (hidden for full-bleed map/image), **Tile border** color.

| Element | Sections (besides Tile) |
|---|---|
| **indicator** | **Value** (color·font·size·weight·italic), **Top label** (color·font·size·weight·italic), **Reference/trend** (color·font·size·weight·italic + trend up/down colors), **Icon** (size·position), **Value animation** (type·duration), **Title** |
| **chart** | **Plot** (chart background·series palette·axis/grid line color·axis-label color·font·size·show value labels·max categories), **Title** |
| **list** | **Table** (header bg·header text·font·size·weight; row text·font·size; zebra·gridline·selected-row color; rows shown), **Title** |
| **pivot** | **Table** (as list) + **Totals** (color·weight), **Title** |
| **map** | **Border** (color·width), **Identify popup** (background·text·accent). No chart bg/series. |
| **category_selector** | **Dropdown** (control bg·text·font·size·border·accent), **Title** |
| **text** | **Text** (font·size·color·weight·italic·alignment) |
| **image** | **Image** (fit: contain/stretch·background behind image·alignment), **Border** |
| **header** | **Title** (font·size·color·weight·italic·alignment), **Logo** (size·position). Banner height = generic Tile height. |

No element shows a control it cannot use.

## Clean split (Configure ⇄ Appearance)

Moved **out of Configure into Appearance** (and read via `style_get`):

- **text**: `align`, `heading`
- **header**: `font_family`, `font_size`, `align`, `logo_slot`, `logo_size`
- **indicator**: `value_size`, `icon_size`, `icon_position`, `animation`,
  `animation_duration_ms`
- **image**: `fit`
- display caps: `max_rows`, `max_cols`, `max_categories`

Configure **keeps** (data/content): layer, fields, expressions, prefix / suffix /
decimals / no-data text, title text, file paths (image/icon/logo), text content.

`ElementConfigForm._rebuild` / `managed_keys` drop the moved keys.

### Migration

A pure helper (`elements/style_migrate.py → migrate_element_style(config, type)`)
relocates legacy top-level visual keys into `config["style"]` and maps
`heading=true` → text bold + large size. Applied when an element is constructed /
loaded so existing `.qgz` and `.qdash` dashboards keep working. Idempotent.

## Element `_restyle()` work

- Extend existing: `indicator`, `chart`, `text`, `header`.
- Add `_restyle()`: `list`, `pivot`, `category_selector`, `image`, `map` —
  apply role styles via inline stylesheets (tables, combo, borders, popup).
- `chart`: thread the new keys (axis/label color·font·size, value labels) into
  the painter via the existing `set_theme` plus a small `set_style(dict)`;
  painters fall back to theme values when a key is absent.
- Base: per-tile title styling (above).

## Testing & registration

- `test/test_style_schema.py` (pure): every `type_name` in `ELEMENT_TYPES` has a
  schema; every field has a resolvable default; no field key collisions; the
  generic Tile section is present.
- `test/test_style_migrate.py` (pure): legacy top-level keys move into `style`;
  `heading` maps correctly; idempotent; unknown keys untouched.
- Register `style_schema.py`, `tile_style_form.py`, `style_migrate.py` in **both**
  `pb_tool.cfg` (`python_files`) and `Makefile` (`PY_FILES`/`SOURCES`).
- Syntax-check all touched modules via `py_compile`.

## Known limitation (deliberate)

Per the chosen scope, the **HTML export** continues to mirror the existing
theme-override keys but does **not** reproduce the new per-role keys initially.
Export parity (porting the role keys into `export/assets/runtime.js` /
`export/theme_css.py`) is a deferred follow-up.

## Out of scope

- Global theme / Settings hub changes.
- Free-form overlap / z-ordering (unchanged).
- HTML-export parity for new per-role keys (deferred follow-up, above).
