import { useMemo, useState } from "react";
import { Dialog } from "./LibraryTools";

export type DuplicateGroup = {
  kind: string;
  tracks: number[];
  warnings: string[];
  note?: string;
  keep: number;
  awaiting_removal: number[];
  merged: boolean;
};
type Entry = {
  id: number;
  available: number;
  metadata: Record<string, string | number>;
  playlists: { name: string; id?: string }[];
  my_tags: { id: string; name: string }[];
  stats?: { cues?: number; plays?: number; rating?: number; added?: string };
};
type Choice = { keep: number; remove: number[] };
type Merge = { keep: number; remove: number[]; okay?: boolean };
type Plan = { merges: Merge[]; okay: DuplicateGroup[] };

const OWN = "Song Dex / ";
const kinds: Record<string, string> = {
  exact: "Identical file contents",
  probable: "Likely duplicates",
  related: "Check before merging",
};
const keyOf = (g: DuplicateGroup) =>
  [...g.tracks].sort((a, b) => a - b).join("-");
const length = (n: string | number | undefined) => {
  const v = Number(n) || 0;
  return `${Math.floor(v / 60)}:${String(Math.floor(v % 60)).padStart(2, "0")}`;
};
const added = (day?: string) =>
  day
    ? `Added ${new Date(day + "T00:00").toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}`
    : "";
const plural = (n: number, word: string) =>
  `${n} ${n === 1 ? word : word.endsWith("y") ? word.slice(0, -1) + "ies" : word + "s"}`;

/** What a merge hands to the kept entry, mirroring the rule the service applies. */
function moves(keep: Entry, removed: Entry[]) {
  const lists = new Set(keep.playlists.map((p) => p.id ?? p.name)),
    tags = new Set(keep.my_tags.map((t) => t.id));
  return removed.map((entry) => {
    const playlists = entry.playlists.filter((p) => {
      const id = p.id ?? p.name;
      if (p.name.startsWith(OWN) || lists.has(id)) return false;
      lists.add(id);
      return true;
    });
    const myTags = entry.my_tags.filter((t) => {
      if (tags.has(t.id)) return false;
      tags.add(t.id);
      return true;
    });
    return { id: entry.id, playlists, myTags };
  });
}

export function Duplicates({
  groups,
  tracks,
  capability,
  dismissed,
  busy,
  action,
  onOpen,
}: {
  groups: DuplicateGroup[];
  tracks: Entry[];
  capability: { enabled: boolean; reason: string };
  dismissed: number;
  busy: boolean;
  action: (
    endpoint: string,
    body?: unknown,
    success?: string,
  ) => Promise<unknown>;
  onOpen: (id: number) => void;
}) {
  const [choices, setChoices] = useState<Record<string, Choice>>({}),
    [picked, setPicked] = useState<Set<string>>(new Set()),
    [show, setShow] = useState("open"),
    [limit, setLimit] = useState(40),
    [pending, setPending] = useState<Plan | null>(null);
  const byId = useMemo(() => new Map(tracks.map((t) => [t.id, t])), [tracks]);
  const candidates = (g: DuplicateGroup) =>
    g.tracks.filter((id) => !g.awaiting_removal.includes(id));
  const choiceFor = (g: DuplicateGroup): Choice =>
    choices[keyOf(g)] ?? {
      keep: g.keep,
      // With warnings and several entries, nothing merges until it is ticked.
      remove:
        g.warnings.length && candidates(g).length > 2
          ? []
          : candidates(g).filter((id) => id !== g.keep),
    };
  const open = groups.filter((g) => !g.merged),
    merged = groups.filter((g) => g.merged),
    clear = open.filter((g) => !g.warnings.length),
    flagged = open.filter((g) => g.warnings.length);
  const visible = { open, clear, flagged, merged }[show] ?? open;
  const chosen = open.filter((g) => picked.has(keyOf(g)));
  const mergesOf = (list: DuplicateGroup[]) =>
    list
      .map((g) => choiceFor(g))
      .filter((c) => c.remove.length)
      .slice(0, 500);
  const summary = (merges: Merge[]) => {
    let playlists = 0,
      tags = 0,
      cues = 0;
    for (const m of merges) {
      const removed = m.remove.map((id) => byId.get(id)!);
      for (const move of moves(byId.get(m.keep)!, removed)) {
        playlists += move.playlists.length;
        tags += move.myTags.length;
      }
      cues += removed.filter((t) => (t.stats?.cues ?? 0) > 0).length;
    }
    return { playlists, tags, cues };
  };
  const set = (g: DuplicateGroup, choice: Choice) =>
    setChoices({ ...choices, [keyOf(g)]: choice });
  const pick = (keys: string[], on: boolean) => {
    const next = new Set(picked);
    for (const key of keys) on ? next.add(key) : next.delete(key);
    setPicked(next);
  };
  const locked = busy || !capability.enabled;
  /** Some entries are ticked and others are not: remixes and versions that stay. */
  const partial = (g: DuplicateGroup) => {
    const ticked = choiceFor(g).remove.length;
    return (
      capability.enabled && ticked > 0 && ticked < candidates(g).length - 1
    );
  };
  const dismiss = (list: DuplicateGroup[]) =>
    action(
      "duplicates/dismiss",
      { groups: list.map((g) => g.tracks) },
      `${plural(list.length, "group")} marked as okay; a group returns if another copy appears`,
    );
  const okay = async (list: DuplicateGroup[]) => {
    const merging = list.filter(partial);
    if (merging.length)
      return setPending({
        merges: merging.map((g) => ({ ...choiceFor(g), okay: true })),
        okay: list.filter((g) => !partial(g)),
      });
    await dismiss(list);
    pick(list.map(keyOf), false);
  };

  return (
    <div className="page-body">
      <div className="callout">
        <strong>Merge duplicates into the entry you keep</strong>
        <p>
          A merge gives the kept entry the other entries' playlist places and My
          Tags, then lists those entries in rekordbox under{" "}
          <em>Song Dex / Duplicates to remove</em>. Cues, beat grids and play
          history stay with their own entry and are not moved. Nothing is
          deleted: remove the listed entries in rekordbox when you are ready.
        </p>
        <p>
          Marking a group as okay keeps its entries apart, as for remixes and
          other versions. Entries ticked to merge are merged first and the rest
          are left untouched.
        </p>
        {!capability.enabled && (
          <p className="difference">
            △ Merging is locked. {capability.reason} Marking groups as okay
            works now.
          </p>
        )}
      </div>
      {!groups.length ? (
        <div className="empty">
          <h2>No duplicate groups found</h2>
          <div>
            <p>
              Scan the collection to compare file hashes, recording names,
              duration, and versions.
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="duplicate-toolbar">
            <label>
              Show{" "}
              <select
                value={show}
                onChange={(e) => {
                  setShow(e.target.value);
                  setLimit(40);
                }}
              >
                <option value="open">All open groups ({open.length})</option>
                <option value="clear">Without warnings ({clear.length})</option>
                <option value="flagged">
                  With warnings ({flagged.length})
                </option>
                <option value="merged">
                  Merged, waiting for removal ({merged.length})
                </option>
              </select>
            </label>
            <button
              className="primary"
              disabled={locked || !clear.length}
              onClick={() => setPending({ merges: mergesOf(clear), okay: [] })}
            >
              Merge all {clear.length} without warnings
            </button>
            {dismissed > 0 && (
              <button
                className="quiet"
                disabled={busy}
                onClick={() =>
                  action(
                    "duplicates/reset-dismissed",
                    undefined,
                    "Groups marked as okay are shown again",
                  )
                }
              >
                Show {plural(dismissed, "okayed group")} again
              </button>
            )}
          </div>
          {show !== "merged" && (
            <div className="duplicate-toolbar duplicate-selection">
              <strong>{plural(chosen.length, "group")} selected</strong>
              <button
                disabled={locked || !mergesOf(chosen).length}
                onClick={() =>
                  setPending({ merges: mergesOf(chosen), okay: [] })
                }
              >
                Merge selected
              </button>
              <button
                disabled={busy || !chosen.length}
                onClick={() => okay(chosen)}
              >
                Mark selected as okay
              </button>
              <button
                className="quiet"
                onClick={() => pick(visible.slice(0, limit).map(keyOf), true)}
              >
                Select the {Math.min(limit, visible.length)} shown
              </button>
              {chosen.length > 0 && (
                <button className="quiet" onClick={() => setPicked(new Set())}>
                  Clear selection
                </button>
              )}
            </div>
          )}
        </>
      )}
      {visible.slice(0, limit).map((g, index) => {
        const choice = choiceFor(g),
          pair = candidates(g).length === 2,
          keep = byId.get(choice.keep)!,
          plan = new Map(
            moves(
              keep,
              choice.remove.map((id) => byId.get(id)!),
            ).map((m) => [m.id, m]),
          );
        const entries = (
          <>
            {g.tracks.map((id) => {
              const t = byId.get(id)!,
                waiting = g.awaiting_removal.includes(id),
                kept = !g.merged && id === choice.keep,
                merging = choice.remove.includes(id),
                move = plan.get(id),
                cues = t.stats?.cues ?? 0;
              return (
                <div
                  className={`duplicate-entry${kept ? " kept" : ""}`}
                  key={id}
                >
                  {!g.merged && !waiting && (
                    <div className="duplicate-roles">
                      <label>
                        <input
                          type="radio"
                          name={`keep-${keyOf(g)}`}
                          checked={kept}
                          onChange={() =>
                            set(g, {
                              keep: id,
                              remove: pair
                                ? [choice.keep]
                                : [
                                    ...choice.remove.filter((i) => i !== id),
                                    // The entry that was kept takes the place of this one.
                                    ...(merging ? [choice.keep] : []),
                                  ],
                            })
                          }
                        />{" "}
                        Keep
                      </label>
                      {!pair && (
                        <label>
                          <input
                            type="checkbox"
                            disabled={kept}
                            checked={merging}
                            onChange={() =>
                              set(g, {
                                keep: choice.keep,
                                remove: merging
                                  ? choice.remove.filter((i) => i !== id)
                                  : [...choice.remove, id],
                              })
                            }
                          />{" "}
                          Merge
                        </label>
                      )}
                    </div>
                  )}
                  <div className="duplicate-detail">
                    <strong>
                      {t.metadata.title || "Untitled"}{" "}
                      {id === g.keep && !g.merged && (
                        <span className="badge success">Suggested keep</span>
                      )}{" "}
                      {waiting && (
                        <span className="badge warn">Remove in rekordbox</span>
                      )}{" "}
                      {!t.available && <span className="badge">Offline</span>}
                    </strong>
                    <p>
                      NO. {String(id).padStart(4, "0")} ·{" "}
                      {t.metadata.artist || "Unknown artist"} ·{" "}
                      {t.metadata.format || "?"}
                      {Number(t.metadata.bitrate) > 0 &&
                        ` ${Math.round(Number(t.metadata.bitrate) / 1000)} kbps`}{" "}
                      · {length(t.metadata.duration)} · {t.metadata.bpm || "—"}{" "}
                      BPM
                      {t.metadata.key ? ` · ${t.metadata.key}` : ""} ·{" "}
                      {plural(cues, "cue")}
                      {t.stats?.added && ` · ${added(t.stats.added)}`}
                    </p>
                    <small>
                      {t.playlists.map((p) => p.name).join(" / ") ||
                        "No playlist membership"}
                      {t.my_tags.length > 0 &&
                        ` · My Tags: ${t.my_tags.map((m) => m.name).join(", ")}`}
                    </small>
                    {merging && move && (
                      <p className="duplicate-move">
                        →{" "}
                        {move.playlists.length || move.myTags.length
                          ? `Moves to the kept entry: ${[
                              ...move.playlists.map((p) => p.name),
                              ...move.myTags.map((m) => `My Tag ${m.name}`),
                            ].join(", ")}`
                          : "Nothing to move; it is only listed for removal"}
                        {cues > 0 &&
                          ` · △ ${plural(cues, "cue")} stay behind on this entry`}
                      </p>
                    )}
                  </div>
                  <button
                    className="quiet"
                    aria-label={`Open ${t.metadata.title} in Song Dex`}
                    onClick={() => onOpen(id)}
                  >
                    ↗
                  </button>
                </div>
              );
            })}
            {g.warnings.map((w) => (
              <p className="difference" key={w}>
                △ {w}
              </p>
            ))}
            {g.note && <p className="duplicate-note">{g.note}</p>}
            {!g.merged && (
              <div className="button-row duplicate-actions">
                <button
                  disabled={locked || !choice.remove.length}
                  onClick={() => setPending({ merges: [choice], okay: [] })}
                >
                  {pair
                    ? "Merge into the kept entry"
                    : choice.remove.length
                      ? `Merge ${plural(choice.remove.length, "ticked entry")} into the kept entry`
                      : "Tick entries to merge"}
                </button>
                <button disabled={busy} onClick={() => okay([g])}>
                  {partial(g)
                    ? "Merge ticked, mark the rest as okay"
                    : "Mark as okay"}
                </button>
              </div>
            )}
          </>
        );
        if (g.merged) {
          const kept = byId.get(
            g.tracks.find((id) => !g.awaiting_removal.includes(id)) ??
              g.tracks[0],
          )!;
          // Nothing left to decide here, so a merged group is one line until opened.
          return (
            <details
              className="duplicate-group duplicate-merged"
              key={keyOf(g)}
            >
              <summary>
                <strong>{kept.metadata.title || "Untitled"}</strong>
                <span>{kept.metadata.artist || "Unknown artist"}</span>
                <span className="badge warn">
                  {plural(g.awaiting_removal.length, "entry")} to remove in
                  rekordbox
                </span>
              </summary>
              {entries}
            </details>
          );
        }
        return (
          <section className="duplicate-group" key={keyOf(g)}>
            <header>
              <h2>
                <input
                  type="checkbox"
                  aria-label={`Select group ${index + 1}`}
                  checked={picked.has(keyOf(g))}
                  onChange={(e) => pick([keyOf(g)], e.target.checked)}
                />{" "}
                Group {String(index + 1).padStart(2, "0")}
              </h2>
              <span
                className={`badge ${g.warnings.length ? "warn" : "neutral"}`}
              >
                {kinds[g.kind]}
              </span>
            </header>
            {entries}
          </section>
        );
      })}
      {visible.length > limit && (
        <button onClick={() => setLimit(limit + 40)}>
          Show more ({visible.length - limit} left)
        </button>
      )}
      {pending &&
        (() => {
          const { merges, okay: untouched } = pending,
            totals = summary(merges),
            entries = merges.reduce((n, m) => n + m.remove.length, 0),
            okayed = merges.filter((m) => m.okay).length + untouched.length;
          return (
            <Dialog title="Merge duplicates?" onClose={() => setPending(null)}>
              <p>
                {plural(entries, "entry")} in {plural(merges.length, "group")}{" "}
                will be merged into the entries you keep:{" "}
                {plural(totals.playlists, "playlist place")} and{" "}
                {plural(totals.tags, "My Tag")} move, and the merged entries are
                listed in <em>Song Dex / Duplicates to remove</em>.
              </p>
              {okayed > 0 && (
                <p>
                  Entries that are not ticked stay untouched, and{" "}
                  {plural(okayed, "group")} will be marked as okay.
                </p>
              )}
              {totals.cues > 0 && (
                <p className="difference">
                  △ {plural(totals.cues, "merged entry")} with cues: those cues
                  are not moved.
                </p>
              )}
              <p>
                rekordbox's database is backed up first and the merge can be
                restored from History. Quit rekordbox and its background agent
                before continuing.
              </p>
              <div className="button-row">
                <button autoFocus onClick={() => setPending(null)}>
                  Cancel
                </button>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={async () => {
                    setPending(null);
                    // A stale group stops here, before anything is written.
                    if (untouched.length && !(await dismiss(untouched))) return;
                    await action(
                      "duplicates/merge",
                      { merges },
                      "Merged. In rekordbox, open Song Dex / Duplicates to remove, remove those entries from the collection, then rescan.",
                    );
                    setChoices({});
                    setPicked(new Set());
                  }}
                >
                  Merge
                </button>
              </div>
            </Dialog>
          );
        })()}
    </div>
  );
}
