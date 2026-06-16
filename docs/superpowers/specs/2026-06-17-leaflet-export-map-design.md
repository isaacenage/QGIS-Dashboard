# Interactive Leaflet map in the single-file HTML export

**Date:** 2026-06-17
**Status:** Approved (design)
**Supersedes:** the static map-snapshot behavior described in `2026-06-16-html-export-design.md`

## Problem

The HTML export already produces a **single self-contained `index.html`** (CSS, JS, data,
images all inlined; no sidecar files). Its one dead spot is the **map tile**, which is
exported as a static PNG screenshot of `iface.mapCanvas()` (`export/map_snapshot.py`,
rendered by `renderMap` at `export/assets/runtime.js:620`). The recipient cannot pan,
zoom, or click features.

We want the exported map to be a **live, interactive Leaflet map** — while keeping the
output a **single emailable file** that opens by double-click.

> Premise correction (verified against the code): there is **no** GeoJSON sidecar export
> and **no** MapLibre in the codebase today (grep for `geojson|maplibre|leaflet|
> writeAsVectorFormat` returns zero matches). The export is already one file; the map is
> simply a screenshot. This work adds vector geometry + Leaflet, kept inline.

## Decisions (locked with the user)

1. **Basemap = online tiles.** Reuse the QGIS project's XYZ layer URL if one exists, else
   OpenStreetMap. The map (and only the map) needs internet; the rest of the dashboard
   stays fully offline.
2. **Map behavior = show features + click-to-identify popup.** No cross-filtering to/from
   the map.
3. **Feature scope = every layer used by any tile** (`referenced_layer_ids`) gets its
   geometry embedded and drawn on the map.
4. **Single file preserved.** Leaflet's own JS/CSS are inlined; only basemap raster tiles
   stream from the network.
5. **Points render as vector circle-markers** (no marker-image dependency).
6. **Identify popup shows all fields** of the clicked feature.

## Core approach

**Geometry travels as a parallel array, index-aligned with the existing `features` list.**

Today `layers[lid] = {fields, features}` and the entire browser runtime cross-filters by
**feature index**. We add `geometry: [geom|null, …]` in the *same order* as `features`.
This keeps the index-based filter machinery untouched and lets the map map any clicked
feature back to its attribute row for the popup.

Rejected alternative: a standalone GeoJSON `FeatureCollection` per layer — it would
duplicate the already-embedded attributes and desync from the index model.

## Components & changes

### 1. Data collection (QGIS-touching)

**New `export/geometry_collect.py`**
- `collect_layer_geometry(layer, project) -> list`: per feature, in the **same
  `getFeatures()` order** as `data_collect.collect_layer_data`, returns a GeoJSON geometry
  dict **reprojected to EPSG:4326**, or `None` (null/empty geometry or transform failure).
  - Reproject via `QgsCoordinateTransform(layer.crs(), QgsCoordinateReferenceSystem("EPSG:4326"), project)`.
  - Serialize with `QgsGeometry.asJson(precision=6)` then `json.loads` to a dict
    (6 decimals ≈ 0.1 m; meaningfully smaller payload).
  - Optional Douglas–Peucker `geom.simplify(tol)` for line/polygon layers above a vertex
    budget; tolerance derived from extent. Points untouched.
  - Never raises: any per-feature failure yields `None` for that feature.

**`export/data_collect.py`**
- Extend `layer_size_info` to add an estimated geometry byte cost so the oversize guard in
  `export_dialog.py` accounts for embedded geometry. Same Proceed / Skip / Cancel dialog;
  wording updated to mention map geometry.

### 2. Basemap detection (QGIS-touching)

**New `export/basemap.py`**
- `detect_basemap(project) -> {url_template, attribution, subdomains, max_zoom, tms}`.
  - Scan project raster layers for an XYZ source (provider `wms`, source contains
    `type=xyz` and `url=`); URL-decode the `url=` template. QGIS and Leaflet share the
    `{x}/{y}/{z}` tokens. `{-y}` → Leaflet `tms: true`.
  - Fallback: OpenStreetMap — `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, standard
    OSM attribution.
  - Pure helper `xyz_template_to_leaflet(url) -> dict | None` split out and **unit-tested**
    without QGIS; returns `None` on unparseable input so the caller falls back to OSM.

### 3. Export model (pure, `export/serialize.py`)

Bump `EXPORT_VERSION` 1 → 2.

- `layers[lid]` gains `geometry: [...]` (parallel to `features`).
- The map tile **drops `map_image`** and gains a `map` block:
  ```json
  {
    "basemap": { "url_template": "...", "attribution": "...",
                 "subdomains": null, "max_zoom": 19, "tms": false },
    "extent": [west, south, east, north],
    "layer_ids": ["...", "..."],
    "fallback_image": "data:image/png;base64,..."
  }
  ```
  `extent` is the iface canvas extent transformed to EPSG:4326. `fallback_image` is the
  existing snapshot, shown only if Leaflet fails to initialize (graceful degradation).
- `_OPTIONAL_TILE_KEYS`: remove `map_image`, add `map`.

### 4. Browser runtime (`export/assets/`)

- **Vendor Leaflet**: new `assets/leaflet.js` + `assets/leaflet.css` (pinned version).
  `html_builder.load_assets()` reads them; `build_html` inlines `leaflet.css` into the
  `<style>` block **before** `runtime.css`, and `leaflet.js` into a `<script>` **before**
  `runtime.js` so `L` is defined when the runtime runs.
- **No image dependency**: points → `L.circleMarker` (vector, theme-colored); lines and
  polygons are vector already. Leaflet's default marker PNGs are never referenced.
- `renderMap` rewritten:
  - Build a container; push `{host, tile, page}` to a new **`MAP_HOSTS`** post-layout pass
    (mirroring `CHART_HOSTS` at `runtime.js:632`), since a Leaflet map must be sized before
    `L.map()` / `invalidateSize()`.
  - In the pass: `L.map(host)` → add basemap `L.tileLayer(url_template, {attribution,
    subdomains, tms, maxZoom})` → one `L.geoJSON` per `layer_id`, color cycled from the
    theme **series palette** so layers are distinguishable → `fitBounds(extent)` →
    `invalidateSize()`.
  - If `L` is undefined or init throws: fall back to `<img src=fallback_image>`.
- **Identify**: each GeoJSON layer's feature `on('click')` opens a themed popup — a
  scrollable table of **all** that feature's `fields` → `features[i]` values, styled with
  the existing theme CSS vars and hairline borders (per the project border rule).
- The map is **not** wired into the cross-filter bus (no source/target).

### 5. Orchestrator (`export/html_export.py`)

- `_collect_layers` also calls `collect_layer_geometry` (skipped layers get
  `geometry: []`).
- `_build_tile` for `type == "map"` builds the `map` block: `detect_basemap(project)`,
  extent from `iface.mapCanvas().extent()` transformed to 4326, `layer_ids` =
  `referenced_layer_ids`, `fallback_image` = the existing `canvas_data_uri` snapshot.

### 6. Packaging

New files live under `export/` and `export/assets/`, which already ship via `extra_dirs`
(per CLAUDE.md). Verify against `pb_tool.cfg` and `Makefile` during implementation; add
entries only if the claim doesn't hold.

### 7. Tests (extend `test/test_html_export.py`, all QGIS-free)

- `xyz_template_to_leaflet`: Google / Esri / OSM templates, `{-y}` TMS, URL-encoded input,
  garbage → `None`.
- Model v2 assembly: `geometry` array index-aligns with `features`; map block shape;
  `fallback_image` present; `map_image` absent.
- Extent → `[west, south, east, north]` ordering.

## Risks & limitations

- **Map needs internet** for basemap tiles (accepted). Vectors still draw; `fallback_image`
  covers total Leaflet failure.
- **File size** grows with geometry — mitigated by 4326 reprojection, 6-decimal precision,
  optional simplification, and the extended size guard.
- **XYZ detection is heuristic** — auth-token or unparseable basemaps fall back to OSM
  rather than failing the export.
- **CRS edge cases** (antimeridian, un-transformable geometry) → that feature's geometry
  becomes `null`; the export never aborts.

## Out of scope (YAGNI)

Map cross-filtering, baked offline tiles, layer-toggle control, clustering, heatmaps,
QGIS-style per-layer symbology matching. All are clean follow-ups.
