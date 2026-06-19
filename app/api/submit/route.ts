// Public-gallery submission intake.
//
// The plugin's "Publish to public" POSTs a finished dashboard here. This route
// holds the only secret — GITHUB_BOT_TOKEN, a Vercel env var that NEVER ships
// in the plugin — and opens a Pull Request adding the dashboard's files. Vercel
// builds a preview deployment of that PR so the maintainer can open the live
// dashboard before merging. Merge = goes live; close = rejected. Contributors
// need no account and no token.
//
// Conflict-free by design: each submission writes only its own folder
// (index.html + thumb.png + meta.json) and NEVER the shared manifest.json — the
// manifest is regenerated at build time (scripts/gen-manifest.mjs) from every
// meta.json, so concurrent submissions can't merge-conflict.

import { gunzipSync } from "node:zlib";
import { buildEntry, slugify, uniqueSlug } from "@/lib/submit-core.mjs";

export const runtime = "nodejs";

// Target gallery repo. The bot token must have Contents + Pull-requests write
// on exactly this repo.
const REPO_OWNER = "isaacenage";
const REPO_NAME = "QGIS-Plugins";
const BASE_BRANCH = "main";
const DASHBOARDS_ROOT = "public/dashboards";
const PUBLIC_VIEW_BASE = "https://qgis.byzenterra.org/qdashboards/view";

const API_ROOT = "https://api.github.com";
const API_VERSION = "2022-11-28";

// Guards (the merge gate is the real control — these just bound abuse).
const MAX_HTML_BYTES = 25 * 1024 * 1024; // decompressed
const MAX_THUMB_BYTES = 4 * 1024 * 1024;
const MAX_TITLE = 200;
const MAX_AUTHOR = 120;
const MAX_DESC = 400;
const MAX_OPEN_SUBMISSIONS = 50;
// Sanity marker that the upload is a real exported dashboard, not arbitrary
// HTML: every export embeds its data in <script ... id="dashboard-data">.
const DASHBOARD_MARKER = 'id="dashboard-data"';

class SubmitError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface SubmitBody {
  title?: unknown;
  author?: unknown;
  description?: unknown;
  html_gz_b64?: unknown;
  thumb_b64?: unknown;
}

function asString(value: unknown, field: string, max: number, required = true): string {
  if (value === undefined || value === null || value === "") {
    if (required) throw new SubmitError(400, `Missing "${field}".`);
    return "";
  }
  if (typeof value !== "string") throw new SubmitError(400, `"${field}" must be text.`);
  const trimmed = value.trim();
  if (required && !trimmed) throw new SubmitError(400, `"${field}" can't be empty.`);
  if (trimmed.length > max) throw new SubmitError(400, `"${field}" is too long.`);
  return trimmed;
}

function decodeBase64(value: unknown, field: string): Buffer {
  if (typeof value !== "string" || !value) {
    throw new SubmitError(400, `Missing "${field}".`);
  }
  try {
    return Buffer.from(value, "base64");
  } catch {
    throw new SubmitError(400, `"${field}" is not valid base64.`);
  }
}

// ---- GitHub REST (raw fetch, no dependency) ---------------------------------

async function gh(
  token: string,
  method: string,
  path: string,
  body?: unknown,
  accept = "application/vnd.github+json",
): Promise<{ status: number; data: any }> {
  const res = await fetch(`${API_ROOT}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: accept,
      "X-GitHub-Api-Version": API_VERSION,
      "User-Agent": "QGIS-Dashboard-Site",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const text = await res.text();
  let data: any = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  return { status: res.status, data };
}

async function ghOk(
  token: string,
  method: string,
  path: string,
  body?: unknown,
): Promise<any> {
  const { status, data } = await gh(token, method, path, body);
  if (status < 200 || status >= 300) {
    const detail = data && data.message ? `: ${data.message}` : "";
    // Don't leak internals to the client; log server-side.
    console.error(`GitHub ${method} ${path} -> ${status}${detail}`);
    throw new SubmitError(502, "The gallery service couldn't reach GitHub. Try again shortly.");
  }
  return data;
}

const repoPath = (sub: string) => `/repos/${REPO_OWNER}/${REPO_NAME}/${sub}`;

/** Slugs already used: existing dashboard folders + open submit/* PR branches. */
async function takenSlugs(token: string): Promise<string[]> {
  const taken: string[] = [];
  const { status, data } = await gh(
    token,
    "GET",
    repoPath(`contents/${DASHBOARDS_ROOT}?ref=${BASE_BRANCH}`),
  );
  if (status === 200 && Array.isArray(data)) {
    for (const item of data) {
      if (item && item.type === "dir" && typeof item.name === "string") taken.push(item.name);
    }
  }
  const pulls = await ghOk(token, "GET", repoPath("pulls?state=open&per_page=100"));
  let openSubmissions = 0;
  if (Array.isArray(pulls)) {
    for (const pr of pulls) {
      const ref: string = pr?.head?.ref || "";
      if (ref.startsWith("submit/")) {
        openSubmissions += 1;
        taken.push(ref.slice("submit/".length));
      }
    }
  }
  if (openSubmissions >= MAX_OPEN_SUBMISSIONS) {
    throw new SubmitError(429, "The gallery has many pending submissions right now. Please try again later.");
  }
  return taken;
}

async function createBlob(token: string, contentB64: string): Promise<string> {
  const blob = await ghOk(token, "POST", repoPath("git/blobs"), {
    content: contentB64,
    encoding: "base64",
  });
  return blob.sha;
}

// ---- handler ----------------------------------------------------------------

async function handle(req: Request): Promise<Response> {
  const token = process.env.GITHUB_BOT_TOKEN;
  if (!token) {
    console.error("GITHUB_BOT_TOKEN is not configured.");
    throw new SubmitError(500, "The gallery service is not configured yet. Please contact the maintainer.");
  }

  let parsed: SubmitBody;
  try {
    parsed = (await req.json()) as SubmitBody;
  } catch {
    throw new SubmitError(400, "Expected a JSON body.");
  }

  const title = asString(parsed.title, "title", MAX_TITLE);
  const author = asString(parsed.author, "author", MAX_AUTHOR, false);
  const description = asString(parsed.description, "description", MAX_DESC, false);
  const thumbBytes = decodeBase64(parsed.thumb_b64, "thumb_b64");
  if (thumbBytes.length > MAX_THUMB_BYTES) {
    throw new SubmitError(413, "The thumbnail is too large.");
  }

  const htmlGz = decodeBase64(parsed.html_gz_b64, "html_gz_b64");
  let htmlBuf: Buffer;
  try {
    htmlBuf = gunzipSync(htmlGz);
  } catch {
    throw new SubmitError(400, "The dashboard data could not be read (bad gzip).");
  }
  if (htmlBuf.length > MAX_HTML_BYTES) {
    throw new SubmitError(413, "This dashboard is too large to publish to the gallery.");
  }
  const html = htmlBuf.toString("utf-8");
  if (!html.includes(DASHBOARD_MARKER)) {
    throw new SubmitError(400, "That file doesn't look like an exported dashboard.");
  }

  // --- unique slug + branch off main's head ---------------------------------
  const slug = uniqueSlug(slugify(title), await takenSlugs(token));
  const ref = await ghOk(token, "GET", repoPath(`git/ref/heads/${BASE_BRANCH}`));
  const headSha: string = ref.object.sha;
  const headCommit = await ghOk(token, "GET", repoPath(`git/commits/${headSha}`));
  const baseTreeSha: string = headCommit.tree.sha;

  const date = new Date().toISOString().slice(0, 10);
  const entry = buildEntry({ slug, title, author, date, description: description || undefined });

  // --- atomic commit: index.html + thumb.png + meta.json --------------------
  const htmlBlob = await createBlob(token, htmlBuf.toString("base64"));
  const thumbBlob = await createBlob(token, thumbBytes.toString("base64"));
  const metaBlob = await createBlob(
    token,
    Buffer.from(JSON.stringify(entry, null, 2) + "\n", "utf-8").toString("base64"),
  );

  const dir = `${DASHBOARDS_ROOT}/${slug}`;
  const tree = await ghOk(token, "POST", repoPath("git/trees"), {
    base_tree: baseTreeSha,
    tree: [
      { path: `${dir}/index.html`, mode: "100644", type: "blob", sha: htmlBlob },
      { path: `${dir}/thumb.png`, mode: "100644", type: "blob", sha: thumbBlob },
      { path: `${dir}/meta.json`, mode: "100644", type: "blob", sha: metaBlob },
    ],
  });
  const commit = await ghOk(token, "POST", repoPath("git/commits"), {
    message: `Dashboard submission: ${title}`,
    tree: tree.sha,
    parents: [headSha],
  });
  await ghOk(token, "POST", repoPath("git/refs"), {
    ref: `refs/heads/submit/${slug}`,
    sha: commit.sha,
  });

  const viewUrl = `${PUBLIC_VIEW_BASE}?d=${encodeURIComponent(slug)}`;
  const prBody = [
    `**Title:** ${title}`,
    author ? `**Author:** ${author}` : null,
    description ? `**Description:** ${description}` : null,
    "",
    `Submitted from the QGIS Dashboard plugin. Preview the deployment, then merge to publish.`,
    "",
    `Will be live at: ${viewUrl}`,
  ]
    .filter((l) => l !== null)
    .join("\n");

  const pr = await ghOk(token, "POST", repoPath("pulls"), {
    title: `Dashboard submission: ${title}`,
    head: `submit/${slug}`,
    base: BASE_BRANCH,
    body: prBody,
  });

  return Response.json({ ok: true, slug, pr_url: pr.html_url, view_url: viewUrl });
}

export async function POST(req: Request): Promise<Response> {
  try {
    return await handle(req);
  } catch (err) {
    if (err instanceof SubmitError) {
      return Response.json({ ok: false, message: err.message }, { status: err.status });
    }
    console.error("Unexpected submit error:", err);
    return Response.json(
      { ok: false, message: "Something went wrong while submitting. Please try again." },
      { status: 500 },
    );
  }
}
