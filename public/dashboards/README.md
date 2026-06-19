# Published dashboards

This folder is the public gallery's data. Each published dashboard is one
self-contained `index.html` plus a `thumb.png`, listed in `manifest.json`.

```
public/dashboards/
├─ manifest.json          # array of entries (the gallery reads this)
└─ <slug>/
   ├─ index.html          # the self-contained, interactive dashboard
   └─ thumb.png           # gallery card thumbnail
```

`manifest.json` entry shape:

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

Normally the plugin's **Publish to public** writes all of this for you. To seed
the gallery by hand: export a dashboard from QGIS (Export to HTML), drop it at
`<slug>/index.html`, add a `thumb.png`, and append an entry to `manifest.json`.
Paths are relative to `public/`; the site prepends its `/qdashboard` base path.
