# Header (brand banner) element — design

Date: 2026-06-16

## Summary

Add a new `header` element type to the Add-element dialog: a branded banner that
**docks to one edge of a page** (top / bottom / left / right) and lives *outside*
the tile grid, with the free-form grid filling the remaining space. The header
carries a styled title (custom font family / size / alignment chosen from the
installed QGIS/Qt fonts) and a single logo image placed in an anchored slot. A
header is **per-page by default** but can be promoted to **show on every page**
via a checkbox. It is the brand chrome of the dashboard and takes no part in
cross-filtering.

The header is reproduced in the interactive HTML export as static brand chrome.

## Decisions (from brainstorming)

- **Placement:** docked banner outside the grid (not a grid tile).
- **Scope:** per-page or global, chosen by a "Show on all pages" checkbox.
- **Precedence:** a per-page header **overrides** the global header on that page;
  every other page shows the global header.
- **Inner content:** a single logo image in an anchored slot (left / right /
  above / below the title) — no free-drag positioning.
- **Background:** theme-driven only (surface + soft hairline border, like every
  tile). No separate brand background colour.
- **Export:** rendered in the single-file HTML export (static).

## Non-goals

- No free-pixel dragging of content inside the banner.
- No rotated/vertical text for left/right anchored banners — text stays
  horizontal.
- No cross-filtering, no data binding (the header is layerless).
- The banner does not zoom or pan with the grid (it is fixed brand chrome).

## Architecture

Read alongside: `elements/base.py`, `elements/image_element.py`,
`add_element_dialog.py`, `page_view.py`, `window.py`, `export/serialize.py`,
`export/html_export.py`, `export/assets/runtime.{js,css}`.

### 1. The element — `elements/header.py`

`HeaderElement(DashboardElement)`:

- `type_name = "header"`, `is_filter_source = False`, `accepts_filter = False`.
- Reuses the base for identity (`id`), config, theme (`effective_theme`,
  `apply_theme`), and `to_dict` persistence.
- Hides the base title/description chrome and builds its own banner body: a
  horizontal/vertical arrangement of the logo (an anchored slot) and the title
  `QLabel`, themed from `effective_theme()`.
- `refresh()` lays out logo + title from `config`; `_restyle()` applies font /
  colours from the theme. Re-themes automatically on `themeChanged` (base wires
  this).
- Logo loading reuses the Image element's approach (QPixmap; SVG via
  `QSvgRenderer` when available) — extract a tiny shared helper if it avoids
  duplication, otherwise mirror the small loader.
- Editing affordances: double-click → Configure; right-click → a small context
  menu (`Configure…` / `Remove`). Because the header is **not** wrapped in a
  `GridTile`, it emits its own `configureRequested` / `removeRequested` signals
  that `window.py` wires.

Config keys:

| key | meaning | default |
|---|---|---|
| `title` | banner text | "Dashboard" |
| `font_family` | font family (from installed fonts) | theme font family |
| `font_size` | title size in px | 22 |
| `align` | `left` / `center` / `right` (title text) | `left` |
| `logo_path` | image file path (reference, not embedded) | "" |
| `logo_slot` | `left` / `right` / `above` / `below` the title | `left` |
| `logo_size` | logo box size in px | 40 |
| `anchor` | docked edge: `top` / `bottom` / `left` / `right` | `top` |
| `thickness` | banner size in px (height if top/bottom, width if left/right) | 80 |

`scope` (per-page vs global) is **not** stored on the element config — it is
tracked by the window's persistence layer (see §4).

### 2. Pure layout helper — `elements/header_layout.py`

Qt-free, unit-tested:

- `box_direction(anchor)` → `("h"|"v", reversed: bool)` mapping each anchor to
  how the page container stacks `[banner, scroll]`:
  - `top` → vertical, banner first
  - `bottom` → vertical, banner last
  - `left` → horizontal, banner first
  - `right` → horizontal, banner last
- `inner_box_direction(logo_slot)` → how logo + title stack inside the banner.
- `resolve_header(page_header, global_header)` → the config dict to render for a
  page (page header wins; else global; else `None`).

### 3. Hosting the banner — `page_view.py` refactor

`PageView` is currently a `QScrollArea`. Refactor so it can host a docked banner
*around* the scrolling canvas without changing its public API:

- Introduce a private `_CanvasScroll(QScrollArea)` that holds the **existing**
  behavior verbatim: `setWidget(canvas)`, `setWidgetResizable(False)`, zoom
  factor + `set_zoom`/`zoom_in`/`zoom_out`/`reset_zoom`, middle-mouse pan, and
  `resizeEvent` → `canvas.sync_size()`.
- `PageView` becomes a thin `QWidget` container with a `QBoxLayout` holding the
  banner (optional) + one `_CanvasScroll`. It **delegates** the existing public
  API (`canvas`, `zoom`, `set_zoom`, `zoom_in`, `zoom_out`, `reset_zoom`) to the
  inner scroll so `window.py` and tests are unchanged.
- New method `set_header(element_or_None)`: removes any current banner widget,
  and if given inserts it at the correct end of a box laid out per
  `box_direction(anchor)`. The banner's fixed dimension is `thickness`
  (`setFixedHeight` for top/bottom, `setFixedWidth` for left/right).

The banner is outside the scroll area, so it stays put while the grid
zooms/pans. The grid resolution dialog is unaffected (the grid lives in the
canvas, still inside the scroll area).

### 4. Scope + persistence — `window.py`

State:

- `self._global_header` — a header config dict or `None`.
- `DashboardPage.header_config` — a per-page header config dict or `None`.

Adding a header:

- `add_element` branches on `type_name == "header"`: it does **not** create a
  canvas tile. From the dialog's "Show on all pages" checkbox:
  - checked → set `self._global_header = config`.
  - unchecked → set the current page's `header_config = config`.
- After any change call `_refresh_all_headers()`: for each page, build/update its
  `PageView` banner from `resolve_header(page.header_config, self._global_header)`
  (creating one `HeaderElement` instance per page, since a widget can live in
  only one layout). `None` → `set_header(None)`.

Configuring a header:

- Reopen `AddElementDialog` in edit mode on the page's resolved `HeaderElement`.
- Toggling "Show on all pages" moves the header global↔per-page: when promoting
  to global, clear the originating page's `header_config`; when demoting, set the
  current page's `header_config` and clear `self._global_header`.

Removing a header:

- From the banner's context menu: clear whichever slot supplied it (page first,
  else global) and `_refresh_all_headers()`.

Persistence (blob → **v4**):

- `save_to_project`: add top-level `"header": self._global_header` (omit when
  `None`) and per page `"header": page.header_config` (omit when `None`).
- `migrate_layout`: bump `version` to 4; carry `raw.get("header")` to
  `out["header"]` and each `page.get("header")` to the page dict. v1–v3 blobs
  simply have no header (→ `None`), so older dashboards load unchanged.
- `load_from_project`: read `data.get("header")` → `self._global_header`; read
  each `p.get("header")` → `page.header_config`; then `_refresh_all_headers()`.
- `clear_all`: reset `self._global_header = None`.

### 5. The Add-element dialog — `add_element_dialog.py`

- Add `"header"` to `_LAYERLESS_TYPES` (hides the Layer row).
- Add a `header` branch in `_rebuild` building rows: Title, **Font**
  (`QFontComboBox`), Font size (`_spin`), Alignment (combo), Logo file
  (`_PathPicker`), Logo position (combo), Logo size (`_spin`), Anchor edge
  (combo), Banner thickness (`_spin`), and a **"Show on all pages"** checkbox.
- Add `QFontComboBox` handling to `_load_values` (`setCurrentFont`),
  `result_config` (`currentFont().family()`), and `managed_keys`.
- The "Show on all pages" checkbox value is read by `window.py` to decide scope;
  it is not written into the element config.

### 6. HTML export — `export/`

- `serialize.py` (pure): include the resolved header per page in the export
  model (`resolve_header`), carrying title / font / size / align / logo slot /
  logo size / anchor / thickness, plus a placeholder for the embedded logo URI.
  Unit-tested in `test/test_html_export.py`.
- `html_export.py` (QGIS-touching): base64-embed the logo file via the existing
  `image_data_uri` helper and attach it to each page's serialized header.
- `export/assets/runtime.css` + `runtime.js`: render a docked banner per page
  using the existing `:root` theme CSS variables plus the header's font / size /
  alignment / anchor / thickness. Static — no interactivity.

### Registration & packaging

- Register `HeaderElement` in `elements/__init__.py` (`ELEMENT_TYPES`) and add a
  label to `ELEMENT_LABELS` (e.g. `"header": "Header (brand banner)"`).
- `elements/header.py` and `elements/header_layout.py` ship automatically — the
  `elements/` package is already an `extra_dir` in `pb_tool.cfg` / `Makefile`,
  so no packaging-config change is needed for files added inside it.

## Testing

- `test/test_header_layout.py` (pure, no QGIS): `box_direction`,
  `inner_box_direction`, and `resolve_header` precedence (page over global; both
  absent → `None`).
- Extend `test/test_html_export.py`: a dashboard with a global header and a
  per-page override produces the correct resolved header in the export model,
  with the logo embedded as a data URI.
- `python -m py_compile` over every touched module.
- `node --check qgis_dashboard/export/assets/runtime.js`.

## Risks / edge cases

- **PageView refactor** is the riskiest change; the `_CanvasScroll` split must
  preserve zoom/pan/`sync_size` exactly. Mitigated by moving the logic verbatim
  and keeping the public API stable (covered by `test/test_multipage.py`).
- **Missing logo file**: show the title alone (mirror the Image element's
  not-found handling — no crash).
- **Promote/demote scope** must not leave a header in both the global and the
  originating page slot — the move clears the source slot.
- **Left/right thickness** could crowd the grid on narrow windows; the grid
  simply gets less room (acceptable; user controls `thickness`).
```
