import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/pixelify-sans/400.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "./style.css";
import { CatalogFilters } from "./CatalogFilters";
import { emptyFilters, matchesFilters, compareTracks } from "./catalog";
import type { Filters } from "./catalog";
import { Dialog, FileBrowser, ImportMusic, ManualEditor } from "./LibraryTools";
import { Backups } from "./Backups";
import { Duplicates } from "./Duplicates";
import { GenreInput } from "./GenreInput";
import { NewPlaylist, TrackLists } from "./Lists";
import type { ListChoices } from "./Lists";
import { ShelfTree } from "./Playlists";
import { shelfMembers, shelfPath } from "./shelf";
import type { Shelf } from "./shelf";
import { Review } from "./Review";
import { AddToLists, SelectionBar } from "./Selection";
import type { ScanRun, Suggested } from "./Review";
import { Tagging } from "./Tagging";
import type { DuplicateGroup } from "./Duplicates";

type Meta = Record<string, string | number>;
type Track = {
  id: number;
  source: string;
  source_id: string;
  revision: string;
  my_tags: { id: string; name: string; category: string }[];
  my_tags_loaded: number;
  path: string;
  available: number;
  metadata: Meta;
  file_metadata: Meta;
  observed_metadata: Meta;
  accepted: Meta;
  overrides: Meta;
  playlists: { name: string; position: number; id?: string }[];
  stats?: { cues?: number; plays?: number; rating?: number; added?: string };
  evidence: Evidence[];
  state: string;
  error: string | null;
};
type Evidence = {
  provider: string;
  title?: string;
  artist?: string;
  url?: string;
  reason?: string;
  error?: string;
  duration_difference?: number;
  version_conflict?: boolean;
};
type Proposal = {
  id: number;
  track_id: number;
  field: string;
  old_value: string;
  new_value: string;
  confidence: string;
  reason: string;
  source: string;
};
type Job = {
  id: string;
  kind: string;
  state: string;
  progress: number;
  total: number;
  message: string;
};
type Operation = {
  id: string;
  state: string;
  created_at: string;
  manifest: {
    kind?: string;
    detail?: string;
    error?: string;
    backup_deleted?: boolean;
    library_status: string;
    dex_status: string;
    tracks: { id: number; file_status: string }[];
  };
};
type State = {
  token: string;
  manual_edits: {
    track_id: number;
    field: string;
    value: string;
    file_status: string;
    library_status: string;
  }[];
  local_writes: {
    id: string;
    track_id: number;
    kind: string;
    state: string;
    created_at: string;
    manifest: {
      path: string;
      error?: string;
      after?: string;
      changes?: Record<string, string>;
      backup_deleted?: boolean;
    };
  }[];
  imports: { id: string; state: string; created_at: string }[];
  tag_sessions: TagSession[];
  assignments: { track_id: number; kind: string; target: string }[];
  assignments_ready: number;
  choices: ListChoices;
  new_lists: { id: string; kind: string; name: string; parent: string }[];
  scan: ScanRun | null;
  suggested: Suggested[];
  queued: number[];
  tracks: Track[];
  proposals: Proposal[];
  jobs: Job[];
  history: {
    id: number;
    kind: string;
    detail: string;
    created_at: string;
    track_id?: number;
  }[];
  operations: Operation[];
  edits_waiting: number;
  restart_needed?: boolean;
  duplicates: DuplicateGroup[];
  duplicates_dismissed: number;
  capability: { enabled: boolean; version: string; reason: string };
  last_scan: string | null;
  relocation_review: {
    source_id: string;
    path: string;
    candidates: string[];
    reason: string;
  }[];
  settings: {
    rekordbox_db: string;
    music_folder: string;
    acoustid_configured: boolean;
    discogs_configured: boolean;
    demo: boolean;
  };
};
type TagSession = {
  id: string;
  state: string;
  position: number;
  total: number;
  created_at: string;
};
type Page =
  "Song Dex" | "Scan & Review" | "Duplicates" | "History" | "Settings";
const pages: Page[] = [
  "Song Dex",
  "Scan & Review",
  "Duplicates",
  "History",
  "Settings",
];
const label = (s: string) => s.replaceAll("_", " ");
/** Suggestions that fill a field which is empty; two values for one field are a choice. */
const blankFills = (tracks: Track[], proposals: Proposal[]) => {
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
      t.source !== "demo" &&
      !t.metadata[p.field] &&
      perField.get(`${p.track_id}:${p.field}`) === 1
    );
  });
};
const dex = (id: number) => String(id).padStart(4, "0");
const duration = (n: string | number | undefined) => {
  const v = Number(n) || 0;
  return `${Math.floor(v / 60)}:${String(Math.floor(v % 60)).padStart(2, "0")}`;
};
const historyTabs = ["Actions", "Logs", "Backups"] as const;
const jobNames: Record<string, string> = {
  scan: "Scanning library",
  availability: "Checking file locations",
  import_music: "Adding music",
  approve: "Approving suggestions",
  sync_edits: "Syncing saved edits",
  tag_check: "Checking imported tracks",
  external_backup: "Backing up to external drive",
};
const jobName = (kind: string) => jobNames[kind] ?? "Finding metadata";
const date = (s: string | null) =>
  s ? new Date(s).toLocaleString() : "Not scanned yet";

function Glyph({ kind = "disc" }: { kind?: string }) {
  const shapes: Record<string, React.ReactNode> = {
    disc: (
      <>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="2" />
        <path d="M7 11a5 5 0 0 1 4-4m2 10a5 5 0 0 0 4-4" />
      </>
    ),
    scan: (
      <>
        <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M6 12h12M9 8h6m-6 8h6" />
      </>
    ),
    duplicates: (
      <>
        <path d="M8 8h12v12H8zM4 16V4h12" />
        <path d="M11 12h6m-6 4h6" />
      </>
    ),
    history: (
      <>
        <path d="M4 8a9 9 0 1 1-1 6M3 3v6h6m3-3v7l4 2" />
      </>
    ),
    settings: (
      <>
        <path d="M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-7 0v6" />
      </>
    ),
  };
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      aria-hidden="true"
    >
      {shapes[kind] || shapes.disc}
    </svg>
  );
}
function Artwork({ track }: { track: Track }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [track.id]);
  return (
    <div className="artwork">
      {track.available && !failed ? (
        <img
          src={`/api/tracks/${track.id}/artwork`}
          loading="lazy"
          onError={() => setFailed(true)}
          alt={`Artwork for ${track.metadata.album || track.metadata.title}`}
        />
      ) : (
        <>
          <div className="record">
            <div />
          </div>
          <span>LOCAL COLLECTION</span>
        </>
      )}
    </div>
  );
}
/** The open track's audio, beside its artwork; says why when it cannot play. */
function Player({ track }: { track: Track }) {
  const [problem, setProblem] = useState("");
  if (!track.available)
    return (
      <p className="player-note">
        {track.source === "demo"
          ? "Audio preview is available after importing your library."
          : "Offline file: reconnect its drive and Check availability to play it."}
      </p>
    );
  return (
    <div className="player">
      <audio
        controls
        preload="metadata"
        src={`/api/tracks/${track.id}/audio`}
        aria-label={`Play ${track.metadata.title || "this recording"}`}
        onError={(e) => {
          const error = e.currentTarget.error;
          setProblem(
            error?.code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED
              ? "This file could not be opened. It may have moved since the last availability check, or its format is not supported here."
              : "The file stopped loading. Check that its drive is still connected.",
          );
        }}
        onCanPlay={() => setProblem("")}
      />
      {problem && (
        <p role="alert" className="error-text">
          {problem}
        </p>
      )}
    </div>
  );
}
function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="empty">
      <Glyph />
      <h2>{title}</h2>
      <div>{children}</div>
    </div>
  );
}

function App() {
  const [data, setData] = useState<State | null>(null),
    [page, setPage] = useState<Page>("Song Dex"),
    [selected, setSelected] = useState<number | null>(null);
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all"),
    [online, setOnline] = useState<"online" | "offline" | null>(null),
    // The rekordbox folder, playlist or smart playlist the library shows.
    [shelfId, setShelfId] = useState<string | null>(null),
    [shelf, setShelf] = useState<Shelf>({ nodes: [], loaded: false }),
    [sort, setSort] = useState("dex"),
    [limit, setLimit] = useState(100),
    [tab, setTab] = useState("Overview"),
    [detailOpen, setDetailOpen] = useState(false);
  const [chosen, setChosen] = useState<Set<number>>(new Set()),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [error, setError] = useState("");
  const [path, setPath] = useState(""),
    [key, setKey] = useState(""),
    [discogs, setDiscogs] = useState(""),
    [discogsKey, setDiscogsKey] = useState(""),
    [discogsSecret, setDiscogsSecret] = useState(""),
    [musicFolder, setMusicFolder] = useState("");
  const [importOpen, setImportOpen] = useState(false),
    [receiptId, setReceiptId] = useState<string | undefined>(),
    [folderOpen, setFolderOpen] = useState(false),
    [tagging, setTagging] = useState<string | null>(null);
  const [musicFilters, setMusicFilters] = useState<Filters>({
    ...emptyFilters,
  });
  const [direction, setDirection] = useState("asc");
  const [confirm, setConfirm] = useState<string | null>(null);
  const offered = useRef<Set<number>>(new Set());
  const [editingTrack, setEditingTrack] = useState<number | null>(null);
  const [editTab, setEditTab] = useState<"Metadata" | "My Tags">("Metadata"),
    // The tracks a new playlist starts with: the open one, or those ticked.
    [newPlaylist, setNewPlaylist] = useState<
      { id: number; title: string }[] | null
    >(null);
  const [marked, setMarked] = useState<Set<number>>(new Set()),
    [bulk, setBulk] = useState<"tags" | "playlists" | null>(null),
    anchor = useRef<number | null>(null);
  const [historyTab, setHistoryTab] =
    useState<(typeof historyTabs)[number]>("Actions");
  const [stale, setStale] = useState("");
  const [railCollapsed, setRailCollapsed] = useState(
    () => localStorage.getItem("songdex-rail") === "1",
  );
  const [shelfHidden, setShelfHidden] = useState(
    () => localStorage.getItem("songdex-shelf-hidden") === "1",
  );
  const modalRef = useRef<HTMLElement>(null);
  useEffect(
    () => setLimit(100),
    [search, filter, online, shelfId, sort, musicFilters, direction],
  );
  useEffect(() => {
    if (!confirm) return;
    const prior = document.activeElement as HTMLElement | null;
    const node = modalRef.current;
    const trap = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || !node) return;
      const items = Array.from(
        node.querySelectorAll<HTMLElement>(
          "button:not(:disabled),input,a[href]",
        ),
      );
      const first = items[0],
        last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      prior?.focus();
    };
  }, [confirm]);
  const searchRef = useRef<HTMLInputElement>(null),
    token = useRef(""),
    watched = useRef<string | null>(null),
    initial = useRef(true);
  const reload = async () => {
    const res = await fetch("/api/state");
    if (!res.ok)
      throw new Error(
        "Song Dex cannot read its catalog. Check that the disk is not full, then restart Song Dex.",
      );
    const d: State = await res.json();
    d.tracks = d.tracks.map((t) => ({
      ...t,
      observed_metadata: t.metadata,
      my_tags: t.my_tags || [],
      my_tags_loaded: t.my_tags_loaded || 0,
      metadata: { ...t.metadata, ...t.accepted },
    }));
    token.current = d.token;
    setData(d);
    // A scan or import that repointed files says so in its closing message.
    const done = d.jobs.find((j: Job) => j.id === watched.current);
    if (done?.state === "complete" && done.message !== "Finished")
      setNotice(done.message);
    watched.current =
      d.jobs.find((j: Job) => j.state === "running")?.id ?? null;
    if (initial.current) {
      setPath(d.settings.rekordbox_db);
      setMusicFolder(d.settings.music_folder);
      initial.current = false;
    }
    setSelected((v) =>
      d.tracks.some((t) => t.id === v) ? v : (d.tracks[0]?.id ?? null),
    );
    // Only suggestions that fill a blank field start ticked, once, when they first
    // appear; anything that replaces a value waits for a deliberate tick.
    const live = new Set(d.proposals.map((p) => p.id)),
      fresh = blankFills(d.tracks, d.proposals)
        .map((p) => p.id)
        .filter((id) => !offered.current.has(id));
    offered.current = live;
    setChosen(
      (prev) => new Set([...prev, ...fresh].filter((id) => live.has(id))),
    );
  };
  // The playlist tree changes only with a scan.
  useEffect(() => {
    if (!data) return;
    fetch("/api/playlists")
      .then((res) => (res.ok ? res.json() : null))
      .then((tree: Shelf | null) => {
        if (!tree) return;
        setShelf(tree);
        setShelfId((id) => (tree.nodes.some((n) => n.id === id) ? id : null));
      })
      .catch(() => {
        // The state refresh reports a service that stopped answering.
      });
  }, [data?.last_scan, data?.settings.demo, data === null]);
  useEffect(() => {
    reload().catch((e) => setError(e.message));
    // A failed refresh leaves a stale screen, so say so until one succeeds again.
    const timer = setInterval(
      () =>
        reload().then(
          () => setStale(""),
          (e) =>
            setStale(
              e instanceof TypeError
                ? "Song Dex is not responding. Start it again from your terminal."
                : e.message,
            ),
        ),
      3000,
    );
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if (document.querySelector(".library-modal")) return;
      if (
        e.key === "/" &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement)
      ) {
        e.preventDefault();
        setPage("Song Dex");
        searchRef.current?.focus();
      }
      if (e.key === "Escape") {
        setDetailOpen(false);
        setConfirm(null);
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  const action = async (endpoint: string, body?: unknown, success?: string) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const res = await fetch("/api/" + endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Songdex-Token": token.current,
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const result = await res.json();
      if (!res.ok)
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : "Please check the entered values",
        );
      if (result.manifest?.error)
        setError(
          "Write interrupted: " +
            result.manifest.error +
            ". Open History to restore.",
        );
      else if (result.message || success) setNotice(result.message || success);
      if (result.job_id) watched.current = result.job_id;
      await reload();
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  };
  /** A request that leaves the notices and the rest of the screen alone. */
  const send = async (endpoint: string, body?: unknown) => {
    const res = await fetch("/api/" + endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Songdex-Token": token.current,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const result = await res.json();
    if (!res.ok)
      throw new Error(
        typeof result.detail === "string" ? result.detail : "Request failed",
      );
    return result;
  };
  const pick = (id: number) => {
    setSelected(id);
    setDetailOpen(true);
    // The tab stays as it was, so tracks can be compared tab by tab.
  };
  const changePage = (p: Page) => {
    setPage(p);
    setDetailOpen(false);
    setNotice("");
    setError("");
  };
  const tracks = data?.tracks ?? [],
    proposals = data?.proposals ?? [];
  const active = data?.jobs.find((j) => j.state === "running"),
    track = tracks.find((t) => t.id === selected);
  // While a scan runs, its results stream in between the full refreshes.
  useEffect(() => {
    if (active?.kind !== "enrich" || page !== "Scan & Review") return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch("/api/review");
        if (!res.ok) return;
        const live = await res.json();
        setData((d) => d && { ...d, ...live });
      } catch {
        // The full refresh reports a service that stopped answering.
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [active?.id, active?.kind, page]);
  const unavailable = tracks.filter(
    (t) => !t.available && t.source !== "demo" && t.state !== "removed",
  );
  const unavailableLocations = unavailable.reduce<Record<string, number>>(
    (locations, t) => {
      const location = t.path.startsWith("/Volumes/")
        ? t.path.split("/").slice(0, 3).join("/")
        : "Local / other file locations";
      locations[location] = (locations[location] || 0) + 1;
      return locations;
    },
    {},
  );
  const shelfOrder = useMemo(
    () => (shelfId ? shelfMembers(shelfId, shelf.nodes, tracks) : null),
    [shelfId, shelf.nodes, tracks],
  );
  const shelfNode = shelf.nodes.find((n) => n.id === shelfId);
  const showShelf = (id: string | null) => {
    const node = shelf.nodes.find((n) => n.id === id);
    setShelfId(id);
    // A playlist opens in its own order; leaving one goes back to Dex order.
    if (node?.kind === "playlist") setSort("playlist");
    changePage("Song Dex");
  };
  // Playlist order only means something while a playlist is shown.
  useEffect(() => {
    if (sort === "playlist" && shelfNode?.kind !== "playlist") setSort("dex");
  }, [sort, shelfNode?.kind]);
  const isOffline = (t: Track) =>
      !t.available && t.source !== "demo" && t.state !== "removed",
    isOnline = (t: Track) => !!t.available && t.state !== "removed";
  // Online and offline counts for what the playlist (or the library) holds.
  const shelved = shelfOrder
      ? tracks.filter((t) => shelfOrder.has(t.id))
      : tracks,
    onlineCount = shelved.filter(isOnline).length,
    offlineCount = shelved.filter(isOffline).length;
  const visible = tracks
    .filter(
      (t) =>
        (!shelfOrder || shelfOrder.has(t.id)) &&
        (online === null || (online === "online" ? isOnline(t) : isOffline(t))),
    )
    .filter(
      (t) =>
        `${t.metadata.title} ${t.metadata.artist} ${t.metadata.album} ${t.metadata.genre}`
          .toLocaleLowerCase()
          .includes(search.toLocaleLowerCase()) &&
        (filter === "all" ||
          (filter === "review"
            ? proposals.some((p) => p.track_id === t.id)
            : filter === "unavailable"
              ? !t.available && t.source !== "demo"
              : filter === "available"
                ? !!t.available
                : filter === "pending_sync"
                  ? data?.manual_edits.some(
                      (e) =>
                        e.track_id === t.id &&
                        t.state !== "removed" &&
                        (e.file_status === "pending" ||
                          e.library_status === "pending"),
                    )
                  : t.state === filter)),
    )
    .filter((t) => matchesFilters(t, musicFilters))
    .sort((a, b) =>
      sort === "playlist" && shelfOrder
        ? ((shelfOrder.get(a.id) ?? 0) - (shelfOrder.get(b.id) ?? 0)) *
          (direction === "asc" ? 1 : -1)
        : compareTracks(a, b, sort === "playlist" ? "dex" : sort, direction),
    );
  const markedTracks = tracks.filter(
      (t) => marked.has(t.id) && t.state !== "removed",
    ),
    shownIds = new Set(visible.map((t) => t.id)),
    allShown = visible.length > 0 && visible.every((t) => marked.has(t.id)),
    someShown = visible.some((t) => marked.has(t.id));
  const markShown = (on: boolean) => {
    const next = new Set(marked);
    for (const t of visible) on ? next.add(t.id) : next.delete(t.id);
    setMarked(next);
  };
  /** Tick or untick a track; with Shift, every shown track from the last one ticked. */
  const mark = (id: number, on: boolean, range: boolean) => {
    const at = visible.findIndex((t) => t.id === id),
      from = range ? visible.findIndex((t) => t.id === anchor.current) : -1,
      [start, end] = from < 0 ? [at, at] : [from, at].sort((a, b) => a - b);
    const next = new Set(marked);
    for (const t of visible.slice(start, end + 1))
      on ? next.add(t.id) : next.delete(t.id);
    setMarked(next);
    anchor.current = id;
  };
  const choices = data?.choices ?? { tags: [], playlists: [], loaded: false };
  useEffect(() => {
    if (visible.length)
      setSelected((current) =>
        visible.some((t) => t.id === current) ? current : visible[0].id,
      );
  }, [musicFilters, search, filter, online, shelfId]);
  const libraryGenres = useMemo(() => {
    const counts = new Map<string, number>();
    for (const t of tracks) {
      const name = String(t.accepted.genre || t.metadata.genre || "");
      if (name && t.state !== "removed")
        counts.set(name, (counts.get(name) ?? 0) + 1);
    }
    return [...counts]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [tracks]);
  // Why saved edits are still waiting: a drive that is away is not something to fix here.
  const waiting = useMemo(() => {
    const held = new Map(tracks.map((t) => [t.id, t])),
      reasons = new Map<number, boolean>();
    for (const e of data?.manual_edits ?? []) {
      const t = held.get(e.track_id);
      if (!t || t.state === "removed") continue;
      const offline = e.file_status === "pending" && !t.available,
        other =
          e.library_status === "pending" ||
          (e.file_status === "pending" && !!t.available);
      if (offline || other)
        reasons.set(t.id, (reasons.get(t.id) ?? true) && !other);
    }
    const offlineOnly = [...reasons.values()].filter(Boolean).length;
    return { offlineOnly, ready: reasons.size - offlineOnly };
  }, [data?.manual_edits, tracks]);
  const openDuplicates = (data?.duplicates ?? []).filter(
    (g) => !g.merged,
  ).length;
  // An unfinished write blocks every later one until it is restored or cleared.
  // While a job or request is running, a write that is mid-flight is not stuck.
  const stuck = (o: { state: string }) =>
    o.state === "recovery_required" ||
    (!active &&
      !busy &&
      ["preparing", "writing", "restoring"].includes(o.state));
  const stuckWrites = (data?.local_writes ?? []).filter(stuck),
    stuckOperations = (data?.operations ?? []).filter(stuck),
    // Finished entries whose backup is gone have nothing left to act on.
    restorable = (o: {
      state: string;
      manifest: { backup_deleted?: boolean };
    }) => !stuck(o) && !o.manifest.backup_deleted,
    unresolved = stuckWrites.length + stuckOperations.length;
  // Only the latest run of each kind: starting over supersedes an older failure.
  const stopped = (data?.jobs ?? []).filter(
    (j, i, jobs) =>
      ["failed", "interrupted"].includes(j.state) &&
      jobs.findIndex((other) => other.kind === j.kind) === i,
  );
  const writeSubject = (w: State["local_writes"][number]) => {
    const t = tracks.find((t) => t.id === w.track_id),
      changes = Object.entries(w.manifest.changes ?? {})
        .map(([field, value]) => `${label(field)} → ${value}`)
        .join(", ");
    return [
      t &&
        `${t.metadata.title || "Untitled"} · ${t.metadata.artist || "Unknown artist"}`,
      changes,
    ]
      .filter(Boolean)
      .join(" · ");
  };
  const writeAction = (w: State["local_writes"][number]) =>
    w.manifest.backup_deleted ? (
      <button disabled>Backup deleted</button>
    ) : w.manifest.after ? (
      <button
        disabled={busy || !!active || w.state === "restored"}
        onClick={() => setConfirm("local:" + w.id)}
      >
        Restore destination backup
      </button>
    ) : stuck(w) ? (
      <button
        disabled={busy || !!active}
        onClick={() => action(`local-writes/${w.id}/restore`)}
      >
        Clear interrupted write
      </button>
    ) : null;
  const operationAction = (op: Operation) =>
    op.manifest.backup_deleted ? (
      <button disabled>Backup deleted</button>
    ) : (
      <button
        disabled={busy || !!active || op.state === "restored"}
        onClick={() => setConfirm(op.id)}
      >
        Restore this operation
      </button>
    );
  const resumeAction = (j: Job) => (
    <button
      disabled={busy || !!active || unresolved > 0}
      onClick={() => action(`jobs/${j.id}/resume`, undefined, "Resuming job")}
    >
      Resume
    </button>
  );
  const writeCard = (w: State["local_writes"][number]) => (
    <section className="operation" key={w.id}>
      <h2>
        Metadata · {w.kind === "file" ? "audio tags" : "rekordbox"} ·{" "}
        {label(w.state)}
      </h2>
      {writeSubject(w) && <p>{writeSubject(w)}</p>}
      <p className="file-path">{w.manifest.path}</p>
      <p>{date(w.created_at)}</p>
      {w.manifest.error && <p className="error-text">{w.manifest.error}</p>}
      {!w.manifest.after && (
        <p>
          Stopped before anything was written, so there is nothing to restore.
          Your Dex correction stays saved.
        </p>
      )}
      {writeAction(w)}
    </section>
  );
  const operationCard = (op: Operation) => (
    <section className="operation" key={op.id}>
      <header>
        <h2>
          {op.manifest.kind
            ? `${op.manifest.kind} · ${label(op.state)}`
            : label(op.state)}
        </h2>
        <Badge tone={op.state === "complete" ? "success" : "warn"}>
          {date(op.created_at)}
        </Badge>
      </header>
      {op.manifest.detail && <p>{op.manifest.detail}</p>}
      <p>
        Dex: {op.manifest.dex_status} · rekordbox: {op.manifest.library_status}
        {!op.manifest.kind &&
          ` · Files: ${
            op.manifest.tracks.filter((t) => t.file_status === "complete")
              .length
          }/${op.manifest.tracks.length}`}
      </p>
      {op.manifest.error && <p className="error-text">{op.manifest.error}</p>}
      {operationAction(op)}
    </section>
  );
  const newLists = data?.new_lists ?? [],
    assignments = data?.assignments ?? [];
  // Tag and playlist choices, and new My Tags and playlists, waiting for rekordbox.
  const choicesWaiting = data &&
    (assignments.length > 0 || newLists.length > 0) && (
      <div className="callout">
        <strong>
          {[
            assignments.length > 0 &&
              `${assignments.length} My Tag and playlist ${assignments.length === 1 ? "choice" : "choices"}`,
            newLists.length > 0 &&
              `${newLists.length} new My Tags and playlists`,
          ]
            .filter(Boolean)
            .join(" and ")}{" "}
          waiting for rekordbox
        </strong>
        <p>
          {data.assignments_ready > 0 &&
            `${data.assignments_ready} can be written now; quit rekordbox first. `}
          {assignments.length > data.assignments_ready &&
            `${assignments.length - data.assignments_ready} belong to new tracks rekordbox has not imported yet. Import their playlist in rekordbox, quit it and rescan: the scan writes them.`}
          {newLists.length > 0 &&
            " New My Tags and playlists are made in rekordbox with the next write."}
        </p>
        {newLists.length > 0 && (
          <ul className="new-lists">
            {newLists.map((n) => (
              <li key={n.id}>
                <Badge>{n.kind === "tag" ? "My Tag" : "Playlist"}</Badge>
                {n.name}
                <button
                  className="mini quiet"
                  disabled={busy}
                  onClick={() =>
                    action(
                      `lists/${n.id}/discard`,
                      undefined,
                      `“${n.name}” dropped, with the choices made for it`,
                    )
                  }
                >
                  Drop
                </button>
              </li>
            ))}
          </ul>
        )}
        {(data.assignments_ready > 0 || newLists.length > 0) && (
          <button
            disabled={busy || !!active || !data.capability.enabled}
            onClick={() => action("assignments/write")}
          >
            Write to rekordbox
          </button>
        )}
        {!data.capability.enabled && (
          <p className="fine">{data.capability.reason}</p>
        )}
      </div>
    );
  /** A track's My Tags: what rekordbox has, and adding more; in the entry and in Edit track. */
  const myTagsPanel = (track: Track) =>
    data && (
      <section className="my-tags-panel">
        <h3>Native rekordbox My Tags</h3>
        <p className="fine">
          These are your saved rekordbox tag assignments, grouped by category.
          They are separate from Genre.
        </p>
        {track.my_tags_loaded ? (
          track.my_tags.length ? (
            <ul>
              {track.my_tags.map((g) => (
                <li key={g.id}>
                  <strong>{g.category || "Uncategorized"}</strong>
                  <span>{g.name}</span>
                  <button
                    onClick={() => {
                      setMusicFilters({
                        ...emptyFilters,
                        tags: [`${track.source}::${g.id}`],
                      });
                      setSearch("");
                      setFilter("all");
                      setOnline(null);
                      setShelfId(null);
                      setDetailOpen(false);
                      setEditingTrack(null);
                      setPage("Song Dex");
                    }}
                  >
                    Find tracks with this tag
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p>No My Tags assigned in the last scan.</p>
          )
        ) : (
          <p>My Tags have not been loaded for this entry.</p>
        )}
        <button
          disabled={
            busy ||
            !!active ||
            track.source === "local" ||
            track.source === "demo"
          }
          onClick={() => action("my-tags/load")}
        >
          Load My Tags from last scan
        </button>
        <h3>Add My Tags and playlists</h3>
        <p className="fine">
          Picks are kept in Song Dex and added in rekordbox with the next write;
          nothing is removed. Loading the last scan reads its saved copy, not
          newer changes in rekordbox.
        </p>
        {track.source === "demo" ? (
          <p>Demo entries have no rekordbox tags.</p>
        ) : (
          <TrackLists
            key={track.id}
            track={track}
            choices={
              data.choices ?? {
                tags: [],
                playlists: [],
                loaded: false,
              }
            }
            pending={assignments.filter((a) => a.track_id === track.id)}
            disabled={busy}
            genres={libraryGenres}
            send={send}
            onChanged={reload}
          />
        )}
        {choicesWaiting}
      </section>
    );
  const withoutGenre = tracks.filter(
    (t) =>
      t.source !== "demo" &&
      t.state !== "removed" &&
      !(t.accepted.genre || t.metadata.genre),
  ).length;
  return (
    <div className="console">
      <header className="housing">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            changePage("Song Dex");
          }}
        >
          <span className="brand-mark">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>
            SONG DEX<small>PERSONAL MUSIC ARCHIVE</small>
          </span>
        </a>
        <div className="housing-right">
          <span className="led" /> LOCAL SYSTEM{" "}
          <span className="model">SD–01</span>
          <div className="vents" />
        </div>
      </header>
      <div className={railCollapsed ? "workspace rail-collapsed" : "workspace"}>
        <nav className="rail" aria-label="Main navigation">
          <button
            className="rail-toggle"
            aria-expanded={!railCollapsed}
            aria-label={railCollapsed ? "Expand menu" : "Collapse menu"}
            title={railCollapsed ? "Expand menu" : "Collapse menu"}
            onClick={() => {
              localStorage.setItem("songdex-rail", railCollapsed ? "" : "1");
              setRailCollapsed(!railCollapsed);
            }}
          >
            {railCollapsed ? "»" : "«"}
          </button>
          <div className="rail-caption">COLLECTION SYSTEM</div>
          {pages.map((p, i) => {
            const button = (
              <button
                key={p}
                className={page === p ? "nav active" : "nav"}
                onClick={() => changePage(p)}
                aria-current={page === p ? "page" : undefined}
                title={railCollapsed ? p : undefined}
              >
                <Glyph
                  kind={
                    ["disc", "scan", "duplicates", "history", "settings"][i]
                  }
                />
                <span>{p}</span>
                {p === "Scan & Review" && proposals.length > 0 && (
                  <b aria-label={`${proposals.length} fields to review`}>
                    {proposals.length}
                  </b>
                )}
                {p === "Duplicates" && openDuplicates > 0 && (
                  <b aria-label={`${openDuplicates} duplicate groups`}>
                    {openDuplicates}
                  </b>
                )}
              </button>
            );
            if (p !== "Song Dex" || railCollapsed || !tracks.length)
              return button;
            return (
              <div key={p} className="nav-group">
                {button}
                <button
                  className="nav-fold"
                  aria-expanded={!shelfHidden}
                  aria-controls="shelf"
                  aria-label={shelfHidden ? "Show playlists" : "Hide playlists"}
                  title={shelfHidden ? "Show playlists" : "Hide playlists"}
                  onClick={() => {
                    localStorage.setItem(
                      "songdex-shelf-hidden",
                      shelfHidden ? "" : "1",
                    );
                    setShelfHidden(!shelfHidden);
                  }}
                >
                  {shelfHidden ? "▸" : "▾"}
                </button>
                {!shelfHidden && (
                  <ShelfTree
                    shelf={shelf}
                    tracks={tracks}
                    selected={page === "Song Dex" ? shelfId : undefined}
                    onSelect={showShelf}
                  />
                )}
              </div>
            );
          })}
          <div className="rail-bottom">
            <div className="mini-disc">
              <Glyph />
            </div>
            <p>
              Your music.
              <br />
              Accounted for.
            </p>
            <span>LOCAL / PRIVATE / YOURS</span>
          </div>
        </nav>
        <main className={`screen ${detailOpen ? "detail-open" : ""}`}>
          <div className="screen-top">
            <span>
              <span className="square" />{" "}
              {page === "Song Dex" ? "COLLECTION INDEX" : page.toUpperCase()}
            </span>
            <span>
              {data?.settings.demo ? "DEMO LIBRARY" : "LOCAL LIBRARY"}{" "}
              <span className="connection">●</span>
            </span>
          </div>
          {error && (
            <div className="message error" role="alert">
              <strong>Action needed</strong>
              <span>{error}</span>
              <button onClick={() => setError("")} aria-label="Dismiss error">
                ×
              </button>
            </div>
          )}
          {notice && (
            <div className="message success" role="status">
              {notice}
              <button onClick={() => setNotice("")} aria-label="Dismiss notice">
                ×
              </button>
            </div>
          )}
          {stale && (
            <div className="message error" role="alert">
              <strong>Not updating</strong>
              <span>{stale}</span>
            </div>
          )}
          {data?.restart_needed && (
            <div className="message error" role="alert">
              <strong>Restart Song Dex</strong>
              <span>
                Its code changed after it started, so some actions on this page
                can fail. Stop it in its terminal (Ctrl+C) and run
                .venv/bin/song-dex again.
              </span>
            </div>
          )}
          {(unresolved > 0 || stopped.length > 0) && (
            <section className="blockers" role="alert">
              <h2>
                {unresolved > 0
                  ? "Changes are blocked until you sort this out"
                  : "A job stopped before it finished"}
              </h2>
              <ol>
                {stuckWrites.map((w) => (
                  <li key={w.id}>
                    <div>
                      <strong>
                        Unfinished write to{" "}
                        {w.kind === "file" ? "audio tags" : "rekordbox"}
                      </strong>
                      <p>
                        {[
                          writeSubject(w),
                          w.manifest.error,
                          w.manifest.after
                            ? "Restoring puts back the backup taken before the write."
                            : "Nothing was written, so clearing it is safe. Your correction stays saved in Song Dex.",
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                    {writeAction(w)}
                  </li>
                ))}
                {stuckOperations.map((op) => (
                  <li key={op.id}>
                    <div>
                      <strong>
                        Unfinished {op.manifest.kind || "metadata apply"}
                      </strong>
                      <p>
                        {[
                          op.manifest.detail,
                          op.manifest.error,
                          "Restoring puts back the backup taken before it started.",
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                    {operationAction(op)}
                  </li>
                ))}
                {stopped.map((j) => (
                  <li key={j.id}>
                    <div>
                      <strong>
                        {jobName(j.kind)} stopped
                        {j.total > 0 && ` at ${j.progress} of ${j.total}`}
                      </strong>
                      <p>
                        {j.message}
                        {unresolved > 0 &&
                          " · Resume once the items above are cleared."}
                      </p>
                    </div>
                    {resumeAction(j)}
                  </li>
                ))}
              </ol>
            </section>
          )}
          {data?.settings.demo && (
            <div className="demo-banner">
              DEMO MODE{" "}
              <span>
                Illustrative entries. No music files connected or modified.
              </span>
            </div>
          )}
          {active && (
            <div className="job" role="status">
              <span>
                {jobName(active.kind)} · {active.message}
              </span>
              <progress value={active.progress} max={active.total || 1} />
            </div>
          )}
          {!data ? (
            <Empty title="Connecting to your Dex">
              <p>The local catalog will appear here.</p>
              <button
                onClick={() => reload().catch((e) => setError(e.message))}
              >
                Retry connection
              </button>
            </Empty>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    {page === "Song Dex"
                      ? "EVERY TRACK HAS A STORY"
                      : "YOUR LIBRARY, IN ORDER"}
                  </div>
                  <h1>{page}</h1>
                  <p>
                    {
                      {
                        "Song Dex": "A field guide to the music you keep.",
                        "Scan & Review":
                          "Check the evidence. Keep what belongs.",
                        Duplicates:
                          "Same recording, different files? Look closer.",
                        History:
                          "Every scan, decision, and change leaves a record.",
                        Settings:
                          "Connect your collection and choose your sources.",
                      }[page]
                    }
                  </p>
                </div>
                {page === "Song Dex" && (
                  <div className="button-row library-actions">
                    <button
                      disabled={busy || !!active || data.settings.demo}
                      onClick={() => {
                        setReceiptId(undefined);
                        setImportOpen(true);
                      }}
                    >
                      + Add music
                    </button>
                    <button
                      disabled={busy || data.settings.demo}
                      onClick={() =>
                        setNewPlaylist(
                          track && track.source !== "demo"
                            ? [
                                {
                                  id: track.id,
                                  title: String(
                                    track.metadata.title ||
                                      "Untitled recording",
                                  ),
                                },
                              ]
                            : [],
                        )
                      }
                    >
                      + New playlist
                    </button>
                    <button
                      className="primary"
                      disabled={busy || !!active || data.settings.demo}
                      onClick={() =>
                        action("scan", undefined, "Library scan started")
                      }
                    >
                      <Glyph kind="scan" />
                      {data.last_scan ? "Rescan library" : "Import library"}
                    </button>
                  </div>
                )}
              </div>
              {page === "Song Dex" &&
                (tracks.length === 0 ? (
                  <div className="onboarding">
                    <div className="welcome-emblem">
                      <Glyph />
                    </div>
                    <div className="eyebrow">ENTRY NO. ————</div>
                    <h2>Your collection starts here.</h2>
                    <p>
                      Connect your rekordbox library to give every recording a
                      home. Song Dex keeps track of what you know, what changed,
                      and what still needs a closer look.
                    </p>
                    <div className="button-row">
                      <button
                        className="primary"
                        disabled={busy || !!active}
                        onClick={() =>
                          action("scan", undefined, "Library scan started")
                        }
                      >
                        Import rekordbox library
                      </button>
                      <button
                        disabled={busy}
                        onClick={() =>
                          action(
                            "demo",
                            undefined,
                            "Demo loaded — all entries are illustrative",
                          )
                        }
                      >
                        Explore demo
                      </button>
                    </div>
                    <p className="fine">
                      Quit rekordbox before importing. Set a different library
                      path in Settings.
                    </p>
                  </div>
                ) : (
                  <>
                    <div className="catalog-summary">
                      <span>
                        <strong>{tracks.length.toLocaleString()}</strong>{" "}
                        indexed tracks
                      </span>
                      <span>
                        <strong>{proposals.length}</strong> fields to review
                      </span>
                      <span>
                        <strong>{data.duplicates.length}</strong> duplicate
                        groups
                      </span>
                      <span className="last-scan">
                        Last scan: {date(data.last_scan)}
                      </span>
                    </div>
                    <div className="catalog-grid">
                      <section className="list-pane" aria-label="Track catalog">
                        <div className="search-row">
                          <label className="search">
                            <span aria-hidden="true">⌕</span>
                            <input
                              ref={searchRef}
                              aria-label="Search your music"
                              placeholder="Find a title, artist, or album…"
                              value={search}
                              onChange={(e) => setSearch(e.target.value)}
                            />
                            <kbd>/</kbd>
                          </label>
                          <select
                            aria-label="Filter catalog"
                            value={filter}
                            onChange={(e) => setFilter(e.target.value)}
                          >
                            <option value="all">All tracks</option>
                            <option value="review">Needs review</option>
                            <option value="pending_sync">
                              Saved edits awaiting sync
                            </option>
                            <option value="conflict">Conflicts</option>
                          </select>
                        </div>
                        <div className="availability-row">
                          <div
                            className="availability-toggle"
                            role="group"
                            aria-label="Show online or offline files"
                          >
                            {(
                              [
                                ["online", "●", "Online", onlineCount],
                                ["offline", "○", "Offline", offlineCount],
                              ] as const
                            ).map(([value, mark, name, count]) => (
                              <button
                                key={value}
                                className={online === value ? "on" : ""}
                                aria-pressed={online === value}
                                title={
                                  online === value
                                    ? "Show every file again"
                                    : `Show only ${name.toLowerCase()} files`
                                }
                                onClick={() =>
                                  setOnline(online === value ? null : value)
                                }
                              >
                                <span aria-hidden="true">{mark}</span> {name}{" "}
                                <b>{count.toLocaleString()}</b>
                              </button>
                            ))}
                          </div>
                          <button
                            className="availability-check"
                            disabled={busy || !!active}
                            title="Check availability: look for each file at its saved location again"
                            onClick={() =>
                              action(
                                "availability",
                                undefined,
                                "Checking saved file locations",
                              )
                            }
                          >
                            ↻ Check
                          </button>
                        </div>
                        {shelfNode && (
                          <div className="shelf-banner">
                            <div>
                              <small>
                                {
                                  {
                                    folder: "PLAYLIST FOLDER",
                                    playlist: "PLAYLIST",
                                    smart: "SMART PLAYLIST",
                                  }[shelfNode.kind]
                                }
                              </small>
                              <strong>
                                {shelfPath(shelfNode.id, shelf.nodes)}
                              </strong>
                              {shelfNode.kind === "smart" &&
                                (shelfNode.error ? (
                                  <span className="error-text">
                                    {shelfNode.error}
                                  </span>
                                ) : (
                                  <span>
                                    {(shelfNode.rules ?? []).join(
                                      shelfNode.match === "any"
                                        ? " · or "
                                        : " · and ",
                                    )}
                                    . Matches as of the last scan; change the
                                    rules in rekordbox.
                                  </span>
                                ))}
                              {shelfNode.kind === "folder" && (
                                <span>Every track in its playlists.</span>
                              )}
                            </div>
                            <button
                              aria-label="Show all tracks"
                              title="Show all tracks"
                              onClick={() => showShelf(null)}
                            >
                              ×
                            </button>
                          </div>
                        )}
                        <CatalogFilters
                          tracks={tracks}
                          value={musicFilters}
                          onChange={setMusicFilters}
                          busy={busy || !!active}
                          onLoadTags={() => action("my-tags/load")}
                        />
                        <div className="sort-row">
                          <label>
                            Order{" "}
                            <select
                              aria-label="Sort catalog"
                              value={sort}
                              onChange={(e) => setSort(e.target.value)}
                            >
                              {shelfNode?.kind === "playlist" && (
                                <option value="playlist">Playlist order</option>
                              )}
                              <option value="dex">Dex number</option>
                              <option value="title">Title</option>
                              <option value="artist">Artist</option>
                              <option value="album">Album</option>
                              <option value="my_tags">My Tags</option>
                              <option value="genre">Genre</option>
                              <option value="bpm">BPM</option>
                              <option value="key">Key</option>
                              <option value="year">Year</option>
                              <option value="duration">Duration</option>
                              <option value="format">Format</option>
                              <option value="added">Date added</option>
                            </select>
                          </label>
                        </div>
                        <div className="sort-direction">
                          <label>
                            Direction{" "}
                            <select
                              aria-label="Sort direction"
                              value={direction}
                              onChange={(e) => setDirection(e.target.value)}
                            >
                              <option value="asc">Ascending</option>
                              <option value="desc">Descending</option>
                            </select>
                          </label>
                          <strong>
                            {visible.length.toLocaleString()} /{" "}
                            {shelved.length.toLocaleString()} tracks
                          </strong>
                        </div>
                        <div className="list-label">
                          <label className="track-check">
                            <input
                              type="checkbox"
                              aria-label="Select every shown track"
                              disabled={!visible.length}
                              checked={allShown}
                              ref={(el) => {
                                if (el)
                                  el.indeterminate = someShown && !allShown;
                              }}
                              onChange={() => markShown(!allShown)}
                            />
                          </label>
                          <span>NO. / RECORDING</span>
                          <span>BPM / TIME</span>
                        </div>
                        <div className="track-list">
                          {visible.slice(0, limit).map((t) => (
                            <div
                              key={t.id}
                              className={`track-item${marked.has(t.id) ? " marked" : ""}`}
                            >
                              <label
                                className="track-check"
                                title="Select. Shift-click selects every track from the last one."
                              >
                                <input
                                  type="checkbox"
                                  aria-label={`Select ${t.metadata.title || "Untitled recording"}`}
                                  checked={marked.has(t.id)}
                                  onChange={(e) =>
                                    mark(
                                      t.id,
                                      e.target.checked,
                                      (e.nativeEvent as MouseEvent).shiftKey,
                                    )
                                  }
                                />
                              </label>
                              <button
                                className={`track-row ${selected === t.id ? "selected" : ""}`}
                                onClick={() => pick(t.id)}
                                aria-pressed={selected === t.id}
                              >
                                <span className="track-cursor">
                                  {selected === t.id ? "▶" : ""}
                                </span>
                                <span className="track-index">{dex(t.id)}</span>
                                <span className="track-name">
                                  <strong>
                                    {t.metadata.title || "Untitled recording"}
                                  </strong>
                                  <small>
                                    {t.metadata.artist || "Unknown artist"}
                                  </small>
                                  <small className="track-facets">
                                    {[
                                      t.metadata.key
                                        ? `Key ${t.metadata.key}`
                                        : "",
                                      t.metadata.year
                                        ? String(t.metadata.year)
                                        : "",
                                      ...t.my_tags.map((g) => g.name),
                                    ]
                                      .filter(Boolean)
                                      .join(" · ")}
                                  </small>
                                  {!t.available && t.source !== "demo" && (
                                    <span className="offline-label">
                                      ○ Offline file
                                    </span>
                                  )}
                                  {t.source === "local" && (
                                    <span className="offline-label">
                                      New import · local
                                    </span>
                                  )}
                                </span>
                                <span className="track-stats">
                                  <b>{t.metadata.bpm || "—"}</b>
                                  <small>{duration(t.metadata.duration)}</small>
                                </span>
                                {proposals.some((p) => p.track_id === t.id) && (
                                  <span
                                    className="review-dot"
                                    title="Metadata proposals available"
                                  />
                                )}
                              </button>
                            </div>
                          ))}
                          {visible.length > limit && (
                            <button
                              className="wide"
                              onClick={() => setLimit((n) => n + 100)}
                            >
                              Show 100 more entries ({visible.length - limit}{" "}
                              remaining)
                            </button>
                          )}
                          {!visible.length && (
                            <Empty title="No matching entries">
                              <p>Try another search or filter.</p>
                              <button
                                onClick={() => {
                                  setSearch("");
                                  setFilter("all");
                                  setOnline(null);
                                  setMusicFilters({ ...emptyFilters });
                                }}
                              >
                                Clear filters
                              </button>
                            </Empty>
                          )}
                        </div>
                        {markedTracks.length > 0 && (
                          <SelectionBar
                            count={markedTracks.length}
                            hidden={
                              markedTracks.filter((t) => !shownIds.has(t.id))
                                .length
                            }
                            shown={visible.length}
                            canSelectMore={!allShown}
                            onSelectAll={() => markShown(true)}
                            onClear={() => setMarked(new Set())}
                            actions={(() => {
                              const demo =
                                  data.settings.demo ||
                                  markedTracks.some((t) => t.source === "demo"),
                                lists = demo
                                  ? "Demo entries have no rekordbox tags"
                                  : !choices.loaded
                                    ? "Rescan the rekordbox library first"
                                    : undefined;
                              return [
                                {
                                  label: "Add My Tags…",
                                  disabled: !!lists || busy,
                                  hint: lists,
                                  onSelect: () => setBulk("tags"),
                                },
                                {
                                  label: "Add to playlist…",
                                  disabled: !!lists || busy,
                                  hint: lists,
                                  onSelect: () => setBulk("playlists"),
                                },
                                {
                                  label: "New playlist with these…",
                                  disabled: demo || busy,
                                  hint: demo ? lists : undefined,
                                  onSelect: () =>
                                    setNewPlaylist(
                                      markedTracks.map((t) => ({
                                        id: t.id,
                                        title: String(
                                          t.metadata.title ||
                                            "Untitled recording",
                                        ),
                                      })),
                                    ),
                                },
                                {
                                  label: "Scan these tracks",
                                  disabled: demo || busy || !!active,
                                  hint: demo
                                    ? "Demo entries make no lookups"
                                    : active
                                      ? "Wait for the running job"
                                      : "Look up metadata, genres, My Tags and playlists",
                                  onSelect: async () => {
                                    if (
                                      await action("lookup", {
                                        scope: "selected",
                                        ids: markedTracks.map((t) => t.id),
                                      })
                                    )
                                      setPage("Scan & Review");
                                  },
                                },
                              ];
                            })()}
                          />
                        )}
                        <div className="list-footer">
                          {visible.length} ENTRIES{" "}
                          <span>SELECT A RECORDING TO INSPECT →</span>
                        </div>
                      </section>
                      {track && (
                        <aside
                          className="detail-pane"
                          aria-label="Selected recording"
                        >
                          <div className="detail-number">
                            <button
                              className="back"
                              onClick={() => setDetailOpen(false)}
                            >
                              ← Back to tracks
                            </button>
                            <span>DEX ENTRY</span>
                            <strong>NO. {dex(track.id)}</strong>
                          </div>
                          <div className="detail-hero">
                            <Artwork track={track} />
                            <div className="detail-titles">
                              <Badge
                                tone={
                                  track.state === "conflict"
                                    ? "warn"
                                    : "neutral"
                                }
                              >
                                {track.source === "demo"
                                  ? "Demo entry"
                                  : track.state}
                              </Badge>
                              <h2>
                                {track.metadata.title || "Untitled recording"}
                              </h2>
                              <p>{track.metadata.artist || "Unknown artist"}</p>
                              <small>
                                {track.metadata.album || "Album not identified"}
                              </small>
                            </div>
                            <Player key={track.id} track={track} />
                          </div>
                          <div
                            className="detail-tabs"
                            role="tablist"
                            aria-label="Recording details"
                          >
                            {[
                              "Overview",
                              "Metadata",
                              "My Tags",
                              "Sources",
                              "History",
                            ].map((t) => (
                              <button
                                key={t}
                                role="tab"
                                tabIndex={tab === t ? 0 : -1}
                                onKeyDown={(e) => {
                                  if (
                                    e.key === "ArrowRight" ||
                                    e.key === "ArrowLeft"
                                  ) {
                                    e.preventDefault();
                                    const names = [
                                      "Overview",
                                      "Metadata",
                                      "My Tags",
                                      "Sources",
                                      "History",
                                    ];
                                    const next =
                                      names[
                                        (names.indexOf(t) +
                                          (e.key === "ArrowRight"
                                            ? 1
                                            : names.length - 1)) %
                                          names.length
                                      ];
                                    setTab(next);
                                    (
                                      e.currentTarget.parentElement?.querySelector(
                                        `[data-tab="${next}"]`,
                                      ) as HTMLElement
                                    )?.focus();
                                  }
                                }}
                                data-tab={t}
                                aria-selected={tab === t}
                                onClick={() => setTab(t)}
                              >
                                {t}
                              </button>
                            ))}
                          </div>
                          <div
                            className="detail-content"
                            role="tabpanel"
                            aria-label={tab}
                          >
                            {tab === "My Tags" && myTagsPanel(track)}
                            {tab === "Overview" && (
                              <>
                                <div className="stats-grid">
                                  {[
                                    ["BPM", track.metadata.bpm || "—"],
                                    ["KEY", track.metadata.key || "—"],
                                    [
                                      "LENGTH",
                                      duration(track.metadata.duration),
                                    ],
                                    ["FORMAT", track.metadata.format || "—"],
                                  ].map(([k, v]) => (
                                    <div key={k}>
                                      <span>{k}</span>
                                      <strong>{v}</strong>
                                    </div>
                                  ))}
                                </div>
                                <div className="data-line">
                                  <span>Genre</span>
                                  <b>
                                    {track.metadata.genre || "Not identified"}
                                  </b>
                                </div>
                                <div className="data-line">
                                  <span>Version</span>
                                  <b>
                                    {track.metadata.version || "Not specified"}
                                  </b>
                                </div>
                                <h3>
                                  Found in {track.playlists.length}{" "}
                                  {track.playlists.length === 1
                                    ? "playlist"
                                    : "playlists"}
                                </h3>
                                {track.playlists.length ? (
                                  track.playlists.map((p, i) => (
                                    <div className="playlist" key={i}>
                                      <span>▤</span>
                                      {p.name}
                                      <small>#{p.position}</small>
                                    </div>
                                  ))
                                ) : (
                                  <p className="muted">
                                    No playlist membership found.
                                  </p>
                                )}
                                {track.error && (
                                  <p role="alert" className="error-text">
                                    {track.error}
                                  </p>
                                )}
                                {proposals.some(
                                  (p) => p.track_id === track.id,
                                ) && (
                                  <button
                                    className="wide"
                                    onClick={() => changePage("Scan & Review")}
                                  >
                                    Review metadata proposals →
                                  </button>
                                )}
                              </>
                            )}
                            {tab === "Metadata" && (
                              <ManualEditor
                                key={track.id}
                                track={track}
                                busy={busy || !!active}
                                request={action}
                                genres={libraryGenres}
                                statuses={data.manual_edits.filter(
                                  (e) => e.track_id === track.id,
                                )}
                              />
                            )}
                            {tab === "Sources" &&
                              (track.evidence.length ? (
                                track.evidence.map((e, i) => (
                                  <div className="evidence" key={i}>
                                    <strong>{e.provider}</strong>
                                    {e.title && (
                                      <p>
                                        {e.title} · {e.artist}
                                      </p>
                                    )}
                                    <p>{e.reason || e.error}</p>
                                    {e.duration_difference != null && (
                                      <small>
                                        Duration difference:{" "}
                                        {e.duration_difference.toFixed(1)}s
                                      </small>
                                    )}
                                    {e.url && (
                                      <a
                                        href={e.url}
                                        target="_blank"
                                        rel="noreferrer"
                                      >
                                        Inspect source ↗
                                      </a>
                                    )}
                                  </div>
                                ))
                              ) : (
                                <Empty title="Evidence starts here">
                                  <p>
                                    {track.source === "demo"
                                      ? "Demo entries do not query external providers."
                                      : "Run metadata lookup from Scan & Review to find recording candidates."}
                                  </p>
                                </Empty>
                              ))}
                            {tab === "History" && (
                              <>
                                <p className="fine">
                                  Stable library reference: {track.source_id}
                                </p>
                                {data.history
                                  .filter((h) => h.track_id === track.id)
                                  .map((h) => (
                                    <div className="evidence" key={h.id}>
                                      <strong>{h.kind}</strong>
                                      <p>{h.detail}</p>
                                      <small>{date(h.created_at)}</small>
                                    </div>
                                  ))}
                                <h3>Accepted metadata</h3>
                                {Object.keys(track.accepted).length ? (
                                  Object.entries(track.accepted).map(
                                    ([k, v]) => (
                                      <div className="data-line" key={k}>
                                        <span>{label(k)}</span>
                                        <b>{v}</b>
                                      </div>
                                    ),
                                  )
                                ) : (
                                  <p>No corrections accepted yet.</p>
                                )}
                                <p className="file-path">
                                  {track.path || "Demo — no local file"}
                                </p>
                              </>
                            )}
                          </div>
                        </aside>
                      )}
                    </div>
                  </>
                ))}
              {page === "Scan & Review" && (
                <Review
                  tracks={tracks}
                  proposals={proposals}
                  suggested={data.suggested ?? []}
                  queued={data.queued ?? []}
                  scan={data.scan ?? null}
                  active={active}
                  choices={
                    data.choices ?? { tags: [], playlists: [], loaded: false }
                  }
                  chosen={chosen}
                  setChosen={setChosen}
                  busy={busy}
                  demo={data.settings.demo}
                  genres={libraryGenres}
                  action={action}
                  onEditTrack={setEditingTrack}
                  notices={
                    <>
                      {data.tag_sessions
                        .filter((t) => t.state !== "checking" || !active)
                        .map((t) => (
                          <div className="callout" key={t.id}>
                            <strong>
                              Tagging {t.total} imported{" "}
                              {t.total === 1 ? "track" : "tracks"} · at track{" "}
                              {Math.min(t.position + 1, t.total)}
                            </strong>
                            <p>
                              {t.state === "checking"
                                ? "The checks before tagging stopped part-way. Continue to finish them, or tag now."
                                : `Imported ${date(t.created_at)}. Pick up where you left off.`}
                            </p>
                            <div className="button-row">
                              <button
                                className="primary"
                                disabled={busy}
                                onClick={() => setTagging(t.id)}
                              >
                                Continue tagging
                              </button>
                              {t.state === "checking" && (
                                <button
                                  disabled={busy || !!active}
                                  onClick={() =>
                                    action(
                                      `tagging/${t.id}/check`,
                                      undefined,
                                      "Checks started",
                                    )
                                  }
                                >
                                  Finish the checks
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      {choicesWaiting}
                      {data.relocation_review.length > 0 && (
                        <div className="callout">
                          <strong>
                            {data.relocation_review.length} missing{" "}
                            {data.relocation_review.length === 1
                              ? "file has"
                              : "files have"}{" "}
                            a possible match in your music folder
                          </strong>
                          <p>
                            These were not repointed because the match is not
                            certain. Relocate them in rekordbox if they are the
                            same track.
                          </p>
                          {data.relocation_review.map((r) => (
                            <p key={r.source_id} className="file-path">
                              {r.path} → {r.candidates.join(" or ")} ({r.reason}
                              )
                            </p>
                          ))}
                        </div>
                      )}
                      {!data.capability.enabled && (
                        <div className="callout">
                          <strong>Write compatibility pending</strong>
                          <p>{data.capability.reason}</p>
                          <span>
                            Scanning, matching and review remain available.
                            Approving a suggestion saves it in Song Dex now and
                            queues it for rekordbox.
                          </span>
                        </div>
                      )}
                      {data.edits_waiting > 0 && (
                        <div className="callout">
                          <strong>
                            {data.edits_waiting}{" "}
                            {data.edits_waiting === 1
                              ? "track has"
                              : "tracks have"}{" "}
                            approved edits waiting to reach rekordbox or audio
                            tags
                          </strong>
                          <p>
                            {waiting.ready > 0 &&
                              `${waiting.ready} can be retried now. `}
                            {waiting.offlineOnly > 0 &&
                              `${waiting.offlineOnly} are only waiting for a drive that is offline. `}
                            Edits wait while rekordbox writes are locked,
                            rekordbox is open, or a file is offline or in a
                            format without tag support. Tracks removed from
                            rekordbox are skipped.
                          </p>
                          <button
                            disabled={busy || !!active}
                            onClick={() =>
                              action("edits/sync", undefined, "Sync started")
                            }
                          >
                            Sync saved edits now
                          </button>
                        </div>
                      )}
                    </>
                  }
                />
              )}
              {page === "Duplicates" && (
                <Duplicates
                  groups={data.duplicates}
                  tracks={tracks}
                  capability={data.capability}
                  dismissed={data.duplicates_dismissed}
                  busy={busy || !!active}
                  action={action}
                  onOpen={(id) => {
                    changePage("Song Dex");
                    pick(id);
                  }}
                />
              )}
              {page === "History" && (
                <div className="page-body">
                  <div
                    className="detail-tabs history-tabs"
                    role="tablist"
                    aria-label="History"
                  >
                    {historyTabs.map((t, index) => (
                      <button
                        key={t}
                        role="tab"
                        tabIndex={historyTab === t ? 0 : -1}
                        onKeyDown={(e) => {
                          if (e.key !== "ArrowRight" && e.key !== "ArrowLeft")
                            return;
                          e.preventDefault();
                          const next =
                            historyTabs[
                              (index +
                                (e.key === "ArrowRight"
                                  ? 1
                                  : historyTabs.length - 1)) %
                                historyTabs.length
                            ];
                          setHistoryTab(next);
                          (
                            e.currentTarget.parentElement?.querySelector(
                              `[data-tab="${next}"]`,
                            ) as HTMLElement
                          )?.focus();
                        }}
                        data-tab={t}
                        aria-selected={historyTab === t}
                        onClick={() => setHistoryTab(t)}
                      >
                        {t}
                        {t === "Actions" && unresolved > 0 && (
                          <>
                            {" "}
                            <Badge tone="warn">{unresolved} to sort out</Badge>
                          </>
                        )}
                      </button>
                    ))}
                  </div>
                  {historyTab === "Actions" && (
                    <div role="tabpanel" aria-label="Actions">
                      {stuckWrites.map(writeCard)}
                      {stuckOperations.map(operationCard)}
                      {data.jobs
                        .filter((j) =>
                          ["failed", "interrupted"].includes(j.state),
                        )
                        .map((j) => (
                          <div className="callout" key={j.id}>
                            <strong>
                              {j.kind}: {j.state}
                            </strong>
                            <p>{j.message}</p>
                            {resumeAction(j)}
                          </div>
                        ))}
                      {data.imports
                        .filter((i) => i.state !== "preview")
                        .map((i) => (
                          <section className="operation" key={i.id}>
                            <h2>Music import · {i.state}</h2>
                            <p>{date(i.created_at)}</p>
                            <div className="button-row">
                              <button
                                onClick={() => {
                                  setReceiptId(i.id);
                                  setImportOpen(true);
                                }}
                              >
                                View import receipt
                              </button>
                              {data.tag_sessions.some((t) => t.id === i.id) && (
                                <button
                                  className="primary"
                                  onClick={() => setTagging(i.id)}
                                >
                                  Continue tagging
                                </button>
                              )}
                            </div>
                          </section>
                        ))}
                      {data.local_writes.filter(restorable).map(writeCard)}
                      {data.operations.filter(restorable).map(operationCard)}
                    </div>
                  )}
                  {historyTab === "Backups" && (
                    <div role="tabpanel" aria-label="Backups">
                      <Backups locked={busy || !!active} action={action} />
                    </div>
                  )}
                  {historyTab === "Logs" && (
                    <div role="tabpanel" aria-label="Logs">
                      {data.jobs
                        .filter((j) => j.state === "partial")
                        .map((j) => (
                          <div className="callout" key={j.id}>
                            <strong>
                              {j.kind}: {j.state}
                            </strong>
                            <p>{j.message}</p>
                          </div>
                        ))}
                      {data.history.length ? (
                        data.history.map((h) => (
                          <div className="history-row" key={h.id}>
                            <span className="history-node" />
                            <div>
                              <strong>{h.kind}</strong>
                              <p>{h.detail}</p>
                            </div>
                            <time>{date(h.created_at)}</time>
                          </div>
                        ))
                      ) : (
                        <Empty title="A clean slate">
                          <p>
                            Your scans, decisions, and changes will appear here.
                          </p>
                        </Empty>
                      )}
                    </div>
                  )}
                </div>
              )}
              {page === "Settings" && (
                <div className="page-body settings">
                  <section>
                    <h2>Library connection</h2>
                    <p>
                      Connect one personal collection. Music can live on this
                      Mac or a mounted external drive.
                    </p>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        action(
                          "settings",
                          {
                            rekordbox_db: path,
                            music_folder: musicFolder,
                            ...(key ? { acoustid_key: key } : {}),
                            ...(discogs ? { discogs_token: discogs } : {}),
                            ...(discogsKey ? { discogs_key: discogsKey } : {}),
                            ...(discogsSecret
                              ? { discogs_secret: discogsSecret }
                              : {}),
                          },
                          "Settings saved",
                        );
                        setKey("");
                        setDiscogs("");
                        setDiscogsKey("");
                        setDiscogsSecret("");
                      }}
                    >
                      <label>
                        rekordbox database
                        <input
                          value={path}
                          onChange={(e) => setPath(e.target.value)}
                          required
                          spellCheck={false}
                        />
                      </label>
                      <label>
                        Main music folder
                        <input
                          value={musicFolder}
                          onChange={(e) => setMusicFolder(e.target.value)}
                          required
                          spellCheck={false}
                        />
                      </label>
                      <button
                        type="button"
                        disabled={busy || !!active}
                        onClick={() => setFolderOpen(true)}
                      >
                        Choose music folder
                      </button>
                      <p className="fine">
                        New music is copied or moved here after you review the
                        import. Existing tracks keep their current locations.
                      </p>
                      <label>
                        AcoustID application key{" "}
                        <span className="muted">optional</span>
                        <input
                          type="password"
                          value={key}
                          onChange={(e) => setKey(e.target.value)}
                          autoComplete="off"
                          placeholder={
                            data.settings.acoustid_configured
                              ? "Key configured — leave blank to keep"
                              : "Enter your application key"
                          }
                        />
                      </label>
                      <p className="fine">
                        Fingerprint lookup also requires Chromaprint’s fpcalc
                        executable. Only a fingerprint and duration are sent;
                        audio stays local.
                      </p>
                      <label>
                        Discogs personal access token{" "}
                        <span className="muted">optional</span>
                        <input
                          type="password"
                          value={discogs}
                          onChange={(e) => setDiscogs(e.target.value)}
                          autoComplete="off"
                          placeholder={
                            data.settings.discogs_configured
                              ? "Token configured — leave blank to keep"
                              : "Paste the token from discogs.com/settings/developers"
                          }
                        />
                      </label>
                      <label>
                        Discogs consumer key{" "}
                        <span className="muted">
                          optional, with its secret, instead of a token
                        </span>
                        <input
                          type="password"
                          value={discogsKey}
                          onChange={(e) => setDiscogsKey(e.target.value)}
                          autoComplete="off"
                          placeholder={
                            data.settings.discogs_configured
                              ? "Configured — leave blank to keep"
                              : "Consumer Key of your Discogs application"
                          }
                        />
                      </label>
                      <label>
                        Discogs consumer secret
                        <input
                          type="password"
                          value={discogsSecret}
                          onChange={(e) => setDiscogsSecret(e.target.value)}
                          autoComplete="off"
                          placeholder={
                            data.settings.discogs_configured
                              ? "Configured — leave blank to keep"
                              : "Consumer Secret of your Discogs application"
                          }
                        />
                      </label>
                      <p className="fine">
                        Used to suggest a genre for tracks without one. Only the
                        artist and title are sent. This application uses
                        Discogs’ API but is not affiliated with, sponsored or
                        endorsed by Discogs. ‘Discogs’ is a trademark of Zink
                        Media, LLC.
                      </p>
                      <button className="primary" disabled={busy || !!active}>
                        Save settings
                      </button>
                    </form>
                  </section>
                  <section>
                    <h2>Compatibility</h2>
                    <div className="data-line">
                      <span>rekordbox version</span>
                      <strong>{data.capability.version}</strong>
                    </div>
                    <div className="data-line">
                      <span>Direct writes</span>
                      <Badge
                        tone={data.capability.enabled ? "success" : "warn"}
                      >
                        {data.capability.enabled
                          ? "Verified"
                          : "Locked pending verification"}
                      </Badge>
                    </div>
                    <p>
                      {data.capability.reason ||
                        "Compatibility checks passed for this installation."}
                    </p>
                    <p className="fine">
                      BPM, key, beatgrids, cues, artwork, and file locations are
                      preserved. Metadata write support is checked separately
                      for MP3, FLAC, AIFF, and M4A.
                    </p>
                  </section>
                  <section>
                    <h2>Metadata sources</h2>
                    <div className="data-line">
                      <span>MusicBrainz</span>
                      <b>Catalog lookup</b>
                    </div>
                    <div className="data-line">
                      <span>AcoustID</span>
                      <b>
                        {data.settings.acoustid_configured
                          ? "Configured"
                          : "Optional"}
                      </b>
                    </div>
                    <div className="data-line">
                      <span>Discogs</span>
                      <b>
                        {data.settings.discogs_configured
                          ? "Configured"
                          : "Optional"}
                      </b>
                    </div>
                    <div className="data-line">
                      <span>Every Noise at Once</span>
                      <b>Genre names for the picker</b>
                    </div>
                    <p className="fine">
                      SongData, Spotify and DJ catalogs are planned
                      integrations; no access is assumed.
                    </p>
                  </section>
                  {unavailable.length > 0 && (
                    <section>
                      <h2>Unavailable locations</h2>
                      <p>
                        {unavailable.length.toLocaleString()} files could not be
                        found during the last scan. Reconnect their drives and
                        rescan; their Dex entries are retained.
                      </p>
                      {Object.entries(unavailableLocations).map(
                        ([location, count]) => (
                          <div className="data-line" key={location}>
                            <span>{location}</span>
                            <b>{count.toLocaleString()} files</b>
                          </div>
                        ),
                      )}
                    </section>
                  )}
                  {data.settings.demo && (
                    <section>
                      <h2>Demo library</h2>
                      <p>
                        Remove the illustrative entries before importing your
                        collection.
                      </p>
                      <button
                        disabled={busy}
                        onClick={() =>
                          action(
                            "demo/clear",
                            undefined,
                            "Demo cleared. Ready to import your library.",
                          )
                        }
                      >
                        Exit demo
                      </button>
                    </section>
                  )}
                </div>
              )}
            </>
          )}
          <footer className="screen-footer">
            <span>SONG DEX / v0.1</span>
            <span>{busy ? "WORKING…" : "● SAVED LOCALLY"}</span>
            <span>SELECT · INSPECT · REFINE</span>
          </footer>
        </main>
      </div>
      <footer className="housing-footer">
        <span>RECORDING ARCHIVE UNIT</span>
        <div className="hardware-dots">
          <i />
          <i />
          <i />
        </div>
        <span>DESIGNED FOR YOUR COLLECTION</span>
      </footer>
      {data && importOpen && (
        <ImportMusic
          folder={data.settings.music_folder}
          request={action}
          busy={busy || !!active}
          receiptId={receiptId}
          requestError={error}
          sessions={data.tag_sessions}
          onTag={(id) => {
            setImportOpen(false);
            setTagging(id);
          }}
          onClose={() => setImportOpen(false)}
        />
      )}
      {data && tagging && (
        <Tagging
          sessionId={tagging}
          tracks={tracks}
          proposals={proposals}
          queued={data.queued ?? []}
          genres={libraryGenres}
          demo={data.settings.demo}
          capability={data.capability}
          busy={busy || !!active}
          lookingUp={active?.kind === "enrich"}
          manualEdits={data.manual_edits}
          send={send}
          action={action}
          onClose={() => {
            setTagging(null);
            void reload();
          }}
        />
      )}
      {folderOpen && (
        <Dialog
          title="Choose music folder"
          onClose={() => setFolderOpen(false)}
        >
          <FileBrowser
            request={action}
            selected={[]}
            onSelect={() => {}}
            initialPath={musicFolder}
            onFolder={(p) => {
              setMusicFolder(p);
              setFolderOpen(false);
            }}
          />
        </Dialog>
      )}
      {data && newPlaylist && (
        <NewPlaylist
          choices={choices}
          tracks={newPlaylist}
          send={send}
          onClose={() => setNewPlaylist(null)}
          onDone={async (message) => {
            setNewPlaylist(null);
            await reload();
            setNotice(message);
          }}
        />
      )}
      {data && bulk && (
        <AddToLists
          kind={bulk}
          tracks={markedTracks}
          choices={choices}
          genres={libraryGenres}
          send={send}
          onChanged={reload}
          onClose={() => setBulk(null)}
          onDone={async (message) => {
            setBulk(null);
            await reload();
            setNotice(message);
          }}
        />
      )}
      {editingTrack !== null &&
        (() => {
          const t = tracks.find((t) => t.id === editingTrack);
          return (
            t && (
              <Dialog
                title={`Edit track · NO. ${dex(t.id)}`}
                onClose={() => setEditingTrack(null)}
              >
                {/* The page's own error banner sits behind this dialog. */}
                {error && (
                  <p role="alert" className="error-text">
                    {error}
                  </p>
                )}
                <div
                  className="detail-tabs edit-tabs"
                  role="tablist"
                  aria-label="Edit track"
                >
                  {(["Metadata", "My Tags"] as const).map((name) => (
                    <button
                      key={name}
                      role="tab"
                      aria-selected={editTab === name}
                      onClick={() => setEditTab(name)}
                    >
                      {name}
                    </button>
                  ))}
                </div>
                {editTab === "My Tags" ? (
                  myTagsPanel(t)
                ) : (
                  <ManualEditor
                    key={t.id}
                    track={t}
                    busy={busy || !!active}
                    request={action}
                    genres={libraryGenres}
                    statuses={
                      data?.manual_edits.filter((e) => e.track_id === t.id) ??
                      []
                    }
                  />
                )}
              </Dialog>
            )
          );
        })()}
      {confirm && (
        <div className="modal-backdrop">
          <section
            ref={modalRef}
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
          >
            <h2 id="confirm-title">Restore this operation?</h2>
            <p>
              {confirm.startsWith("local:")
                ? "Restore this destination from its backup. Your saved Dex correction remains available for later syncing. Newer changes will block restoration."
                : "Restore the backed-up audio files, rekordbox database, and accepted metadata. Newer changes will block restoration."}
            </p>
            <p>Quit rekordbox and its background agent before continuing.</p>
            <div className="button-row">
              <button
                autoFocus
                onClick={() => setConfirm(null)}
                disabled={busy}
              >
                Cancel
              </button>
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  action(
                    confirm.startsWith("local:")
                      ? `local-writes/${confirm.slice(6)}/restore`
                      : `operations/${confirm}/restore`,
                    undefined,
                    "Operation restored",
                  )
                }
              >
                {busy ? "Working…" : "Restore"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
