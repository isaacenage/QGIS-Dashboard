import Link from "next/link";
import { Wordmark } from "./logo";
import { SITE, withBase } from "@/lib/site";

const NAV = [
  { href: withBase("/#features"), label: "Features" },
  { href: withBase("/guide"), label: "Guide" },
  { href: withBase("/gallery"), label: "Gallery" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-paper/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Link href={withBase("/")} aria-label="QGIS Dashboard home">
          <Wordmark size={30} />
        </Link>
        <nav className="hidden items-center gap-1 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-full px-3.5 py-2 text-sm font-medium text-muted transition-colors hover:bg-accent/8 hover:text-accent-ink"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <a
            href={SITE.repo}
            target="_blank"
            rel="noreferrer"
            className="hidden rounded-full px-3.5 py-2 text-sm font-medium text-muted transition-colors hover:text-ink sm:inline-flex"
          >
            GitHub
          </a>
          <a href={withBase("/guide#install")} className="btn btn-primary text-sm">
            Install
          </a>
        </div>
      </div>
    </header>
  );
}
