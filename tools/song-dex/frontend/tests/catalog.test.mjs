import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";
const source = fs.readFileSync(
  new URL("../src/catalog.ts", import.meta.url),
  "utf8",
);
const js = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  },
}).outputText;
const { matchesFilters, compareTracks, emptyFilters, tagKey } = await import(
  "data:text/javascript;base64," + Buffer.from(js).toString("base64")
);
const track = (id, metadata = {}, tags = []) => ({
  id,
  metadata,
  source: "library",
  my_tags: tags,
  my_tags_loaded: 1,
  playlists: [{ name: "Warm up" }],
});
const one = { id: "a", name: "Warm", category: "Energy" },
  two = { id: "b", name: "Vocal", category: "Parts" };
const t = track(
  1,
  { bpm: 124.5, year: 2001, key: "4A", genre: "House", format: "FLAC" },
  [one, two],
);
test("combines ranges, tags, key, genre, format and playlist", () => {
  const f = {
    ...emptyFilters,
    tags: [tagKey(t, one)],
    keys: ["4A", "8A"],
    genres: ["House"],
    formats: ["FLAC"],
    bpmMin: "124.5",
    bpmMax: "125",
    yearMin: "2000",
    yearMax: "2001",
    playlists: ["Warm up"],
  };
  assert.equal(matchesFilters(t, f), true);
  assert.equal(matchesFilters(t, { ...f, yearMax: "2000" }), false);
});
test("several values of one field match any of them; fields combine", () => {
  const f = { ...emptyFilters, tags: ["library::a", "library::missing"] };
  assert.equal(matchesFilters(t, f), true);
  assert.equal(
    matchesFilters(t, { ...f, tags: ["another-library::a"] }),
    false,
  );
  assert.equal(
    matchesFilters(t, { ...f, genres: ["Techno", "House"], keys: ["4A"] }),
    true,
  );
  assert.equal(matchesFilters(t, { ...f, genres: ["Techno"] }), false);
});
test("date added ranges use the rekordbox day; unknown days never match", () => {
  const dated = { ...t, stats: { added: "2024-03-09" } };
  const f = { ...emptyFilters, addedFrom: "2024-03-01", addedTo: "2024-03-09" };
  assert.equal(matchesFilters(dated, f), true);
  assert.equal(matchesFilters(dated, { ...f, addedTo: "2024-03-08" }), false);
  assert.equal(matchesFilters(t, f), false);
  assert.deepEqual(
    [{ ...t, id: 5 }, dated, { ...t, id: 9, stats: { added: "2023-01-01" } }]
      .sort((a, b) => compareTracks(a, b, "added", "asc"))
      .map((x) => x.id),
    [9, 1, 5],
  );
});
test("unknown metadata never matches bounded ranges or confirmed untagged", () => {
  const unknown = { ...track(2), my_tags_loaded: 0 };
  assert.equal(matchesFilters(unknown, emptyFilters), true);
  assert.equal(
    matchesFilters(unknown, { ...emptyFilters, bpmMax: "130" }),
    false,
  );
  assert.equal(
    matchesFilters(unknown, { ...emptyFilters, tagState: "untagged" }),
    false,
  );
  assert.equal(
    matchesFilters(unknown, { ...emptyFilters, tagState: "unknown" }),
    true,
  );
  assert.equal(
    matchesFilters(track(3), { ...emptyFilters, tagState: "untagged" }),
    true,
  );
});
test("BPM and year sort numerically, unknowns last in both directions", () => {
  const rows = [
    track(1, { bpm: 100, year: 2001 }),
    track(2, { bpm: 99, year: 1999 }),
    track(3, { bpm: 0, year: "" }),
  ];
  assert.deepEqual(
    [...rows]
      .sort((a, b) => compareTracks(a, b, "bpm", "asc"))
      .map((t) => t.id),
    [2, 1, 3],
  );
  assert.deepEqual(
    [...rows]
      .sort((a, b) => compareTracks(a, b, "year", "desc"))
      .map((t) => t.id),
    [1, 2, 3],
  );
});
test("key sorting uses natural numbers; ties keep Dex order", () => {
  const rows = [
    track(3, { key: "10A" }),
    track(2, { key: "2A" }),
    track(1, { key: "2A" }),
  ];
  assert.deepEqual(
    rows.sort((a, b) => compareTracks(a, b, "key", "asc")).map((t) => t.id),
    [1, 2, 3],
  );
});
test("My Tag ordering includes category and missing values stay last", () => {
  const rows = [track(1, {}, [two]), track(2, {}, [one]), track(3)];
  assert.deepEqual(
    rows.sort((a, b) => compareTracks(a, b, "my_tags", "asc")).map((t) => t.id),
    [2, 1, 3],
  );
});
