import type { Metadata } from "next";
import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
import { HUB } from "@/lib/site";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  display: "swap",
});
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

// Root layout owns <html>/<body>/fonts and the hub-level title scope. It does
// NOT render any header/footer: the hub page ("/") supplies its own chrome, and
// the dashboard section (app/qdashboards/layout.tsx) supplies the plugin chrome.
export const metadata: Metadata = {
  title: {
    default: `${HUB.name} — ${HUB.tagline}`,
    template: `%s · ${HUB.name}`,
  },
  description:
    "A growing collection of free, open-source QGIS plugins by Isaac Enage — practical tools that extend the desktop GIS you already use.",
  metadataBase: new URL(`https://${HUB.domain}`),
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable}`}
      >
        {children}
      </body>
    </html>
  );
}
