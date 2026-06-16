# Interactive Leaflet Map in HTML Export — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static PNG map screenshot in the single-file HTML export with a live, pannable Leaflet map whose features are clickable (identify popup), kept inside one emailable file.

**Architecture:** Per-feature geometry is reprojected to WGS84 and embedded as a `geometry` array index-aligned with each layer's existing `features` array. The browser builds a Leaflet map per map-tile: an online basemap (the project's XYZ layer if present, else OSM) under vector layers colored by the theme palette, with all-fields identify popups. Leaflet's JS/CSS are vendored and inlined so the file stays self-contained; only basemap tiles stream from the network.

**Tech Stack:** Python 3 (PyQGIS), vanilla JS, Leaflet 1.9.4 (latest stable), `unittest` (QGIS-free pure tests).

**Spec:** `docs/superpowers/specs/2026-06-17-leaflet-export-map-design.md`

---

## File Structure

**New files:**
- `qgis_dashboard/export/basemap.py` — resolve the Leaflet basemap (XYZ detection + OSM fallback). Pure helper `xyz_template_to_leaflet` + QGIS-touching `detect_basemap`.
- `qgis_dashboard/export/geometry_collect.py` — read per-feature geometry → GeoJSON (WGS84), index-aligned with `data_collect`.
- `qgis_dashboard/export/size_estimate.py` — pure byte estimator (so the size guard can account for geometry and stay unit-testable).
- `qgis_dashboard/export/assets/leaflet.js`, `qgis_dashboard/export/assets/leaflet.css` — vendored Leaflet runtime.

**Modified files:**
- `qgis_dashboard/export/serialize.py` — bump `EXPORT_VERSION`→2; swap `map_image` for a `map` block in optional tile keys.
- `qgis_dashboard/export/data_collect.py` — `layer_size_info` delegates to `size_estimate`, counts geometry.
- `qgis_dashboard/export/html_export.py` — collect geometry; build the `map` block.
- `qgis_dashboard/export/html_builder.py` — `load_assets` reads Leaflet; `build_html` inlines it.
- `qgis_dashboard/export/assets/runtime.js` — rewrite `renderMap`; add a `MAP_HOSTS` post-layout init pass.
- `qgis_dashboard/export/assets/runtime.css` — map container + identify-popup styling.
- `qgis_dashboard/test/test_html_export.py` — new pure tests.
- `CLAUDE.md` — update the "static snapshot" notes to the new interactive map.

**Packaging note:** `export/` and `export/assets/` ship via `extra_dirs` (per CLAUDE.md), so new files there ship automatically. Task 9 verifies this against `pb_tool.cfg` and `Makefile`.

**Test command (all pure tests, no QGIS):**
```bash
cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_html_export.py
```

---

## Task 1: Basemap resolver (`export/basemap.py`)

**Files:**
- Create: `qgis_dashboard/export/basemap.py`
- Test: `qgis_dashboard/test/test_html_export.py`

- [ ] **Step 1: Write the failing tests**

Add to `test/test_html_export.py` — extend the imports and add a new test class:

```python
from export.basemap import xyz_template_to_leaflet, OSM_BASEMAP


class XyzTemplateTest(unittest.TestCase):
    def test_osm_style_passthrough(self):
        out = xyz_template_to_leaflet(
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
        self.assertEqual(out["url_template"],
                         "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
        self.assertFalse(out["tms"])

    def test_url_encoded_tokens_are_decoded(self):
        out = xyz_template_to_leaflet(
            "https://a.tile/%7Bz%7D/%7Bx%7D/%7By%7D.png")
        self.assertEqual(out["url_template"], "https://a.tile/{z}/{x}/{y}.png")

    def test_tms_minus_y_flagged_and_normalized(self):
        out = xyz_template_to_leaflet("https://a.tile/{z}/{x}/{-y}.png")
        self.assertTrue(out["tms"])
        self.assertIn("{y}", out["url_template"])
        self.assertNotIn("{-y}", out["url_template"])

    def test_garbage_returns_none(self):
        self.assertIsNone(xyz_template_to_leaflet("not a url"))
        self.assertIsNone(xyz_template_to_leaflet(""))
        self.assertIsNone(xyz_template_to_leaflet(None))

    def test_osm_fallback_constant_is_valid(self):
        self.assertIn("{z}", OSM_BASEMAP["url_template"])
        self.assertEqual(OSM_BASEMAP["tms"], False)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_html_export.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'export.basemap'`

- [ ] **Step 3: Create `export/basemap.py`**

```python
# -*- coding: utf-8 -*-
"""Resolve the basemap for the interactive Leaflet export map.

The exported map is an online Leaflet slippy map. If the QGIS project already
contains an XYZ tile layer we reuse its URL template (so the export matches what
the user sees in QGIS); otherwise we fall back to OpenStreetMap.

``xyz_template_to_leaflet`` is pure (no QGIS) and unit-tested; ``detect_basemap``
scans the project and delegates to it.
"""

import re
from urllib.parse import unquote

OSM_BASEMAP = {
    "url_template": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "attribution": "© OpenStreetMap contributors",
    "subdomains": None,
    "max_zoom": 19,
    "tms": False,
}


def xyz_template_to_leaflet(url):
    """Convert a QGIS XYZ ``url=`` template into a Leaflet basemap dict.

    Returns ``None`` when *url* has no usable ``{x}/{y}/{z}`` tokens so the
    caller can fall back to OSM. ``{-y}`` (TMS addressing) sets ``tms=True`` and
    is normalized to ``{y}`` for Leaflet.
    """
    if not url:
        return None
    text = unquote(str(url)).strip()
    if "{x}" not in text or "{z}" not in text:
        return None
    tms = "{-y}" in text
    if tms:
        text = text.replace("{-y}", "{y}")
    if "{y}" not in text:
        return None
    return {
        "url_template": text,
        "attribution": "",
        "subdomains": None,
        "max_zoom": 19,
        "tms": tms,
    }


def detect_basemap(project):
    """Return a Leaflet basemap dict for *project* — its XYZ layer, else OSM."""
    try:
        layers = list(project.mapLayers().values())
    except Exception:
        return dict(OSM_BASEMAP)
    for layer in layers:
        try:
            source = layer.source() or ""
        except Exception:
            source = ""
        if "type=xyz" in source and "url=" in source:
            match = re.search(r"url=([^&]+)", source)
            if match:
                parsed = xyz_template_to_leaflet(match.group(1))
                if parsed:
                    return parsed
    return dict(OSM_BASEMAP)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_html_export.py`
Expected: PASS (all tests, including the 5 new ones)

- [ ] **Step 5: Commit**

```bash
git add qgis_dashboard/export/basemap.py qgis_dashboard/test/test_html_export.py
git commit -m "feat: basemap resolver for Leaflet export (XYZ detect + OSM fallback)"
```

---

## Task 2: Export model v2 — `map` block (`export/serialize.py`)

**Files:**
- Modify: `qgis_dashboard/export/serialize.py` (`EXPORT_VERSION`, `_OPTIONAL_TILE_KEYS`, docstring)
- Test: `qgis_dashboard/test/test_html_export.py`

- [ ] **Step 1: Write the failing tests**

Add a new test class to `test/test_html_export.py`:

```python
class MapBlockTest(unittest.TestCase):
    def test_map_block_passthrough(self):
        tile = {"id": "m", "type": "map", "grid": {},
                "map": {"basemap": {"url_template": "u"},
                        "extent": [0, 1, 2, 3], "layer_ids": ["L1"]}}
        out = build_tile(tile)
        self.assertEqual(out["map"]["extent"], [0, 1, 2, 3])
        self.assertEqual(out["map"]["layer_ids"], ["L1"])

    def test_map_image_no_longer_passed_through(self):
        tile = {"id": "m", "type": "map", "grid": {},
                "map_image": "data:image/png;base64,AAAA"}
        out = build_tile(tile)
        self.assertNotIn("map_image", out)

    def test_version_is_two(self):
        self.assertEqual(EXPORT_VERSION, 2)

    def test_layers_geometry_carried_through(self):
        model = build_model((12, 8), {}, "p1",
                            [{"id": "p1", "title": "P", "connections": {},
                              "tiles": []}],
                            {"L1": {"fields": [], "features": [], "geometry": []}})
        self.assertIn("geometry", model["layers"]["L1"])
```

Also **update the existing** `BuildTileTest.test_optional_keys_passthrough` (it asserts `map_image` passthrough, which is being removed). Replace its body with the `map` block:

```python
    def test_optional_keys_passthrough(self):
        tile = {"id": "m", "type": "map", "grid": {},
                "map": {"extent": [0, 1, 2, 3]},
                "layer_id": "L1", "base_pass": [0, 2]}
        out = build_tile(tile)
        self.assertEqual(out["map"], {"extent": [0, 1, 2, 3]})
        self.assertEqual(out["layer_id"], "L1")
        self.assertEqual(out["base_pass"], [0, 2])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_html_export.py`
Expected: FAIL — `test_version_is_two` (EXPORT_VERSION is 1) and `test_map_block_passthrough` (KeyError/missing `map`).

- [ ] **Step 3: Edit `export/serialize.py`**

Change the version constant:
```python
EXPORT_VERSION = 2
```

Change `_OPTIONAL_TILE_KEYS` — remove `"map_image"`, add `"map"`:
```python
# Optional per-tile keys copied through verbatim when present (and not None).
_OPTIONAL_TILE_KEYS = (
    "layer_id", "base_pass", "map", "image_uri", "indicator_value",
    "icon_uri", "logo_uri",
)
```

In the module docstring, update the tile-shape line from `"map_image"?` to `"map"?` and add `geometry` to the layers line:
```python
#            "layer_id"?, "base_pass"?, "map"?, "image_uri"?,
#            "indicator_value"?}
#         ]}
#       ],
#       "layers": {"<layer id>": {"fields": [...], "features": [ {field: val} ],
#                                 "geometry": [ geojson_geom_or_null ]}}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_html_export.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qgis_dashboard/export/serialize.py qgis_dashboard/test/test_html_export.py
git commit -m "feat: export model v2 with map block (replaces map_image)"
```

---

## Task 3: Pure size estimator (`export/size_estimate.py`)

**Files:**
- Create: `qgis_dashboard/export/size_estimate.py`
- Modify: `qgis_dashboard/export/data_collect.py:101-112` (`layer_size_info`)
- Test: `qgis_dashboard/test/test_html_export.py`

- [ ] **Step 1: Write the failing tests**

Add to `test/test_html_export.py`:

```python
from export.size_estimate import estimate_layer_bytes


class SizeEstimateTest(unittest.TestCase):
    def test_geometry_adds_to_estimate(self):
        base = estimate_layer_bytes(100, 5, include_geometry=False)
        with_geom = estimate_layer_bytes(100, 5, include_geometry=True)
        self.assertGreater(with_geom, base)

    def test_zero_features_is_zero(self):
        self.assertEqual(estimate_layer_bytes(0, 5, include_geometry=True), 0)

    def test_field_count_floored_at_one(self):
        # 0 fields must not zero out the attribute estimate
        self.assertGreater(estimate_layer_bytes(10, 0, include_geometry=False), 0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_html_export.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'export.size_estimate'`

- [ ] **Step 3: Create `export/size_estimate.py`**

```python
# -*- coding: utf-8 -*-
"""Pure byte-size estimate for a layer's embedded export payload.

Kept QGIS-free (and separate from :mod:`data_collect`, which imports QGIS) so
the size-guard math is unit-testable. The numbers are deliberately rough — they
only need to flag a layer that would bloat the single-file HTML export.
"""

_ATTR_CELL_BYTES = 24    # avg JSON bytes per attribute cell
_GEOM_FEATURE_BYTES = 120  # avg JSON bytes per feature's WGS84 geometry


def estimate_layer_bytes(feature_count, field_count, include_geometry=False):
    """Estimate embedded bytes for *feature_count* features.

    Attribute cost is ``features * max(fields, 1) * 24``; geometry adds a flat
    ~120 bytes per feature when included.
    """
    count = max(int(feature_count or 0), 0)
    cols = max(int(field_count or 0), 1)
    total = count * cols * _ATTR_CELL_BYTES
    if include_geometry:
        total += count * _GEOM_FEATURE_BYTES
    return total
```

- [ ] **Step 4: Rewrite `layer_size_info` in `export/data_collect.py`**

Replace the existing `layer_size_info` (lines 101-112) with a delegating version that counts geometry:

```python
def layer_size_info(layer):
    """Return ``(feature_count, estimated_bytes)`` for the size guard.

    The byte estimate (from :mod:`size_estimate`) now includes the per-feature
    WGS84 geometry the interactive map embeds, so the guard reflects the real
    single-file payload.
    """
    from .size_estimate import estimate_layer_bytes
    count = layer.featureCount()
    if count is None or count < 0:
        count = 0
    cols = len(layer.fields())
    return count, estimate_layer_bytes(count, cols, include_geometry=True)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_html_export.py`
Expected: PASS

- [ ] **Step 6: Syntax-check the QGIS-touching change**

Run: `cd qgis_dashboard && python -m py_compile export/data_collect.py export/size_estimate.py`
Expected: no output (success)

- [ ] **Step 7: Commit**

```bash
git add qgis_dashboard/export/size_estimate.py qgis_dashboard/export/data_collect.py qgis_dashboard/test/test_html_export.py
git commit -m "feat: size guard accounts for embedded map geometry"
```

---

## Task 4: Geometry collection (`export/geometry_collect.py`)

**Files:**
- Create: `qgis_dashboard/export/geometry_collect.py`

This module imports QGIS and cannot be unit-tested without it; verification is `py_compile` plus the in-QGIS run in Task 9.

- [ ] **Step 1: Create `export/geometry_collect.py`**

```python
# -*- coding: utf-8 -*-
"""Collect per-feature geometry (reprojected to WGS84) for the export map.

Parallel to :func:`data_collect.collect_layer_data`: it walks the same
``getFeatures()`` order and returns one GeoJSON geometry dict per feature (or
``None``), so the geometry list index-aligns with the attribute ``features``
list the runtime already cross-filters by. Geometry is reprojected to EPSG:4326
(Leaflet's CRS) and rounded to 6 decimals. No vertex simplification is applied —
full geometry fidelity is preserved.
"""

import json

from qgis.core import (
    QgsGeometry, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsProject,
)

WGS84 = "EPSG:4326"
_PRECISION = 6


def collect_layer_geometry(layer, project=None):
    """Return a list of GeoJSON geometry dicts (or ``None``) for *layer*.

    The list is in ``layer.getFeatures()`` order so it index-aligns with
    :func:`data_collect.collect_layer_data`'s ``features``.
    """
    project = project or QgsProject.instance()
    dest = QgsCoordinateReferenceSystem(WGS84)
    src = layer.crs()
    transform = None
    if src.isValid() and dest.isValid() and src != dest:
        transform = QgsCoordinateTransform(src, dest, project)

    out = []
    for feat in layer.getFeatures():
        out.append(_feature_geojson(feat.geometry(), transform))
    return out


def _feature_geojson(geom, transform):
    """One feature's geometry -> a GeoJSON geometry dict, or ``None``."""
    if geom is None or geom.isNull() or geom.isEmpty():
        return None
    if transform is not None:
        geom = QgsGeometry(geom)   # copy: never mutate the source feature
        try:
            if geom.transform(transform) != 0:
                return None
        except Exception:
            return None
    try:
        text = geom.asJson(_PRECISION)
    except Exception:
        return None
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None
```

- [ ] **Step 2: Syntax-check**

Run: `cd qgis_dashboard && python -m py_compile export/geometry_collect.py`
Expected: no output (success)

- [ ] **Step 3: Commit**

```bash
git add qgis_dashboard/export/geometry_collect.py
git commit -m "feat: collect per-feature WGS84 geometry for export map"
```

---

## Task 5: Orchestrator wiring (`export/html_export.py`)

**Files:**
- Modify: `qgis_dashboard/export/html_export.py`

QGIS-touching; verified by `py_compile` + Task 9.

- [ ] **Step 1: Update imports**

At the top of `html_export.py`, extend the QGIS import and add the two collectors:

```python
from qgis.core import (
    QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
)

from .serialize import build_model
from .theme_css import theme_to_css_vars
from .html_builder import build_html, load_assets
from .data_collect import (
    collect_layer_data, base_pass_indices, image_data_uri, layer_size_info,
)
from .geometry_collect import collect_layer_geometry
from .basemap import detect_basemap
from .map_snapshot import canvas_data_uri
```

- [ ] **Step 2: Embed geometry in `_collect_layers`**

Replace the body of `_collect_layers` with the version that attaches geometry (skipped layers get an empty geometry list):

```python
def _collect_layers(window, skip_layers):
    """Return ``(layers_model, fid_indexes)`` for referenced layers."""
    project = QgsProject.instance()
    layers_model = {}
    fid_indexes = {}
    for lid in referenced_layer_ids(window):
        layer = project.mapLayer(lid)
        if layer is None:
            continue
        if lid in skip_layers:
            layers_model[lid] = {
                "fields": [f.name() for f in layer.fields()],
                "features": [], "geometry": [], "skipped": True,
            }
            fid_indexes[lid] = {}
        else:
            data, fid_index = collect_layer_data(layer)
            data["geometry"] = collect_layer_geometry(layer, project)
            layers_model[lid] = data
            fid_indexes[lid] = fid_index
    return layers_model, fid_indexes
```

- [ ] **Step 3: Add the map-block builders**

Add these two functions above `_build_tile`:

```python
def _canvas_extent_4326(iface, project):
    """The current map-canvas extent as ``[west, south, east, north]`` (WGS84)."""
    if iface is None:
        return None
    canvas = iface.mapCanvas()
    if canvas is None:
        return None
    try:
        extent = canvas.extent()
        src = canvas.mapSettings().destinationCrs()
        dest = QgsCoordinateReferenceSystem("EPSG:4326")
        if src.isValid() and src != dest:
            transform = QgsCoordinateTransform(src, dest, project)
            extent = transform.transformBoundingBox(extent)
        return [extent.xMinimum(), extent.yMinimum(),
                extent.xMaximum(), extent.yMaximum()]
    except Exception:
        return None


def _build_map_block(window, layers_model):
    """The interactive-map descriptor: basemap, extent, drawable layers, fallback."""
    project = QgsProject.instance()
    iface = getattr(window, "iface", None)
    layer_ids = [lid for lid in sorted(referenced_layer_ids(window))
                 if lid in layers_model]
    return {
        "basemap": detect_basemap(project),
        "extent": _canvas_extent_4326(iface, project),
        "layer_ids": layer_ids,
        "fallback_image": canvas_data_uri(iface),
    }
```

- [ ] **Step 4: Use the map block in `_build_tile`**

Change the `_build_tile` signature to take `window`/`layers_model` instead of `map_uri`, and replace the map branch:

```python
def _build_tile(tile, fid_indexes, skip_layers, window, layers_model):
    element = tile.element
    gx, gy, gw, gh = tile.grid_rect()
    out = {
        "id": element.id,
        "type": element.type_name,
        "config": dict(element.config),
        "grid": {"x": gx, "y": gy, "w": gw, "h": gh},
    }
    lid = element.config.get("layer_id")
    if lid:
        out["layer_id"] = lid
        if lid in fid_indexes and lid not in skip_layers:
            out["base_pass"] = base_pass_indices(
                element.layer(), element.config.get("base_filter"),
                fid_indexes[lid])
    if element.type_name == "map":
        out["map"] = _build_map_block(window, layers_model)
    elif element.type_name == "image":
        out["image_uri"] = image_data_uri(element.config.get("path"))
    elif element.type_name == "header":
        logo = (element.config.get("logo_path") or "").strip()
        if logo:
            out["logo_uri"] = image_data_uri(logo)
    elif element.type_name == "indicator":
        out["indicator_value"] = _indicator_baseline(element)
        icon = element.config.get("icon_path")
        if icon:
            out["icon_uri"] = image_data_uri(icon)
    return out
```

- [ ] **Step 5: Update the caller in `export_dashboard`**

In `export_dashboard`, drop the `map_uri` line and pass `window`/`layers_model` to `_build_tile`:

```python
def export_dashboard(window, out_path, skip_layers=None):
    """Write the dashboard to *out_path* as a single HTML file. Returns the path."""
    skip_layers = set(skip_layers or [])
    layers_model, fid_indexes = _collect_layers(window, skip_layers)

    pages = []
    for page in window.pages():
        tiles = [_build_tile(t, fid_indexes, skip_layers, window, layers_model)
                 for t in page.canvas.tiles()]
        pages.append({
            "id": page.id,
            "title": page.title,
            "connections": window.bus.connections_to_dict(page.id),
            "tiles": tiles,
        })

    current = window.current_page()
    model = build_model(
        (window.canvas_cols(), window.canvas_rows()),
        window.bus.theme.to_dict(),
        current.id if current else None,
        pages, layers_model,
        gap=window.canvas_gap())

    css_vars = theme_to_css_vars(model["theme"])
    runtime_css, runtime_js, leaflet_css, leaflet_js = load_assets()
    html = build_html(model, css_vars, runtime_css, runtime_js,
                      leaflet_css=leaflet_css, leaflet_js=leaflet_js,
                      title=_project_title())

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out_path
```

(`load_assets` returning four values and `build_html`'s new keywords are added in Task 6; this step assumes them.)

- [ ] **Step 6: Syntax-check**

Run: `cd qgis_dashboard && python -m py_compile export/html_export.py`
Expected: no output (success)

- [ ] **Step 7: Commit**

```bash
git add qgis_dashboard/export/html_export.py
git commit -m "feat: build interactive map block in HTML export orchestrator"
```

---

## Task 6: Vendor Leaflet + inline it (`html_builder.py` + assets)

**Files:**
- Create: `qgis_dashboard/export/assets/leaflet.js`, `qgis_dashboard/export/assets/leaflet.css`
- Modify: `qgis_dashboard/export/html_builder.py` (`load_assets`, `build_html`)
- Test: `qgis_dashboard/test/test_html_export.py`

- [ ] **Step 1: Download Leaflet 1.9.4 into the assets dir**

Run (confirm 1.9.4 is still the latest stable at https://leafletjs.com/download.html; bump the version in both URLs if a newer stable exists):

```bash
cd "qgis_dashboard/export/assets"
curl -L -o leaflet.js  https://unpkg.com/leaflet@1.9.4/dist/leaflet.js
curl -L -o leaflet.css https://unpkg.com/leaflet@1.9.4/dist/leaflet.css
```

Verify they downloaded (not an error page):
```bash
head -c 80 leaflet.js   # expect a license/comment banner, e.g. "/* @preserve ... Leaflet 1.9.4"
node --check leaflet.js  # optional, if node is available -> no output on success
```

- [ ] **Step 2: Write the failing test**

Add to `HtmlBuilderTest` in `test/test_html_export.py`:

```python
    def test_build_html_inlines_leaflet_before_runtime(self):
        model = build_model((1, 1), {}, None, [], {})
        html = build_html(model, "", "/*RT_CSS*/", "/*RT_JS*/",
                          leaflet_css="/*LEAFLET_CSS*/",
                          leaflet_js="/*LEAFLET_JS*/", title="D")
        self.assertIn("/*LEAFLET_CSS*/", html)
        self.assertIn("/*LEAFLET_JS*/", html)
        # leaflet CSS before runtime CSS; leaflet JS before runtime JS
        self.assertLess(html.index("/*LEAFLET_CSS*/"), html.index("/*RT_CSS*/"))
        self.assertLess(html.index("/*LEAFLET_JS*/"), html.index("/*RT_JS*/"))
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_html_export.py`
Expected: FAIL — `build_html() got an unexpected keyword argument 'leaflet_css'`

- [ ] **Step 4: Update `html_builder.py`**

Change `load_assets` to also read the Leaflet files:

```python
def load_assets():
    """Return ``(runtime_css, runtime_js, leaflet_css, leaflet_js)``."""
    return (_read_asset("runtime.css"), _read_asset("runtime.js"),
            _read_asset("leaflet.css"), _read_asset("leaflet.js"))
```

Change `build_html` to accept and inline the Leaflet assets (leaflet CSS before runtime CSS; a dedicated leaflet `<script>` before the runtime `<script>`):

```python
def build_html(model, css_vars, runtime_css, runtime_js,
               leaflet_css="", leaflet_js="", title="Dashboard"):
    """Return the complete ``index.html`` document as a string."""
    data_json = embed_json(model)
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>{}</title>".format(_escape_html(title)),
        "<style>",
        css_vars,
        leaflet_css,
        runtime_css,
        "</style>",
        "</head>",
        "<body>",
        '<div id="app"></div>',
        '<script type="application/json" id="dashboard-data">',
        data_json,
        "</script>",
        "<script>",
        leaflet_js,
        "</script>",
        "<script>",
        runtime_js,
        "</script>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_html_export.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add qgis_dashboard/export/assets/leaflet.js qgis_dashboard/export/assets/leaflet.css qgis_dashboard/export/html_builder.py qgis_dashboard/test/test_html_export.py
git commit -m "feat: vendor and inline Leaflet 1.9.4 in HTML export"
```

---

## Task 7: Map + identify styles (`export/assets/runtime.css`)

**Files:**
- Modify: `qgis_dashboard/export/assets/runtime.css`

Browser-verified (Task 9). No automated test.

- [ ] **Step 1: Find the existing map style block**

Run: `cd qgis_dashboard && grep -n "dash-map" export/assets/runtime.css`
Expected: a `.dash-map-wrap` and/or `.dash-map` rule (the static-image styling).

- [ ] **Step 2: Replace/extend the map styles**

Ensure the wrap fills the tile and the Leaflet container has an explicit size and theme skin, and add the identify-popup styling. Replace the existing `.dash-map`/`.dash-map-wrap` rules with:

```css
.dash-map-wrap { width: 100%; height: 100%; position: relative; }
.dash-map-wrap img.dash-map { width: 100%; height: 100%; object-fit: cover;
  border-radius: var(--radius); }
.dash-map-wrap .leaflet-container {
  width: 100%; height: 100%;
  border-radius: var(--radius);
  font-family: var(--font-family);
  background: var(--surface-bg);
}
/* identify popup — themed, hairline borders (never heavy outlines) */
.dash-identify { font-family: var(--font-family); color: var(--text);
  font-size: 12px; max-height: 180px; overflow: auto; }
.dash-identify table { border-collapse: collapse; }
.dash-identify th, .dash-identify td {
  text-align: left; padding: 2px 10px 2px 0;
  border-bottom: 1px solid var(--border); vertical-align: top; }
.dash-identify th { color: var(--muted); font-weight: 600; white-space: nowrap; }
.leaflet-popup-content-wrapper { border-radius: var(--radius); }
```

- [ ] **Step 3: Commit**

```bash
git add qgis_dashboard/export/assets/runtime.css
git commit -m "feat: themed Leaflet map + identify popup styles"
```

---

## Task 8: Interactive map runtime (`export/assets/runtime.js`)

**Files:**
- Modify: `qgis_dashboard/export/assets/runtime.js` (`renderMap` at ~620; post-layout pass at ~719-732; resize handler at ~766-772)

Browser-verified (Task 9). `node --check` for syntax.

- [ ] **Step 1: Add an HTML-escape helper (if absent)**

Run: `cd qgis_dashboard && grep -n "function escapeHtml" export/assets/runtime.js`
If **no** match, add this near the `el(` helper (~line 231):

```javascript
  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
```
(If `escapeHtml` already exists, skip this step and reuse it.)

- [ ] **Step 2: Replace `renderMap` and add the map helpers**

Replace the whole `renderMap` function (lines ~620-629) with:

```javascript
  // ---- interactive Leaflet map ----------------------------------------
  var MAP_HOSTS = [];      // {host, tile} for the post-layout init pass
  var MAP_INSTANCES = [];  // live L.map objects, torn down on page switch

  function renderMap(body, tile) {
    var wrap = el("div", "dash-map-wrap");
    body.appendChild(wrap);
    if (tile.map && typeof L !== "undefined") {
      MAP_HOSTS.push({ host: wrap, tile: tile });
    } else if (tile.map && tile.map.fallback_image) {
      var img = el("img", "dash-map"); img.src = tile.map.fallback_image;
      wrap.appendChild(img);
    } else {
      wrap.appendChild(el("div", "dash-note", "Map — view in QGIS"));
    }
  }

  function featureCollection(layer) {
    var rows = layer.features || [];
    var geoms = layer.geometry || [];
    var feats = [];
    for (var i = 0; i < rows.length; i++) {
      if (!geoms[i]) continue;
      feats.push({ type: "Feature", geometry: geoms[i], properties: rows[i] });
    }
    return { type: "FeatureCollection", features: feats };
  }

  function identifyHtml(fields, props) {
    props = props || {};
    var names = (fields && fields.length) ? fields : Object.keys(props);
    var rows = names.map(function (name) {
      var v = props[name];
      if (v === null || v === undefined) v = "";
      return "<tr><th>" + escapeHtml(name) + "</th><td>" +
             escapeHtml(v) + "</td></tr>";
    }).join("");
    return '<div class="dash-identify"><table>' + rows + "</table></div>";
  }

  function initMap(host, tile) {
    var m = tile.map || {};
    var map;
    try {
      map = L.map(host);
    } catch (e) {
      if (m.fallback_image) {
        var img = el("img", "dash-map"); img.src = m.fallback_image;
        host.appendChild(img);
      }
      return;
    }
    var bm = m.basemap || {};
    var opts = { maxZoom: bm.max_zoom || 19 };
    if (bm.attribution) opts.attribution = bm.attribution;
    if (bm.subdomains) opts.subdomains = bm.subdomains;
    if (bm.tms) opts.tms = true;
    L.tileLayer(bm.url_template ||
      "https://tile.openstreetmap.org/{z}/{x}/{y}.png", opts).addTo(map);

    var bounds = null;
    (m.layer_ids || []).forEach(function (lid, idx) {
      var layer = DATA.layers[lid];
      if (!layer || !layer.geometry) return;
      var fc = featureCollection(layer);
      if (!fc.features.length) return;
      var col = color(idx);
      var gj = L.geoJSON(fc, {
        style: function () {
          return { color: col, weight: 2, fillColor: col, fillOpacity: 0.25 };
        },
        pointToLayer: function (f, latlng) {
          return L.circleMarker(latlng, { radius: 5, color: col,
            fillColor: col, fillOpacity: 0.85, weight: 1 });
        },
        onEachFeature: function (f, lyr) {
          lyr.bindPopup(identifyHtml(layer.fields, f.properties));
        }
      }).addTo(map);
      try {
        var b = gj.getBounds();
        if (b.isValid()) bounds = bounds ? bounds.extend(b) : b;
      } catch (e) {}
    });

    var ext = m.extent;
    if (ext && ext.length === 4) {
      map.fitBounds([[ext[1], ext[0]], [ext[3], ext[2]]]);
    } else if (bounds) {
      map.fitBounds(bounds);
    } else {
      map.setView([0, 0], 2);
    }
    map.invalidateSize();
    MAP_INSTANCES.push(map);
  }
```

- [ ] **Step 3: Reset + init maps in `renderPage`**

In `renderPage` (lines ~719-732), tear down old maps, reset the host list, and init after layout. Replace the function with:

```javascript
  function renderPage(page) {
    CHART_HOSTS = [];
    MAP_INSTANCES.forEach(function (mp) { try { mp.remove(); } catch (e) {} });
    MAP_INSTANCES = [];
    MAP_HOSTS = [];
    var area = document.getElementById("page-area");
    area.innerHTML = "";
    var wrap = el("div", "dash-pagewrap");
    var scroll = el("div", "dash-scroll");
    scroll.appendChild(buildGrid(page));
    wrap.appendChild(scroll);
    area.appendChild(wrap);
    // charts and maps need their host measured after layout
    requestAnimationFrame(function () {
      CHART_HOSTS.forEach(function (c) { drawChart(c.host, c.tile, c.page); });
      MAP_HOSTS.forEach(function (h) { initMap(h.host, h.tile); });
    });
  }
```

- [ ] **Step 4: Keep maps sized on window resize**

In the resize handler (lines ~766-772), add an `invalidateSize` sweep alongside the chart redraw:

```javascript
  var resizeTimer = null;
  window.addEventListener("resize", function () {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      CHART_HOSTS.forEach(function (c) { drawChart(c.host, c.tile, c.page); });
      MAP_INSTANCES.forEach(function (mp) {
        try { mp.invalidateSize(); } catch (e) {}
      });
    }, 150);
  });
```

- [ ] **Step 5: Syntax-check the runtime**

Run: `node --check qgis_dashboard/export/assets/runtime.js`
Expected: no output (success). (If `node` is unavailable, skip — Task 9's browser load will surface syntax errors.)

- [ ] **Step 6: Commit**

```bash
git add qgis_dashboard/export/assets/runtime.js
git commit -m "feat: interactive Leaflet map with identify popups in export runtime"
```

---

## Task 9: Packaging check, docs, and end-to-end verification

**Files:**
- Modify: `CLAUDE.md`
- Verify: `qgis_dashboard/pb_tool.cfg`, `qgis_dashboard/Makefile`

- [ ] **Step 1: Confirm assets ship in the package**

Run:
```bash
cd qgis_dashboard && grep -n "extra_dirs\|EXTRA_DIRS" pb_tool.cfg Makefile
```
Expected: `export` listed under `extra_dirs` (pb_tool.cfg) and `EXTRA_DIRS` (Makefile). Since `assets/` lives inside `export/`, the new `leaflet.js`/`leaflet.css` and the new `.py` modules ship automatically. If `export` is **not** listed, add it to both — but per CLAUDE.md it already is; this is a confirmation step only.

- [ ] **Step 2: Update CLAUDE.md — the map element row**

Find: `Desktop-only — the HTML export's map is a static snapshot and does not filter.`
Replace with:
`In the HTML export the map is an interactive Leaflet map (online basemap — the project's XYZ layer if present, else OpenStreetMap — with the dashboard's layers drawn as clickable WGS84 vector features and an all-fields identify popup); it does not cross-filter, and a static canvas snapshot is embedded only as a fallback when Leaflet can't initialize. The basemap needs network; the rest of the file stays offline.`

- [ ] **Step 3: Update CLAUDE.md — the HTML export section**

Find: `the map tile grabbed to a base64 PNG (a static snapshot — an interactive web map is impossible under double-click `file://`)`
Replace with:
`each referenced layer's geometry reprojected to WGS84 and embedded as a per-feature GeoJSON array (index-aligned with its attribute rows) so the map tile becomes an interactive Leaflet map (vendored, inlined Leaflet 1.9.4; online basemap tiles; a base64 canvas snapshot kept only as the no-Leaflet fallback)`

Find: `there is no MapLibre/charting library.`
Replace with:
`there is no charting library, and the only map dependency is Leaflet (vendored and inlined, so the file stays self-contained; only its basemap tiles stream from the network).`

Find: `The **map** stays a static snapshot, so its extent cross-filtering is desktop-only.`
Replace with:
`The **map** is an interactive Leaflet map (pan/zoom + click-to-identify) but does not cross-filter — that remains desktop-only — and its basemap tiles require a network connection.`

- [ ] **Step 4: Run the full pure test suite once more**

Run: `cd qgis_dashboard && PYTHONPATH=$(pwd) python test/test_html_export.py`
Expected: PASS (every test)

- [ ] **Step 5: Manual end-to-end verification in QGIS**

1. Copy/symlink `qgis_dashboard/` into the QGIS plugins dir and enable the plugin.
2. Open a project that has at least one vector layer and (optionally) an XYZ basemap layer.
3. Build a dashboard with a **map** tile plus a chart/list bound to the vector layer.
4. Settings hub → **Export to HTML…**, save `test.html`.
5. Double-click `test.html` (online). Verify:
   - The map renders a real slippy basemap (the project's XYZ if present, else OSM).
   - Your layer's features are drawn and colored; **clicking a feature opens an all-fields popup**.
   - Pan/zoom works; the map fits the QGIS extent on load.
   - Charts/lists/cross-filtering still work.
6. Go offline and reload: the dashboard still loads and cross-filters; only the basemap tiles are blank (expected).

- [ ] **Step 6: Commit the docs**

```bash
git add CLAUDE.md
git commit -m "docs: HTML export map is now interactive Leaflet"
```

---

## Self-Review notes (resolved)

- **Spec coverage:** basemap detection (T1), model v2 + map block (T2), size guard incl. geometry (T3), geometry collection (T4), orchestrator/extent (T5), Leaflet vendoring + inlining (T6), themed styles (T7), runtime map + identify (T8), packaging + docs + e2e (T9). All spec sections covered.
- **Type consistency:** `_OPTIONAL_TILE_KEYS` uses `"map"` (T2) which `_build_tile` writes (T5) and `renderMap` reads as `tile.map` (T8). `load_assets` returns 4 values (T6) matching `export_dashboard`'s unpack (T5). `estimate_layer_bytes(feature_count, field_count, include_geometry)` defined in T3 and called there. `color(i)` (existing `runtime.js:243`) reused in T8.
- **No simplification:** geometry kept full-fidelity, only 6-decimal precision (T4), per the finalized spec.
