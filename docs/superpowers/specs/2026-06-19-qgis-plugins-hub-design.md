# QGIS Plugins hub — design

**Date:** 2026-06-19
**Author:** Isaac Enage (with Claude)

## Goal

Refactor the existing single-plugin website so the repo root domain becomes an
umbrella **QGIS Plugins** hub, and the current QGIS Dashboard marketing site
moves under `/qdashboards`. The repo becomes the home for *all* of Isaac
Enage's QGIS plugins; `qgis_dashboards/` (the Python plugin source) stays put
and is never part of the website's routing.

This is **one Next.js app** with route segments — not a new app, not a folder
move on disk. URL paths come from the `app/` route tree, not directory
location.

## Target URL map

| URL | Content |
|-----|---------|
| `/` | NEW **QGIS Plugins** hub (rich showcase) |
| `/qdashboards` | QGIS Dashboard landing (the former homepage) |
| `/qdashboards/gallery` | Published-dashboard gallery |
| `/qdashboards/guide` | Plugin guide |
| `/qdashboards/view` | Public dashboard viewer (iframe) |
| `/dashboards/**` | Published dashboard static files (in `public/`, served at root) |

The previous global `basePath: "/qdashboard"` is removed. The `/qdashboards`
prefix is now a real route segment, applied to dashboard page links by the
`withBase()` helper (constant prefix, not a Next basePath).

## Architecture

### Routing & layouts (nested)
- `app/layout.tsx` (root) — html/body/fonts + hub-level metadata
  (`QGIS Plugins`). Renders `{children}` only; no shared header/footer here.
- `app/page.tsx` — the NEW hub page; renders its own `HubHeader` / `HubFooter`.
- `app/qdashboards/layout.tsx` (new) — wraps dashboard pages in the existing
  `SiteHeader` + `<main>` + `SiteFooter`; sets dashboard metadata
  (`QGIS Dashboard`).
- `app/qdashboards/{page,gallery,guide,view}` — the former `app/{page,…}`,
  moved verbatim.

### Config
- `next.config.ts` — drop `basePath` and the `NEXT_PUBLIC_BASE_PATH` env block;
  keep `outputFileTracingExcludes` (still excludes `qgis_dashboards/`).
  **Requires a `npm run dev` restart** (config changes are not hot-reloaded).

### Link prefixing (`lib/site.ts`)
- `withBase(path)` keeps prefixing dashboard page links, now with the fixed
  constant `"/qdashboards"` (no longer read from env).
- `viewUrl(slug)` → `/qdashboards/view?d=<slug>`.
- `SITE` stays the **dashboard** identity (`name: "QGIS Dashboard"`). Add a
  separate `HUB` identity (`name: "QGIS Plugins"`, tagline, author, repo,
  github profile, email). `SITE.repo` repointed to
  `github.com/isaacenage/QGIS-Plugins`.

### Static assets (`lib/manifest.ts`)
Published dashboards live in `public/dashboards/` and are served from the root
(`/dashboards/...`) now that basePath is gone. `loadManifest`, `dashboardSrc`,
and `thumbSrc` use plain `/dashboards/...` paths (drop `withBase` for these —
they are assets, not routes).

### Hub page (Direction A — centered + spotlight)
Sections, reusing existing design tokens (`globals.css`) and `Logo`:
1. **HubHeader** — `QGIS Plugins` wordmark + nav (Plugins / About / GitHub).
2. **Centered hero** — headline "Tools that make QGIS do more", collection
   intro crediting Isaac Enage, CTAs (Explore QGIS Dashboard → `/qdashboards`,
   GitHub).
3. **Featured spotlight** — QGIS Dashboard screenshot/preview + pitch + feature
   chips + "Open QGIS Dashboard →".
4. **All plugins grid** — one rich QGIS Dashboard card + a dashed
   "More coming soon" slot, driven by a `lib/plugins.ts` registry.
5. **About the maker** — short Isaac Enage bio + GitHub/Email.
6. **HubFooter**.

New small components: `components/hub-header.tsx`, `components/hub-footer.tsx`,
`components/plugin-card.tsx`, `components/plugin-spotlight.tsx`. New
`lib/plugins.ts` (plugin registry: name, slug/href, blurb, features, status).
`components/logo.tsx` gains a `HubWordmark` ("QGIS Plugins").

### Plugin contract (one line)
`qgis_dashboards/github_publish.py` — `PUBLIC_BASE_URL` →
`https://qgis.byzenterra.org/qdashboards` so the plugin's
*Publish to public* writes correct public view URLs. This is the only edit to
`qgis_dashboards/`.

### Docs
`README.md` updated: repo is now a multi-plugin store + hub site; dev URL note
(`/` hub, `/qdashboards` dashboard); footer/domain string `/qdashboards`.

## Out of scope (YAGNI)
- No second plugin yet (registry has room; "coming soon" slot only).
- No newsletter/contact backend.
- No Vercel multi-zones/separate apps.
- No change to the plugin's publish *path* (`public/dashboards/`), only its URL.

## Verification
- `npm run build` passes (type-check + route compile).
- `python -m py_compile qgis_dashboards/github_publish.py`.
- Manual: `/` shows hub; `/qdashboards`, `/qdashboards/gallery|guide|view`
  resolve; gallery still loads `/dashboards/manifest.json`.
