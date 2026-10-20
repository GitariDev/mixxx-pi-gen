import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";
const source = fs.readFileSync(
  new URL("../src/shelf.ts", import.meta.url),
  "utf8",
);
const js = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  },
}).outputText;
const { shelfMembers, shelfPath } = await import(
  "data:text/javascript;base64," + Buffer.from(js).toString("base64")
);
const nodes = [
  { id: "f", name: "Sets", parent: "root", kind: "folder", seq: 1 },
  { id: "p", name: "Opening", parent: "f", kind: "playlist", seq: 1 },
  { id: "s", name: "Jazz", parent: "f", kind: "smart", seq: 2, tracks: [3, 1] },
];
const tracks = [
  { id: 1, state: "indexed", playlists: [{ id: "p", position: 2 }] },
  { id: 2, state: "indexed", playlists: [{ id: "p", position: 1 }] },
  { id: 4, state: "removed", playlists: [{ id: "p", position: 3 }] },
];
test("a playlist lists its tracks in playlist order, without removed ones", () => {
  assert.deepEqual(
    [...shelfMembers("p", nodes, tracks)],
    [
      [2, 0],
      [1, 1],
    ],
  );
});
test("a smart playlist lists its matches", () => {
  assert.deepEqual([...shelfMembers("s", nodes, tracks).keys()], [3, 1]);
});
test("a folder holds every track in its playlists once", () => {
  assert.deepEqual([...shelfMembers("f", nodes, tracks).keys()], [2, 1, 3]);
  assert.equal(shelfMembers("missing", nodes, tracks).size, 0);
});
test("a node's path names its folders", () => {
  assert.equal(shelfPath("s", nodes), "Sets / Jazz");
});
