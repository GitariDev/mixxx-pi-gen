import { useEffect, useState } from "react";
import { Dialog } from "./LibraryTools";

type Backup = {
  id: string;
  label: string;
  detail: string;
  state: string;
  created_at: string;
  size: number;
  undoable: boolean;
  locked: boolean;
};
type Listing = { items: Backup[]; total: number; free: number };

const space = (bytes: number) =>
  bytes >= 1e9
    ? `${(bytes / 1e9).toFixed(1)} GB`
    : bytes >= 1e6
      ? `${Math.round(bytes / 1e6)} MB`
      : "under 1 MB";
const plural = (n: number) => `${n} ${n === 1 ? "backup" : "backups"}`;
const DAY = 24 * 60 * 60 * 1000;

type Drive = {
  path: string;
  name: string;
  free: number;
  total: number;
  writable: boolean;
  last: { scope: string; finished_at: string; failed: number } | null;
};
type Overview = {
  drives: Drive[];
  rekordbox_db: string;
  sizes: {
    database: number;
    rekordbox: number;
    music: number;
    catalog: number;
  };
  music_files: number;
  music_missing: number;
};
type Scope = "database" | "rekordbox" | "library";
const scopes: { id: Scope; label: string; detail: string }[] = [
  {
    id: "database",
    label: "rekordbox database",
    detail:
      "master.db and the playlist file: your collection, playlists, My Tags, cues and hot cues. Quickest.",
  },
  {
    id: "rekordbox",
    label: "rekordbox folder",
    detail:
      "The database plus waveforms and beat grids, artwork and rekordbox's own rolling backups.",
  },
  {
    id: "library",
    label: "Whole library",
    detail:
      "The rekordbox folder and every music file in the collection. Music is mirrored once per drive, so later backups only copy new or changed files.",
  },
];

function ExternalBackup({
  locked,
  action,
  onClose,
}: {
  locked: boolean;
  action: (endpoint: string, body?: unknown) => Promise<unknown>;
  onClose: () => void;
}) {
  const [overview, setOverview] = useState<Overview | null>(null),
    [failed, setFailed] = useState(""),
    [drive, setDrive] = useState(""),
    [scope, setScope] = useState<Scope>("database"),
    [catalog, setCatalog] = useState(true);
  const load = () => {
    setFailed("");
    fetch("/api/backups/external")
      .then((res) => {
        if (!res.ok) throw new Error("Could not list the connected drives");
        return res.json();
      })
      .then((found: Overview) => {
        setOverview(found);
        // Keep the chosen drive while it is still connected.
        setDrive((d) =>
          found.drives.some((x) => x.path === d && x.writable)
            ? d
            : (found.drives.find((x) => x.writable)?.path ?? ""),
        );
      })
      .catch((e) => setFailed(e.message));
  };
  useEffect(load, []);

  const sizes = overview?.sizes,
    chosen = overview?.drives.find((d) => d.path === drive),
    needed = sizes
      ? (scope === "database" ? sizes.database : sizes.rekordbox) +
        (scope === "library" ? sizes.music : 0) +
        (catalog ? sizes.catalog : 0)
      : 0,
    label = (id: string) => scopes.find((s) => s.id === id)?.label ?? id;
  return (
    <Dialog title="Back up to an external drive" onClose={onClose}>
      {!overview ? (
        <p className={failed ? "error-text" : undefined}>
          {failed || "Looking for drives…"}
        </p>
      ) : (
        <>
          <fieldset className="backup-choice">
            <legend>Drive</legend>
            {!overview.drives.length && (
              <p>
                No external drives are connected. Connect one, then refresh.
              </p>
            )}
            {overview.drives.map((d) => (
              <label key={d.path} className={d.writable ? "" : "disabled"}>
                <input
                  type="radio"
                  name="drive"
                  disabled={!d.writable}
                  checked={drive === d.path}
                  onChange={() => setDrive(d.path)}
                />
                <div>
                  <strong>{d.name}</strong>
                  <p>
                    {space(d.free)} free of {space(d.total)}
                    {!d.writable && " · read-only"}
                    {d.last &&
                      ` · last backup ${new Date(d.last.finished_at).toLocaleString()} (${label(d.last.scope)})`}
                  </p>
                </div>
              </label>
            ))}
            <button type="button" className="quiet" onClick={load}>
              Refresh drives
            </button>
          </fieldset>
          <fieldset className="backup-choice">
            <legend>What to back up</legend>
            {scopes.map((s) => (
              <label key={s.id}>
                <input
                  type="radio"
                  name="scope"
                  checked={scope === s.id}
                  onChange={() => setScope(s.id)}
                />
                <div>
                  <strong>{s.label}</strong>
                  <p>{s.detail}</p>
                </div>
                <span className="backup-size">
                  {space(
                    s.id === "database"
                      ? overview.sizes.database
                      : s.id === "rekordbox"
                        ? overview.sizes.rekordbox
                        : overview.sizes.rekordbox + overview.sizes.music,
                  )}
                </span>
              </label>
            ))}
            <label>
              <input
                type="checkbox"
                checked={catalog}
                onChange={(e) => setCatalog(e.target.checked)}
              />
              <div>
                <strong>Also the Song Dex catalog</strong>
                <p>
                  Reviews, history and settings, including saved AcoustID and
                  Discogs keys.
                </p>
              </div>
              <span className="backup-size">
                {space(overview.sizes.catalog)}
              </span>
            </label>
          </fieldset>
          {scope === "library" && overview.music_missing > 0 && (
            <p className="difference">
              △ {overview.music_missing} of{" "}
              {overview.music_files + overview.music_missing} music files are
              offline or missing and will be skipped.
            </p>
          )}
          {chosen && needed > chosen.free && (
            <p className="difference">
              △ This needs up to {space(needed)} but {chosen.name} has{" "}
              {space(chosen.free)} free
              {scope === "library" &&
                "; music already backed up there is not copied again"}
              .
            </p>
          )}
          <p className="fine">
            Quit rekordbox first. Each backup goes in a dated folder under “Song
            Dex Backups” on the drive, with a README on how to restore. Nothing
            on the drive is deleted.
          </p>
          {failed && <p className="error-text">{failed}</p>}
          <div className="button-row">
            <button onClick={onClose}>Cancel</button>
            <button
              className="primary"
              disabled={locked || !chosen}
              onClick={async () => {
                onClose();
                await action("backups/external", { drive, scope, catalog });
              }}
            >
              Start backup{chosen && ` to ${chosen.name}`}
            </button>
          </div>
        </>
      )}
    </Dialog>
  );
}

export function Backups({
  locked,
  action,
}: {
  locked: boolean;
  action: (
    endpoint: string,
    body?: unknown,
    success?: string,
  ) => Promise<unknown>;
}) {
  const [listing, setListing] = useState<Listing | null>(null),
    [failed, setFailed] = useState(""),
    [picked, setPicked] = useState<Set<string>>(new Set()),
    [limit, setLimit] = useState(100),
    [confirm, setConfirm] = useState(false),
    [external, setExternal] = useState(false);
  const load = () =>
    fetch("/api/backups")
      .then((res) => {
        if (!res.ok) throw new Error("Could not read the backups folder");
        return res.json();
      })
      .then((found: Listing) => {
        setListing(found);
        setFailed("");
        // Drop ticks for backups that are gone.
        const live = new Set(found.items.map((b) => b.id));
        setPicked((prev) => new Set([...prev].filter((id) => live.has(id))));
      })
      .catch((e) => setFailed(e.message));
  useEffect(() => {
    load();
  }, []);

  if (!listing)
    return (
      <p className={failed ? "error-text" : undefined}>
        {failed || "Measuring backups…"}
      </p>
    );
  const { items, total, free } = listing,
    chosen = items.filter((b) => picked.has(b.id)),
    chosenSize = chosen.reduce((n, b) => n + b.size, 0);
  const pick = (list: Backup[]) =>
    setPicked(new Set(list.filter((b) => !b.locked).map((b) => b.id)));
  const toggle = (id: string) => {
    const next = new Set(picked);
    next.has(id) ? next.delete(id) : next.add(id);
    setPicked(next);
  };

  return (
    <>
      <div className="callout">
        <strong>
          {plural(items.length)} use {space(total)} · {space(free)} free on this
          disk
        </strong>
        <p>
          Before every write, Song Dex copies what it is about to change. Only
          the latest change to rekordbox or to a file can be undone, so a backup
          is removed automatically once a newer change, a restore or an edit
          made elsewhere means it can no longer be undone. Deleting a backup
          never touches your music or rekordbox.
        </p>
        {failed && <p className="error-text">{failed}</p>}
        <div className="button-row">
          <button disabled={locked} onClick={() => setExternal(true)}>
            Back up to external drive
          </button>
        </div>
      </div>
      {external && (
        <ExternalBackup
          locked={locked}
          action={action}
          onClose={() => setExternal(false)}
        />
      )}
      {!items.length ? (
        <div className="empty">
          <h2>No backups yet</h2>
          <div>
            <p>One is taken before each change to rekordbox or a file.</p>
          </div>
        </div>
      ) : (
        <div className="duplicate-toolbar">
          <strong>
            {plural(chosen.length)} selected
            {chosen.length > 0 && ` · ${space(chosenSize)}`}
          </strong>
          <button
            className="primary"
            disabled={locked || !chosen.length}
            onClick={() => setConfirm(true)}
          >
            Delete selected
          </button>
          <button
            disabled={items.every((b) => b.locked || picked.has(b.id))}
            onClick={() => pick(items)}
          >
            Select all
          </button>
          <button
            onClick={() =>
              pick(
                items.filter(
                  (b) => Date.now() - Date.parse(b.created_at) > 7 * DAY,
                ),
              )
            }
          >
            Select older than a week
          </button>
          {chosen.length > 0 && (
            <button className="quiet" onClick={() => setPicked(new Set())}>
              Clear selection
            </button>
          )}
        </div>
      )}
      {items.slice(0, limit).map((b) => (
        <label className="backup-row" key={b.id}>
          <input
            type="checkbox"
            disabled={b.locked}
            checked={picked.has(b.id)}
            onChange={() => toggle(b.id)}
          />
          <div>
            <strong>
              {b.label}{" "}
              {b.undoable && (
                <span className="badge success">Can still be undone</span>
              )}{" "}
              {b.locked && (
                <span className="badge warn">
                  Needed to recover an unfinished write
                </span>
              )}
            </strong>
            <p>{b.detail}</p>
          </div>
          <time>{new Date(b.created_at).toLocaleString()}</time>
          <span className="backup-size">{space(b.size)}</span>
        </label>
      ))}
      {items.length > limit && (
        <button onClick={() => setLimit(limit + 100)}>
          Show more ({items.length - limit} left)
        </button>
      )}
      {confirm && (
        <Dialog title="Delete backups?" onClose={() => setConfirm(false)}>
          <p>
            {plural(chosen.length)} will be deleted, freeing {space(chosenSize)}
            . Your music and rekordbox are not touched, and the entries stay in
            History.
          </p>
          {chosen.some((b) => b.undoable) && (
            <p className="difference">
              △ {plural(chosen.filter((b) => b.undoable).length)} can still be
              undone now. After deleting, those changes can no longer be
              restored.
            </p>
          )}
          <p>This cannot be reversed.</p>
          <div className="button-row">
            <button autoFocus onClick={() => setConfirm(false)}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={locked}
              onClick={async () => {
                setConfirm(false);
                await action("backups/delete", {
                  ids: chosen.map((b) => b.id),
                });
                await load();
              }}
            >
              Delete
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
