# Repo restructure — plugins/ source directory

**Date:** 2026-06-19
**Author:** Isaac Enage (with Claude)

## Goal

Separate plugin **source code** from website **routes** so the repo scales as
more QGIS plugins are added. The plugin's installable Python folder moves out of
the repo root into a dedicated `plugins/` directory; the website (Next.js app)
keeps its required root config and its per-plugin route segments under `app/`.

This is the `plugins/`-sibling structure (chosen over a Turborepo `apps/web`
split and over burying Python in the `app/` route tree).

## Target structure

```
QGIS Plugins/
├─ app/                  website routes (one segment per plugin)
│  ├─ page.tsx           hub  (/)
│  └─ qdashboards/       (/qdashboards …)
├─ components/  lib/  public/
├─ plugins/              ALL plugin source (installable QGIS plugins)
│  └─ qgis_dashboards/   the QGIS Dashboard plugin (moved here, intact)
├─ docs/
├─ next.config.ts  package.json  tsconfig.json  postcss.config.mjs
└─ README.md  LICENSE
```

Two things per plugin live in two places, by design:
- **Web pages** → `app/<slug>/`
- **Plugin source** → `plugins/<name>/`

## The move

`qgis_dashboards/` → `plugins/qgis_dashboards/`, moved **whole and intact** so
the Plugin Builder layout (`pb_tool.cfg`, `Makefile`, `metadata.txt`,
`resources/`, `test/`, relative imports) keeps working and the folder is still
copyable into a QGIS `python/plugins/` directory. Done with a filesystem move +
`git add -A` so git records renames and the untracked `__pycache__` (gitignored)
is not left behind at the old path.

## Reference updates (the only places the old root path leaks out)

1. `next.config.ts` — `outputFileTracingExcludes` `./qgis_dashboards/**` →
   `./plugins/**` (exclude all plugin source from the web build trace).
2. `tsconfig.json` — `exclude` `"qgis_dashboards"` → `"plugins"`.
3. `app/qdashboards/guide/page.tsx` — install instruction folder name →
   `plugins/qgis_dashboards`.
4. `components/logo.tsx` — provenance comment → `plugins/qgis_dashboards/icons.py`.
5. `CLAUDE.md` — all path mentions (`qgis_dashboards/` → `plugins/qgis_dashboards/`,
   `cd qgis_dashboards` → `cd plugins/qgis_dashboards`).
6. `README.md` — plugin paths + "adding a plugin" steps point at `plugins/`.

`.gitignore` patterns are path-agnostic (`__pycache__/`, `*.py[cod]`, `*.zip`)
and need no change.

## Unaffected (deliberately)

- Plugin internals: relative imports, and `github_publish.py`'s
  `public/dashboards` paths (those are paths *inside the target website repo*
  for the GitHub publish API, not local filesystem paths).
- The website never imports Python.
- Dev/build commands at root (`npm run dev`, `npm run build`).
- Historical dated specs in `docs/` (left as records of the repo at their time).

## Verification

- `npm run build` passes (route map unchanged: `/`, `/qdashboards/*`).
- From `plugins/qgis_dashboards/`: `python -m py_compile github_publish.py`
  and `python test/test_github_publish.py` pass.
- `grep -rn "qgis_dashboards"` shows no stale **root-relative** references
  outside `plugins/` and the historical `docs/` specs.
