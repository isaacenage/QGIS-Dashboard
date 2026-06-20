# Filter & Legend widgets + map cross-filter fixes — design

Date: 2026-06-21
Status: approved (pending written-spec review)

## Background

Cross-filter connections between dashboard tiles were partly broken, and the
user wants two new source widgets plus a richer map source. This spec covers
one already-shipped bug fix (recorded for completeness) and three new pieces of
work.

The plugin's cross-filter model is *source → action → target*, wired explicitly
per page on the `DashboardBus`. A source calls `bus.set_filter(self.id, expr)`;
a target re-queries with `bus.combined_filter_for(self.id)` (the AND of every
*connected* source's expression). Two hard rules constrain the design:

- **Never mutate shared project layers** to filter (no `setSubsetString` on a
  project layer) — filtering is per-element via `QgsFeatureRequest`.
- **New element types** register in `elements/__init__.py`, get an `el_<type>`
  glyph in `icons.ICONS`, Configure rows in `add_element_dialog.py`, and ship
  via the `elements/` extra-dir (no per-file packaging entry needed).

## Work item 0 — bug fixes (DONE, recorded here)

Two related defects made aggregate/spatial filters silently no-op:

1. **Indicator never reacted to any connection.** It computes its value with a
   QGIS aggregate expression (`sum("x")`, `count(1)`) via `base.evaluate()`, and
   QGIS aggregates ignore the request filter. Fixed by `elements/aggregate_filter.py`
   (`inject_filter`) which splices the live combined filter into each aggregate
   call as `filter:=(<expr>)`; wired into `base.evaluate()`. Unit-tested in
   `test/test_aggregate_filter.py`.

2. **Map extent filter reached the indicator but not chart/list/pivot.** The
   extent expression references `@layer`/`layer_property(@layer,'crs')`. The
   indicator's `evaluate()` builds a scoped `QgsExpressionContext` so those
   resolve; `iter_features()` set the filter expression with **no** context, so
   `layer_property` was NULL → `intersects` NULL → `coalesce(…, true)` passed
   every feature. Fixed by attaching the same scoped context to the
   `iter_features()` request in `base.py`.

Both are committed and compile-clean. End-to-end confirmation requires a running
QGIS (cannot launch from CI shell).

## Work item 1 — Filter widget (definition-query source)

A new presentational-input tile that builds an ArcGIS-style *definition query*
across one or more category columns and pushes it as a single filter.

- **File:** `elements/filter_element.py` → `FilterElement`.
- **Flags:** `type_name = "filter"`, `is_filter_source = True`,
  `accepts_filter = False` (a pure source — it never narrows its own value lists,
  so the user can always re-pick).
- **Config:** `layer_id`, `fields: list[str]` (the category columns).
- **UI:** one row per configured field — `QLabel(field)` + a `QComboBox`
  pre-populated with `(All)` then the sorted unique values of that field
  (`layer.uniqueValues(idx)`, computed WITHOUT the dashboard filter, mirroring
  `category_selector.refresh`). Rows stacked in the body.
- **Behavior:** on any combo change, build the expression as the AND of
  `"field" = 'value'` for every field whose combo is not `(All)`; if none are
  set, push `None` (clear). Single value per column, AND-combined across columns.
  Non-cascading for v1 (each column always lists all its unique values).
- **Interactivity:** `set_interactive` enables/disables the combos (Build mode
  disables, like `category_selector`). `_on_filters_cleared` resets every combo
  to `(All)`.
- **Theming:** reuse the combo role styling from `category_selector._restyle`.

Wired (Connections editor) to the map and/or any data tile. Against the map it
yields a `subsetString`-compatible expression (AND of equalities), so the map
can render the filtered subset (work item 3).

## Work item 2 — Legend widget (symbology-driven source)

A tile that mirrors the bound layer's real map legend; toggling classes filters.

- **File:** `elements/legend_element.py` → `LegendElement`. Pure expression
  helper: `elements/legend_model.py`.
- **Flags:** `type_name = "legend"`, `is_filter_source = True`,
  `accepts_filter = False`.
- **Config:** `layer_id`.
- **Renderer reading (QGIS-side, in the element):** inspect the layer's renderer.
  - `QgsCategorizedSymbolRenderer`: `classAttribute()` + each category's
    `value()`, `label()`, `symbol()`.
  - `QgsGraduatedSymbolRenderer`: `classAttribute()` + each range's
    `lowerValue()/upperValue()`, `label()`, `symbol()`.
  - Any other renderer (single symbol, rule-based): show a single non-toggle row
    ("No categories to filter") — the widget is inert but valid.
- **UI:** a checkable `QListWidget`; each row = symbol swatch
  (`QgsSymbolLayerUtils.symbolPreviewPixmap`) + class label, checked by default.
  Unchecking removes that class from the filter.
- **Behavior:** push the filter built from the *checked* classes via
  `legend_model`:
  - categorized → `categories_to_expression(field, values)` →
    `"field" IN ('a','b')` (numeric values unquoted; NULL → `"field" IS NULL`
    OR-ed in; all checked → `None`).
  - graduated → `ranges_to_expression(field, ranges)` →
    `(("f" >= lo AND "f" <= hi) OR (…))` (all checked → `None`).
- **`legend_model.py` (pure, unit-tested):** `categories_to_expression`,
  `ranges_to_expression`, plus a `_literal(value)` quoting helper
  (string vs numeric vs NULL). No QGIS imports → testable on plain values, like
  `pivot_engine`/`chart_data`.

## Work item 3 — Map element changes

### 3a. Source filter mode

Replace the bool `extent_filter_enabled` with `source_filter_mode` ∈
`{"off", "extent", "selection", "relay"}` (default `"extent"`).

- **Migration** (in `MapElement.__init__`/reconfigure read path): legacy
  `extent_filter_enabled == False` → `"off"`; `True`/absent → `"extent"`. Keep
  reading the old key if present so older `.qgz`/`.qdash` blobs still load; write
  only the new key going forward.
- `extent` — current behavior (push the visible-frame spatial expression).
- `selection` — push `$id IN (<selected fids>)` from the bound layer's
  `selectedFeatureIds()`; subscribe to the layer's `selectionChanged` while in
  this mode (debounced through the existing `_filter_timer`). Empty selection →
  clear.
- `relay` — re-push the map's own incoming combined filter
  (`bus.combined_filter_for(self.id)`) under the map's id to its targets, so a
  Filter/Legend wired only to the map propagates onward. Guarded by a
  `_last_relay_expr` check (only `set_filter` when it actually changes) to avoid
  a `filtersChanged` → recompute → re-push loop.
- `off` — never push (pause without unwiring).

The push dispatch (`_push_extent_filter`, renamed/generalized to
`_push_source_filter`) selects strategy by mode; all modes remain gated on
`isVisible()` and Use mode.

### 3b. Map as a visual target (the new machinery)

So Filter/Legend visibly hide non-matching features on the map:

- Flip `accepts_filter = True`. On `filtersChanged`, compute
  `incoming = bus.combined_filter_for(self.id)`.
- If `incoming` is non-empty, build/refresh a **clone** of the bound layer
  (`layer.clone()` — an independent layer over the same provider) and call
  `clone.setSubsetString(incoming)`. If it returns `True`, render the clone in
  place of the bound layer in the canvas layer list; if `False` (e.g. a spatial
  expr from another map), discard the clone and mirror unfiltered.
- The canvas layer list is otherwise still `src.layers()` with only the bound
  layer swapped for the clone. Rebuilt on `filtersChanged`/`layersChanged`;
  the clone is held in `self._filtered_clone` and released in `teardown`
  (and replaced rather than leaked on each rebuild).
- Loop safety: in `relay` mode the map both subsets (target) and re-pushes
  (source); the `_last_relay_expr` guard plus subsetting being idempotent
  prevents runaway `filtersChanged` storms.

Note the asymmetry this introduces: the map ignores the dashboard filter for its
*identify*/*fly-to* helpers (unchanged) but honors it for *rendering*. That is
intentional and documented in the module docstring.

## Work item 4 — registry, dialog, icons, persistence

- `elements/__init__.py`: import + register `FilterElement`, `LegendElement` in
  `ELEMENT_TYPES`; add `ELEMENT_LABELS["filter"] = "Filter"`,
  `ELEMENT_LABELS["legend"] = "Legend"`.
- `icons.py`: add `el_filter` (a funnel glyph) and `el_legend` (stacked
  swatch+line rows) stroke icons so the Add-element picker shows them.
- `add_element_dialog.py`:
  - `filter` → a fields multi-select (comma-separated `QLineEdit` of field names,
    consistent with the `list` element's "Fields (comma sep)" row, OR a small
    multi-check field list — start with comma-sep for parity/simplicity).
  - `legend` → just the layer row (categories come from the renderer); no extra
    rows.
  - `map` → replace the `extent_filter_enabled` checkbox with a
    `source_filter_mode` `QComboBox` (`Off / Visible extent / Selected features /
    Relay active filter`).
- Persistence is automatic via `base.to_dict()`; values are JSON-serializable
  (lists of strings, mode string). No new save-format version needed.

## Testing

- **Pure, no-QGIS (run directly, like `test_chart_data.py`):**
  - `test/test_legend_model.py` — `categories_to_expression` (string/numeric/
    NULL/all-checked), `ranges_to_expression` (single/multi/all-checked).
  - `test/test_aggregate_filter.py` — already added (item 0).
- **Compile checks** for all touched/new modules via `py_compile`.
- **Manual QGIS verification** (documented, can't run headless here): Filter
  definition-query subsets the wired map; Legend class toggles subset the map;
  map `selection`/`relay`/`extent` modes each drive a wired chart + indicator.

## Out of scope (follow-ups)

- **HTML export** support for `filter`/`legend` (the export uses a separate
  client-side index-set model in `runtime.js`; the new widgets are desktop-only
  for now and degrade to inert in export).
- **Cascading** Filter dropdowns (column B options depending on column A).
- **Multi-value per Filter column** (single value per column for v1).
- Graduated-legend range editing beyond on/off class toggles.
