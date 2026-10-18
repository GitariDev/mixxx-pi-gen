import React, { useState } from "react";
import { GenreInput } from "./GenreInput";
import type { GenreCount } from "./GenreInput";
import { Dialog } from "./LibraryTools";
import "./lists.css";

export type ListChoices = {
  tags: { id: string; name: string; category: string; new?: boolean }[];
  playlists: { id: string; name: string; new?: boolean }[];
  categories?: { id: string; name: string }[];
  folders?: { id: string; name: string; new?: boolean }[];
  creatable?: boolean;
  loaded: boolean;
};
export type Picked = { tags: Set<string>; playlists: Set<string> };
type Kind = "tags" | "playlists";

/** A name typed for a new My Tag in one category; Enter makes it. */
function NewTag({
  disabled,
  genres,
  onCreate,
}: {
  disabled: boolean;
  genres: GenreCount[];
  onCreate: (name: string) => Promise<unknown>;
}) {
  const [name, setName] = useState<string | null>(null);
  if (name === null)
    return (
      <button
        type="button"
        className="tag-choice new-choice"
        disabled={disabled}
        onClick={() => setName("")}
      >
        + New
      </button>
    );
  const make = async () => {
    if (name.trim() && (await onCreate(name.trim()))) setName(null);
  };
  return (
    <span className="new-tag">
      {/* Genres suggest names: your library's first, then Every Noise at Once's. */}
      <GenreInput
        autoFocus
        maxLength={100}
        value={name}
        library={genres}
        placeholder="New My Tag, e.g. a genre"
        label="Name of the new My Tag"
        onChange={setName}
        onEnter={() => void make()}
        onEscape={() => setName(null)}
      />
      <button
        type="button"
        className="mini"
        disabled={disabled || !name.trim()}
        onClick={() => void make()}
      >
        Add
      </button>
      <button
        type="button"
        className="mini quiet"
        onClick={() => setName(null)}
      >
        Cancel
      </button>
    </span>
  );
}

/**
 * My Tags by category and playlists to pick for a track, with new ones made on
 * the spot. New ones are created in rekordbox with the next write of choices.
 */
export function ListPicker({
  choices,
  held,
  picked,
  disabled = false,
  onToggle,
  onCreate,
  searchRef,
  genres = [],
}: {
  choices: ListChoices;
  /** What rekordbox already gives the track: shown ticked, not changeable. */
  held: Picked;
  picked: Picked;
  disabled?: boolean;
  onToggle: (kind: Kind, id: string, on?: boolean) => void;
  /** Makes a new My Tag or playlist and returns its ID (null when it failed). */
  onCreate: (
    kind: "tag" | "playlist" | "folder",
    name: string,
    parent: string,
  ) => Promise<string | null>;
  searchRef?: React.Ref<HTMLInputElement>;
  /** The library's genres with counts, suggested as names for new My Tags. */
  genres?: GenreCount[];
}) {
  const [search, setSearch] = useState(""),
    [folder, setFolder] = useState("root"),
    [folderName, setFolderName] = useState("");
  const known = choices.categories ?? [];
  // Categories new tags can go in, then any others the tags name.
  const categories = [
    ...known,
    ...[...new Set(choices.tags.map((t) => t.category || "My Tags"))]
      .filter((name) => !known.some((c) => c.name === name))
      .map((name) => ({ id: "", name })),
  ];
  const query = search.trim().toLocaleLowerCase();
  const listed = choices.playlists.filter(
    (p) =>
      (!query || p.name.toLocaleLowerCase().includes(query)) &&
      !held.playlists.has(p.id),
  );
  const name = (id: string) =>
    choices.playlists.find((p) => p.id === id)?.name ?? "Playlist";
  const inFolder =
    folder === "new"
      ? folderName.trim()
      : (choices.folders?.find((f) => f.id === folder)?.name ?? "");
  // Matching what would be made: the folder's path and the typed name.
  const exact = choices.playlists.some(
    (p) =>
      p.name.toLocaleLowerCase() ===
      [inFolder, search.trim()].filter(Boolean).join(" / ").toLocaleLowerCase(),
  );
  const create = async (
    kind: "tag" | "playlist",
    text: string,
    parent: string,
  ) => {
    const id = await onCreate(kind, text, parent);
    if (id) onToggle(kind === "tag" ? "tags" : "playlists", id, true);
    return id;
  };
  const canCreate = !!choices.creatable && !disabled;

  return (
    <>
      <section className="tagging-section">
        <h4>My Tags</h4>
        {categories.map((category) => (
          <div key={category.name} className="tag-category">
            <span>{category.name}</span>
            <div className="tag-choices">
              {choices.tags
                .filter((t) => (t.category || "My Tags") === category.name)
                .map((t) => {
                  const has = held.tags.has(t.id);
                  return (
                    <button
                      type="button"
                      key={t.id}
                      className={`tag-choice${t.new ? " is-new" : ""}`}
                      aria-pressed={has || picked.tags.has(t.id)}
                      disabled={has || disabled}
                      title={
                        has
                          ? "Already in rekordbox"
                          : t.new
                            ? "New; made in rekordbox with the next write"
                            : undefined
                      }
                      onClick={() => onToggle("tags", t.id)}
                    >
                      {t.name}
                    </button>
                  );
                })}
              {category.id && canCreate && (
                <NewTag
                  disabled={disabled}
                  genres={genres}
                  onCreate={(text) => create("tag", text, category.id)}
                />
              )}
            </div>
          </div>
        ))}
        {choices.loaded && !choices.creatable && (
          <p className="fine">
            Rescan the rekordbox library to make new My Tags and playlists here.
          </p>
        )}
      </section>
      <section className="tagging-section">
        <h4>Playlists</h4>
        <div className="tag-choices">
          {[...held.playlists].map((id) => (
            <span key={id} className="badge success">
              ✓ {name(id)}
            </span>
          ))}
          {[...picked.playlists]
            .filter((id) => !held.playlists.has(id))
            .map((id) => (
              <button
                type="button"
                key={id}
                className="tag-choice"
                aria-pressed
                disabled={disabled}
                onClick={() => onToggle("playlists", id)}
                aria-label={`Remove from ${name(id)}`}
              >
                {name(id)} ×
              </button>
            ))}
        </div>
        <label className="playlist-search">
          Find or make a playlist
          <input
            ref={searchRef}
            value={search}
            placeholder="Type to filter; Enter adds the first match"
            disabled={disabled}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              e.preventDefault();
              if (listed.length) onToggle("playlists", listed[0].id, true);
              else if (search.trim() && canCreate)
                void create("playlist", search.trim(), folder);
              else return;
              setSearch("");
            }}
          />
        </label>
        {search.trim() && !exact && canCreate && (
          <div className="new-playlist">
            <span>
              New playlist <strong>“{search.trim()}”</strong> in
            </span>
            <select
              value={folder}
              aria-label="Folder for the new playlist"
              onChange={(e) => setFolder(e.target.value)}
            >
              <option value="root">The top level</option>
              {choices.folders?.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
              <option value="new">+ New folder…</option>
            </select>
            {folder === "new" && (
              <input
                className="folder-name"
                maxLength={100}
                value={folderName}
                placeholder="New folder name"
                aria-label="Name of the new folder"
                onChange={(e) => setFolderName(e.target.value)}
              />
            )}
            <button
              type="button"
              className="mini"
              disabled={folder === "new" && !folderName.trim()}
              onClick={async () => {
                const parent =
                  folder === "new"
                    ? await onCreate("folder", folderName.trim(), "root")
                    : folder;
                if (!parent) return;
                if (folder === "new") {
                  setFolder(parent);
                  setFolderName("");
                }
                if (await create("playlist", search.trim(), parent))
                  setSearch("");
              }}
            >
              + Make playlist
            </button>
          </div>
        )}
        <div className="playlist-choices">
          {listed.map((p) => (
            <label key={p.id}>
              <input
                type="checkbox"
                checked={picked.playlists.has(p.id)}
                disabled={disabled}
                onChange={() => onToggle("playlists", p.id)}
              />{" "}
              {p.name}
              {p.new && <small className="new-mark"> new</small>}
            </label>
          ))}
          {!listed.length && (
            <p className="muted">No playlists match “{search}”.</p>
          )}
        </div>
        <p className="fine">
          Smart playlists and Song Dex’s own lists are not offered. Choices are
          only added; remove tags and playlists in rekordbox. New My Tags and
          playlists are made in rekordbox with the next write.
        </p>
      </section>
    </>
  );
}

/** A library track's My Tags and playlists, saved as they are picked. */
export function TrackLists({
  track,
  choices,
  pending,
  disabled,
  genres,
  send,
  onChanged,
}: {
  track: {
    id: number;
    my_tags: { id: string }[];
    playlists: { id?: string }[];
  };
  choices: ListChoices;
  /** Choices for this track not yet written to rekordbox. */
  pending: { kind: string; target: string }[];
  disabled: boolean;
  genres: GenreCount[];
  send: (endpoint: string, body?: unknown) => Promise<any>;
  onChanged: () => Promise<unknown>;
}) {
  const fromPending = (): Picked => ({
    tags: new Set(pending.filter((a) => a.kind === "tag").map((a) => a.target)),
    playlists: new Set(
      pending.filter((a) => a.kind === "playlist").map((a) => a.target),
    ),
  });
  const [picked, setPicked] = useState<Picked>(fromPending),
    [error, setError] = useState("");
  const signature = pending
    .map((a) => a.kind + a.target)
    .sort()
    .join();
  // Follow saves made elsewhere (and new lists getting their rekordbox IDs).
  React.useEffect(() => setPicked(fromPending()), [track.id, signature]);
  const held: Picked = {
    tags: new Set(track.my_tags.map((t) => String(t.id))),
    playlists: new Set(
      track.playlists.flatMap((p) => (p.id ? [String(p.id)] : [])),
    ),
  };
  const save = async (next: Picked) => {
    setPicked(next);
    setError("");
    try {
      await send(`tracks/${track.id}/lists`, {
        tags: [...next.tags],
        playlists: [...next.playlists],
      });
      await onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not keep the choice");
      setPicked(fromPending());
    }
  };
  return (
    <div className="library-lists">
      <ListPicker
        genres={genres}
        choices={choices}
        held={held}
        picked={picked}
        disabled={disabled}
        onToggle={(kind, id, on) => {
          const next = new Set(picked[kind]);
          (on ?? !next.has(id)) ? next.add(id) : next.delete(id);
          void save({ ...picked, [kind]: next });
        }}
        onCreate={async (kind, name, parent) => {
          setError("");
          try {
            const made = await send("lists", { kind, name, parent });
            await onChanged();
            return made.id as string;
          } catch (e) {
            setError(e instanceof Error ? e.message : "Could not make it");
            return null;
          }
        }}
      />
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
    </div>
  );
}

/** Make a playlist, in an existing folder or a new one, optionally with the selected track. */
export function NewPlaylist({
  choices,
  track,
  pending,
  send,
  onDone,
  onClose,
}: {
  choices: ListChoices;
  track?: { id: number; title: string };
  /** The selected track's choices not yet written, kept alongside the new one. */
  pending: { kind: string; target: string }[];
  send: (endpoint: string, body?: unknown) => Promise<any>;
  onDone: (message: string) => Promise<unknown>;
  onClose: () => void;
}) {
  const [name, setName] = useState(""),
    [folder, setFolder] = useState("root"),
    [folderName, setFolderName] = useState(""),
    [inside, setInside] = useState("root"),
    [withTrack, setWithTrack] = useState(!!track),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false);
  const making = folder === "new";
  const ready = name.trim() && (!making || folderName.trim()) && !saving;
  const make = async () => {
    if (!ready) return;
    setSaving(true);
    setError("");
    try {
      const parent = making
        ? (
            await send("lists", {
              kind: "folder",
              name: folderName.trim(),
              parent: inside,
            })
          ).id
        : folder;
      const made = await send("lists", {
        kind: "playlist",
        name: name.trim(),
        parent,
      });
      if (track && withTrack)
        await send(`tracks/${track.id}/lists`, {
          tags: pending.filter((a) => a.kind === "tag").map((a) => a.target),
          playlists: [
            ...pending
              .filter((a) => a.kind === "playlist")
              .map((a) => a.target),
            made.id,
          ],
        });
      await onDone(
        made.existing
          ? `“${made.name}” already exists${track && withTrack ? "; the track is added to it with the next write" : ""}.`
          : `“${made.name}” is made in rekordbox with the next Write to rekordbox${track && withTrack ? ", with this track in it" : ""}.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not make the playlist");
      setSaving(false);
    }
  };
  if (!choices.creatable)
    return (
      <Dialog title="New playlist" onClose={onClose}>
        <p>
          Rescan the rekordbox library first, so Song Dex knows your playlist
          folders.
        </p>
      </Dialog>
    );
  return (
    <Dialog title="New playlist" onClose={onClose}>
      <form
        className="new-playlist-form"
        onSubmit={(e) => {
          e.preventDefault();
          void make();
        }}
      >
        <label>
          Name
          <input
            autoFocus
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          Folder
          <select value={folder} onChange={(e) => setFolder(e.target.value)}>
            <option value="root">The top level</option>
            {choices.folders?.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
                {f.new ? " (new)" : ""}
              </option>
            ))}
            <option value="new">+ New folder…</option>
          </select>
        </label>
        {making && (
          <div className="new-folder">
            <label>
              New folder name
              <input
                maxLength={100}
                value={folderName}
                onChange={(e) => setFolderName(e.target.value)}
              />
            </label>
            <label>
              Inside
              <select
                value={inside}
                onChange={(e) => setInside(e.target.value)}
              >
                <option value="root">The top level</option>
                {choices.folders?.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
        {track && (
          <label className="confirm-option">
            <input
              type="checkbox"
              checked={withTrack}
              onChange={(e) => setWithTrack(e.target.checked)}
            />
            Add NO. {String(track.id).padStart(4, "0")} “{track.title}”
          </label>
        )}
        <p className="fine">
          It is made in rekordbox, with any tracks you put in it, by the next
          Write to rekordbox. Until then it can be picked like any playlist and
          dropped again.
        </p>
        {error && (
          <p role="alert" className="error-text">
            {error}
          </p>
        )}
        <div className="button-row">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={!ready}>
            {saving ? "Making…" : "Make playlist"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
