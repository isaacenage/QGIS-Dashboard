// Centralized site copy + links, so pages and the plugin's published URLs stay
// in sync. The plugin builds the same view URL in github_publish.public_view_url.

export const SITE = {
  name: "QGIS Dashboard",
  tagline: "Interactive, cross-filtering dashboards — built right inside QGIS.",
  domain: "qgis.byzenterra.org",
  basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? "",
  author: "Isaac Enage",
  authorEmail: "isaacenagework@gmail.com",
  repo: "https://github.com/isaacenage/QGIS-Dashboard",
  issues: "https://github.com/isaacenage/QGIS-Dashboard/issues",
} as const;

/** Prefix an absolute-from-root path with the configured basePath. */
export function withBase(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${SITE.basePath}${p}`;
}

/** The public viewer URL for a published dashboard slug. */
export function viewUrl(slug: string): string {
  return withBase(`/view?d=${encodeURIComponent(slug)}`);
}
