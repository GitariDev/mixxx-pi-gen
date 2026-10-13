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
    [confirm, setConfirm] = useState(false);
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
      </div>
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
