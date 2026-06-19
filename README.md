# QGIS Dashboard

Build **ArcGIS-Dashboards-style interactive dashboards** from your QGIS project's
vector layers — charts, indicators, lists, a live map and selectors that
**cross-filter each other in real time**. Free and open-source.

This repository holds **two things**:

| Path | What it is |
|------|------------|
| [`qgis_dashboards/`](qgis_dashboards/) | **The QGIS plugin** (Python / PyQt). The shippable plugin — install it into QGIS. |
| repo root (`app/`, `components/`, `lib/`, `public/`) | **The website** — a Next.js app (marketing, guide, and the public dashboard **gallery**), deployed to Vercel at `qgis.byzenterra.org/qdashboard`. |

The two never import each other. They meet at a single contract:
[`public/dashboards/manifest.json`](public/dashboards/) — the plugin's
*Publish to public* writes it; the website's gallery reads it.

## Website (repo root)

```bash
npm install
npm run dev      # http://localhost:3000/qdashboard
npm run build    # production build
```

Served under the `/qdashboard` base path (configured in `next.config.ts`).
Published dashboards live as static files in `public/dashboards/` — see that
folder's README for the layout and how to seed one by hand.

## Plugin (`qgis_dashboards/`)

A QGIS plugin; there is no app build — "running" means loading it inside QGIS.
Copy the `qgis_dashboards/` folder into your QGIS profile's `python/plugins/`
directory and enable **QGIS Dashboard** under *Plugins → Manage*. Full
architecture and developer notes are in [`CLAUDE.md`](CLAUDE.md).

## Author

Built by **Isaac Enage** · <isaacenagework@gmail.com>
