import Link from "next/link";
import { Logo } from "./logo";
import type { Plugin } from "@/lib/plugins";

// The featured-plugin block on the hub: a stylized dashboard preview beside the
// pitch. The preview echoes the plugin's signature — a grid of tiles where the
// "unrelated" ones dim, the cross-filter language used across the site.
export function PluginSpotlight({ plugin }: { plugin: Plugin }) {
  return (
    <div className="tile grid items-center gap-8 p-6 sm:p-8 lg:grid-cols-2">
      <PreviewBoard />
      <div>
        <Logo size={40} />
        <h3 className="display mt-4 text-2xl text-ink">{plugin.name}</h3>
        <p className="mt-3 leading-relaxed text-muted">{plugin.pitch}</p>
        <div className="mt-5 flex flex-wrap gap-2">
          {plugin.features.map((f) => (
            <span
              key={f}
              className="rounded-full bg-accent/8 px-3 py-1 text-xs font-medium text-accent-ink"
            >
              {f}
            </span>
          ))}
        </div>
        <div className="mt-7">
          <Link href={plugin.href} className="btn btn-primary">
            Open {plugin.name} →
          </Link>
        </div>
      </div>
    </div>
  );
}

// A small, decorative cross-filter board: the blue tiles are "selected", the
// rest dim — the dashboard's core interaction, rendered statically.
function PreviewBoard() {
  const tiles = [
    "active", "dim", "dim",
    "dim", "active", "dim",
    "dim", "dim", "active",
  ];
  return (
    <div
      className="aspect-[4/3] w-full rounded-card border border-line bg-paper p-4"
      aria-hidden
    >
      <div className="grid h-full grid-cols-3 grid-rows-3 gap-2.5">
        {tiles.map((state, i) => (
          <div
            key={i}
            className={
              state === "active"
                ? "rounded-lg bg-accent/85 shadow-sm"
                : "rounded-lg border border-line bg-surface opacity-40"
            }
          />
        ))}
      </div>
    </div>
  );
}
