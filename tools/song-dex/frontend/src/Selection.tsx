import { useEffect, useRef, useState } from "react";
import type { GenreCount } from "./GenreInput";
import { Dialog } from "./LibraryTools";
import { ListPicker } from "./Lists";
import type { ListChoices, Picked } from "./Lists";

export type BulkAction = {
  label: string;
  onSelect: () => void;
  disabled?: boolean;
  /** Why it is unavailable, or what it does. */
  hint?: string;
};

/** The tracks ticked in the library, and a menu of what to do with them. */
export function SelectionBar({
  count,
  hidden,
  shown,
  canSelectMore,
  onSelectAll,
  onClear,
  actions,
}: {
  count: number;
  /** Ticked tracks the current search and filters leave out. */
  hidden: number;
  /** Tracks the current search and filters show. */
  shown: number;
  canSelectMore: boolean;
  onSelectAll: () => void;
  onClear: () => void;
  actions: BulkAction[];
}) {
  const [open, setOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    menu.current
      ?.querySelector<HTMLElement>("[role=menuitem]:not(:disabled)")
      ?.focus();
    const away = (e: MouseEvent) => {
      if (!menu.current?.parentElement?.contains(e.target as Node))
        setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);
  const items = () =>
    Array.from(
      menu.current?.querySelectorAll<HTMLElement>(
        "[role=menuitem]:not(:disabled)",
      ) ?? [],
    );
  return (
    <div className="selection-bar" role="region" aria-label="Selected tracks">
      <div className="selection-count">
        <strong>{count.toLocaleString()} selected</strong>
        {hidden > 0 && (
          <small>{hidden.toLocaleString()} hidden by search or filters</small>
        )}
      </div>
      <div className="button-row">
        <button
          className="quiet"
          disabled={!canSelectMore}
          onClick={onSelectAll}
        >
          Select all {shown.toLocaleString()} shown
        </button>
        <button className="quiet" onClick={onClear}>
          Deselect all
        </button>
        <div className="action-menu">
          <button
            className="primary"
            aria-haspopup="menu"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            Actions <span aria-hidden="true">▴</span>
          </button>
          {open && (
            <div
              ref={menu}
              role="menu"
              aria-label="Actions for the selected tracks"
              onKeyDown={(e) => {
                const list = items(),
                  at = list.indexOf(document.activeElement as HTMLElement);
                if (e.key === "Escape") {
                  e.stopPropagation();
                  setOpen(false);
                  (
                    menu.current?.previousElementSibling as HTMLElement
                  )?.focus();
                } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                  e.preventDefault();
                  const step = e.key === "ArrowDown" ? 1 : -1;
                  list[(at + step + list.length) % list.length]?.focus();
                } else if (e.key === "Tab") setOpen(false);
              }}
            >
              {actions.map((a) => (
                <button
                  key={a.label}
                  role="menuitem"
                  disabled={a.disabled}
                  onClick={() => {
                    setOpen(false);
                    a.onSelect();
                  }}
                >
                  <span>{a.label}</span>
                  {a.hint && <small>{a.hint}</small>}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Give every selected track the same My Tags or playlists. */
export function AddToLists({
  kind,
  tracks,
  choices,
  genres,
  send,
  onChanged,
  onDone,
  onClose,
}: {
  kind: "tags" | "playlists";
  tracks: {
    id: number;
    my_tags: { id: string }[];
    playlists: { id?: string }[];
  }[];
  choices: ListChoices;
  genres: GenreCount[];
  send: (endpoint: string, body?: unknown) => Promise<any>;
  onChanged: () => Promise<unknown>;
  onDone: (message: string) => Promise<unknown>;
  onClose: () => void;
}) {
  const [picked, setPicked] = useState<Picked>({
      tags: new Set(),
      playlists: new Set(),
    }),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false);
  // Shown as already there only when every selected track has it.
  const every = (sets: Set<string>[]) =>
    sets.length
      ? new Set([...sets[0]].filter((id) => sets.every((s) => s.has(id))))
      : new Set<string>();
  const held: Picked = {
    tags: every(tracks.map((t) => new Set(t.my_tags.map((g) => String(g.id))))),
    playlists: every(
      tracks.map(
        (t) =>
          new Set(t.playlists.flatMap((p) => (p.id ? [String(p.id)] : []))),
      ),
    ),
  };
  const chosen = picked.tags.size + picked.playlists.size;
  const n = tracks.length.toLocaleString();
  return (
    <Dialog
      title={kind === "tags" ? `Add My Tags to ${n}` : `Add ${n} to playlists`}
      onClose={onClose}
      wide
    >
      <p className="fine">
        Each selected track gets what you pick, alongside its other choices. A
        track that already has one is left as it is.
      </p>
      {!choices.loaded ? (
        <p>Rescan the rekordbox library first, so Song Dex knows them.</p>
      ) : (
        <div className="library-lists">
          <ListPicker
            only={kind}
            genres={genres}
            choices={choices}
            held={held}
            picked={picked}
            disabled={saving}
            onToggle={(k, id, on) => {
              const next = new Set(picked[k]);
              (on ?? !next.has(id)) ? next.add(id) : next.delete(id);
              setPicked({ ...picked, [k]: next });
            }}
            onCreate={async (k, name, parent) => {
              setError("");
              try {
                const made = await send("lists", { kind: k, name, parent });
                await onChanged();
                return made.id as string;
              } catch (e) {
                setError(e instanceof Error ? e.message : "Could not make it");
                return null;
              }
            }}
          />
        </div>
      )}
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      <div className="button-row dialog-actions">
        <button onClick={onClose}>Cancel</button>
        <button
          className="primary"
          disabled={!chosen || saving}
          onClick={async () => {
            setSaving(true);
            setError("");
            try {
              const result = await send("lists/add", {
                ids: tracks.map((t) => t.id),
                tags: [...picked.tags],
                playlists: [...picked.playlists],
              });
              await onDone(result.message);
            } catch (e) {
              setError(e instanceof Error ? e.message : "Could not add them");
              setSaving(false);
            }
          }}
        >
          {saving
            ? "Adding…"
            : chosen
              ? `Add ${chosen} ${kind === "tags" ? "My Tag" : "playlist"}${chosen === 1 ? "" : "s"} to ${n} ${tracks.length === 1 ? "track" : "tracks"}`
              : "Pick what to add"}
        </button>
      </div>
    </Dialog>
  );
}
