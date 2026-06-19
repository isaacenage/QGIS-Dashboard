"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { DashboardEntry, loadManifest } from "@/lib/manifest";
import { withBase } from "@/lib/site";
import { GalleryCard } from "./gallery-card";

// Loads the manifest client-side so newly published dashboards show up without
// a rebuild. `limit` trims to a teaser; `showEmpty` toggles the empty state.

export function GalleryGrid({
  limit,
  showEmpty = true,
}: {
  limit?: number;
  showEmpty?: boolean;
}) {
  const [state, setState] = useState<"loading" | "ready">("loading");
  const [entries, setEntries] = useState<DashboardEntry[]>([]);

  useEffect(() => {
    let alive = true;
    loadManifest().then((data) => {
      if (!alive) return;
      // newest first
      const sorted = [...data].sort((a, b) => (a.date < b.date ? 1 : -1));
      setEntries(limit ? sorted.slice(0, limit) : sorted);
      setState("ready");
    });
    return () => {
      alive = false;
    };
  }, [limit]);

  if (state === "loading") {
    return (
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: limit ?? 3 }).map((_, i) => (
          <div key={i} className="tile aspect-[16/9] animate-pulse opacity-60" />
        ))}
      </div>
    );
  }

  if (entries.length === 0) {
    if (!showEmpty) return null;
    return <EmptyState />;
  }

  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {entries.map((entry) => (
        <GalleryCard key={entry.slug} entry={entry} />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="tile flex flex-col items-center gap-3 px-6 py-16 text-center">
      <div className="eyebrow">Nothing published yet</div>
      <h3 className="display text-2xl">The gallery is waiting for its first dashboard</h3>
      <p className="max-w-md text-muted">
        Build a dashboard in QGIS, then use{" "}
        <span className="font-medium text-ink">Publish to public</span> to send it
        here. It will appear as an interactive card you can open and explore.
      </p>
      <Link href={withBase("/guide#publish")} className="btn btn-ghost mt-2">
        How to publish
      </Link>
    </div>
  );
}
