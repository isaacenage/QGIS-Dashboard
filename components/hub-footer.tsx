import Link from "next/link";
import { Logo } from "./logo";
import { HUB } from "@/lib/site";

// The root hub's footer — umbrella branding, links to each plugin and to the
// maker. Kept deliberately light; the dashboard section has its own richer
// SiteFooter.
export function HubFooter() {
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-12 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <Logo size={28} />
            <span className="display text-base font-semibold">
              QGIS Plugins
            </span>
          </div>
          <p className="mt-3 max-w-xs text-sm text-muted">{HUB.tagline}</p>
        </div>

        <div className="flex gap-12">
          <FooterCol
            title="Plugins"
            links={[{ href: "/qdashboards", label: "QGIS Dashboard" }]}
          />
          <FooterCol
            title="Project"
            external
            links={[
              { href: HUB.repo, label: "Source on GitHub" },
              { href: HUB.github, label: "More by Isaac" },
              { href: `mailto:${HUB.authorEmail}`, label: "Contact" },
            ]}
          />
        </div>
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-1 px-5 py-5 text-sm text-faint sm:flex-row sm:items-center sm:justify-between">
          <span>
            Built by{" "}
            <span className="font-medium text-muted">{HUB.author}</span>. Free &
            open-source.
          </span>
          <span className="stat text-xs">{HUB.domain}</span>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({
  title,
  links,
  external,
}: {
  title: string;
  links: { href: string; label: string }[];
  external?: boolean;
}) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wider text-faint">
        {title}
      </h3>
      <ul className="mt-3 space-y-2">
        {links.map((l) => (
          <li key={l.label}>
            {external ? (
              <a
                href={l.href}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-muted transition-colors hover:text-accent-ink"
              >
                {l.label}
              </a>
            ) : (
              <Link
                href={l.href}
                className="text-sm text-muted transition-colors hover:text-accent-ink"
              >
                {l.label}
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
