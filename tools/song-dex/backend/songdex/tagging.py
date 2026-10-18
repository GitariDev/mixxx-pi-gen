"""Quick tagging: give imported tracks My Tags and playlist places, one by one.

An import's tracks first go through the scan checks (metadata and genre lookup;
duplicates come from the catalog). Then a session steps through them so the user
can listen and pick My Tags and normal playlists for each, with suggestions from
the track's artist, genre, year and possible duplicates.

Choices are kept in the Dex as pending assignments. Those for tracks rekordbox
lists are written in one journaled change. A new file has no rekordbox entry
until rekordbox imports it, so its choices wait for the scan that finds it.
Song Dex only adds: assignments made in rekordbox are removed there.
"""

from __future__ import annotations

import json
from collections import Counter

from . import audio, rekordbox
from .db import cosmetic, dump, now
from .duplicates import FOLDER, Duplicates
from .operations import Operations
from .providers import loose, main_artist

# Assignment kind → its key in a rekordbox.assign plan.
KINDS = {"tag": "tags", "playlist": "playlists"}


def merged(track):
    return {**track["metadata"], **track["accepted"]}


def held(track, pending=None):
    """What rekordbox has for the track as of the last scan, plus choices not yet written."""
    extra = (pending or {}).get(track["id"], {})
    return {
        "tag": {str(t["id"]) for t in track["my_tags"]} | extra.get("tag", set()),
        "playlist": {
            str(p["id"]) for p in track["playlists"] if p.get("id") is not None
        }
        | extra.get("playlist", set()),
    }


def names_genre(tag, genre):
    """True when a tag's name is a word of the genre: Afro → Afro House, Dub → Raggae/Dub."""
    words = cosmetic(genre).split()
    for part in {tag, *tag.split("/")}:
        part = cosmetic(part)
        if not part:
            continue
        if f" {part} " in f" {' '.join(words)} ":
            return True
        # Afro → Afrobeats; short names (Alt, Dub) only match whole words.
        if (
            " " not in part
            and len(part) >= 4
            and any(w.startswith(part) for w in words)
        ):
            return True
    return False


class Library:
    """The collection grouped by main artist and by genre, for suggesting many tracks."""

    def __init__(self, tracks):
        self.artists, self.genres = {}, {}
        for t in tracks:
            if t["state"] == "removed":
                continue
            m = merged(t)
            self.artists.setdefault(loose(main_artist(m.get("artist", ""))), []).append(
                t
            )
            self.genres.setdefault(cosmetic(m.get("genre", "")), []).append(t)

    def by_artist(self, artist):
        return self.artists.get(loose(artist), [])

    def by_genre(self, genre):
        return self.genres.get(cosmetic(genre), [])


def suggestions(
    track, tracks, choices, twins=(), genres=(), pending=None, library=None
):
    """My Tags and playlists the track probably belongs in, with the reasons why.

    `twins` are entries it may duplicate, `genres` adds suggested genre values to
    the track's own, and `pending` holds choices made but not yet written. A
    prebuilt `library` (a Library of `tracks`) saves regrouping for every track.
    """
    library = library or Library(tracks)
    found = {}

    def add(kind, target, reason):
        reasons = found.setdefault((kind, str(target)), [])
        if reason not in reasons:
            reasons.append(reason)

    def crowd(group, describe):
        """Assignments shared by enough of `group` to be a habit, not a one-off."""
        counts = Counter()
        for other in group:
            for kind, targets in held(other, pending).items():
                counts.update((kind, t) for t in targets)
        for (kind, target), n in counts.items():
            if n / len(group) >= 0.25 and (n >= 2 or len(group) <= 2):
                add(kind, target, describe(n))

    m = merged(track)
    for twin in twins:
        for kind, targets in held(twin, pending).items():
            for target in targets:
                add(kind, target, f"On NO. {twin['id']:04d}, a possible duplicate")
    artist = main_artist(m.get("artist", ""))
    if loose(artist):
        same = [o for o in library.by_artist(artist) if o["id"] != track["id"]]
        if same:
            crowd(same, lambda n: f"{n} of your {len(same)} other tracks by {artist}")
    names = [g for g in dict.fromkeys([m.get("genre", ""), *genres]) if cosmetic(g)]
    for genre in names:
        for tag in choices["tags"]:
            if names_genre(tag["name"], genre):
                add("tag", tag["id"], f"Genre {genre}")
        same = [o for o in library.by_genre(genre) if o["id"] != track["id"]]
        if same:
            crowd(same, lambda n, g=genre, s=same: f"{n} of your {len(s)} {g} tracks")
    year = str(m.get("year", ""))[:4]
    if year.isdigit():
        decades = {f"{int(year) // 10 * 10}s", f"{int(year) % 100 // 10}0s"}
        for tag in choices["tags"]:
            if cosmetic(tag["name"]) in decades:
                add("tag", tag["id"], f"Released in {year}")
    have = held(track, pending)
    known = {
        "tag": {t["id"] for t in choices["tags"]},
        "playlist": {p["id"] for p in choices["playlists"]},
    }
    return sorted(
        (
            {"kind": kind, "id": target, "reasons": reasons}
            for (kind, target), reasons in found.items()
            if target in known[kind] and target not in have[kind]
        ),
        key=lambda s: (-len(s["reasons"]), s["kind"] != "tag"),
    )


class Tagging:
    def __init__(self, service):
        self.service, self.store = service, service.store

    # -- Session -------------------------------------------------------------------

    def imported(self, iid):
        """Dex tracks for an import's finished files, in the order they were imported."""
        with self.store.connect() as db:
            row = db.execute("SELECT plan FROM imports WHERE id=?", (iid,)).fetchone()
        if not row:
            raise ValueError("Import not found")
        tracks = [t for t in self.store.tracks() if t["state"] != "removed"]
        ids = []
        for entry in json.loads(row["plan"])["entries"]:
            if entry["status"] != "complete":
                continue
            paths = {entry["destination"], entry.get("repoint")}
            # A file rekordbox listed has its rekordbox entry; prefer that to a local one.
            found = sorted(
                (t for t in tracks if t["path"] in paths),
                key=lambda t: t["source"] == "local",
            )
            if found and found[0]["id"] not in ids:
                ids.append(found[0]["id"])
        return ids

    def open(self, iid):
        """Start (or bring up to date) the session for an import; it shares the import's ID."""
        ids = self.imported(iid)
        with self.store.connect() as db:
            db.execute(
                """INSERT INTO tag_sessions(id,tracks,state,created_at) VALUES (?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET tracks=excluded.tracks""",
                (iid, dump(ids), "checking", now()),
            )
        return ids

    def row(self, sid):
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM tag_sessions WHERE id=?", (sid,)).fetchone()
        if not row:
            raise ValueError("Tagging session not found")
        return {
            **dict(row),
            "tracks": json.loads(row["tracks"]),
            "checked": json.loads(row["checked"]),
        }

    def prepare(self, job_id, iid):
        """The import job's last step: run the checks, then hand over to tagging."""
        ids = self.open(iid)
        if not ids:
            return None
        failed = self.check(job_id, iid)
        return (
            f"Checked {len(ids)} imported tracks"
            + (
                f" ({failed} lookups failed; retry from Scan & Review)"
                if failed
                else ""
            )
            + ". Ready to tag."
        )

    def check(self, job_id, sid):
        """Metadata and genre lookup for each track; resumes where it stopped."""
        session = self.row(sid)
        ids, checked = session["tracks"], session["checked"]
        self.service.progress(job_id, total=len(ids), progress=0)
        failed = 0
        for index, tid in enumerate(ids):
            if tid not in checked:
                track = self.store.track(tid)
                # Tracks rekordbox listed may have been looked up before.
                if not track["evidence"] or track["error"]:
                    failed += self.service.enrich_track(tid)
                checked.append(tid)
                with self.store.connect() as db:
                    db.execute(
                        "UPDATE tag_sessions SET checked=? WHERE id=?",
                        (dump(checked), sid),
                    )
            self.service.progress(
                job_id,
                progress=index + 1,
                message=f"Checking metadata and genres: {index + 1} of {len(ids)} tracks",
            )
        with self.store.connect() as db:
            db.execute(
                "UPDATE tag_sessions SET state='ready' WHERE id=? AND state='checking'",
                (sid,),
            )
        return failed

    def choices(self):
        """My Tags and playlists from the last scan, read from its snapshot if need be."""
        saved = self.store.setting("library_choices")
        if saved is not None:
            return {**saved, "loaded": True}
        with self.store.connect() as db:
            job = db.execute(
                "SELECT id FROM jobs WHERE kind='scan' AND state='complete' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        copy = job and self.store.root / "snapshots" / job["id"] / "master.db"
        if (
            copy
            and copy.exists()
            and audio.digest(copy) == self.store.setting("library_hash")
        ):
            try:
                saved = rekordbox.read_choices(copy, FOLDER)
                self.store.set_setting("library_choices", saved)
                return {**saved, "loaded": True}
            except Exception:
                pass
        return {"tags": [], "playlists": [], "loaded": False}

    def assignments(self, status=None):
        with self.store.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM assignments"
                    + (" WHERE status=?" if status else "")
                    + " ORDER BY created_at",
                    (status,) if status else (),
                )
            ]

    # -- Suggestions from scans ---------------------------------------------------

    def keep_suggestions(self, tid, found):
        """Record a scan's suggestions for a track; ones the user turned down stay down."""
        with self.store.connect() as db:
            targets = {(s["kind"], str(s["id"])) for s in found}
            for row in db.execute(
                "SELECT kind,target FROM assignments WHERE track_id=? AND status='suggested'",
                (tid,),
            ).fetchall():
                if (row["kind"], row["target"]) not in targets:
                    db.execute(
                        "DELETE FROM assignments WHERE track_id=? AND kind=? AND target=? AND status='suggested'",
                        (tid, row["kind"], row["target"]),
                    )
            for s in found:
                db.execute(
                    """INSERT INTO assignments(track_id,kind,target,status,created_at,reasons)
                    VALUES (?,?,?,'suggested',?,?) ON CONFLICT(track_id,kind,target)
                    DO UPDATE SET reasons=excluded.reasons WHERE assignments.status='suggested'""",
                    (tid, s["kind"], str(s["id"]), now(), dump(s["reasons"])),
                )

    def suggested(self):
        """Suggestions waiting for a decision, for tracks still in the collection."""
        with self.store.connect() as db:
            rows = db.execute(
                """SELECT a.track_id,a.kind,a.target,a.reasons FROM assignments a
                JOIN tracks t ON t.id=a.track_id
                WHERE a.status='suggested' AND t.state!='removed' ORDER BY a.track_id""",
            ).fetchall()
        return [{**dict(r), "reasons": json.loads(r["reasons"])} for r in rows]

    def decide(self, items, approve):
        """Approve (it waits to be written like any choice) or turn down suggestions."""
        known = self.choices()
        targets = {
            "tag": {t["id"] for t in known["tags"]},
            "playlist": {p["id"] for p in known["playlists"]},
        }
        changed = 0
        with self.store.connect() as db:
            for item in items:
                kind, target = item["kind"], str(item["target"])
                if approve and target not in targets.get(kind, ()):
                    raise ValueError(
                        "A My Tag or playlist is no longer in rekordbox. Rescan the library and scan again"
                    )
                changed += db.execute(
                    "UPDATE assignments SET status=? WHERE track_id=? AND kind=? AND target=? AND status='suggested'",
                    (
                        "pending" if approve else "rejected",
                        item["track_id"],
                        kind,
                        target,
                    ),
                ).rowcount
        return changed

    def session(self, sid):
        session = self.row(sid)
        tracks = self.store.tracks()
        by_id = {t["id"]: t for t in tracks}
        ids = [
            i
            for i in session["tracks"]
            if i in by_id and by_id[i]["state"] != "removed"
        ]
        choices = self.choices()
        source = self.store.setting("last_scan_source")
        twins = {}
        for group in Duplicates(Operations(self.service)).groups(tracks):
            if group["merged"]:
                continue
            for i in set(group["tracks"]) & set(ids):
                twins.setdefault(i, set()).update(set(group["tracks"]) - {i})
        genres = {}
        for p in self.store.proposals():
            if p["field"] == "genre" and p["track_id"] in ids:
                genres.setdefault(p["track_id"], []).append(p["new_value"])
        chosen, pending = {}, {}
        for a in self.assignments():
            if a["status"] == "pending":
                pending.setdefault(a["track_id"], {}).setdefault(a["kind"], set()).add(
                    a["target"]
                )
            if a["track_id"] in ids and a["status"] in ("pending", "saved"):
                chosen.setdefault(a["track_id"], {"pending": {}, "saved": {}})[
                    "pending" if a["status"] == "pending" else "saved"
                ].setdefault(KINDS[a["kind"]], []).append(a["target"])
        items = []
        for i in ids:
            t = by_id[i]
            mine = chosen.get(i, {"pending": {}, "saved": {}})
            items.append(
                {
                    "id": i,
                    "in_rekordbox": t["source"] == source,
                    "checked": i in session["checked"],
                    "pending": {k: mine["pending"].get(k, []) for k in KINDS.values()},
                    "saved": {k: mine["saved"].get(k, []) for k in KINDS.values()},
                    "duplicates": sorted(twins.get(i, ())),
                    "suggestions": suggestions(
                        t,
                        tracks,
                        choices,
                        [by_id[d] for d in sorted(twins.get(i, ()))],
                        genres.get(i, ()),
                        # The track's own choices show as chosen, not as suggestions.
                        {k: v for k, v in pending.items() if k != i},
                    ),
                }
            )
        return {
            "id": sid,
            "state": session["state"],
            "position": min(session["position"], max(len(ids) - 1, 0)),
            "choices": choices,
            "tracks": items,
        }

    def choose(self, sid, tid, tags, playlists, position):
        """Keep the track's chosen tags and playlists; ones it already has are dropped."""
        session = self.row(sid)
        if tid not in session["tracks"]:
            raise ValueError("That track is not part of this tagging session")
        choices = self.choices()
        wanted = {"tag": set(map(str, tags)), "playlist": set(map(str, playlists))}
        known = {
            "tag": {t["id"] for t in choices["tags"]},
            "playlist": {p["id"] for p in choices["playlists"]},
        }
        if any(wanted[k] - known[k] for k in wanted):
            raise ValueError(
                "A My Tag or playlist is no longer in rekordbox. Rescan the library and choose again"
            )
        have = held(self.store.track(tid))
        with self.store.connect() as db:
            for kind in KINDS:
                targets = sorted(wanted[kind] - have[kind])
                db.execute(
                    "DELETE FROM assignments WHERE track_id=? AND kind=? AND status='pending' "
                    f"AND target NOT IN ({','.join('?' * len(targets))})",
                    (tid, kind, *targets),
                )
                for target in targets:
                    db.execute(
                        """INSERT INTO assignments(track_id,kind,target,status,created_at)
                        VALUES (?,?,?,'pending',?) ON CONFLICT(track_id,kind,target)
                        DO UPDATE SET status='pending' WHERE assignments.status!='pending'""",
                        (tid, kind, target, now()),
                    )
            db.execute(
                "UPDATE tag_sessions SET position=? WHERE id=?",
                (max(0, min(int(position), len(session["tracks"]) - 1)), sid),
            )
        return {"saved": True}

    def finish(self, sid):
        self.row(sid)
        with self.store.connect() as db:
            db.execute("UPDATE tag_sessions SET state='done' WHERE id=?", (sid,))
        return {"done": True}

    def summaries(self):
        """Sessions still open, for picking up where the user left off."""
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT * FROM tag_sessions WHERE state!='done' ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "id": r["id"],
                "state": r["state"],
                "position": r["position"],
                "total": len(json.loads(r["tracks"])),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # -- Writing to rekordbox --------------------------------------------------------

    def waiting(self):
        """Pending assignments whose track rekordbox lists, with its content ID."""
        with self.store.connect() as db:
            rows = db.execute(
                """SELECT a.track_id,a.kind,a.target,t.source_id FROM assignments a
                JOIN tracks t ON t.id=a.track_id
                WHERE a.status='pending' AND t.source=? AND t.state!='removed'""",
                (self.store.setting("last_scan_source"),),
            ).fetchall()
        return [dict(r) for r in rows]

    def write(self):
        if not self.service.lock.acquire(False):
            raise ValueError("Another operation is running")
        try:
            result = self._write()
        finally:
            self.service.lock.release()
        if result is None:
            raise ValueError(
                "Nothing to write yet: the chosen tracks are not in rekordbox. "
                "Import the playlist in rekordbox, quit it and rescan"
            )
        return result

    def _write(self):
        """Write every pending assignment rekordbox can take; the caller holds the lock."""
        rows = self.waiting()
        if not rows:
            return None
        plan = {}
        for r in rows:
            plan.setdefault(r["source_id"], {"tags": [], "playlists": []})[
                KINDS[r["kind"]]
            ].append(r["target"])
        tags = sum(r["kind"] == "tag" for r in rows)
        detail = (
            f"Added {tags} My Tags and {len(rows) - tags} playlist places "
            f"to {len(plan)} tracks"
        )
        result = Operations(self.service).change_library(
            "tags and playlists",
            detail,
            list(plan),
            lambda staged: rekordbox.assign(staged, plan),
        )
        if result["manifest"]["library_status"] != "complete":
            return result
        with self.store.connect() as db:
            for r in rows:
                db.execute(
                    "UPDATE assignments SET status='saved' WHERE track_id=? AND kind=? AND target=? AND status='pending'",
                    (r["track_id"], r["kind"], r["target"]),
                )
            for tid in {r["track_id"] for r in rows}:
                db.execute(
                    "INSERT INTO history(track_id,kind,detail,created_at) VALUES (?,?,?,?)",
                    (tid, "tags and playlists", "Written to rekordbox", now()),
                )
        return {**result, "message": f"{detail} in rekordbox."}

    def after_scan(self):
        """A scan that finds newly imported tracks in rekordbox writes their choices."""
        rows = self.waiting()
        if not rows:
            return None
        tracks = len({r["track_id"] for r in rows})
        try:
            result = self._write()
        except ValueError as exc:
            # Nothing was written; the next scan tries again.
            return f"Tags and playlists for {tracks} tracks are waiting: {exc}"
        if "message" not in result:
            raise ValueError(
                f"Tags and playlists for {tracks} tracks were not written: "
                f"{result['manifest'].get('error')}. Restore the operation in History."
            )
        return result["message"]
