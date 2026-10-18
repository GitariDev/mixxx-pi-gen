import React, { useEffect, useMemo, useRef, useState } from "react";
import { CatalogFilters } from "./CatalogFilters";
import { emptyFilters, matchesFilters } from "./catalog";
import type { Filters } from "./catalog";
import { GenreInput } from "./GenreInput";
import type { GenreCount } from "./GenreInput";
import { Dialog } from "./LibraryTools";
import "./review.css";

type Meta = Record<string, string | number>;
export type ReviewTrack = {
  id: number;
  source: string;
  path: string;
  available: number;
  state: string;
  error: string | null;
  metadata: Meta;
  file_metadata: Meta;
  evidence: unknown[];
  my_tags: { id: string; name: string; category: string }[];
  my_tags_loaded: number;
  playlists: { name: string; id?: string }[];
  descriptors?: Descriptors;
};
/** What MusicBrainz and Discogs say about a track beyond its own tags. */
type Descriptors = {
  musicbrainz?: {
    genres?: string[];
    tags?: string[];
    artist?: string;
    artist_genres?: string[];
    url?: string;
  };
  discogs?: {
    styles?: string[];
    genres?: string[];
    label?: string;
    year?: string;
    release?: string;
    url?: string;
  };
};
export type Proposal = {
  id: number;
  track_id: number;
  field: string;
  old_value: string;
  new_value: string;
  confidence: string;
  reason: string;
  source: string;
};
export type Suggested = {
  track_id: number;
  kind: "tag" | "playlist";
  target: string;
  reasons: string[];
};
/** One track of a scan: its ID, then the catalog, genre and tags lookup states. */
type Item = [number, string, string, string];
const lookups = (i: Item) => [i[1], i[2], i[3]];
export type ScanRun = {
  job_id: string;
  state: string;
  label: string;
  created_at: string;
  items: Item[];
};
type Job = { id: string; kind: string; state: string; message: string };
type Choices = {
  tags: { id: string; name: string; category: string }[];
  playlists: { id: string; name: string }[];
};
type Act = (endpoint: string, body?: unknown, success?: string) => Promise<any>;

const label = (s: string) => s.replaceAll("_", " ");
const dex = (id: number) => String(id).padStart(4, "0");
const plural = (n: number, word: string) =>
  `${n.toLocaleString()} ${n === 1 ? word : word.endsWith("y") ? word.slice(0, -1) + "ies" : word + "s"}`;
const blank = (v: unknown) => !String(v ?? "").trim();
const noGenre = (v: unknown) =>
  ["", "unknown genre", "other"].includes(
    String(v ?? "")
      .trim()
      .toLowerCase(),
  );
const usable = (t: ReviewTrack) => t.source !== "demo" && t.state !== "removed";
const FINISHED = new Set(["done", "failed", "skipped"]);
const SOURCES = ["Catalog", "Genre", "Tags"];
const stateNames: Record<string, string> = {
  queued: "waiting",
  running: "looking up",
  done: "done",
  failed: "failed",
  skipped: "not needed",
};
const keyOf = (s: { track_id: number; kind: string; target: string }) =>
  `${s.track_id}:${s.kind}:${s.target}`;
const strip = ({ track_id, kind, target }: Suggested) => ({
  track_id,
  kind,
  target,
});

/** What a scan by type looks at; the service applies the same tests. */
const scanKinds: [string, string, string, (t: ReviewTrack) => boolean][] = [
  [
    "genre",
    "Genre sync",
    "Tracks without a genre",
    (t) => noGenre(t.metadata.genre),
  ],
  [
    "year",
    "Missing year",
    "Tracks without a year",
    (t) => blank(t.metadata.year),
  ],
  [
    "album",
    "Missing album",
    "Tracks without an album",
    (t) => blank(t.metadata.album),
  ],
  [
    "artist",
    "No artist tag",
    "Artist and title read from the name",
    (t) => blank(t.metadata.artist),
  ],
  [
    "untagged",
    "Without My Tags",
    "Tracks with no My Tags yet",
    (t) => !!t.my_tags_loaded && !t.my_tags.length,
  ],
  ["failed", "Lookups that failed", "Try them again", (t) => !!t.error],
];

/** One suggestion per field, preferring the high-confidence one. */
export const onePerField = (list: Proposal[]) => [
  ...new Map(
    [...list]
      .sort(
        (a, b) =>
          Number(a.confidence === "high") - Number(b.confidence === "high"),
      )
      .map((p) => [p.field, p.id]),
  ).values(),
];
/** Safe to take without a look: the only value for a field that is blank or a high-confidence match. */
export const withoutWarnings = (
  tracks: ReviewTrack[],
  proposals: Proposal[],
) => {
  const held = new Map(tracks.map((t) => [t.id, t])),
    perField = new Map<string, number>();
  for (const p of proposals)
    perField.set(
      `${p.track_id}:${p.field}`,
      (perField.get(`${p.track_id}:${p.field}`) ?? 0) + 1,
    );
  return proposals.filter((p) => {
    const t = held.get(p.track_id);
    return (
      t &&
      usable(t) &&
      perField.get(`${p.track_id}:${p.field}`) === 1 &&
      (p.confidence === "high" || blank(p.old_value))
    );
  });
};
/** Replace a suggested value with the user's; approves it too when asked. */
export async function correctSuggestion(
  action: Act,
  p: Proposal,
  value: string,
  approve: boolean,
) {
  const done = await action(
    `proposals/${p.id}/edit`,
    { value },
    approve ? undefined : "Suggestion corrected and selected",
  );
  if (!done?.id) return null;
  if (approve) await action("proposals/approve", { ids: [done.id] });
  return done.id as number;
}

function Thumb({ track }: { track: ReviewTrack }) {
  const [failed, setFailed] = useState(false);
  return (
    <span className="thumb" aria-hidden="true">
      {track.available && !failed ? (
        <img
          src={`/api/tracks/${track.id}/artwork`}
          loading="lazy"
          decoding="async"
          alt=""
          onError={() => setFailed(true)}
        />
      ) : (
        <i />
      )}
    </span>
  );
}

/** Selects every suggestion of one entry; half-set when only some are selected. */
function EntryCheckbox({
  title,
  picked,
  total,
  onChange,
}: {
  title: string;
  picked: number;
  total: number;
  onChange: (on: boolean) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = picked > 0 && picked < total;
  }, [picked, total]);
  return (
    <input
      ref={ref}
      type="checkbox"
      aria-label={`Select all suggestions for ${title}`}
      checked={total > 0 && picked === total}
      disabled={!total}
      // A click here selects the entry; it should not also open or close the row.
      onClick={(e) => e.stopPropagation()}
      onChange={() => onChange(picked < total)}
    />
  );
}

function SourceLink({ p }: { p: Proposal }) {
  if (p.source.startsWith("https://"))
    return (
      <a href={p.source} target="_blank" rel="noreferrer">
        {p.source.startsWith("https://www.discogs.com/")
          ? "Data provided by Discogs ↗"
          : p.source.includes("acoustid")
            ? "AcoustID ↗"
            : "MusicBrainz ↗"}
      </a>
    );
  return (
    <span>
      {p.source === "manual"
        ? "Your correction"
        : p.source === "name"
          ? "From the track name"
          : "Demo evidence"}
    </span>
  );
}

/** A suggested value as one added line, with its approvals; Edit swaps in an input. */
function Candidate({
  p,
  queued,
  locked,
  picked,
  onPick,
  genres,
  act,
}: {
  p: Proposal;
  queued: boolean;
  locked: boolean;
  picked?: boolean;
  onPick?: () => void;
  genres: GenreCount[];
  act: Act;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const save = async (approve: boolean) => {
    if (editing === null) return;
    const id = await correctSuggestion(act, p, editing, approve);
    if (id) {
      setEditing(null);
      if (!approve) onPick?.();
    }
  };
  return (
    <div className={`diff-line added${queued ? " queued" : ""}`}>
      {onPick ? (
        <input
          type="checkbox"
          aria-label={`Select ${label(p.field)} ${p.new_value}`}
          checked={!!picked}
          disabled={queued}
          onChange={onPick}
        />
      ) : (
        <span />
      )}
      <span className="diff-sign" aria-hidden="true">
        +
      </span>
      {editing !== null ? (
        <form
          className="diff-edit"
          onSubmit={(e) => {
            e.preventDefault();
            void save(false);
          }}
        >
          {p.field === "genre" ? (
            <GenreInput
              library={genres}
              value={editing}
              onChange={setEditing}
            />
          ) : (
            <input
              autoFocus
              maxLength={255}
              aria-label={`Corrected ${label(p.field)}`}
              value={editing}
              onChange={(e) => setEditing(e.target.value)}
            />
          )}
          <div className="diff-actions">
            <button
              type="button"
              className="mini primary"
              disabled={locked || !editing.trim()}
              onClick={() => void save(true)}
            >
              Save & approve
            </button>
            <button type="submit" className="mini" disabled={!editing.trim()}>
              Save
            </button>
            <button
              type="button"
              className="mini quiet"
              onClick={() => setEditing(null)}
            >
              Cancel
            </button>
          </div>
          <small>Suggested: {p.new_value}</small>
        </form>
      ) : (
        <>
          <span className="diff-value">
            <strong>{p.new_value}</strong>
            <small>
              <span className={p.confidence === "high" ? "sure" : "unsure"}>
                {p.confidence === "high" ? "High confidence" : "Check"}
              </span>
              {" · "}
              <SourceLink p={p} />
              {p.reason && <span className="diff-reason"> · {p.reason}</span>}
            </small>
          </span>
          <span className="diff-actions">
            {queued ? (
              <span className="badge success">Saving…</span>
            ) : (
              <>
                <button
                  className="mini approve"
                  disabled={locked}
                  onClick={() => act("proposals/approve", { ids: [p.id] })}
                >
                  ✓ Approve
                </button>
                <button
                  className="mini"
                  onClick={() => setEditing(p.new_value)}
                >
                  Edit
                </button>
                <button
                  className="mini"
                  aria-label={`Reject ${label(p.field)} ${p.new_value}`}
                  title="Reject"
                  onClick={() =>
                    act(
                      "proposals/reject",
                      { ids: [p.id] },
                      "Suggestion rejected",
                    )
                  }
                >
                  ✕
                </button>
              </>
            )}
          </span>
        </>
      )}
    </div>
  );
}

/** The genres, styles and label the sources give the track, which suggestions draw on. */
function Described({ d }: { d?: Descriptors }) {
  const mb = d?.musicbrainz,
    dg = d?.discogs;
  const mbText = [
    ...(mb?.genres ?? []),
    ...(mb?.tags ?? []).map((t) => `#${t}`),
  ].join(", ");
  const dgText = [
    [...(dg?.styles ?? []), ...(dg?.genres ?? [])].join(", "),
    dg?.label,
    dg?.year,
  ]
    .filter(Boolean)
    .join(" · ");
  if (!mbText && !mb?.artist_genres?.length && !dgText) return null;
  return (
    <div className="described">
      {(mbText || !!mb?.artist_genres?.length) && (
        <p>
          <span>MusicBrainz</span>
          {mbText}
          {!!mb?.artist_genres?.length &&
            `${mbText ? " · " : ""}${mb.artist}: ${mb.artist_genres.join(", ")}`}
          {mb?.url && (
            <a href={mb.url} target="_blank" rel="noreferrer">
              ↗
            </a>
          )}
        </p>
      )}
      {dgText && (
        <p>
          <span>Discogs</span>
          {dgText}
          {dg?.url && (
            <a href={dg.url} target="_blank" rel="noreferrer">
              Data provided by Discogs ↗
            </a>
          )}
        </p>
      )}
    </div>
  );
}

/** A track's suggestions as an inline diff: current value removed, suggested values added. */
export function TrackDiff({
  track,
  proposals,
  suggested = [],
  choices,
  queued,
  locked,
  genres,
  act,
  picked,
  onPick,
  onEditTrack,
}: {
  track: ReviewTrack;
  proposals: Proposal[];
  suggested?: Suggested[];
  choices?: Choices;
  queued: Set<number>;
  locked: boolean;
  genres: GenreCount[];
  act: Act;
  /** Selection for bulk approval; without it lines have no checkboxes. */
  picked?: { fields: Set<number>; tags: Set<string> };
  onPick?: (fields: number[], tags: string[], on: boolean) => void;
  onEditTrack?: () => void;
}) {
  const fields = new Map<string, Proposal[]>();
  for (const p of proposals)
    fields.set(p.field, [...(fields.get(p.field) ?? []), p]);
  const name = (s: Suggested) =>
    s.kind === "tag"
      ? choices?.tags.find((t) => t.id === s.target)?.name
      : choices?.playlists.find((p) => p.id === s.target)?.name;
  const open = proposals.filter((p) => !queued.has(p.id));
  return (
    <div className="diff">
      <Described d={track.descriptors} />
      {[...fields].map(([field, list]) => {
        const current = String(track.metadata[field] ?? ""),
          file = String(track.file_metadata[field] ?? "");
        return (
          <div className="diff-field" key={field}>
            <span className="diff-label">{label(field)}</span>
            <div>
              {!blank(current) && (
                <div className="diff-line removed">
                  <span />
                  <span className="diff-sign" aria-hidden="true">
                    −
                  </span>
                  <span className="diff-value">
                    {current}
                    {track.available === 1 && file !== current && (
                      <small>File tag: {file || "empty"}</small>
                    )}
                  </span>
                </div>
              )}
              {list.map((p) => (
                <Candidate
                  key={p.id}
                  p={p}
                  queued={queued.has(p.id)}
                  locked={locked}
                  genres={genres}
                  act={act}
                  picked={picked?.fields.has(p.id)}
                  onPick={
                    onPick &&
                    (() => onPick([p.id], [], !picked?.fields.has(p.id)))
                  }
                />
              ))}
            </div>
          </div>
        );
      })}
      {(["tag", "playlist"] as const).map((kind) => {
        const list = suggested.filter((s) => s.kind === kind);
        if (!list.length) return null;
        return (
          <div className="diff-field" key={kind}>
            <span className="diff-label">
              {kind === "tag" ? "My Tags" : "Playlists"}
            </span>
            <div>
              {list.map((s) => (
                <div className="diff-line added" key={keyOf(s)}>
                  {onPick ? (
                    <input
                      type="checkbox"
                      aria-label={`Select ${name(s)}`}
                      checked={!!picked?.tags.has(keyOf(s))}
                      onChange={() =>
                        onPick([], [keyOf(s)], !picked?.tags.has(keyOf(s)))
                      }
                    />
                  ) : (
                    <span />
                  )}
                  <span className="diff-sign" aria-hidden="true">
                    +
                  </span>
                  <span className="diff-value">
                    <strong>
                      {kind === "playlist" && "▤ "}
                      {name(s) ?? "Unknown"}
                    </strong>
                    <small>{s.reasons.join(" · ")}</small>
                  </span>
                  <span className="diff-actions">
                    <button
                      className="mini approve"
                      onClick={() =>
                        act("suggestions/approve", { items: [strip(s)] })
                      }
                    >
                      ✓ Add
                    </button>
                    <button
                      className="mini"
                      aria-label={`Do not add ${name(s)}`}
                      title="Do not add"
                      onClick={() =>
                        act("suggestions/reject", { items: [strip(s)] })
                      }
                    >
                      ✕
                    </button>
                  </span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
      <div className="diff-footer">
        <button
          className="mini approve"
          disabled={locked || (!open.length && !suggested.length)}
          onClick={async () => {
            if (open.length)
              await act("proposals/approve", { ids: onePerField(open) });
            if (suggested.length)
              await act("suggestions/approve", {
                items: suggested.map(strip),
              });
          }}
        >
          ✓ Approve track
        </button>
        <button
          className="mini"
          disabled={!open.length && !suggested.length}
          onClick={async () => {
            if (open.length)
              await act(
                "proposals/reject",
                { ids: open.map((p) => p.id) },
                "Suggestions rejected for this track",
              );
            if (suggested.length)
              await act("suggestions/reject", {
                items: suggested.map(strip),
              });
          }}
        >
          Reject all
        </button>
        {onEditTrack && (
          <button className="mini quiet" onClick={onEditTrack}>
            Edit track
          </button>
        )}
      </div>
    </div>
  );
}

function ScanMenu({
  tracks,
  disabled,
  onScan,
  onCustom,
}: {
  tracks: ReviewTrack[];
  disabled: boolean;
  onScan: (scope: string, kind?: string) => void;
  onCustom: () => void;
}) {
  const [open, setOpen] = useState(false),
    [types, setTypes] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", key);
    };
  }, [open]);
  const pool = useMemo(() => tracks.filter(usable), [tracks]);
  const fresh = pool.filter((t) => !t.evidence.length || t.error).length;
  const choose = (scope: string, kind?: string) => {
    setOpen(false);
    onScan(scope, kind);
  };
  const option = (
    title: string,
    detail: string,
    count: React.ReactNode,
    onClick: () => void,
    off = false,
    extra: React.HTMLAttributes<HTMLButtonElement> = {},
  ) => (
    <button role="menuitem" disabled={off} onClick={onClick} {...extra}>
      <span>
        {title}
        <small>{detail}</small>
      </span>
      <b>{count}</b>
    </button>
  );
  return (
    <div className="scan-menu" ref={ref}>
      <button
        className="primary"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen(!open)}
      >
        Scan ▾
      </button>
      {open && (
        <div className="scan-options" role="menu">
          <p>Finds metadata, genres, My Tags and playlists</p>
          {option(
            "New tracks",
            "Not looked up yet, or the lookup failed",
            fresh.toLocaleString(),
            () => choose("new"),
            !fresh,
          )}
          {option(
            "Full library",
            "Everything again; earlier answers are reused",
            pool.length.toLocaleString(),
            () => choose("all"),
            !pool.length,
          )}
          {option(
            "By type",
            "Genre sync and other gaps",
            types ? "▾" : "▸",
            () => setTypes(!types),
            false,
            { "aria-expanded": types },
          )}
          {types && (
            <div className="scan-types" role="group" aria-label="By type">
              {scanKinds.map(([kind, title, detail, test]) => {
                const n = pool.filter(test).length;
                return (
                  <React.Fragment key={kind}>
                    {option(
                      title,
                      detail,
                      n.toLocaleString(),
                      () => choose("type", kind),
                      !n,
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          )}
          {option(
            "Custom filter…",
            "Search, genres, My Tags, playlists, BPM, year",
            "›",
            () => {
              setOpen(false);
              onCustom();
            },
            !pool.length,
          )}
        </div>
      )}
    </div>
  );
}

function CustomScan({
  tracks,
  busy,
  onLoadTags,
  onScan,
  onClose,
}: {
  tracks: ReviewTrack[];
  busy: boolean;
  onLoadTags: () => void;
  onScan: (ids: number[]) => void;
  onClose: () => void;
}) {
  const [filters, setFilters] = useState<Filters>({ ...emptyFilters }),
    [search, setSearch] = useState("");
  const pool = useMemo(() => tracks.filter(usable), [tracks]);
  const query = search.trim().toLocaleLowerCase();
  const matching = pool.filter(
    (t) =>
      (!query ||
        `${t.metadata.title} ${t.metadata.artist} ${t.metadata.album} ${t.metadata.genre}`
          .toLocaleLowerCase()
          .includes(query)) &&
      matchesFilters(t, filters),
  );
  return (
    <Dialog title="Scan with a custom filter" onClose={onClose} wide>
      <label className="custom-scan-search">
        Search
        <input
          autoFocus
          value={search}
          placeholder="Title, artist, album or genre"
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      <CatalogFilters
        tracks={pool}
        value={filters}
        onChange={setFilters}
        onLoadTags={onLoadTags}
        busy={busy}
      />
      <div className="button-row">
        <button onClick={onClose}>Cancel</button>
        <button
          className="primary"
          disabled={busy || !matching.length}
          onClick={() => onScan(matching.map((t) => t.id))}
        >
          Scan {plural(matching.length, "track")}
        </button>
      </div>
    </Dialog>
  );
}

function ScanStatus({
  scan,
  running,
  busy,
  act,
}: {
  scan: ScanRun;
  running: boolean;
  busy: boolean;
  act: Act;
}) {
  const n = scan.items.length,
    finished = (s: string) => FINISHED.has(s);
  const done = scan.items.filter((i) => lookups(i).every(finished)).length;
  const failed = scan.items.filter(
    (i) => i[1] === "failed" || i[2] === "failed",
  ).length;
  return (
    <div className="scan-status" role="status">
      <div>
        <strong>{scan.label}</strong>
        <span>
          {running
            ? `Scanning ${done.toLocaleString()} of ${plural(n, "track")}`
            : scan.state === "interrupted"
              ? `Stopped at ${done.toLocaleString()} of ${n.toLocaleString()}`
              : `${plural(n, "track")} scanned ${new Date(scan.created_at).toLocaleDateString()}`}
          {failed > 0 && ` · ${plural(failed, "lookup")} failed`}
        </span>
      </div>
      <progress value={done} max={n || 1} />
      <ul aria-label="Lookups">
        {SOURCES.map((name, i) => (
          <li key={name}>
            {name}{" "}
            <b>
              {scan.items.filter((item) => finished(lookups(item)[i])).length}
            </b>
            /{n}
          </li>
        ))}
      </ul>
      {running ? (
        <button
          className="mini"
          disabled={busy}
          onClick={() => act("lookup/stop")}
        >
          Stop
        </button>
      ) : (
        ["interrupted", "failed"].includes(scan.state) && (
          <button
            className="mini"
            disabled={busy}
            onClick={() =>
              act(`jobs/${scan.job_id}/resume`, undefined, "Scan resumed")
            }
          >
            Resume
          </button>
        )
      )}
    </div>
  );
}

function Pips({ states }: { states: string[] }) {
  return (
    <span
      className="pips"
      aria-label={states
        .map((s, i) => `${SOURCES[i]} ${stateNames[s] ?? s}`)
        .join(", ")}
    >
      {states.map((s, i) => (
        <i
          key={i}
          className={s}
          title={`${SOURCES[i]}: ${stateNames[s] ?? s}`}
        />
      ))}
    </span>
  );
}

/** Scan & Review: start scans, follow them as they run, and approve what they find. */
export function Review({
  tracks,
  proposals,
  suggested,
  queued,
  scan,
  active,
  choices,
  chosen,
  setChosen,
  busy,
  demo,
  genres,
  action,
  onEditTrack,
  notices,
}: {
  tracks: ReviewTrack[];
  proposals: Proposal[];
  suggested: Suggested[];
  queued: number[];
  scan: ScanRun | null;
  active?: Job;
  choices: Choices;
  chosen: Set<number>;
  setChosen: (next: Set<number>) => void;
  busy: boolean;
  demo: boolean;
  genres: GenreCount[];
  action: Act;
  onEditTrack: (id: number) => void;
  /** Callouts about imports, writes and syncing, shown above the list. */
  notices: React.ReactNode;
}) {
  const scanning = active?.kind === "enrich";
  const [view, setView] = useState<"review" | "scan">(
    scanning ? "scan" : "review",
  );
  const [tagPicks, setTagPicks] = useState<Set<string>>(new Set()),
    [limit, setLimit] = useState(100),
    [custom, setCustom] = useState(false),
    [confirm, setConfirm] = useState<"selected" | "safe" | null>(null),
    [withTags, setWithTags] = useState(false);
  useEffect(() => {
    if (scanning) setView("scan");
  }, [scanning, scan?.job_id]);
  useEffect(() => setLimit(100), [view]);

  const byId = useMemo(() => new Map(tracks.map((t) => [t.id, t])), [tracks]);
  const waiting = useMemo(() => new Set(queued), [queued]);
  const fieldsOf = useMemo(() => {
    const map = new Map<number, Proposal[]>();
    for (const p of proposals)
      map.set(p.track_id, [...(map.get(p.track_id) ?? []), p]);
    return map;
  }, [proposals]);
  const tagsOf = useMemo(() => {
    const map = new Map<number, Suggested[]>();
    for (const s of suggested)
      map.set(s.track_id, [...(map.get(s.track_id) ?? []), s]);
    return map;
  }, [suggested]);
  const states = useMemo(
    () => new Map((scan?.items ?? []).map((i) => [i[0], lookups(i)])),
    [scan],
  );
  const toReview = useMemo(
    () =>
      [...new Set([...fieldsOf.keys(), ...tagsOf.keys()])]
        .filter((id) => byId.has(id))
        .sort((a, b) => a - b),
    [fieldsOf, tagsOf, byId],
  );
  const scanned = (scan?.items ?? [])
    .map((i) => i[0])
    .filter((id) => byId.has(id));
  const list = view === "scan" ? scanned : toReview;
  // Ticks and edits made mid-approval would act on suggestions that are about to go.
  const approving = busy || active?.kind === "approve";
  const locked = approving || demo || (!!active && !scanning);

  const safe = useMemo(
    () => withoutWarnings(tracks, proposals).filter((p) => !waiting.has(p.id)),
    [tracks, proposals, waiting],
  );
  const pickedFields = proposals.filter((p) => chosen.has(p.id)),
    pickedTags = suggested.filter((s) => tagPicks.has(keyOf(s)));
  const pick = (fields: number[], tags: string[], on: boolean) => {
    const next = new Set(chosen);
    for (const id of fields) {
      const p = proposals.find((x) => x.id === id);
      // One value per field: ticking one unticks the other candidates.
      if (on && p)
        for (const other of fieldsOf.get(p.track_id) ?? [])
          if (other.field === p.field) next.delete(other.id);
      on ? next.add(id) : next.delete(id);
    }
    setChosen(next);
    const nextTags = new Set(tagPicks);
    for (const key of tags) on ? nextTags.add(key) : nextTags.delete(key);
    setTagPicks(nextTags);
  };
  const tracksIn = (ids: { track_id: number }[]) =>
    new Set(ids.map((p) => p.track_id)).size;
  const approve = async (ids: number[], items: Suggested[]) => {
    for (let i = 0; i < ids.length; i += 5000)
      if (!(await action("proposals/approve", { ids: ids.slice(i, i + 5000) })))
        return false;
    for (let i = 0; i < items.length; i += 5000)
      if (
        !(await action("suggestions/approve", {
          items: items.slice(i, i + 5000).map(strip),
        }))
      )
        return false;
    return true;
  };
  const scanWith = (body: unknown) => {
    setCustom(false);
    void action("lookup", body);
  };

  return (
    <div className="page-body review-page">
      <div className="review-toolbar">
        <ScanMenu
          tracks={tracks}
          disabled={busy || !!active || demo || !tracks.length}
          onScan={(scope, kind) => scanWith({ scope, kind })}
          onCustom={() => setCustom(true)}
        />
        <button
          disabled={busy || !!active || demo}
          onClick={() => action("scan", undefined, "Library rescan started")}
        >
          Rescan rekordbox library
        </button>
        <button
          className="merge-all"
          disabled={locked || !safe.length}
          onClick={() => setConfirm("safe")}
        >
          Approve all {safe.length.toLocaleString()} without warnings
        </button>
      </div>
      {scan && (
        <ScanStatus scan={scan} running={scanning} busy={busy} act={action} />
      )}
      {notices}
      <div className="review-views" role="tablist" aria-label="Show">
        <button
          role="tab"
          aria-selected={view === "review"}
          onClick={() => setView("review")}
        >
          To review <b>{toReview.length.toLocaleString()}</b>
        </button>
        <button
          role="tab"
          aria-selected={view === "scan"}
          disabled={!scan}
          onClick={() => setView("scan")}
        >
          {scan ? scan.label : "Last scan"}{" "}
          <b>{scanned.length.toLocaleString()}</b>
        </button>
      </div>
      <fieldset className="review-list" disabled={approving}>
        {active?.kind === "approve" && (
          <p className="review-locked" role="status">
            Approval in progress. The list unlocks when it finishes.
          </p>
        )}
        {!list.length ? (
          <div className="empty">
            <h2>Nothing waiting for review</h2>
            <div>
              <p>
                Scan your library to find metadata, genres, My Tags and
                playlists. Ambiguous or missing data leaves your tags intact.
              </p>
            </div>
          </div>
        ) : (
          <ol className="review-rows">
            {list.slice(0, limit).map((id) => {
              const t = byId.get(id)!,
                fields = fieldsOf.get(id) ?? [],
                tags = tagsOf.get(id) ?? [],
                state = states.get(id),
                count = fields.length + tags.length,
                picked =
                  fields.filter((p) => chosen.has(p.id)).length +
                  tags.filter((s) => tagPicks.has(keyOf(s))).length,
                pending = state?.some((s) => !FINISHED.has(s)),
                title = String(t.metadata.title || t.path.split("/").pop());
              const head = (
                <>
                  <EntryCheckbox
                    title={title}
                    picked={picked}
                    total={count}
                    onChange={(on) =>
                      pick(
                        on ? onePerField(fields) : fields.map((p) => p.id),
                        tags.map(keyOf),
                        on,
                      )
                    }
                  />
                  <Thumb track={t} />
                  <span className="row-titles">
                    <strong>{title}</strong>
                    <small>
                      NO. {dex(id)} · {t.metadata.artist || "Unknown artist"}
                      {t.metadata.album ? ` · ${t.metadata.album}` : ""}
                    </small>
                  </span>
                  <span className="row-changes">
                    {count ? (
                      <>
                        {[...new Set(fields.map((p) => p.field))].map((f) => (
                          <span className="chip" key={f}>
                            {label(f)}
                          </span>
                        ))}
                        {(["tag", "playlist"] as const).map((kind) => {
                          const n = tags.filter((s) => s.kind === kind).length;
                          return n ? (
                            <span className="chip tag" key={kind}>
                              +{n} {kind === "tag" ? "My Tag" : "playlist"}
                              {n > 1 ? "s" : ""}
                            </span>
                          ) : null;
                        })}
                      </>
                    ) : (
                      <span className="row-note">
                        {pending
                          ? state?.includes("running")
                            ? "Looking up…"
                            : "Waiting"
                          : state?.some((s) => s === "failed")
                            ? "Lookup failed"
                            : "No changes found"}
                      </span>
                    )}
                  </span>
                  {state ? <Pips states={state} /> : <span />}
                </>
              );
              return (
                <li key={id} className={pending ? "scanning" : undefined}>
                  {count ? (
                    <details className="review-row">
                      <summary>{head}</summary>
                      <TrackDiff
                        track={t}
                        proposals={fields}
                        suggested={tags}
                        choices={choices}
                        queued={waiting}
                        locked={locked}
                        genres={genres}
                        act={action}
                        picked={{ fields: chosen, tags: tagPicks }}
                        onPick={pick}
                        onEditTrack={() => onEditTrack(id)}
                      />
                    </details>
                  ) : (
                    <div className="review-row quiet-row">{head}</div>
                  )}
                </li>
              );
            })}
          </ol>
        )}
        {list.length > limit && (
          <button className="show-more" onClick={() => setLimit(limit + 100)}>
            Show more ({(list.length - limit).toLocaleString()} left)
          </button>
        )}
        {(pickedFields.length > 0 || pickedTags.length > 0) && (
          <div className="review-actions">
            <div>
              <strong>
                {plural(pickedFields.length + pickedTags.length, "change")}{" "}
                selected
              </strong>
              <small>
                Across{" "}
                {plural(tracksIn([...pickedFields, ...pickedTags]), "track")}
              </small>
            </div>
            <div className="button-row">
              <button
                className="quiet"
                onClick={() => {
                  setChosen(new Set());
                  setTagPicks(new Set());
                }}
              >
                Clear
              </button>
              <button
                onClick={async () => {
                  if (pickedFields.length)
                    await action(
                      "proposals/reject",
                      { ids: pickedFields.map((p) => p.id) },
                      "Selected suggestions rejected",
                    );
                  if (pickedTags.length)
                    await action("suggestions/reject", {
                      items: pickedTags.map(strip),
                    });
                  setChosen(new Set());
                  setTagPicks(new Set());
                }}
              >
                Reject selected
              </button>
              <button
                className="primary"
                disabled={locked}
                onClick={() => setConfirm("selected")}
              >
                Approve selected
              </button>
            </div>
          </div>
        )}
      </fieldset>
      {custom && (
        <CustomScan
          tracks={tracks}
          busy={busy}
          onLoadTags={() => action("my-tags/load")}
          onScan={(ids) => scanWith({ scope: "custom", ids })}
          onClose={() => setCustom(false)}
        />
      )}
      {confirm &&
        (() => {
          const fields = confirm === "safe" ? safe : pickedFields,
            tags =
              confirm === "safe" ? (withTags ? suggested : []) : pickedTags,
            replacing = fields.filter((p) => !blank(p.old_value)).length;
          return (
            <Dialog
              title={
                confirm === "safe"
                  ? "Approve everything without warnings?"
                  : "Approve the selected changes?"
              }
              onClose={() => setConfirm(null)}
            >
              <p>
                {plural(fields.length, "field")} on{" "}
                {plural(tracksIn(fields), "track")}: {fields.length - replacing}{" "}
                fill a blank field and {replacing} replace a value
                {confirm === "safe" &&
                  " from a high-confidence match. Each is the only suggestion for its field"}
                . They are saved in Song Dex and written to rekordbox and
                reachable audio files, each backed up first.
                {scanning && " They are saved as the scan goes."}
              </p>
              {confirm === "safe" && suggested.length > 0 && (
                <label className="confirm-option">
                  <input
                    type="checkbox"
                    checked={withTags}
                    onChange={(e) => setWithTags(e.target.checked)}
                  />{" "}
                  Also add the{" "}
                  {plural(suggested.length, "suggested My Tag and playlist")}
                </label>
              )}
              {tags.length > 0 && (
                <p>
                  {plural(tags.length, "My Tag and playlist choice")} wait to be
                  written to rekordbox.
                </p>
              )}
              <p>Quit rekordbox and its background agent before continuing.</p>
              <div className="button-row">
                <button autoFocus onClick={() => setConfirm(null)}>
                  Cancel
                </button>
                <button
                  className="primary"
                  disabled={busy || (!fields.length && !tags.length)}
                  onClick={async () => {
                    setConfirm(null);
                    if (
                      await approve(
                        fields.map((p) => p.id),
                        tags,
                      )
                    ) {
                      setChosen(new Set());
                      setTagPicks(new Set());
                    }
                  }}
                >
                  Approve {plural(fields.length + tags.length, "change")}
                </button>
              </div>
            </Dialog>
          );
        })()}
    </div>
  );
}
