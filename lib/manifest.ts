import { withBase } from "./site";

// The single contract between the plugin and this site. The plugin's
// "Publish to public" writes public/dashboards/manifest.json as an array of
// these entries; the gallery reads them. Paths are relative to public/.
export interface DashboardEntry {
  slug: string;
  title: string;
  author: string;
  date: string; // ISO YYYY-MM-DD
  path: string; // e.g. "dashboards/<slug>/index.html"
  thumb?: string; // e.g. "dashboards/<slug>/thumb.png"
  description?: string;
}

/** URL of a dashboard's self-contained index.html (for the viewer iframe). */
export function dashboardSrc(entry: DashboardEntry): string {
  return withBase(`/${entry.path.replace(/^\/+/, "")}`);
}

/** URL of a dashboard's thumbnail, or null if it has none. */
export function thumbSrc(entry: DashboardEntry): string | null {
  if (!entry.thumb) return null;
  return withBase(`/${entry.thumb.replace(/^\/+/, "")}`);
}

/**
 * Load the published-dashboard manifest at runtime (client-side fetch), so new
 * dashboards appear without a code change. Returns [] on any failure — a fresh
 * gallery with an empty manifest is a valid, expected state.
 */
export async function loadManifest(): Promise<DashboardEntry[]> {
  try {
    const res = await fetch(withBase("/dashboards/manifest.json"), {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    if (!Array.isArray(data)) return [];
    return data.filter(
      (e): e is DashboardEntry =>
        e && typeof e.slug === "string" && typeof e.path === "string",
    );
  } catch {
    return [];
  }
}
