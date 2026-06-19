import Link from "next/link";
import { HeroCrossfilterDemo } from "@/components/hero-crossfilter-demo";
import { Section } from "@/components/section";
import { FeatureTile } from "@/components/feature-tile";
import { GalleryGrid } from "@/components/gallery-grid";
import { ThemeSwatch, Preset } from "@/components/theme-swatch";
import { Icons } from "@/components/icons";
import { SITE, withBase } from "@/lib/site";

const PRESETS: Preset[] = [
  {
    name: "Summarizer Blue",
    window: "#fafafa",
    surface: "#ffffff",
    text: "#252b33",
    accent: "#2b7de9",
    series: ["#2b7de9", "#13a10e", "#c19c00", "#d13438", "#8764b8"],
  },
  {
    name: "Indigo SaaS",
    window: "#f5f3ff",
    surface: "#ffffff",
    text: "#312e81",
    accent: "#6366f1",
    series: ["#6366f1", "#22c55e", "#f59e0b", "#ec4899", "#06b6d4"],
  },
  {
    name: "Midnight Slate",
    window: "#0f172a",
    surface: "#1e293b",
    text: "#e2e8f0",
    accent: "#38bdf8",
    series: ["#38bdf8", "#34d399", "#fbbf24", "#f87171", "#a78bfa"],
  },
  {
    name: "Rose Editorial",
    window: "#fff1f2",
    surface: "#ffffff",
    text: "#3f1d2e",
    accent: "#be185d",
    series: ["#be185d", "#9d174d", "#b45309", "#0f766e", "#7c3aed"],
  },
];

const FEATURES = [
  { icon: "indicator", name: "Indicator", role: "target", desc: "A big aggregate value with optional reference, trend, an icon and animated counting." },
  { icon: "chart", name: "Chart", role: "source · target", desc: "23 chart types — bar, line, area, pie, donut, scatter, histogram and more. Click to filter." },
  { icon: "pivot", name: "Pivot", role: "source · target", desc: "A cross-tab matrix with row/column fields, aggregates and grand totals. Cells filter on click." },
  { icon: "list", name: "List", role: "target", desc: "A feature table; picking a row zooms and flashes the matching feature on the map." },
  { icon: "map", name: "Live map", role: "spatial source", desc: "A live mirror of your QGIS canvas — pan, identify, fly-to, and push an extent filter to other tiles." },
  { icon: "selector", name: "Selector", role: "source", desc: "A dropdown of unique values — the cleanest way to drive every other tile from one choice." },
  { icon: "text", name: "Text", role: "presentational", desc: "Free text and headings, edited in place — titles, notes and annotations for the page." },
  { icon: "image", name: "Image", role: "presentational", desc: "Drop in a logo or figure — PNG, JPG, SVG or animated GIF, scaled to the tile." },
  { icon: "header", name: "Header", role: "presentational", desc: "A brand banner tile with a styled title and an anchored logo slot for the dashboard." },
] as const;

export default function HomePage() {
  return (
    <>
      {/* ---------- hero ---------- */}
      <section className="relative overflow-hidden border-b border-line">
        <div className="pointer-events-none absolute inset-0 -z-10 opacity-[0.6]">
          <div className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-cat-blue/15 blur-3xl" />
          <div className="absolute right-0 top-40 h-72 w-72 rounded-full bg-cat-amber/10 blur-3xl" />
        </div>
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-20 lg:grid-cols-[1.05fr_1.1fr] lg:py-28">
          <div>
            <p className="eyebrow">Free QGIS plugin · cross-filtering built in</p>
            <h1 className="display mt-5 text-4xl text-ink sm:text-5xl lg:text-[3.4rem]">
              Your QGIS layers,
              <br />
              <span className="text-accent">wired together</span> as a live
              dashboard.
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">
              Drop charts, indicators, lists and a live map onto a canvas inside
              your QGIS project. Click any value and every tile cross-filters in
              real time — no export, no separate web app, no cost.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href={withBase("/guide#install")} className="btn btn-primary">
                Install the plugin
              </Link>
              <Link href={withBase("/gallery")} className="btn btn-ghost">
                Explore the gallery
              </Link>
            </div>
            <p className="stat mt-6 text-xs text-faint">
              Try the demo on the right → click a zone to filter.
            </p>
          </div>
          <div className="lg:pl-4">
            <HeroCrossfilterDemo />
          </div>
        </div>
      </section>

      {/* ---------- what it is ---------- */}
      <Section
        eyebrow="What it is"
        title="An ArcGIS-Dashboards experience, native to QGIS"
        lead={
          <>
            QGIS is a powerful map-maker, but turning those maps into an
            interactive dashboard used to mean a paid platform or a separate web
            app. QGIS Dashboard fills that gap — dashboards that live right
            inside your <span className="stat">.qgz</span> project, driven by the
            vector layers you already have.
          </>
        }
      >
        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          {[
            { k: "Inside QGIS", v: "Layout and config save into your project file. Reopen and it's exactly as you left it." },
            { k: "Data-driven", v: "Every tile binds to a layer through the QGIS expression engine — no copies, no sync." },
            { k: "Cross-filtered", v: "Selecting in one tile filters all the others, the way a real BI dashboard behaves." },
          ].map((c) => (
            <div key={c.k} className="tile p-5">
              <div className="display text-lg text-accent">{c.k}</div>
              <p className="mt-2 text-sm leading-relaxed text-muted">{c.v}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* ---------- features ---------- */}
      <div className="border-y border-line bg-surface/40">
        <Section
          id="features"
          eyebrow="The tiles"
          title="Nine element types, one canvas"
          lead="Add tiles from an icon picker, arrange them freely, then lock the layout to use it. Sources push filters; targets react."
        >
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <FeatureTile key={f.name} icon={f.icon} name={f.name} role={f.role}>
                {f.desc}
              </FeatureTile>
            ))}
          </div>
        </Section>
      </div>

      {/* ---------- cross-filter explainer ---------- */}
      <Section
        id="cross-filter"
        eyebrow="The idea"
        title={
          <>
            Click once. <span className="text-accent">Everything</span> responds.
          </>
        }
        lead="Cross-filtering is the whole point. Wiring is explicit and user-editable — you decide which tiles a source filters, following the ArcGIS source → action → target model, scoped per page."
      >
        <div className="mt-10 grid items-center gap-8 lg:grid-cols-2">
          <ol className="space-y-5">
            {[
              { n: "01", t: "Pick a source", d: "A chart bar, a pivot cell, a selector value or the map's extent." },
              { n: "02", t: "It pushes a filter", d: "The selection becomes a QGIS expression on the shared bus." },
              { n: "03", t: "Targets recompute", d: "Every connected tile re-queries its layer under the combined filter — instantly." },
            ].map((s) => (
              <li key={s.n} className="flex gap-4">
                <span className="stat text-sm text-faint">{s.n}</span>
                <div>
                  <div className="font-semibold">{s.t}</div>
                  <p className="text-sm text-muted">{s.d}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="tile p-6">
            <Icons.crossfilter className="h-8 w-8 text-accent" />
            <p className="mt-4 leading-relaxed text-muted">
              Filters never touch your project layers — each tile queries through
              its own <span className="stat text-ink">QgsFeatureRequest</span>, so
              other plugins and views are untouched. Build mode moves and resizes
              tiles; Use mode locks the layout and turns interaction on.
            </p>
          </div>
        </div>
      </Section>

      {/* ---------- themes ---------- */}
      <div className="border-y border-line bg-surface/40">
        <Section
          id="themes"
          eyebrow="Make it yours"
          title="Twelve coordinated themes — or your own"
          lead="Pick a ready-made palette-and-font pairing, light or dark, or fine-tune every color, the chart palette and the type. Themes restyle the canvas; the export carries them through."
        >
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {PRESETS.map((p) => (
              <ThemeSwatch key={p.name} preset={p} />
            ))}
          </div>
        </Section>
      </div>

      {/* ---------- gallery teaser ---------- */}
      <Section
        eyebrow="In the wild"
        title="Dashboards people have published"
        lead="Built with the plugin and shared straight to this gallery. Open any one — it stays fully interactive in your browser."
      >
        <div className="mt-10">
          <GalleryGrid limit={3} showEmpty />
        </div>
        <div className="mt-8">
          <Link href={withBase("/gallery")} className="btn btn-ghost">
            See the whole gallery
          </Link>
        </div>
      </Section>

      {/* ---------- who made it + CTA ---------- */}
      <div className="border-t border-line bg-surface/40">
        <Section
          eyebrow="Who made it"
          title="A free answer to a simple question"
          lead={
            <>
              &ldquo;Are there any <i>free</i> dashboards in QGIS that connect to
              the map we make?&rdquo; A friend&rsquo;s question pointed at a real
              gap — so {SITE.author} built QGIS Dashboard to fill it. It&rsquo;s
              completely free and open-source; anyone can use it.
            </>
          }
        >
          <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
            <a href={withBase("/guide#install")} className="btn btn-primary">
              Get started
            </a>
            <a href={SITE.repo} target="_blank" rel="noreferrer" className="btn btn-ghost">
              View source on GitHub
            </a>
            <a href={`mailto:${SITE.authorEmail}`} className="stat text-sm text-muted hover:text-accent-ink">
              {SITE.authorEmail}
            </a>
          </div>
        </Section>
      </div>
    </>
  );
}
