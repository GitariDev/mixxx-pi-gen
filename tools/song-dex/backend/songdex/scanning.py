"""Metadata scans: every lookup for a chosen set of tracks, side by side.

A scan lists its tracks first, then three workers run at once, each over the
whole list and each recording its own state per track, so the review fills in
as they go: catalog matching (AcoustID and MusicBrainz), a genre (Discogs, else
the main artist's), and My Tag and playlist suggestions. For one track the genre
waits for its catalog match and the suggestions wait for its genre, as each uses
what the one before found; across tracks they overlap.

Approvals made during a scan are queued: the scan holds the one write lock, so
it saves them between lookups.
"""

from __future__ import annotations

import json
import threading

from .db import cosmetic
from .duplicates import Duplicates
from .editing import Editing
from .operations import Operations
from .tagging import Library, Tagging, suggestions

SOURCES = ("catalog", "genre", "tags")
FINISHED = {"done", "failed", "skipped"}


def blank(value, field=""):
    text = cosmetic(str(value or ""))
    return text in ("", "unknown genre", "other") if field == "genre" else not text


# A scan by type: which tracks it looks at.
KINDS = {
    "genre": ("Genre sync", lambda t, m: blank(m.get("genre"), "genre")),
    "year": ("Missing year", lambda t, m: blank(m.get("year"))),
    "album": ("Missing album", lambda t, m: blank(m.get("album"))),
    "artist": ("No artist tag", lambda t, m: blank(m.get("artist"))),
    "untagged": (
        "Without My Tags",
        lambda t, m: t["my_tags_loaded"] and not t["my_tags"],
    ),
    "failed": ("Lookups that failed", lambda t, m: bool(t["error"])),
}

# Requests to stop a running scan, by job ID.
stopping = {}


def scope(tracks, name, kind=None, ids=None):
    """The tracks a scan covers, in Dex order, and what to call it."""
    usable = [t for t in tracks if t["source"] != "demo" and t["state"] != "removed"]
    if name == "new":
        chosen, label = (
            [t for t in usable if not t["evidence"] or t["error"]],
            "New tracks",
        )
    elif name == "all":
        chosen, label = usable, "Full library"
    elif name == "type" and kind in KINDS:
        label, test = KINDS[kind]
        chosen = [t for t in usable if test(t, {**t["metadata"], **t["accepted"]})]
    elif name == "custom" and ids:
        wanted = set(ids)
        chosen, label = [t for t in usable if t["id"] in wanted], "Custom filter"
    else:
        raise ValueError("Choose what to scan")
    if not chosen:
        raise ValueError("No tracks match this scan")
    return [t["id"] for t in chosen], label


class Scanning:
    def __init__(self, service):
        self.service, self.store = service, service.store
        self.providers = service.providers
        self.changed = threading.Condition()

    # -- Running -------------------------------------------------------------------

    def run(self, job_id, payload):
        """Returns the job's closing state and message."""
        self.job_id, self.ids = job_id, payload["ids"]
        with self.store.connect() as db:
            db.executemany(
                "INSERT OR IGNORE INTO scan_items(job_id,track_id,position) VALUES (?,?,?)",
                [(job_id, tid, i) for i, tid in enumerate(self.ids)],
            )
            # Work cut short by a restart starts again.
            for source in SOURCES:
                db.execute(
                    f"UPDATE scan_items SET {source}='queued' WHERE job_id=? AND {source}='running'",
                    (job_id,),
                )
            self.states = {
                r["track_id"]: {s: r[s] for s in SOURCES}
                for r in db.execute(
                    "SELECT * FROM scan_items WHERE job_id=?", (job_id,)
                )
            }
        self.service.progress(job_id, total=len(self.ids))
        stop = stopping.setdefault(job_id, threading.Event())
        workers = [
            threading.Thread(target=self.work, args=(source, step), daemon=True)
            for source, step in (
                ("catalog", self.catalog),
                ("genre", self.genre),
                ("tags", self.tags),
            )
        ]
        for w in workers:
            w.start()
        editing = Editing(self.service)
        try:
            while any(w.is_alive() for w in workers):
                self.save_queued(editing)
                self.report()
                with self.changed:
                    self.changed.wait(0.5)
            self.save_queued(editing)
            self.report()
        finally:
            stopping.pop(job_id, None)
        failed = sum(
            1 for s in self.states.values() if "failed" in (s["catalog"], s["genre"])
        )
        if stop.is_set():
            return "interrupted", "Stopped; resume it from History"
        if failed:
            return (
                "partial",
                f"Finished with {failed} lookup failures; existing metadata preserved",
            )
        return "complete", f"Scanned {len(self.ids)} tracks"

    def save_queued(self, editing):
        try:
            editing.drain()
        except Exception as exc:
            # Approvals stay queued and are tried again.
            self.store.log("review", f"Queued approvals are waiting: {exc}")

    def report(self):
        done = sum(all(s[k] in FINISHED for k in SOURCES) for s in self.states.values())
        self.service.progress(
            self.job_id,
            progress=done,
            message=f"Scanned {done} of {len(self.ids)} tracks",
        )

    def mark(self, tid, source, state):
        with self.store.connect() as db:
            db.execute(
                f"UPDATE scan_items SET {source}=? WHERE job_id=? AND track_id=?",
                (state, self.job_id, tid),
            )
        with self.changed:
            self.states[tid][source] = state
            self.changed.notify_all()

    def wait_for(self, tid, source):
        """Until another worker has finished this track (or the scan stops)."""
        stop = stopping.get(self.job_id)
        with self.changed:
            while self.states[tid][source] not in FINISHED and not (
                stop and stop.is_set()
            ):
                self.changed.wait(0.5)

    def work(self, source, step):
        stop = stopping[self.job_id]
        for tid in self.ids:
            if stop.is_set():
                return
            if self.states[tid][source] in FINISHED:
                continue
            self.mark(tid, source, "running")
            try:
                state = step(tid)
            except Exception:
                state = "failed"
            # Stopped while waiting on another worker: this track is left to resume.
            self.mark(tid, source, "queued" if state is None else state)

    # -- The three lookups -----------------------------------------------------------

    def track(self, tid):
        track = self.store.track(tid)
        if track["state"] == "removed":
            return None
        return {**track, "metadata": {**track["metadata"], **track["accepted"]}}

    def catalog(self, tid):
        if not self.track(tid):
            return "skipped"
        return "failed" if self.service.enrich_track(tid, genre=False) else "done"

    def genre(self, tid):
        self.wait_for(tid, "catalog")
        if stopping[self.job_id].is_set():
            return None
        track = self.track(tid)
        if not track:
            return "skipped"
        track = self.providers.named(track)
        if not self.providers.needs_genre(track):
            return "skipped"
        self.providers.find_genre(track)
        return "done"

    def tags(self, tid):
        self.wait_for(tid, "genre")
        if stopping[self.job_id].is_set():
            return None
        track = self.track(tid)
        if not track:
            return "skipped"
        context = self.context()
        if not context["choices"]["tags"] and not context["choices"]["playlists"]:
            return "skipped"
        with self.store.connect() as db:
            genres = [
                r[0]
                for r in db.execute(
                    "SELECT new_value FROM proposals WHERE track_id=? AND field='genre' AND status='pending'",
                    (tid,),
                )
            ]
        found = suggestions(
            track,
            context["tracks"],
            context["choices"],
            [context["by_id"][i] for i in context["twins"].get(tid, ())],
            genres,
            context["pending"],
            context["library"],
        )
        Tagging(self.service).keep_suggestions(tid, found)
        return "done"

    def context(self):
        """What suggestions are made from, gathered once per scan."""
        if getattr(self, "_context", None) is None:
            tracks = self.store.tracks()
            twins = {}
            for group in Duplicates(Operations(self.service)).groups(tracks):
                if not group["merged"]:
                    for i in group["tracks"]:
                        twins.setdefault(i, set()).update(set(group["tracks"]) - {i})
            pending = {}
            tagging = Tagging(self.service)
            for a in tagging.assignments("pending"):
                pending.setdefault(a["track_id"], {}).setdefault(a["kind"], set()).add(
                    a["target"]
                )
            self._context = {
                "tracks": tracks,
                "by_id": {t["id"]: t for t in tracks},
                "library": Library(tracks),
                "choices": tagging.choices(),
                "twins": {k: sorted(v) for k, v in twins.items()},
                "pending": pending,
            }
        return self._context

    # -- Reading -------------------------------------------------------------------

    def latest(self):
        """The most recent scan and the state of each of its tracks."""
        with self.store.connect() as db:
            job = db.execute(
                "SELECT id,state,payload,progress,total,message,created_at FROM jobs "
                "WHERE kind='enrich' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if not job:
                return None
            items = [
                [r["track_id"], r["catalog"], r["genre"], r["tags"]]
                for r in db.execute(
                    "SELECT * FROM scan_items WHERE job_id=? ORDER BY position",
                    (job["id"],),
                )
            ]
        payload = json.loads(job["payload"])
        return {
            "job_id": job["id"],
            "state": job["state"],
            "label": payload.get("label", "Metadata lookup"),
            "created_at": job["created_at"],
            "items": items,
        }


def stop(store):
    with store.connect() as db:
        job = db.execute(
            "SELECT id FROM jobs WHERE kind='enrich' AND state='running'"
        ).fetchone()
    if not job or job["id"] not in stopping:
        raise ValueError("No scan is running")
    stopping[job["id"]].set()
    return {"message": "Stopping the scan after the current lookups"}
