import Link from "next/link";
import { HubHeader } from "@/components/hub-header";
import { HubFooter } from "@/components/hub-footer";
import { Section } from "@/components/section";
import { PluginSpotlight } from "@/components/plugin-spotlight";
import { PluginCard, ComingSoonCard } from "@/components/plugin-card";
import { PLUGINS, featuredPlugin } from "@/lib/plugins";
import { HUB } from "@/lib/site";

// The root QGIS Plugins hub (Direction A — centered hero + featured spotlight).
// Lives at "/", renders its own chrome; the dashboard site is under /qdashboards.
export default function HubPage() {
  const featured = featuredPlugin();

  return (
    <>
      <HubHeader />
      <main>
        {/* ---------- hero (centered) ---------- */}
        <section className="relative overflow-hidden border-b border-line">
          <div className="pointer-events-none absolute inset-0 -z-10 opacity-[0.6]">
            <div className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-cat-blue/15 blur-3xl" />
            <div className="absolute right-0 top-32 h-72 w-72 rounded-full bg-cat-amber/10 blur-3xl" />
          </div>
          <div className="mx-auto max-w-3xl px-5 py-20 text-center lg:py-28">
            <p className="eyebrow justify-center">
              Free &amp; open-source · built for QGIS
            </p>
            <h1 className="display mt-5 text-4xl text-ink sm:text-5xl lg:text-[3.4rem]">
              Tools that make
              <br />
              <span className="text-accent">QGIS do more</span>.
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-muted">
              A growing collection of free, open-source QGIS plugins by{" "}
              {HUB.author} — practical tools that extend the desktop GIS you
              already use. No subscriptions, no separate apps.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link href="/qdashboards" className="btn btn-primary">
                Explore QGIS Dashboard →
              </Link>
              <a
                href={HUB.repo}
                target="_blank"
                rel="noreferrer"
                className="btn btn-ghost"
              >
                View on GitHub
              </a>
            </div>
          </div>
        </section>

        {/* ---------- featured spotlight ---------- */}
        {featured && (
          <Section
            eyebrow="Featured plugin"
            title={featured.name}
            lead="The first tool in the collection — and the one that started it."
          >
            <div className="mt-10">
              <PluginSpotlight plugin={featured} />
            </div>
          </Section>
        )}

        {/* ---------- all plugins ---------- */}
        <div className="border-y border-line bg-surface/40">
          <Section
            id="plugins"
            eyebrow="The collection"
            title="All plugins"
            lead="Each one is free, open-source and installs straight into QGIS. The shelf grows over time."
          >
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {PLUGINS.map((p) => (
                <PluginCard key={p.slug} plugin={p} />
              ))}
              <ComingSoonCard />
            </div>
          </Section>
        </div>

        {/* ---------- about the maker ---------- */}
        <Section
          id="about"
          eyebrow="Who's behind this"
          title={
            <>
              Made by <span className="text-accent">{HUB.author}</span>
            </>
          }
          lead="I build free QGIS tools to fill gaps I kept hitting in real GIS work. Everything here is open-source — use it, fork it, suggest features."
        >
          <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
            <a
              href={HUB.github}
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary"
            >
              GitHub profile
            </a>
            <a href={HUB.repo} target="_blank" rel="noreferrer" className="btn btn-ghost">
              This repo
            </a>
            <a
              href={`mailto:${HUB.authorEmail}`}
              className="stat text-sm text-muted hover:text-accent-ink"
            >
              {HUB.authorEmail}
            </a>
          </div>
        </Section>
      </main>
      <HubFooter />
    </>
  );
}
