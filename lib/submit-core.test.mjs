// Unit tests for the pure submission helpers. No deps — run with:
//   node --test lib/submit-core.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { slugify, uniqueSlug, buildEntry, sortEntries } from "./submit-core.mjs";

test("slugify: basic", () => {
  assert.equal(slugify("Harbor Traffic"), "harbor-traffic");
});

test("slugify: accents and symbols", () => {
  assert.equal(slugify("Población & Café 2024!"), "poblacion-cafe-2024");
});

test("slugify: collapses and trims", () => {
  assert.equal(slugify("  --Hello   World--  "), "hello-world");
});

test("slugify: empty falls back", () => {
  assert.equal(slugify(""), "dashboard");
  assert.equal(slugify("!!!"), "dashboard");
  assert.equal(slugify(null), "dashboard");
  assert.equal(slugify(undefined), "dashboard");
});

test("slugify: custom fallback", () => {
  assert.equal(slugify("###", "untitled"), "untitled");
});

test("slugify: matches the Python port for a tricky title", () => {
  // Same input the plugin's test_github_publish.py asserts on.
  assert.equal(slugify("My Map"), "my-map");
});

test("uniqueSlug: free slug returned unchanged", () => {
  assert.equal(uniqueSlug("harbor", []), "harbor");
  assert.equal(uniqueSlug("harbor", ["other"]), "harbor");
});

test("uniqueSlug: appends incrementing suffix on collision", () => {
  assert.equal(uniqueSlug("harbor", ["harbor"]), "harbor-2");
  assert.equal(uniqueSlug("harbor", ["harbor", "harbor-2"]), "harbor-3");
  assert.equal(uniqueSlug("harbor", ["harbor", "harbor-2", "harbor-3"]), "harbor-4");
});

test("uniqueSlug: skips gaps correctly", () => {
  // -2 taken but -3 free → -3
  assert.equal(uniqueSlug("harbor", ["harbor", "harbor-2"]), "harbor-3");
});

test("buildEntry: full shape", () => {
  assert.deepEqual(buildEntry({ slug: "s", title: "Title", author: "Isaac", date: "2026-06-20" }), {
    slug: "s",
    title: "Title",
    author: "Isaac",
    date: "2026-06-20",
    path: "dashboards/s/index.html",
    thumb: "dashboards/s/thumb.png",
  });
});

test("buildEntry: description optional", () => {
  assert.ok(!("description" in buildEntry({ slug: "s", date: "d" })));
  assert.equal(buildEntry({ slug: "s", date: "d", description: "hi" }).description, "hi");
});

test("buildEntry: title defaults to slug, author to empty", () => {
  const e = buildEntry({ slug: "s", date: "d" });
  assert.equal(e.title, "s");
  assert.equal(e.author, "");
});

test("sortEntries: newest date first, ties by title", () => {
  const out = sortEntries([
    { slug: "a", title: "Beta", date: "2026-01-01" },
    { slug: "b", title: "Alpha", date: "2026-06-20" },
    { slug: "c", title: "Alpha", date: "2026-01-01" },
  ]);
  assert.deepEqual(out.map((e) => e.slug), ["b", "c", "a"]);
});

test("sortEntries: does not mutate input", () => {
  const input = [
    { slug: "a", date: "2026-01-01" },
    { slug: "b", date: "2026-06-20" },
  ];
  sortEntries(input);
  assert.deepEqual(input.map((e) => e.slug), ["a", "b"]);
});
