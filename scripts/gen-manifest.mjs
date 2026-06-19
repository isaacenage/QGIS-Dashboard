// Build-time manifest generator.
//
// Scans public/dashboards/<slug>/meta.json (one per published dashboard) and
// writes public/dashboards/manifest.json — the file the gallery fetches at
// runtime (lib/manifest.ts:loadManifest). Wired as the "prebuild" script, so
// `next build` (which Vercel runs on every deploy, including PR merges)
// regenerates it automatically. Because submissions write only their own
// meta.json and never this shared file, concurrent submissions never conflict.

import { readdir, readFile, writeFile } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { sortEntries } from "../lib/submit-core.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DASHBOARDS_DIR = join(ROOT, "public", "dashboards");
const MANIFEST_PATH = join(DASHBOARDS_DIR, "manifest.json");

async function collectEntries() {
  let dirents;
  try {
    dirents = await readdir(DASHBOARDS_DIR, { withFileTypes: true });
  } catch {
    return []; // no dashboards folder yet → empty gallery is valid
  }
  const entries = [];
  for (const dirent of dirents) {
    if (!dirent.isDirectory()) continue;
    const metaPath = join(DASHBOARDS_DIR, dirent.name, "meta.json");
    try {
      const raw = await readFile(metaPath, "utf-8");
      const entry = JSON.parse(raw);
      if (entry && typeof entry.slug === "string" && typeof entry.path === "string") {
        entries.push(entry);
      } else {
        console.warn(`gen-manifest: skipping ${dirent.name} (meta.json missing slug/path)`);
      }
    } catch {
      console.warn(`gen-manifest: skipping ${dirent.name} (no readable meta.json)`);
    }
  }
  return sortEntries(entries);
}

async function main() {
  const entries = await collectEntries();
  await writeFile(MANIFEST_PATH, JSON.stringify(entries, null, 2) + "\n", "utf-8");
  console.log(`gen-manifest: wrote ${entries.length} entr${entries.length === 1 ? "y" : "ies"} to ${MANIFEST_PATH}`);
}

main().catch((err) => {
  console.error("gen-manifest failed:", err);
  process.exit(1);
});
