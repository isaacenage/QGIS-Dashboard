# QGIS Plugins

A growing collection of **free, open-source QGIS plugins** by Isaac Enage, plus
the website that showcases them. Plugin **source code** lives under `plugins/`;
the **website** (a Next.js app) lives at the repo root with one route segment
per plugin under `app/`.

## What's in the repo

| Path | What it is |
|------|------------|
| repo root (`app/`, `components/`, `lib/`, `public/`) | **The website** — one Next.js app. `/` is the **QGIS Plugins** hub; each plugin gets a route segment (currently `/qdashboards`). Deployed to Vercel at `qgis.byzenterra.org`. |
| [`plugins/`](plugins/) | **All plugin source.** One self-contained, installable QGIS plugin per folder. |
| [`plugins/qgis_dashboards/`](plugins/qgis_dashboards/) | **QGIS Dashboard** — the QGIS plugin (Python / PyQt). The shippable plugin; install it into QGIS. Featured on the site at `/qdashboards`. |

The website and the plugins never import each other. QGIS Dashboard meets the
site at a single contract: [`public/dashboards/manifest.json`](public/dashboards/)
— the plugin's *Publish to public* writes it; the site's gallery reads it.

### Adding another plugin

1. Drop the plugin's source folder under `plugins/` (e.g. `plugins/qgis_<name>/`).
2. Add a row to [`lib/plugins.ts`](lib/plugins.ts).
3. Create its route segment under `app/<slug>/` (mirror `app/qdashboards/`).

## Website (repo root)

```bash
npm install
npm run dev      # http://localhost:3000/  (hub) · /qdashboards (dashboard)
npm run build    # production build
```

Served from the domain **root** — there is no Next `basePath`. The
`/qdashboards` prefix is a real route segment, applied to dashboard links by
`lib/site.ts → withBase()`. Published dashboards live as static files in
`public/dashboards/` (served from `/dashboards/...`) — see that folder's README
for the layout and how to seed one by hand.

## QGIS Dashboard plugin (`plugins/qgis_dashboards/`)

Build **ArcGIS-Dashboards-style interactive dashboards** from your QGIS
project's vector layers — charts, indicators, lists, a live map and selectors
that **cross-filter each other in real time**.

There is no app build — "running" means loading it inside QGIS. Copy the
`plugins/qgis_dashboards/` folder into your QGIS profile's `python/plugins/`
directory and enable **QGIS Dashboard** under *Plugins → Manage*. Full
architecture and developer notes are in [`CLAUDE.md`](CLAUDE.md).

## Author

Built by **Isaac Enage** · <isaacenagework@gmail.com>
