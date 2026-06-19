"use client";

import { useRef, useState } from "react";

// Wraps a published dashboard's self-contained index.html in an iframe. The
// export is confirmed iframe-safe (no top/parent refs, responsive resize), so
// it stays fully interactive — cross-filtering, charts and the Leaflet map all
// work inside the frame.

export function DashboardFrame({ src, title }: { src: string; title: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  const fullscreen = () => ref.current?.requestFullscreen?.();

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked — no-op */
    }
  };

  return (
    <div ref={ref} className="tile flex h-full flex-col overflow-hidden bg-surface">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-accent" />
          <span className="truncate text-sm font-semibold">{title}</span>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            onClick={copyLink}
            className="rounded-full px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:bg-accent/8 hover:text-accent-ink"
          >
            {copied ? "Link copied" : "Copy link"}
          </button>
          <a
            href={src}
            target="_blank"
            rel="noreferrer"
            className="rounded-full px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:bg-accent/8 hover:text-accent-ink"
          >
            Open ↗
          </a>
          <button
            type="button"
            onClick={fullscreen}
            className="rounded-full px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:bg-accent/8 hover:text-accent-ink"
          >
            Fullscreen
          </button>
        </div>
      </div>
      {/*
        Published dashboards are now contributed by untrusted authors and served
        from this site's own origin. WITHHOLD allow-same-origin so their inline
        JS is sandboxed off our origin (cookies/storage) — combining it with
        allow-scripts would disable the sandbox entirely. The export is
        self-contained (no parent/top refs, no localStorage), so it stays fully
        interactive under allow-scripts alone.
      */}
      <iframe
        src={src}
        title={title}
        className="h-full w-full flex-1 bg-white"
        sandbox="allow-scripts allow-popups"
      />
    </div>
  );
}
