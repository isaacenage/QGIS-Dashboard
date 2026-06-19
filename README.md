# QGIS Plugins

A growing collection of **free, open-source QGIS plugins** by Isaac Enage, plus
the website that showcases them. This repository is the home for every plugin —
each one keeps its own source folder here.

## What's in the repo

| Path | What it is |
|------|------------|
| repo root (`app/`, `components/`, `lib/`, `public/`) | **The website** — one Next.js app. `/` is the **QGIS Plugins** hub; each plugin gets a route segment (currently `/qdashboards`). Deployed to Vercel at `qgis.byzenterra.org`. |
| [`qgis_dashboards/`](qgis_dashboards/) | **QGIS Dashboard** — the QGIS plugin (Python / PyQt). The shippable plugin; install it into QGIS. Featured on the site at `/qdashboards`. |

The website and the plugins never import each other. QGIS Dashboard meets the
site at a single contract: [`public/dashboards/manifest.json`](public/dashboards/)
— the plugin's *Publish to public* writes it; the site's gallery reads it.

### Adding another plugin

1. Drop the plugin's source folder at the repo root (e.g. `qgis_<name>/`).
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

## QGIS Dashboard plugin (`qgis_dashboards/`)

Build **ArcGIS-Dashboards-style interactive dashboards** from your QGIS
project's vector layers — charts, indicators, lists, a live map and selectors
that **cross-filter each other in real time**.

There is no app build — "running" means loading it inside QGIS. Copy the
`qgis_dashboards/` folder into your QGIS profile's `python/plugins/` directory
and enable **QGIS Dashboard** under *Plugins → Manage*. Full architecture and
developer notes are in [`CLAUDE.md`](CLAUDE.md).

## Author

Built by **Isaac Enage** · <isaacenagework@gmail.com>
