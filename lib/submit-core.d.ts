// Type declarations for the pure ESM helpers in submit-core.mjs, so the
// TypeScript API route imports them with real types.

export interface ManifestEntry {
  slug: string;
  title: string;
  author: string;
  date: string;
  path: string;
  thumb: string;
  description?: string;
}

export function slugify(title: string | null | undefined, fallback?: string): string;

export function uniqueSlug(base: string, taken: Iterable<string>): string;

export function buildEntry(fields: {
  slug: string;
  title?: string;
  author?: string;
  date: string;
  description?: string;
}): ManifestEntry;

export function sortEntries<T extends { date?: string; title?: string }>(entries: T[]): T[];
