# Public-gallery contributions via serverless intake

**Date:** 2026-06-20
**Status:** Approved — ready for implementation

## Problem

The plugin's **Publish to public** commits a dashboard *directly* to
`isaacenage/QGIS-Plugins` via the GitHub Git Data API, using a token that needs
**Contents: write** on that repo. GitHub has no anonymous writes, so only the
repo owner (or an explicitly-added collaborator) can publish. The plugin's
users are **non-technical GIS specialists** who do not have GitHub accounts and
cannot be expected to create tokens. The goal is to let *anyone* contribute a
dashboard to the public gallery while the owner moderates what goes live.

A Google-Drive intake was considered and rejected: writing to a Drive the owner
controls requires an embedded credential (service-account JSON / OAuth secret),
which leaks once shipped in a public plugin and grants direct access to the
owner's Google account. (Drive writes are impossible with an API key alone.)

## Solution overview

A single **serverless intake endpoint** on the existing Next.js/Vercel site.
The plugin POSTs a finished dashboard to it. The endpoint holds a **server-side
bot token** (a Vercel environment variable, never shipped in the plugin) and
opens a **Pull Request** that adds the dashboard's files. Vercel auto-builds a
**PR preview deployment**, so the owner can open the real, live dashboard
before merging. **Merge = goes live; close = rejected.** Contributors need no
account and no token — only the public endpoint URL.

```
GIS user clicks "Publish to public" (title / author / description)
        │  HTTPS POST {title, author, description?, html_gz_b64, thumb_b64}
        ▼
https://qgis.byzenterra.org/api/submit        (Next.js route, Vercel)
        │  validate → unique slug → GitHub REST API with GITHUB_BOT_TOKEN
        ▼
PR on isaacenage/QGIS-Plugins adding
  public/dashboards/<slug>/{index.html, thumb.png, meta.json}
        ▼
Vercel preview deployment of the PR
        ▼
Owner opens preview → merge (LIVE) or close (REJECTED)
```

## Components

### 1. `app/api/submit/route.ts` (new, server-only)
- **Method:** `POST`. Runtime: Node.js (needs `zlib` gunzip + larger body).
- **Request body** (JSON):
  `{ title: string, author: string, description?: string,
     html_gz_b64: string, thumb_b64: string }`
  - `html_gz_b64` — base64 of **gzipped** `index.html`.
  - `thumb_b64` — base64 of the PNG thumbnail.
- **Why gzip:** Vercel serverless functions cap request bodies at ~4.5 MB.
  Self-contained dashboards (embedded data + inlined Leaflet) routinely exceed
  that uncompressed; HTML compresses ~5–10×, so gzip keeps typical dashboards
  (~20–40 MB raw) under the wire budget. The plugin keeps its existing
  oversize-data guard for anything still too large.
- **Validation (fail-fast, user-safe messages):**
  - Required fields present and of correct type.
  - Decoded gzip size ≤ `MAX_HTML_BYTES` (25 MB) and the base64 wire payload
    within the function body limit.
  - Decompressed HTML contains the dashboard runtime marker (sanity check it is
    actually an exported dashboard, not arbitrary upload).
  - `title`/`author` length caps; `description` optional, capped.
- **Behavior:**
  1. `slug = uniqueSlug(slugify(title))` — `slugify` ported from
     `github_publish.py`; uniqueness checked against existing
     `public/dashboards/*/` folders on the default branch **and** open
     `submit/*` PR branches; collisions get `-2`, `-3`, ….
  2. Create branch `submit/<slug>` off the default branch's head.
  3. Commit three files via the Git Data API (blobs → tree → commit → ref),
     mirroring the current Python client, all server-side:
     - `public/dashboards/<slug>/index.html`
     - `public/dashboards/<slug>/thumb.png`
     - `public/dashboards/<slug>/meta.json` — the manifest entry
       (`{slug, title, author, date, path, thumb, description?}`).
  4. Open a PR: title `Dashboard submission: <title>`, body with author /
     description / prospective public URL.
  5. Respond `{ ok: true, pr_url, slug, view_url }` (the view URL is the URL it
     *will* have once merged).
- **GitHub access:** raw `fetch` to `https://api.github.com` with
  `Authorization: Bearer ${process.env.GITHUB_BOT_TOKEN}` — no new npm
  dependency (the site stays next/react-only).
- **Abuse controls (light — the merge gate is the real control):** hard payload
  size cap; reject non-dashboard payloads; best-effort guard on the number of
  open `submit/*` PRs. Nothing is public until merged, so spam only fills a PR
  queue that can be bulk-closed. Robust per-IP rate-limiting (Upstash KV) is a
  documented future upgrade, not in scope.

### 2. Conflict-free manifest
**Problem:** `public/dashboards/manifest.json` is one shared file; two
concurrent submissions editing it would merge-conflict.
**Fix:** each submission writes its own `meta.json` in its folder, and
`manifest.json` is **generated at build time** from all `meta.json` files.
- `scripts/gen-manifest.mjs` (new) — scans `public/dashboards/*/meta.json`,
  sorts by date desc, writes `public/dashboards/manifest.json`.
- Wired as `"prebuild"` in `package.json` so `next build` (run by Vercel on
  every deploy, including PR merges) regenerates it automatically.
- Submission PRs **never touch** the shared manifest → no conflicts.
- The gallery reader `lib/manifest.ts → loadManifest()` is **unchanged**
  (still fetches `/dashboards/manifest.json`); the contract is identical.
- The committed `manifest.json` becomes a generated artifact; the by-hand
  seeding path documented in `public/dashboards/README.md` is updated to add a
  folder + `meta.json` instead of editing `manifest.json`.

### 3. Security hardening — viewer iframe
Dashboards are served from the site's **own origin** (`/dashboards/...`). The
viewer iframe currently uses
`sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"`.
`allow-scripts` + `allow-same-origin` together **disables** the sandbox,
letting embedded JS reach the site's origin. Harmless while only the owner
publishes; an XSS hole once authors are untrusted.
- **Change** `components/dashboard-frame.tsx` to `sandbox="allow-scripts
  allow-popups"` (drop `allow-same-origin` and `allow-popups-to-escape-sandbox`).
- Verify during implementation that an exported dashboard remains fully
  interactive (cross-filter, charts, Leaflet) under that sandbox; the export is
  self-contained and reads no `localStorage`, so it should. If any feature
  needs same-origin, serve dashboards from a separate subdomain instead
  (documented fallback, not expected to be needed).
- The **review gate remains the primary control** — every dashboard is
  previewed before going live.

### 4. Plugin changes (net simplification)
- `publish_dialog.py` — remove **GitHub token / repository / branch** fields.
  Keep title (prefilled from project), author, description. Success screen
  becomes "Submitted for review — it will appear in the gallery once approved,"
  with a link to the PR and/or gallery. The local-token security note is
  removed (no token is stored anymore).
- `publisher.py` — replace the multi-step Git Data flow with: build HTML
  (`build_dashboard_html`) + thumbnail (`render_thumbnail_png`), **gzip** the
  HTML, base64 both, POST one JSON payload to the submit endpoint; map HTTP
  errors to `PublishError` with user-safe messages. Keep `render_thumbnail_png`
  and `oversize_referenced_layers`.
- `github_client.py` — the GitHub-API client is no longer used by the plugin
  (its logic moves into the route). Replaced by a thin
  `submit_client.py` POST helper using `QgsNetworkAccessManager` (same blocking
  event-loop + timeout pattern), raising `PublishError`. `github_client.py` is
  removed from the plugin and de-registered from `pb_tool.cfg`/`Makefile`.
- `github_publish.py` — pure helpers (`slugify`, `build_entry`, manifest logic)
  are ported to TypeScript in the route/generator. The Python module is reduced
  to what the plugin still needs (the endpoint URL constant + any payload
  helper) or removed; `DEFAULT_REPO`/branch/token constants are deleted from
  the plugin. The only server coordinate left in the plugin is the **public
  endpoint URL**.
- Endpoint URL constant, e.g. `SUBMIT_URL = "https://qgis.byzenterra.org/api/submit"`.

### 5. Owner setup (manual — documented in the spec and surfaced at hand-off)
Steps that require the owner's own accounts (cannot be automated):
1. Create a **fine-grained** GitHub token scoped to `isaacenage/QGIS-Plugins`
   with **Contents: Read and write** + **Pull requests: Read and write**.
2. Add it in Vercel → Project → Settings → Environment Variables as
   `GITHUB_BOT_TOKEN` (Production + Preview).
3. Confirm Vercel preview deployments are enabled (default).

## Data flow / contracts

- **Plugin → endpoint:** JSON `{title, author, description?, html_gz_b64, thumb_b64}`.
- **Endpoint → GitHub:** branch + 3-file commit + PR (Git Data API).
- **`meta.json` (per dashboard):** the `DashboardEntry` shape from
  `lib/manifest.ts` (`{slug, title, author, date, path, thumb, description?}`),
  `path`/`thumb` relative to `public/` (e.g. `dashboards/<slug>/index.html`).
- **Build → gallery:** `prebuild` regenerates `manifest.json`; `loadManifest()`
  fetches it unchanged.

## Error handling

- Endpoint returns structured JSON errors with a `message` field and an
  appropriate HTTP status (400 validation, 413 too large, 429 too many open
  submissions, 500 GitHub/transport). The plugin surfaces `message` verbatim in
  a `PublishError` dialog.
- Plugin: transport failures and non-2xx responses map to `PublishError` with a
  plain message ("Couldn't reach the gallery service", "The gallery service
  rejected the dashboard: <message>").
- Missing `GITHUB_BOT_TOKEN` on the server → 500 with a generic message (logged
  server-side); never leak the token or internal detail to the client.

## Testing

- **TypeScript (pure, no network):** `slugify`, `uniqueSlug` (collision →
  suffix), `buildEntry`/`meta.json` shape, and `gen-manifest` (folder scan →
  sorted manifest) — extracted into a pure module and unit-tested.
- **Python:** payload builder + gzip round-trip (pure, runs under bare
  `PYTHONPATH`); update/replace `test/test_github_publish.py` for whatever pure
  logic remains. The QGIS-touching POST path is exercised manually in QGIS.
- **Manual:** end-to-end — publish from the plugin against a deployed
  preview/production endpoint, confirm a PR opens with a working preview, merge,
  confirm the gallery shows the card and the viewer renders it under the tighter
  sandbox.

## Trade-offs / out of scope

- Publishing is **no longer instant** — it is "submitted, goes live on
  approval." This matches the owner's manual-promotion intent.
- No contributor accounts, no post-publish edit/delete by contributors (the
  owner manages via the repo). A polished Blob-backed admin UI is explicitly out
  of scope.
- Bot PRs are authored by the owner's own token (acceptable for a solo
  maintainer); a dedicated machine-user account is a documented future option.
- Large dashboards still bloat git history (status quo — the direct-commit model
  already did this); acceptable for a curated, low-volume gallery.
- Robust per-IP rate-limiting (Upstash KV) is a future upgrade.
