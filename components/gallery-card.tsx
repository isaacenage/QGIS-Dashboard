import Link from "next/link";
import { DashboardEntry, thumbSrc } from "@/lib/manifest";
import { viewUrl } from "@/lib/site";
import { Logo } from "./logo";

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function GalleryCard({ entry }: { entry: DashboardEntry }) {
  const thumb = thumbSrc(entry);
  return (
    <Link
      href={viewUrl(entry.slug)}
      className="tile group flex flex-col overflow-hidden transition-transform duration-200 hover:-translate-y-1"
    >
      <div className="relative aspect-[16/9] overflow-hidden bg-paper">
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumb}
            alt={`${entry.title} preview`}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <PlaceholderThumb />
        )}
        <span className="absolute right-3 top-3 rounded-full bg-surface/90 px-3 py-1 text-xs font-medium text-accent-ink opacity-0 backdrop-blur transition-opacity group-hover:opacity-100">
          Open ↗
        </span>
      </div>
      <div className="flex flex-1 flex-col p-4">
        <h3 className="display text-lg leading-snug">{entry.title}</h3>
        {entry.description && (
          <p className="mt-1.5 line-clamp-2 text-sm text-muted">
            {entry.description}
          </p>
        )}
        <div className="mt-auto flex items-center justify-between pt-3 text-xs text-faint">
          <span>{entry.author}</span>
          <span className="stat">{formatDate(entry.date)}</span>
        </div>
      </div>
    </Link>
  );
}

function PlaceholderThumb() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-accent/5 via-paper to-cat-green/5">
      <Logo size={48} className="opacity-30" />
    </div>
  );
}
