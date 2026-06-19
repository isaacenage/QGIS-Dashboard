import Link from "next/link";
import { Logo } from "./logo";
import type { Plugin } from "@/lib/plugins";

// A plugin tile in the hub's "All plugins" grid. Live plugins link to their
// section; the grid pairs these with a dashed "coming soon" slot.
export function PluginCard({ plugin }: { plugin: Plugin }) {
  return (
    <Link
      href={plugin.href}
      className="tile group flex flex-col p-6 transition-transform hover:-translate-y-0.5"
    >
      <Logo size={36} />
      <h3 className="display mt-4 text-lg text-ink">{plugin.name}</h3>
      <p className="mt-2 flex-1 text-sm leading-relaxed text-muted">
        {plugin.blurb}
      </p>
      <span className="mt-4 text-sm font-semibold text-accent-ink group-hover:underline">
        Explore →
      </span>
    </Link>
  );
}

// The placeholder slot that keeps the grid from feeling empty before plugin #2.
export function ComingSoonCard() {
  return (
    <div className="flex min-h-[160px] flex-col items-center justify-center rounded-card border border-dashed border-line-strong p-6 text-center">
      <span className="display text-lg text-faint">More plugins</span>
      <p className="mt-1 text-sm text-faint">coming soon</p>
    </div>
  );
}
