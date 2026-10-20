import { useEffect, useMemo, useRef, useState } from "react";
import type { GenreCount } from "./GenreInput";
import { Dialog, ManualEditor } from "./LibraryTools";
import type { EditableTrack, Status } from "./LibraryTools";
import { ListPicker } from "./Lists";
import type { ListChoices } from "./Lists";
import { TrackDiff } from "./Review";
import type { Proposal, ReviewTrack } from "./Review";

type Entry = ReviewTrack & EditableTrack;
type Lists = { tags: string[]; playlists: string[] };
type Suggestion = { kind: "tag" | "playlist"; id: string; reasons: string[] };
type Item = {
  id: number;
  in_rekordbox: boolean;
  checked: boolean;
  pending: Lists;
  saved: Lists;
  duplicates: number[];
  suggestions: Suggestion[];
};
type Session = {
  id: string;
  state: string;
  position: number;
  choices: ListChoices;
  tracks: Item[];
};
type Picked = { tags: Set<string>; playlists: Set<string> };

const dex = (id: number) => String(id).padStart(4, "0");
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
const typing = (target: EventTarget | null) =>
  target instanceof HTMLInputElement ||
  target instanceof HTMLTextAreaElement ||
  target instanceof HTMLSelectElement;
const stored = (key: string) => localStorage.getItem(key) !== "0";

/** Step through an import's tracks, listening to each and giving it My Tags and playlists. */
export function Tagging({
  sessionId,
  tracks,
  proposals,
  queued,
  genres,
  demo,
  capability,
  busy,
  lookingUp,
  manualEdits,
  send,
  action,
  onClose,
}: {
  sessionId: string;
  tracks: Entry[];
  proposals: Proposal[];
  queued: number[];
  genres: GenreCount[];
  demo: boolean;
  capability: { enabled: boolean; reason: string };
  busy: boolean;
  /** A metadata lookup (scan) is running. */
  lookingUp: boolean;
  manualEdits: Status[];
  send: (endpoint: string, body?: unknown) => Promise<any>;
  action: (
    endpoint: string,
    body?: unknown,
    success?: string,
  ) => Promise<unknown>;
  onClose: () => void;
}) {
  const [session, setSession] = useState<Session | null>(null),
    [index, setIndex] = useState(0),
    [picked, setPicked] = useState<Record<number, Picked>>({}),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false),
    [summary, setSummary] = useState(false),
    [editing, setEditing] = useState(false);
  const [autoplay, setAutoplay] = useState(() => stored("songdex-autoplay")),
    [skipIntro, setSkipIntro] = useState(() => stored("songdex-skip-intro"));
  const player = useRef<HTMLAudioElement>(null),
    searchRef = useRef<HTMLInputElement>(null);
  const byId = useMemo(() => new Map(tracks.map((t) => [t.id, t])), [tracks]);
  const waiting = useMemo(() => new Set(queued), [queued]);

  const load = async (first = false) => {
    try {
      const r = await fetch(`/api/tagging/${sessionId}`);
      const body = await r.json();
      if (!r.ok)
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : "Cannot load this tagging session",
        );
      const s: Session = body;
      setSession(s);
      // Choices already made start selected; later loads only refresh suggestions.
      setPicked((prior) => {
        const next = { ...prior };
        for (const t of s.tracks)
          if (first || !next[t.id])
            next[t.id] = {
              tags: new Set(t.pending.tags),
              playlists: new Set(t.pending.playlists),
            };
        return next;
      });
      if (first) setIndex(s.position);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cannot load this session");
    }
  };
  useEffect(() => {
    void load(true);
  }, [sessionId]);
  // A lookup started here brings new My Tag and playlist suggestions when it ends.
  const wasLookingUp = useRef(lookingUp);
  useEffect(() => {
    if (wasLookingUp.current && !lookingUp) void load();
    wasLookingUp.current = lookingUp;
  }, [lookingUp]);

  const items = session?.tracks ?? [];
  const item = items[index];
  const track = item && byId.get(item.id);
  const choices = session?.choices ?? {
    tags: [],
    playlists: [],
    loaded: false,
  };
  const tagName = new Map(choices.tags.map((t) => [t.id, t.name])),
    playlistName = new Map(choices.playlists.map((p) => [p.id, p.name]));
  const mine: Picked = (item && picked[item.id]) || {
    tags: new Set(),
    playlists: new Set(),
  };
  // What rekordbox (or an earlier write) already gives the track: shown, not changeable.
  const held = {
    tags: new Set([
      ...(track?.my_tags.map((t) => String(t.id)) ?? []),
      ...(item?.saved.tags ?? []),
    ]),
    playlists: new Set([
      ...(track?.playlists.flatMap((p) => (p.id ? [String(p.id)] : [])) ?? []),
      ...(item?.saved.playlists ?? []),
    ]),
  };
  const suggested = (item?.suggestions ?? []).filter(
    (s) => !held[s.kind === "tag" ? "tags" : "playlists"].has(s.id),
  );
  const isPicked = (s: Suggestion) =>
    mine[s.kind === "tag" ? "tags" : "playlists"].has(s.id);

  const toggle = (kind: "tags" | "playlists", id: string, on?: boolean) => {
    if (!item || held[kind].has(id)) return;
    setPicked((prior) => {
      const current = prior[item.id] ?? mine;
      const next = new Set(current[kind]);
      (on ?? !next.has(id)) ? next.add(id) : next.delete(id);
      return { ...prior, [item.id]: { ...current, [kind]: next } };
    });
  };

  /** Make a new My Tag or playlist; the session reloads so it can be picked. */
  const createList = async (
    kind: "tag" | "playlist" | "folder",
    name: string,
    parent: string,
  ) => {
    setError("");
    try {
      const made = await send("lists", { kind, name, parent });
      await load();
      return made.id as string;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not make it");
      return null;
    }
  };

  /** Keep the current track's choices, then move to `to` (or the summary past the end). */
  const go = async (to: number) => {
    if (!session || saving) return false;
    setError("");
    if (item) {
      setSaving(true);
      try {
        await send(`tagging/${session.id}/tracks/${item.id}`, {
          tags: [...mine.tags],
          playlists: [...mine.playlists],
          position: Math.min(to, items.length - 1),
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not keep the choices");
        setSaving(false);
        return false;
      }
      setSaving(false);
      // Choices for this track feed the suggestions for the ones after it.
      void load();
    }
    if (to >= items.length) setSummary(true);
    else setIndex(Math.max(0, to));
    return true;
  };

  const close = async () => {
    if (!item || summary || (await go(index))) onClose();
  };

  // Each new track starts playing, past its intro if asked.
  useEffect(() => {
    const audio = player.current;
    if (!audio || summary) return;
    const start = () => {
      if (skipIntro && audio.duration > 60)
        audio.currentTime = Math.round(audio.duration * 0.3);
    };
    if (audio.readyState >= 1) start();
    else audio.addEventListener("loadedmetadata", start, { once: true });
    if (autoplay) void audio.play().catch(() => {});
    return () => audio.removeEventListener("loadedmetadata", start);
  }, [item?.id, summary]);

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (summary || typing(e.target) || e.metaKey || e.ctrlKey || e.altKey)
        return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        void go(index + 1);
      } else if (e.key === "ArrowLeft" && index > 0) {
        e.preventDefault();
        void go(index - 1);
      } else if (e.key === "p" || e.key === "P") {
        const audio = player.current;
        if (audio) audio.paused ? void audio.play() : audio.pause();
      } else if (e.key === "f" || e.key === "F") {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (/^[1-9]$/.test(e.key)) {
        const s = suggested[Number(e.key) - 1];
        if (s) toggle(s.kind === "tag" ? "tags" : "playlists", s.id);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  });

  if (!session)
    return (
      <Dialog title="Tag imported tracks" onClose={onClose} wide>
        {error ? (
          <p role="alert" className="error-text">
            {error}
          </p>
        ) : (
          <p>Loading the imported tracks…</p>
        )}
      </Dialog>
    );

  if (!items.length)
    return (
      <Dialog title="Tag imported tracks" onClose={onClose} wide>
        <p>
          No tracks from this import are in the Dex. Files that were skipped or
          failed to import are not tagged.
        </p>
      </Dialog>
    );

  if (summary) {
    // Tracks with choices not yet written to rekordbox.
    const chosen = items.filter((t) =>
      (["tags", "playlists"] as const).some((kind) =>
        [...(picked[t.id]?.[kind] ?? [])].some(
          (id) => !t.saved[kind].includes(id),
        ),
      ),
    );
    const ready = chosen.filter((t) => t.in_rekordbox),
      later = chosen.filter((t) => !t.in_rekordbox);
    return (
      <Dialog title="Tagging done" onClose={onClose} wide>
        <p>
          {chosen.length
            ? `${plural(chosen.length, "track")} of ${items.length} have My Tags or playlists to add.`
            : "Nothing is waiting: no new choices, or they are already in rekordbox."}
        </p>
        {ready.length > 0 && (
          <div className="callout">
            <strong>
              {plural(ready.length, "track")} already in rekordbox
            </strong>
            <p>
              Their choices can be written now: one backed-up change you can
              restore from History. Quit rekordbox first.
            </p>
            {!capability.enabled && (
              <p className="difference">△ {capability.reason}</p>
            )}
            <button
              className="primary"
              disabled={busy || !capability.enabled}
              onClick={async () => {
                if (await action("assignments/write")) await load();
              }}
            >
              Write to rekordbox
            </button>
          </div>
        )}
        {later.length > 0 && (
          <div className="callout">
            <strong>
              {plural(later.length, "new track")} waiting for rekordbox
            </strong>
            <p>
              rekordbox has no entry for these yet. Import the playlist in
              rekordbox (File → Import → Import Playlist), quit rekordbox and
              rescan here: the scan writes their tags and playlists.
            </p>
            <a
              className="button"
              href={`/api/imports/${session.id}/playlist`}
              download
            >
              Download rekordbox import playlist
            </a>
          </div>
        )}
        {error && (
          <p role="alert" className="error-text">
            {error}
          </p>
        )}
        <div className="button-row">
          <button
            onClick={() => {
              setSummary(false);
              setIndex(items.length - 1);
            }}
          >
            Back to tracks
          </button>
          <button
            className="primary"
            onClick={async () => {
              try {
                await send(`tagging/${session.id}/finish`);
                onClose();
              } catch (e) {
                setError(e instanceof Error ? e.message : "Request failed");
              }
            }}
          >
            Finish
          </button>
        </div>
      </Dialog>
    );
  }

  const m = track?.metadata ?? {};
  const twins = item.duplicates.map((id) => byId.get(id)).filter(Boolean);
  const metadataWaiting = proposals.filter((p) => p.track_id === item.id);
  const facts = [m.album, m.genre, m.year, m.bpm && `${m.bpm} BPM`, m.key]
    .filter(Boolean)
    .join(" · ");

  return (
    <Dialog title="Tag imported tracks" onClose={() => void close()} wide>
      <div className="tagging-progress">
        <span>
          Track {index + 1} of {items.length}
        </span>
        <progress value={index + 1} max={items.length} />
      </div>
      {!choices.loaded && (
        <p className="difference">
          △ Your My Tags and playlists are not loaded yet. Rescan the library,
          then come back to tag.
        </p>
      )}
      <section className="tagging-track">
        <div className="tagging-art">
          {track?.available ? (
            <img
              src={`/api/tracks/${item.id}/artwork`}
              alt=""
              onError={(e) => (e.currentTarget.style.visibility = "hidden")}
            />
          ) : null}
        </div>
        <div className="tagging-titles">
          <small>NO. {dex(item.id)}</small>
          <h3>{m.title || track?.path.split("/").pop() || "Unknown track"}</h3>
          <p>{m.artist || "Unknown artist"}</p>
          {facts && <p className="muted">{facts}</p>}
          {/* What the checks before tagging found for this track. */}
          <div className="tagging-badges" aria-label="Checks">
            {!item.checked ? (
              <span className="badge warn">Not checked yet</span>
            ) : track?.error ? (
              <span className="badge warn">Metadata lookup failed</span>
            ) : (
              <span className="badge success">✓ Metadata & genre checked</span>
            )}
            {metadataWaiting.length > 0 && (
              <span className="badge warn">
                {plural(metadataWaiting.length, "metadata suggestion")} below
              </span>
            )}
            {twins.length ? (
              <span className="badge warn">
                △ {plural(twins.length, "possible duplicate")}
              </span>
            ) : (
              <span className="badge success">✓ No duplicates</span>
            )}
            {!item.in_rekordbox && (
              <span className="badge warn">Not in rekordbox yet</span>
            )}
          </div>
        </div>
      </section>
      {track?.available ? (
        <audio
          key={`audio-${item.id}`}
          ref={player}
          controls
          preload="metadata"
          src={`/api/tracks/${item.id}/audio`}
          aria-label="Listen to this track"
          className="tagging-player"
        />
      ) : (
        <p className="fine">Audio file unavailable.</p>
      )}
      <div className="tagging-options">
        <label>
          <input
            type="checkbox"
            checked={autoplay}
            onChange={(e) => {
              setAutoplay(e.target.checked);
              localStorage.setItem(
                "songdex-autoplay",
                e.target.checked ? "1" : "0",
              );
            }}
          />{" "}
          Play each track
        </label>
        <label>
          <input
            type="checkbox"
            checked={skipIntro}
            onChange={(e) => {
              setSkipIntro(e.target.checked);
              localStorage.setItem(
                "songdex-skip-intro",
                e.target.checked ? "1" : "0",
              );
            }}
          />{" "}
          Start past the intro
        </label>
      </div>
      {track && (
        <section className="tagging-section tagging-metadata">
          <div className="tagging-heading">
            <h4>Metadata</h4>
            <div className="button-row">
              <button
                className="quiet"
                disabled={busy || demo}
                title="Look up metadata, genres, My Tags and playlists for this track again"
                onClick={() =>
                  void action(
                    "lookup",
                    { scope: "selected", ids: [track.id] },
                    "Looking this track up again",
                  )
                }
              >
                {lookingUp ? "Looking up…" : "Look up again"}
              </button>
              <button
                className="quiet"
                aria-expanded={editing}
                onClick={() => setEditing((v) => !v)}
              >
                {editing ? "Done editing" : "Edit metadata"}
              </button>
            </div>
          </div>
          {metadataWaiting.length > 0 && (
            <TrackDiff
              track={track}
              proposals={metadataWaiting}
              queued={waiting}
              locked={busy || demo}
              genres={genres}
              act={action}
            />
          )}
          {metadataWaiting.length === 0 && !editing && (
            <p className="fine">
              {lookingUp
                ? "Looking up suggestions for this track…"
                : "No metadata suggestions. Edit the fields yourself or look the track up again."}
            </p>
          )}
          {editing && (
            <ManualEditor
              key={`editor-${track.id}`}
              track={track}
              busy={busy}
              request={action}
              genres={genres}
              statuses={manualEdits.filter((e) => e.track_id === track.id)}
            />
          )}
        </section>
      )}
      {twins.length > 0 && (
        <div className="callout">
          <strong>Possible duplicate</strong>
          {twins.map((t) => (
            <p key={t!.id}>
              NO. {dex(t!.id)} · {t!.metadata.title} — {t!.metadata.artist}
              <span className="file-path">{t!.path}</span>
            </p>
          ))}
          <p className="fine">
            Its tags and playlists are suggested below. Merge or keep both from
            Duplicates.
          </p>
        </div>
      )}
      {suggested.length > 0 && (
        <section className="tagging-section">
          <div className="tagging-heading">
            <h4>Suggested</h4>
            <button
              className="quiet"
              disabled={suggested.every(isPicked)}
              onClick={() =>
                suggested.forEach((s) =>
                  toggle(s.kind === "tag" ? "tags" : "playlists", s.id, true),
                )
              }
            >
              Add all
            </button>
          </div>
          <div className="tag-choices">
            {suggested.map((s, i) => (
              <button
                key={s.kind + s.id}
                className="tag-choice suggestion"
                aria-pressed={isPicked(s)}
                onClick={() =>
                  toggle(s.kind === "tag" ? "tags" : "playlists", s.id)
                }
                title={s.reasons.join("\n")}
              >
                {i < 9 && <kbd>{i + 1}</kbd>}
                <span>
                  {s.kind === "tag"
                    ? tagName.get(s.id)
                    : `▤ ${playlistName.get(s.id)}`}
                  <small>{s.reasons[0]}</small>
                </span>
              </button>
            ))}
          </div>
        </section>
      )}
      <ListPicker
        key={`picker-${item.id}`}
        genres={genres}
        choices={choices}
        held={held}
        picked={mine}
        onToggle={toggle}
        onCreate={createList}
        searchRef={searchRef}
      />
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      <div className="button-row tagging-nav">
        <button disabled={!index || saving} onClick={() => void go(index - 1)}>
          ← Previous
        </button>
        <button
          className="primary"
          disabled={saving}
          onClick={() => void go(index + 1)}
        >
          {index + 1 < items.length ? "Next track →" : "Review and finish"}
        </button>
      </div>
      <p className="fine">
        Keys: ← → move between tracks (choices are kept as you go) · P play or
        pause · 1–9 add a suggestion · F find a playlist
      </p>
    </Dialog>
  );
}
