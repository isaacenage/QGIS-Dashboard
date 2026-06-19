import type { Metadata } from "next";
import { SITE } from "@/lib/site";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

// The QGIS Dashboard section. Root layout owns <html>/<body>/fonts; this nested
// layout adds the dashboard's own chrome (header + footer) and its title scope,
// so the hub at "/" stays free of the plugin-branded navigation.
export const metadata: Metadata = {
  title: {
    default: `${SITE.name} — ${SITE.tagline}`,
    template: `%s · ${SITE.name}`,
  },
  description:
    "A free, open-source QGIS plugin for building ArcGIS-Dashboards-style interactive dashboards from your project's vector layers — charts, indicators, lists, a live map and selectors that cross-filter each other in real time.",
};

export default function DashboardSectionLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <SiteHeader />
      <main>{children}</main>
      <SiteFooter />
    </>
  );
}
