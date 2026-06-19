import Link from "next/link";
import { Logo } from "./logo";
import { SITE, withBase } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-12 sm:grid-cols-2 md:grid-cols-4">
        <div className="sm:col-span-2 md:col-span-1">
          <div className="flex items-center gap-2.5">
            <Logo size={28} />
            <span className="display text-base font-semibold">QGIS Dashboard</span>
          </div>
          <p className="mt-3 max-w-xs text-sm text-muted">{SITE.tagline}</p>
        </div>

        <FooterCol
          title="Product"
          links={[
            { href: withBase("/#features"), label: "Features" },
            { href: withBase("/#cross-filter"), label: "Cross-filtering" },
            { href: withBase("/#themes"), label: "Themes" },
            { href: withBase("/gallery"), label: "Gallery" },
          ]}
        />
        <FooterCol
          title="Learn"
          links={[
            { href: withBase("/guide#install"), label: "Install" },
            { href: withBase("/guide#build"), label: "Build a dashboard" },
            { href: withBase("/guide#publish"), label: "Publish" },
          ]}
        />
        <FooterCol
          title="Project"
          external
          links={[
            { href: SITE.repo, label: "Source on GitHub" },
            { href: SITE.issues, label: "Report an issue" },
            { href: `mailto:${SITE.authorEmail}`, label: "Contact" },
          ]}
        />
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-1 px-5 py-5 text-sm text-faint sm:flex-row sm:items-center sm:justify-between">
          <span>
            Built by{" "}
            <span className="font-medium text-muted">{SITE.author}</span>. Free &
            open-source.
          </span>
          <span className="stat text-xs">{SITE.domain}/qdashboard</span>
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
