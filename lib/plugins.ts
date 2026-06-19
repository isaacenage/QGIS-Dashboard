// The catalog of plugins the hub lists. The repo is the home for every QGIS
// plugin Isaac Enage ships; each entry that is `status: "live"` links to its
// own section under the site (e.g. /qdashboards). Add a new plugin by adding a
// row here and creating its app/<slug>/ route segment.

export interface Plugin {
  slug: string; // route segment, e.g. "qdashboards"
  name: string;
  blurb: string; // one-line summary for the grid card
  pitch: string; // a fuller paragraph for the spotlight
  href: string; // where its card/CTA links (internal route or external)
  features: string[]; // short chips shown in the spotlight
  status: "live" | "soon";
}

export const PLUGINS: Plugin[] = [
  {
    slug: "qdashboards",
    name: "QGIS Dashboard",
    blurb:
      "Interactive, cross-filtering dashboards built from your vector layers.",
    pitch:
      "ArcGIS-Dashboards-style interactive dashboards built right inside your QGIS project. Charts, indicators, lists, a live map and selectors that cross-filter each other in real time — no export, no separate web app, no cost.",
    href: "/qdashboards",
    features: ["23 chart types", "Live cross-filter", "12 themes", "HTML export"],
    status: "live",
  },
];

/** The one plugin to spotlight on the hub (first live entry). */
export function featuredPlugin(): Plugin | undefined {
  return PLUGINS.find((p) => p.status === "live");
}
