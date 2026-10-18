import { useEffect, useRef, useState } from "react";
import { GenreInput } from "./GenreInput";
import type { GenreCount } from "./GenreInput";

type Request = (
  endpoint: string,
  body?: unknown,
  success?: string,
) => Promise<any>;
type Status = {
  track_id: number;
  field: string;
  value: string;
  file_status: string;
  library_status: string;
};
const fields = [
  "title",
  "artist",
  "version",
  "album",
  "album_artist",
  "year",
  "label",
  "genre",
];
const label = (s: string) => s.replaceAll("_", " ");

export function ManualEditor({
  track,
  statuses,
  busy,
  request,
  genres,
}: {
  genres: GenreCount[];
  track: {
    id: number;
    metadata: Record<string, string | number>;
    file_metadata: Record<string, string | number>;
    observed_metadata: Record<string, string | number>;
    revision: string;
    available: number;
    source: string;
  };
  statuses: Status[];
  busy: boolean;
  request: Request;
}) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [base, setBase] = useState(track.revision);
  const [message, setMessage] = useState("");
  const dirty = Object.keys(draft).length > 0;
  useEffect(() => {
    if (!dirty) setBase(track.revision);
  }, [track.revision, dirty]);
  const stale = dirty && base !== track.revision;
  return (
    <form
      className="manual-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const result = await request(`tracks/${track.id}/edit`, {
          changes: draft,
          revision: base,
        });
        if (result?.saved) {
          setDraft({});
          setMessage(result.message);
        }
      }}
    >
      <h3>Edit metadata</h3>
      <p className="fine">
        Save your correction to the Dex immediately, including while a drive is
        offline. Available, supported audio tags are backed up and saved when
        rekordbox is closed. Your values stay locked during metadata lookups.
      </p>
      {!track.available && (
        <div className="offline-note">
          <strong>○ File offline</strong>
          <p>
            You can still edit everything below. File tags wait until the drive
            returns.
          </p>
        </div>
      )}
      {fields.map((field) => (
        <label key={field}>
          {label(field)}
          {field === "genre" ? (
            <GenreInput
              library={genres}
              value={draft[field] ?? String(track.metadata[field] ?? "")}
              onChange={(value) => setDraft({ ...draft, [field]: value })}
            />
          ) : (
            <input
              maxLength={255}
              value={draft[field] ?? String(track.metadata[field] ?? "")}
              inputMode={field === "year" ? "numeric" : "text"}
              onChange={(e) => setDraft({ ...draft, [field]: e.target.value })}
            />
          )}
        </label>
      ))}
      {stale && (
        <p role="alert">
          This entry changed while you were editing. Reload the fields before
          saving.
        </p>
      )}
      <div className="button-row">
        <button
          className="primary"
          disabled={
            busy ||
            !dirty ||
            stale ||
            Object.values(draft).some((v) => !v.trim())
          }
        >
          Save metadata
        </button>
        {dirty && (
          <button
            type="button"
            onClick={() => {
              setDraft({});
              setBase(track.revision);
            }}
          >
            Reload fields
          </button>
        )}
      </div>
      <p className="fine">
        Empty values do not erase tags. BPM, key, cues and grids are preserved.
      </p>
      {message && <p role="status">{message}</p>}
      {statuses.length > 0 && (
        <section className="sync-status">
          <h3>Saved destinations</h3>
          <p className="fine">All values below are saved in the Dex.</p>
          {statuses.map((s) => (
            <div key={s.field} className="sync-field">
              <strong>
                {label(s.field)} · {s.value}
              </strong>
              {s.file_status !== "saved" && (
                <small>
                  Last read from file:{" "}
                  {track.file_metadata[s.field] || "Empty / unknown"}
                </small>
              )}
              {s.library_status === "pending" && (
                <small>
                  Last read from rekordbox:{" "}
                  {track.observed_metadata[s.field] || "Empty / unknown"}
                </small>
              )}
              <span>
                Audio tags: {s.file_status === "saved" ? "saved" : "pending"}
              </span>
              <span>
                rekordbox:{" "}
                {s.library_status === "not_in_rekordbox"
                  ? "not imported"
                  : s.library_status}
              </span>
            </div>
          ))}
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              const r = await request(`tracks/${track.id}/sync`);
              if (r) setMessage(r.message);
            }}
          >
            Sync saved edits
          </button>
          <p className="fine">
            Reconnect offline drives and check availability before syncing.
            Direct rekordbox writes remain queued until compatibility
            verification is complete.
          </p>
        </section>
      )}
    </form>
  );
}

export function Dialog({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null),
    // Escape calls the latest onClose, not the one from when the dialog opened.
    closing = useRef(onClose);
  closing.current = onClose;
  useEffect(() => {
    const prior = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        closing.current();
      }
      if (e.key !== "Tab") return;
      const items = Array.from(
        ref.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled),input:not(:disabled),select:not(:disabled),a[href]",
        ) ?? [],
      );
      if (!items.length) return;
      const first = items[0],
        last = items[items.length - 1];
      if (
        e.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === ref.current)
      ) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", key, true);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", key, true);
      document.body.style.overflow = overflow;
      prior?.focus();
    };
  }, []);
  return (
    <div className="library-modal">
      <div
        className={wide ? "library-dialog wide" : "library-dialog"}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
        tabIndex={-1}
      >
        <header>
          <div>
            <div className="eyebrow">COLLECTION TOOLS</div>
            <h2>{title}</h2>
          </div>
          <button aria-label={`Close ${title}`} onClick={onClose}>
            ×
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

type Listing = {
  path: string;
  parent: string;
  entries: { path: string; name: string; folder: boolean }[];
  shortcuts: { name: string; path: string }[];
};
export function FileBrowser({
  request,
  selected,
  onSelect,
  onFolder,
  initialPath = "",
}: {
  request: Request;
  selected: string[];
  onSelect: (paths: string[]) => void;
  onFolder?: (path: string) => void;
  initialPath?: string;
}) {
  const [listing, setListing] = useState<Listing | null>(null),
    [path, setPath] = useState(initialPath),
    [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [entryView, setEntryView] = useState<"files" | "folders">(
    onFolder ? "folders" : "files",
  );
  const [entrySearch, setEntrySearch] = useState("");
  const open = async (p: string) => {
    setLoading(true);
    setError("");
    const result = await request("files/browse", { path: p });
    if (result) {
      setListing(result);
      setPath(result.path);
      setEntrySearch("");
      setEntryView(
        onFolder ||
          !result.entries.some((e: Listing["entries"][number]) => !e.folder)
          ? "folders"
          : "files",
      );
    } else
      setError(
        "Unable to open that folder. Check the path and drive connection.",
      );
    setLoading(false);
  };
  useEffect(() => {
    void open(initialPath);
  }, []);
  return (
    <section className="file-browser">
      <form
        className="folder-path"
        onSubmit={(e) => {
          e.preventDefault();
          void open(path);
        }}
      >
        <label>
          Folder path
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            spellCheck={false}
          />
        </label>
        <button disabled={loading}>Go</button>
      </form>
      <div className="button-row shortcuts">
        {listing?.shortcuts.map((s) => (
          <button
            key={s.name}
            disabled={loading}
            onClick={() => void open(s.path)}
          >
            {s.name}
          </button>
        ))}
      </div>
      <div className="browser-toolbar">
        <button
          disabled={loading || !listing || listing.parent === listing.path}
          onClick={() => listing && void open(listing.parent)}
        >
          ↑ Parent folder
        </button>
        {onFolder && (
          <button
            className="primary"
            disabled={loading || !listing}
            onClick={() => listing && onFolder(listing.path)}
          >
            Use this folder
          </button>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      {!onFolder && (
        <div
          className="file-view-buttons"
          role="group"
          aria-label="Show files or folders"
        >
          <button
            type="button"
            aria-pressed={entryView === "files"}
            onClick={() => {
              setEntryView("files");
              setEntrySearch("");
            }}
          >
            Audio files ({listing?.entries.filter((e) => !e.folder).length ?? 0}
            )
          </button>
          <button
            type="button"
            aria-pressed={entryView === "folders"}
            onClick={() => {
              setEntryView("folders");
              setEntrySearch("");
            }}
          >
            Folders ({listing?.entries.filter((e) => e.folder).length ?? 0})
          </button>
        </div>
      )}
      <label className="file-entry-search">
        {entryView === "files" ? "Find audio files" : "Find folders"}
        <input
          value={entrySearch}
          onChange={(e) => setEntrySearch(e.target.value)}
          placeholder={
            entryView === "files"
              ? "Search filenames, .mp3, .flac…"
              : "Search folder names…"
          }
        />
      </label>
      <p
        className="fine"
        title="Uses creation date, or modification date, when the drive has no Date Added metadata."
      >
        {entryView === "folders"
          ? "Folders: date added · newest first"
          : "Audio files: date added · newest first. Switch to Folders to open or select a whole folder."}
      </p>
      <div className="file-entries" aria-busy={loading}>
        {loading ? (
          <p role="status">Reading folder…</p>
        ) : (
          listing?.entries
            .filter(
              (e) =>
                e.folder === (entryView === "folders") &&
                e.name
                  .toLocaleLowerCase()
                  .includes(entrySearch.toLocaleLowerCase()),
            )
            .map((entry) => (
              <div className="file-entry" key={entry.path}>
                {!onFolder && (
                  <input
                    type="checkbox"
                    id={`file-${encodeURIComponent(entry.path)}`}
                    aria-label={`Select ${entry.name}${entry.folder ? " folder" : ""}`}
                    checked={selected.includes(entry.path)}
                    onChange={(e) =>
                      onSelect(
                        e.target.checked
                          ? [...selected, entry.path]
                          : selected.filter((p) => p !== entry.path),
                      )
                    }
                  />
                )}
                {entry.folder ? (
                  <button onClick={() => void open(entry.path)}>
                    <span aria-hidden="true">▣</span> {entry.name}
                    <span aria-hidden="true"> →</span>
                  </button>
                ) : (
                  <label
                    className="audio-file-name"
                    htmlFor={`file-${encodeURIComponent(entry.path)}`}
                  >
                    ♪ {entry.name}
                    <small>{entry.name.split(".").pop()?.toUpperCase()}</small>
                  </label>
                )}
              </div>
            ))
        )}
        {!loading &&
          listing &&
          !listing.entries.filter(
            (e) =>
              e.folder === (entryView === "folders") &&
              e.name
                .toLocaleLowerCase()
                .includes(entrySearch.toLocaleLowerCase()),
          ).length && (
            <p>
              {entrySearch
                ? "No matching names."
                : entryView === "files"
                  ? "No supported audio files in this folder. Switch to Folders to look inside a subfolder."
                  : "No subfolders here."}
            </p>
          )}
      </div>
      {!onFolder && (
        <p className="fine">
          Switch between Audio files and Folders to select both in one import.
          Selections stay checked across views. Folder imports include
          subfolders. Symbolic links and hidden files are excluded.
        </p>
      )}
    </section>
  );
}

type Receipt = {
  id: string;
  state?: string;
  root: string;
  mode: string;
  entries: {
    source: string;
    destination?: string;
    status: string;
    reason?: string;
    error?: string;
    size?: number;
    repoint?: string;
  }[];
};
export function ImportMusic({
  folder,
  request,
  busy,
  onClose,
  receiptId,
  requestError,
  sessions = [],
  onTag,
}: {
  folder: string;
  request: Request;
  busy: boolean;
  onClose: () => void;
  receiptId?: string;
  requestError?: string;
  sessions?: { id: string; state: string; total: number }[];
  onTag?: (id: string) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]),
    [mode, setMode] = useState("move");
  const [receipt, setReceipt] = useState<Receipt | null>(null),
    [started, setStarted] = useState(false),
    [error, setError] = useState("");
  const loadReceipt = async (id: string) => {
    try {
      const r = await fetch(`/api/imports/${id}`);
      if (!r.ok) throw new Error("Cannot load import receipt");
      setReceipt(await r.json());
    } catch (e) {
      setError(String(e));
    }
  };
  useEffect(() => {
    if (receiptId) void loadReceipt(receiptId);
  }, [receiptId]);
  useEffect(() => {
    if (!receipt || (!started && !receiptId)) return;
    const timer = setInterval(() => void loadReceipt(receipt.id), 1500);
    return () => clearInterval(timer);
  }, [receipt?.id, started, receiptId]);
  const ready =
    receipt?.entries.filter((e) => e.status === "ready").length ?? 0;
  const tagging = sessions.find((s) => s.id === receipt?.id),
    wasChecking = useRef(false);
  // Once the checks finish, go straight on to tagging the tracks.
  useEffect(() => {
    if (tagging?.state === "checking") wasChecking.current = true;
    else if (tagging?.state === "ready" && wasChecking.current) {
      wasChecking.current = false;
      onTag?.(tagging.id);
    }
  }, [tagging?.state]);
  return (
    <Dialog
      title={receiptId ? "Import receipt" : "Add music"}
      onClose={onClose}
    >
      <p>
        Destination{" "}
        <strong className="file-path">{receipt?.root || folder}</strong>
      </p>
      {(error || requestError) && (
        <p role="alert" className="error-text">
          {error || requestError}
        </p>
      )}
      {!receipt && (
        <>
          <FileBrowser
            request={request}
            selected={selected}
            onSelect={setSelected}
          />
          {selected.length > 0 && (
            <details className="selected-paths">
              <summary>{selected.length} selected files / folders</summary>
              {selected.map((p) => (
                <div key={p}>
                  <span>{p}</span>
                  <button
                    aria-label={`Remove ${p}`}
                    onClick={() => setSelected(selected.filter((x) => x !== p))}
                  >
                    ×
                  </button>
                </div>
              ))}
            </details>
          )}
          <label className="import-method">
            Import method
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="move">
                Move · remove originals after verification
              </option>
              <option value="copy">Copy · keep originals</option>
              <option value="index">
                Leave in place · add files where they are
              </option>
            </select>
          </label>
          <p className="fine">
            {mode === "move"
              ? "Each original is removed only after its copy is verified. A file rekordbox already lists moves too and keeps its entry, cues and playlists; quit rekordbox first for those."
              : mode === "copy"
                ? "Originals stay in Downloads or on their source drive. Names are preserved; collisions get a numbered filename."
                : "Nothing is copied or moved: each file is added to the Dex from where it is now, inside the music folder or not."}
          </p>
          <button
            className="primary"
            disabled={busy || !selected.length}
            onClick={async () => {
              const r = await request("imports/preview", {
                paths: selected,
                mode,
              });
              if (r) setReceipt(r);
            }}
          >
            Preview import
          </button>
        </>
      )}
      {receipt && (
        <>
          <div className="import-summary">
            <strong>
              {receipt.state
                ? label(receipt.state)
                : `${ready} ready to import`}
            </strong>
            <span>
              {receipt.entries.filter((e) => e.status === "complete").length}{" "}
              added ·{" "}
              {receipt.entries.filter((e) => e.status === "skipped").length}{" "}
              skipped
            </span>
          </div>
          <div className="import-entries">
            {receipt.entries.map((entry, i) => (
              <div key={i} className="import-entry">
                <strong>{entry.source.split("/").pop()}</strong>
                <span className="badge">{entry.status}</span>
                <p className="file-path">{entry.destination || entry.source}</p>
                {entry.reason && <p>{entry.reason}</p>}
                {entry.error && (
                  <p role="alert" className="error-text">
                    {entry.error}
                  </p>
                )}
              </div>
            ))}
          </div>
          {tagging && (
            <div className="callout">
              <strong>
                {tagging.state === "checking"
                  ? `Checking ${tagging.total} imported tracks`
                  : `${tagging.total} imported tracks are ready to tag`}
              </strong>
              <p>
                {tagging.state === "checking"
                  ? "Metadata, genres and duplicates are checked first. Tagging opens when the checks finish."
                  : "Listen to each track and give it My Tags and playlists."}
              </p>
              {tagging.state !== "checking" && (
                <button className="primary" onClick={() => onTag?.(tagging.id)}>
                  Tag {tagging.total} tracks
                </button>
              )}
            </div>
          )}
          <div className="button-row">
            {(!receipt.state || receipt.state === "preview") && (
              <>
                <button onClick={() => setReceipt(null)} disabled={busy}>
                  Change selection
                </button>
                <button
                  className="primary"
                  disabled={busy || !ready}
                  onClick={async () => {
                    const r = await request(
                      `imports/${receipt.id}/start`,
                      undefined,
                      "Music import started",
                    );
                    if (r) {
                      setStarted(true);
                      void loadReceipt(receipt.id);
                    }
                  }}
                >
                  {receipt.mode === "index"
                    ? `Add ${ready} files to Dex`
                    : `${receipt.mode === "move" ? "Move" : "Copy"} ${ready} files & add to Dex`}
                </button>
              </>
            )}
            {["partial", "interrupted"].includes(receipt.state || "") && (
              <button
                disabled={busy}
                onClick={async () => {
                  const r = await request(`imports/${receipt.id}/start`);
                  if (r) setStarted(true);
                }}
              >
                Retry unfinished files
              </button>
            )}
          </div>
          {receipt.entries.some(
            (e) => e.status === "complete" && !e.repoint,
          ) && (
            <section className="rekordbox-handoff">
              <h3>Add these tracks to rekordbox</h3>
              <p>
                Download the import playlist, then use File → Import → Import
                Playlist in rekordbox. Enable Auto Analysis in rekordbox’s
                Analysis preferences to analyze newly imported tracks. Rescan
                the library here afterward to link their rekordbox entries.
              </p>
              <a
                className="button"
                href={`/api/imports/${receipt.id}/playlist`}
                download
              >
                Download rekordbox import playlist
              </a>
              <p className="fine">
                The playlist references each file where it now is. Song Dex
                does not start rekordbox analysis itself.
              </p>
            </section>
          )}
        </>
      )}
    </Dialog>
  );
}
