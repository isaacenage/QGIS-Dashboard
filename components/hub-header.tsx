import Link from "next/link";
import { HubWordmark } from "./logo";
import { HUB } from "@/lib/site";

// The root hub's own header. Distinct from the dashboard SiteHeader: it brands
// the umbrella "QGIS Plugins" and links to hub sections, not plugin pages.
const NAV = [
  { href: "/#plugins", label: "Plugins" },
  { href: "/#about", label: "About" },
];

export function HubHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-paper/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Link href="/" aria-label="QGIS Plugins home">
          <HubWordmark size={30} />
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
            href={HUB.github}
            target="_blank"
            rel="noreferrer"
            className="hidden rounded-full px-3.5 py-2 text-sm font-medium text-muted transition-colors hover:text-ink sm:inline-flex"
          >
            GitHub
          </a>
          <Link href="/qdashboards" className="btn btn-primary text-sm">
            QGIS Dashboard
          </Link>
        </div>
      </div>
    </header>
  );
}
