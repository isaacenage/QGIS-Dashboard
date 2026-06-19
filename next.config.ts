import type { NextConfig } from "next";

// The site is served from the root of https://qgis.byzenterra.org/ — a single
// Next.js app whose "/" is the QGIS Plugins hub and whose "/qdashboards/*"
// route segment is the QGIS Dashboard site. There is no Next basePath: the
// "/qdashboards" prefix is a real route segment, applied to dashboard links by
// lib/site.ts → withBase(). Published dashboards live as static files under
// public/dashboards/ and are served verbatim from /dashboards/.
const nextConfig: NextConfig = {
  // The plugin source folder is not part of the website; never trace it.
  outputFileTracingExcludes: {
    "*": ["./qgis_dashboards/**"],
  },
};

export default nextConfig;
