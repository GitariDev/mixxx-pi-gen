export type ShelfNode = {
  id: string;
  name: string;
  parent: string;
  kind: "folder" | "playlist" | "smart";
  seq: number;
  // Smart playlists: their rules in words and the Dex IDs they match.
  rules?: string[];
  match?: "all" | "any";
  tracks?: number[];
  error?: string;
};
export type Shelf = { nodes: ShelfNode[]; loaded: boolean };
export type ShelfMember = {
  id: number;
  state: string;
  playlists: { id?: string; position: number }[];
};

/** A playlist's tracks, a smart playlist's matches, or everything inside a
 * folder, each with its place in the list. */
export function shelfMembers(
  id: string,
  nodes: ShelfNode[],
  tracks: ShelfMember[],
): Map<number, number> {
  const order = new Map<number, number>(),
    root = nodes.find((n) => n.id === id);
  const add = (node: ShelfNode, seen: Set<string>) => {
    if (seen.has(node.id)) return;
    seen.add(node.id);
    const place = (t: number) => order.has(t) || order.set(t, order.size);
    if (node.kind === "folder") {
      for (const child of nodes.filter((n) => n.parent === node.id))
        add(child, seen);
    } else if (node.kind === "smart") {
      (node.tracks ?? []).forEach(place);
    } else {
      tracks
        .flatMap((t) =>
          t.state === "removed"
            ? []
            : t.playlists
                .filter((p) => String(p.id) === node.id)
                .map((p) => [t.id, p.position] as const),
        )
        .sort((a, b) => a[1] - b[1])
        .forEach(([t]) => place(t));
    }
  };
  if (root) add(root, new Set());
  return order;
}

/** "Folder / Playlist" for a node. */
export function shelfPath(id: string, nodes: ShelfNode[]) {
  const names: string[] = [],
    seen = new Set<string>();
  let node = nodes.find((n) => n.id === id);
  while (node && !seen.has(node.id)) {
    seen.add(node.id);
    names.unshift(node.name);
    const parent = node.parent;
    node = nodes.find((n) => n.id === parent);
  }
  return names.join(" / ");
}
