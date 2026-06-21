# User-supplied custom fonts (upload, install, embed)

**Date:** 2026-06-21
**Status:** Approved — ready for implementation planning

## Problem

Today the dashboard theme can only use fonts that QGIS/Qt already knows about:
the bundled **Inter** family (`fonts.py`) plus whatever is installed on the
machine. A user who wants a specific brand typeface has no way to bring their
own `.ttf`/`.otf` into the plugin.

We want the user to **upload their own font file** from *Settings → Themes*,
have it:

1. **persist on their PC** so it is available in *every* QGIS project and
   dashboard in the future (not tied to the active project), and
2. **travel with the dashboard** so a shared `.qdash` file and an exported
   HTML dashboard both render with that font on any machine.

## Why this is the right approach (background)

QGIS is a Qt desktop app — there is no browser-style `@font-face` streaming.
Qt can only render a font that physically exists in its `QFontDatabase`. The
plugin already proves the correct pattern in `fonts.py`:
`QFontDatabase.addApplicationFont(path)` registers a font binary at runtime,
after which it appears throughout the Qt application — including, for free, in
the existing `QFontComboBox` body/heading pickers in `AppearanceForm`.

`addApplicationFont` registrations do **not** persist across sessions, so the
design has two cooperating layers:

| Layer | Solves | Mechanism |
|---|---|---|
| **Local install** (profile folder + re-register on load) | "Same PC, every project/dashboard, forever" | copy file → per-profile folder; `addApplicationFont` each load |
| **Embed in `.qdash` / HTML** | "Other PCs / sharing the file" | base64 the bytes into the export; `.qdash` auto-installs on open |

The layers compose: opening a shared `.qdash` that carries an embedded font
also installs it into the local profile, so it works thereafter.

**Decision (confirmed):** the `.qgz` project file stays **names-only** (it keeps
storing just the font *name* in the theme blob). On the same PC the local
profile install covers it; embedding bytes into every project save would bloat
the project XML. Cross-PC `.qgz` sharing relies on the `.qdash` (which embeds)
or on re-adding the font.

## Non-goals (YAGNI)

- **No woff/woff2** support or conversion — `.ttf`/`.otf` only.
- **No OS-level system install** and **no `QgsFontManager`** route. Plugin-managed
  session registration already makes a font available across all projects and
  dashboards on the PC whenever the plugin is enabled (which it is, when in use).
- **No rewrite of saved font names** when a referenced font is removed — the
  theme name stays and simply falls back to the font stack.
- **No `.qgz` byte embedding** (see decision above).

## Architecture

### 1. Local install + registration — `user_fonts.py` (new, QGIS-touching)

A new module mirroring the resilient, idempotent style of `fonts.py` (never
raises into the UI; failures degrade to the fallback font stack).

```
fonts_dir() -> str
    QgsApplication.qgisSettingsDirPath()/qgis_dashboards/fonts/
    Created on demand. Per-profile; independent of any project; survives
    plugin updates.

register_all() -> list[str]
    Scan fonts_dir(), addApplicationFont each *.ttf/*.otf, build an in-memory
    registry {family -> path} (and {family -> font_id} for removal). Returns
    the family names found. Idempotent (skips already-registered paths).

add_font(src_path) -> list[str]
    Validate src is a readable .ttf/.otf; copy into fonts_dir() (dedupe the
    destination filename); register it; update the registry; return the new
    families. On any failure, return [] (caller shows a message bar).

remove_font(family) -> bool
    removeApplicationFont(font_id) for that family and delete its file from
    fonts_dir(). Returns success.

custom_families() -> list[str]
    Sorted family names currently installed as user fonts.

path_for_family(family) -> str | None
    The on-disk file path for an installed custom family (for embedding).
```

**Registration call site:** `DashboardWindow.__init__` already calls
`ensure_fonts_registered()` (window.py:154) before any QSS/font use. Add
`user_fonts.register_all()` immediately after it, so user fonts are in the Qt
font DB before the first `QFontComboBox` or stylesheet is built. This runs once
per window creation, regardless of project, so all dashboards see the fonts.

### 2. UI — Settings → Themes

In `settings_dialog.py`, `_themes_page()` gains a **"Custom fonts"** block,
placed above the embedded `AppearanceForm`:

- a one-line hint ("Add your own .ttf/.otf — available in every dashboard on
  this computer, and embedded into exported and shared dashboards"),
- an **"Add font…"** `QPushButton` opening `QFileDialog.getOpenFileName` with
  filter `Fonts (*.ttf *.otf)`,
- a `QListWidget` of installed custom families, each row with a Remove
  affordance (a small "Remove" button per row, or a selected-row Remove
  button — implementer's choice, styled with the existing CHROME hairlines).

Flow:
- **Add** → `user_fonts.add_font(path)`; on success, refresh the list and call
  the appearance form's `reload_fonts()`. On failure, `iface.messageBar()`
  warning.
- **Remove** → confirm, `user_fonts.remove_font(family)`, refresh list and
  call `reload_fonts()`.

`QFontComboBox` does **not** repopulate when the Qt font DB changes, so
`AppearanceForm` gains:

```
reload_fonts()
    Rebuild/replace the body and heading QFontComboBox widgets in place,
    preserving the current selection and signal wiring, so a freshly added
    font appears in the pickers without reopening Settings.
```

The font management UI lives only in the global *Themes* page (it is a global
concern); the per-tile (`mode="element"`) appearance form is unaffected beyond
inheriting `reload_fonts()`.

### 3. `.qdash` embedding (cross-PC portability)

`_build_layout_dict()` (window.py:1092) stays names-only — it is shared by the
`.qgz` save. Only the **`.qdash` writer** augments the dict.

- **Pure helper** `referenced_families(theme_dict, tile_style_dicts) -> set[str]`
  (Qt-free, unit-tested), placed in `export/theme_css.py` alongside
  `font_face_css` (both are pure and font/export-related; imported by both
  `export/html_export.py` and `window.py`'s `.qdash` save path): collects
  `font_family` + `heading_font` from the global theme dict and from every tile
  `config["style"]` dict. Returns the name set (empty strings dropped).
- The window adds a method that produces the embed blob: intersect
  `referenced_families(...)` with `user_fonts.custom_families()`, then for each
  custom family read its file and emit
  `{family, filename, format, data}` where `format` is `"truetype"` for `.ttf`
  / `"opentype"` for `.otf` and `data` is standard base64 of the file bytes.
- The `.qdash` save path sets `data["fonts"] = <blob>` on the dict returned by
  `_build_layout_dict()` before handing it to `project_io.write_layout_file`.
  (The `.qgz` `save_to_project` keeps using the bare dict — no `fonts` key.)

**Load (shared by `.qgz` and `.qdash`):** `_apply_layout_dict(data)` installs
`data.get("fonts")` *before* `self.bus.set_theme(...)`:

- for each entry, if a file of that `filename` is not already in `fonts_dir()`,
  write the decoded bytes there, then `user_fonts.register_all()` (or register
  the single new file). This both renders the loaded dashboard and installs the
  font into the local profile. A `.qgz` has no `fonts` key, so this is a no-op
  there.

`migrate_layout` must **carry the `fonts` key through untouched** for v3 blobs
(and ignore it for v1/v2 upgrades — they never have it). Verify and add a
passthrough if needed.

### 4. HTML export embedding

- `export/theme_css.py` (pure) gains:

```
font_face_css(entries) -> str
    entries: [{family, format, data_uri}]  (or {family, format, base64})
    Emits one @font-face per entry:
      @font-face { font-family:'<family>';
                   src:url(data:font/ttf;base64,<...>) format('truetype'); }
    Returns "" for an empty list.
```

- `export/html_export.py` (QGIS-touching) collects the referenced custom
  families (same `referenced_families` helper, intersected with
  `user_fonts.custom_families()`), base64-reads each file from `fonts_dir()`,
  builds the `font_face_css(...)` string, and passes it to `build_html`.
- `export/html_builder.py` `build_html(...)` gains a `font_faces=""` parameter,
  inlined into the `<style>` block **before** `css_vars` so the families are
  defined when `:root { --font-family … }` references them.

Purity boundary preserved: I/O and QGIS access stay in `html_export.py`; string
assembly stays in the pure `html_builder.py` / `theme_css.py` (matching the
current split and `test/test_html_export.py`).

## Data shapes

`.qdash` top-level addition (absent in `.qgz`):

```json
"fonts": [
  {
    "family": "Brand Sans",
    "filename": "BrandSans-Regular.ttf",
    "format": "truetype",
    "data": "<base64 of the file bytes>"
  }
]
```

Only families actually referenced by the theme or a tile override and present
in the local custom-font registry are included.

## Edge cases & resilience

- **Invalid / unreadable font file on add** → `add_font` returns `[]`, UI shows
  a message-bar warning; nothing is copied or registered.
- **Duplicate filename on add** → dedupe the destination name (e.g. append a
  numeric suffix) so two different uploads with the same base name coexist.
- **Embedded font already installed on open** → skip rewriting the file; still
  ensure it is registered.
- **Removing a font a theme still uses** → allowed; the saved name remains and
  rendering falls back through the existing font stack. (No name rewrite.)
- **Registration failure for any reason** → degrade to the fallback stack; never
  block window creation or load (same contract as `fonts.py`).
- **`removeApplicationFont` / file delete failure** → report via message bar;
  leave state consistent (don't drop the registry entry if the file is locked).

## Packaging

- Register `user_fonts.py` (and any new pure helper file) in **both**
  `pb_tool.cfg` (`python_files`) and `Makefile` (`PY_FILES` / `SOURCES`).
- The runtime `fonts/` folder lives under the QGIS profile, so **nothing new is
  shipped** in the packaged zip.

## Testing

- **Pure unit tests** (no QGIS), extending `test/test_html_export.py` or a new
  file:
  - `referenced_families(theme_dict, tile_style_dicts)` — picks up global +
    per-tile families, drops empties, dedupes.
  - `font_face_css(entries)` — correct `@font-face` text, `format()` per type,
    `""` for empty input.
  - base64 round-trip of font bytes (encode → decode equals original) and the
    `.ttf`→`truetype` / `.otf`→`opentype` mapping if extracted as a pure helper.
- **QGIS-touching** (`user_fonts` add/remove/register, load-time install) are
  covered by manual install testing; keep any Qt-free sub-helpers
  unit-tested where feasible.

## Affected files

| File | Change |
|---|---|
| `user_fonts.py` | **new** — install/register/remove/embed-source for user fonts |
| `window.py` | call `user_fonts.register_all()` at startup; `.qdash` save adds `fonts` blob; `_apply_layout_dict` installs `fonts`; `referenced_families` usage |
| `settings_dialog.py` | "Custom fonts" block in `_themes_page` (add/remove + list) |
| `appearance_dialog.py` | `AppearanceForm.reload_fonts()` |
| `export/theme_css.py` | pure `font_face_css(entries)` + pure `referenced_families` helper |
| `export/html_export.py` | collect + base64 custom fonts; pass `font_faces` |
| `export/html_builder.py` | `build_html(..., font_faces="")`, inline before css_vars |
| `pb_tool.cfg`, `Makefile` | register new module(s) |
| `test/test_html_export.py` (or new) | pure tests for `referenced_families`, `font_face_css` |
