"use client";

import { useId, useState } from "react";

// The signature: a working three-tile dashboard. Clicking a zone in the chart
// cross-filters the indicator and the map — the plugin's whole premise, live in
// the browser. Click again to clear. This is a hand-built demo, not a real
// export; real dashboards live in the Gallery.

type Zone = { key: string; parcels: number; area: number; color: string };

const ZONES: Zone[] = [
  { key: "Residential", parcels: 1840, area: 612, color: "var(--cat-blue)" },
  { key: "Agricultural", parcels: 1310, area: 2480, color: "var(--cat-green)" },
  { key: "Commercial", parcels: 920, area: 184, color: "var(--cat-amber)" },
  { key: "Industrial", parcels: 410, area: 356, color: "var(--cat-blue)" },
  { key: "Parks", parcels: 280, area: 540, color: "var(--cat-green)" },
];

// A small parcel grid: each cell belongs to a zone (by index into ZONES).
// Hand-laid so the map reads as a believable land-use mosaic.
const GRID: number[] = [
  0, 0, 2, 2, 1, 1, 0, 0,
  0, 0, 2, 3, 1, 1, 1, 0,
  4, 0, 0, 3, 3, 1, 1, 1,
  4, 4, 0, 0, 2, 2, 1, 1,
];
const COLS = 8;

const fmt = (n: number) => n.toLocaleString("en-US");

export function HeroCrossfilterDemo() {
  const [active, setActive] = useState<number | null>(null);
  const titleId = useId();

  const max = Math.max(...ZONES.map((z) => z.parcels));
  const selected = active === null ? null : ZONES[active];
  const totalParcels = ZONES.reduce((s, z) => s + z.parcels, 0);
  const shownParcels = selected ? selected.parcels : totalParcels;
  const shownArea = selected
    ? selected.area
    : ZONES.reduce((s, z) => s + z.area, 0);

  const toggle = (i: number) => setActive((cur) => (cur === i ? null : i));

  return (
    <div
      className="crossfilter tile w-full overflow-hidden"
      aria-labelledby={titleId}
    >
      {/* tile header strip */}
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-accent" />
          <span id={titleId} className="text-sm font-semibold">
            Parcel zoning
          </span>
        </div>
        <button
          type="button"
          onClick={() => setActive(null)}
          className="stat text-xs text-muted transition-colors hover:text-accent-ink disabled:opacity-40"
          disabled={active === null}
        >
          {active === null ? "live" : "clear filter ✕"}
        </button>
      </div>

      <div className="grid gap-px bg-line sm:grid-cols-5">
        {/* indicator tile */}
        <div className="bg-surface p-4 sm:col-span-2">
          <div className="text-xs font-medium uppercase tracking-wide text-faint">
            {selected ? `${selected.key} parcels` : "Total parcels"}
          </div>
          <div className="display stat mt-1 text-4xl text-ink tabular-nums">
            {fmt(shownParcels)}
          </div>
          <div className="mt-1 text-xs text-muted">
            <span className="stat">{fmt(shownArea)}</span> ha mapped
          </div>

          {/* mini map */}
          <div
            className="mt-4 grid gap-1 rounded-lg border border-line bg-paper p-2"
            style={{ gridTemplateColumns: `repeat(${COLS}, 1fr)` }}
            aria-hidden="true"
          >
            {GRID.map((zoneIdx, i) => {
              const dim = active !== null && zoneIdx !== active;
              return (
                <div
                  key={i}
                  data-dim={dim}
                  className="aspect-square rounded-[3px]"
                  style={{ background: ZONES[zoneIdx].color }}
                />
              );
            })}
          </div>
        </div>

        {/* chart tile */}
        <div className="bg-surface p-4 sm:col-span-3">
          <div className="text-xs font-medium uppercase tracking-wide text-faint">
            Parcels by zone
          </div>
          <ul className="mt-3 space-y-2">
            {ZONES.map((z, i) => {
              const dim = active !== null && active !== i;
              const pct = Math.round((z.parcels / max) * 100);
              return (
                <li key={z.key} data-dim={dim}>
                  <button
                    type="button"
                    onClick={() => toggle(i)}
                    aria-pressed={active === i}
                    className="group flex w-full items-center gap-3 text-left"
                  >
                    <span className="w-24 shrink-0 truncate text-xs text-muted group-hover:text-ink">
                      {z.key}
                    </span>
                    <span className="relative h-5 flex-1 overflow-hidden rounded-[5px] bg-paper">
                      <span
                        className="absolute inset-y-0 left-0 rounded-[5px]"
                        style={{ width: `${pct}%`, background: z.color }}
                      />
                    </span>
                    <span className="stat w-12 shrink-0 text-right text-xs tabular-nums text-muted">
                      {fmt(z.parcels)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="mt-3 text-xs text-faint">
            {active === null
              ? "Click a bar to cross-filter →"
              : `Filtered to ${selected?.key}. The indicator and map followed.`}
          </p>
        </div>
      </div>
    </div>
  );
}
