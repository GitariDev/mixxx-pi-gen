import React, { useMemo, useState } from "react";
import type { Shelf, ShelfNode, ShelfMember } from "./shelf";

const marks = { folder: "", playlist: "≡", smart: "✦" };

export function ShelfTree({
  shelf,
  tracks,
  selected,
  onSelect,
}: {
  shelf: Shelf;
  tracks: ShelfMember[];
  // Undefined while another page is open: nothing is highlighted.
  selected: string | null | undefined;
  onSelect: (id: string | null) => void;
}) {
  const [open, setOpen] = useState<Set<string>>(
    () =>
      new Set(JSON.parse(localStorage.getItem("songdex-shelf-open") || "[]")),
  );
  const toggle = (id: string) => {
    const next = new Set(open);
    next.has(id) ? next.delete(id) : next.add(id);
    localStorage.setItem("songdex-shelf-open", JSON.stringify([...next]));
    setOpen(next);
  };
  // Track counts for playlists, from the tracks' own memberships.
  const counts = useMemo(() => {
    const n = new Map<string, number>();
    for (const t of tracks)
      if (t.state !== "removed")
        for (const id of new Set(t.playlists.map((p) => String(p.id))))
          n.set(id, (n.get(id) ?? 0) + 1);
    return n;
  }, [tracks]);
  const children = useMemo(() => {
    const by = new Map<string, ShelfNode[]>();
    for (const n of shelf.nodes)
      by.set(n.parent, [...(by.get(n.parent) ?? []), n]);
    return by;
  }, [shelf.nodes]);
  const known = new Set(shelf.nodes.map((n) => n.id));
  // Top level: rekordbox's root, and anything whose folder is missing.
  const top = shelf.nodes.filter(
    (n) => n.parent === "root" || !known.has(n.parent),
  );
  const row = (n: ShelfNode, depth: number): React.ReactNode => {
    const inside = children.get(n.id) ?? [],
      expanded = open.has(n.id);
    const count =
      n.kind === "smart"
        ? (n.tracks?.length ?? 0)
        : n.kind === "playlist"
          ? (counts.get(n.id) ?? 0)
          : null;
    return (
      <li key={n.id}>
        <div
          className={`shelf-row ${selected === n.id ? "active" : ""}`}
          style={{ paddingLeft: depth * 12 }}
        >
          {n.kind === "folder" ? (
            <button
              className="shelf-caret"
              aria-expanded={expanded}
              aria-label={`${expanded ? "Close" : "Open"} ${n.name}`}
              onClick={() => toggle(n.id)}
            >
              {expanded ? "▾" : "▸"}
            </button>
          ) : (
            <span className="shelf-mark" aria-hidden="true">
              {marks[n.kind]}
            </span>
          )}
          <button
            className="shelf-name"
            aria-current={selected === n.id ? "true" : undefined}
            title={
              n.kind === "smart"
                ? `Smart playlist: ${(n.rules ?? []).join(n.match === "any" ? ", or " : ", and ")}`
                : n.kind === "folder"
                  ? "Every track in this folder's playlists"
                  : undefined
            }
            onClick={() => {
              onSelect(n.id);
              if (n.kind === "folder" && !expanded) toggle(n.id);
            }}
          >
            <span>{n.name}</span>
            {count !== null && <small>{count.toLocaleString()}</small>}
          </button>
        </div>
        {n.kind === "folder" && expanded && inside.length > 0 && (
          <ul>{inside.map((c) => row(c, depth + 1))}</ul>
        )}
      </li>
    );
  };
  return (
    <div id="shelf" className="shelf" aria-label="Playlists">
      <div className={`shelf-row ${selected === null ? "active" : ""}`}>
        <span className="shelf-mark" aria-hidden="true">
          ◆
        </span>
        <button
          className="shelf-name"
          aria-current={selected === null ? "true" : undefined}
          onClick={() => onSelect(null)}
        >
          <span>All tracks</span>
        </button>
      </div>
      {!shelf.loaded ? (
        <p className="shelf-note">Rescan the library to list its playlists.</p>
      ) : shelf.nodes.length === 0 ? (
        <p className="shelf-note">No playlists in rekordbox.</p>
      ) : (
        <ul>{top.map((n) => row(n, 0))}</ul>
      )}
    </div>
  );
}
