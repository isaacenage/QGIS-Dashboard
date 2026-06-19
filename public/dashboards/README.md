# Published dashboards

This folder is the public gallery's data. Each published dashboard is one
self-contained `index.html`, a `thumb.png`, and a `meta.json` describing it.

```
public/dashboards/
├─ manifest.json          # GENERATED — do not edit by hand
└─ <slug>/
   ├─ index.html          # the self-contained, interactive dashboard
   ├─ thumb.png           # gallery card thumbnail
   └─ meta.json           # this dashboard's manifest entry
```

`meta.json` entry shape:

```json
{
  "slug": "harbor-traffic",
  "title": "Harbor Traffic",
  "author": "Isaac Enage",
  "date": "2026-06-19",
  "path": "dashboards/harbor-traffic/index.html",
  "thumb": "dashboards/harbor-traffic/thumb.png",
  "description": "Optional one-line summary shown on the card."
}
```

## How dashboards get here

Normally a contributor's **Publish to public** in the plugin submits a dashboard
to the site's `/api/submit` endpoint, which opens a **Pull Request** adding the
folder above. The maintainer previews it (Vercel builds a preview deployment of
the PR) and merges to publish. Contributors need no account or token.

## `manifest.json` is generated — never edit it

`manifest.json` is the file the gallery fetches at runtime, but it is **built
from every `<slug>/meta.json`** by `scripts/gen-manifest.mjs`, wired as the
`prebuild` step. `next build` (which Vercel runs on every deploy, including PR
merges) regenerates it automatically. Because each submission writes only its
own `meta.json` and never this shared file, concurrent submissions never
merge-conflict.

To regenerate locally: `npm run gen-manifest`.

## Seeding the gallery by hand

Export a dashboard from QGIS (Export to HTML), then create
`<slug>/index.html`, add a `thumb.png`, and write a `<slug>/meta.json` with the
shape above. Run `npm run gen-manifest` (or just `npm run build`) to refresh
`manifest.json`. Paths inside `meta.json` are relative to `public/`.
