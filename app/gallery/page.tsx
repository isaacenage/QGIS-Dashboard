import type { Metadata } from "next";
import { Section } from "@/components/section";
import { GalleryGrid } from "@/components/gallery-grid";

export const metadata: Metadata = {
  title: "Gallery",
  description:
    "Interactive dashboards built with the QGIS Dashboard plugin and published to the public gallery. Open any one — it stays fully interactive in your browser.",
};

export default function GalleryPage() {
  return (
    <Section
      eyebrow="Public gallery"
      title="Dashboards built with QGIS Dashboard"
      lead="Every card below is a real dashboard published from the plugin. Click one to open it full-size — cross-filtering, charts and the live map all work right here in your browser."
    >
      <div className="mt-12">
        <GalleryGrid showEmpty />
      </div>
    </Section>
  );
}
