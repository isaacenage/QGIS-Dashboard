import type { NextConfig } from "next";

// The site is served from a sub-path of an existing domain:
//   https://qgis.byzenterra.org/qdashboard
// basePath makes every route + asset resolve under /qdashboard, both in dev
// (http://localhost:3000/qdashboard) and on Vercel. NEXT_PUBLIC_BASE_PATH lets
// client code (manifest fetch, iframe src) prepend the same prefix.
const basePath = "/qdashboard";

const nextConfig: NextConfig = {
  basePath,
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
  // Published dashboards live as static files under public/dashboards/ and are
  // served verbatim; nothing to transform there.
  outputFileTracingExcludes: {
    "*": ["./qgis_dashboards/**"],
  },
};

export default nextConfig;
