from __future__ import annotations

import json
import threading
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from . import audio, rekordbox
from .backups import Backups
from .db import dump, now
from .providers import Providers, normalized, version_signature


class Service:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self.providers = Providers(store)
        self.unrecorded = None

    def start(self, kind, payload=None, job_id=None):
        if not self.lock.acquire(blocking=False):
            raise ValueError("Another operation is already running")
        job_id = job_id or str(uuid4())
        try:
            with self.store.connect() as db:
                if payload is not None:
                    db.execute(
                        "INSERT INTO jobs(id,kind,state,payload,created_at) VALUES (?,?,?,?,?)",
                        (job_id, kind, "running", dump(payload), now()),
                    )
                else:
                    db.execute("UPDATE jobs SET state='running' WHERE id=?", (job_id,))
            threading.Thread(target=self.run, args=(job_id,), daemon=True).start()
        except BaseException:
            self.lock.release()
            raise
        return job_id

    def progress(self, job_id, **fields):
        with self.store.connect() as db:
            db.execute(
                "UPDATE jobs SET " + ",".join(k + "=?" for k in fields) + " WHERE id=?",
                [*fields.values(), job_id],
            )

    def run(self, job_id):
        try:
            with self.store.connect() as db:
                job = dict(
                    db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
                )
            payload = json.loads(job["payload"])
            note = None
            if job["kind"] == "scan":
                note = self.scan(job_id, payload)
            elif job["kind"] == "import_music":
                from .importing import Importing
                from .tagging import Tagging

                note = Importing(self).run(job_id, payload)
                # Then the scan checks, so the tracks are ready to tag.
                checked = Tagging(self).prepare(job_id, payload["import_id"])
                note = " ".join(filter(None, [note, checked])) or None
            elif job["kind"] == "tag_check":
                from .tagging import Tagging

                note = Tagging(self).prepare(job_id, payload["session_id"])
            elif job["kind"] == "approve":
                from .editing import Editing

                skipped = Editing(self).approve_job(job_id, payload["ids"])
                if skipped:
                    self.progress(
                        job_id,
                        state="partial",
                        message=f"Approved; {skipped} tracks were skipped because a value was not valid",
                    )
                    return
            elif job["kind"] == "sync_edits":
                from .editing import Editing

                left = Editing(self).sync_pending(job_id)
                if left:
                    self.progress(
                        job_id,
                        state="partial",
                        message=f"{left} tracks still have an edit waiting; open one to see why",
                    )
                    return
            elif job["kind"] == "availability":
                tracks = [t for t in self.store.tracks() if t["source"] != "demo"]
                self.progress(job_id, total=len(tracks))
                for index, t in enumerate(tracks):
                    self.ingest(
                        t["source"],
                        {
                            "source_id": t["source_id"],
                            "path": t["path"],
                            "metadata": t["metadata"],
                            "playlists": t["playlists"],
                        },
                    )
                    if t["state"] == "removed":
                        with self.store.connect() as db:
                            db.execute(
                                "UPDATE tracks SET state='removed' WHERE id=?",
                                (t["id"],),
                            )
                    self.progress(
                        job_id,
                        progress=index + 1,
                        message=f"Checked {index + 1} file locations",
                    )
            elif job["kind"] == "enrich":
                from .scanning import Scanning

                if "ids" not in payload:
                    # A lookup started before scans listed their tracks up front.
                    tracks = [
                        t
                        for t in self.store.tracks()
                        if t["source"] != "demo"
                        and (payload.get("refresh") or not t["evidence"] or t["error"])
                    ]
                    payload = {"ids": [t["id"] for t in tracks], "label": "New tracks"}
                    if not tracks:
                        self.progress(
                            job_id, state="complete", message="Nothing to scan"
                        )
                        return
                    self.progress(job_id, payload=dump(payload))
                state, message = Scanning(self).run(job_id, payload)
                self.progress(job_id, state=state, message=message)
                if state == "complete":
                    self.store.log("enrich", "Operation completed")
                return
            self.progress(job_id, state="complete", message=note or "Finished")
            self.store.log(job["kind"], "Operation completed")
        except Exception as exc:
            try:
                self.progress(job_id, state="failed", message=str(exc))
            except Exception:
                # The catalog could not be written either (a full disk does this).
                self.unrecorded = (job_id, str(exc))
        finally:
            # A scan may have found rekordbox changed, which spends its backups.
            Backups(self).prune()
            self.lock.release()
            self.save_queued()

    def save_queued(self):
        """Approvals queued just as a scan finished, which it did not get to."""
        from .editing import Editing

        editing = Editing(self)
        if editing.queued() and self.lock.acquire(blocking=False):
            try:
                editing.drain()
            except Exception:
                pass
            finally:
                self.lock.release()

    def enrich_track(self, tid, genre=True):
        """Look one track up with the providers; 1 when the lookup failed, else 0."""
        track = self.store.track(tid)
        track["metadata"] = {**track["metadata"], **track["accepted"]}
        error = None
        try:
            evidence = self.providers.enrich(track, genre)
        except Exception as exc:
            error = (
                f"{type(exc).__name__}: provider lookup failed. Retry when available."
            )
            evidence = track["evidence"]
        with self.store.connect() as db:
            db.execute(
                "UPDATE tracks SET evidence=?,error=? WHERE id=?",
                (dump(evidence), error, tid),
            )
        return int(error is not None)

    def settle(self):
        """Record a job that died while the catalog was unwritable, once it is writable."""
        if self.unrecorded and self.lock.acquire(blocking=False):
            try:
                job_id, message = self.unrecorded
                self.store.recover()
                self.progress(job_id, state="failed", message=message)
                self.unrecorded = None
            finally:
                self.lock.release()

    def scan(self, job_id, payload):
        source = (
            Path(self.store.setting("rekordbox_db", str(rekordbox.DEFAULT_DB)))
            .expanduser()
            .resolve()
        )
        if rekordbox.live_check_running(self.store.root):
            raise ValueError(
                "A live rekordbox check is in progress; its test changes would be "
                "indexed. Finish or cancel it first."
            )
        destination = self.store.root / "snapshots" / job_id
        self.progress(
            job_id, message="Checking library and taking a consistent snapshot"
        )
        source_hash = rekordbox.snapshot(source, destination)
        rows = rekordbox.read_collection(destination / "master.db")
        try:
            from .duplicates import FOLDER

            # What tagging offers; a scan still counts without it.
            self.store.set_setting(
                "library_choices",
                rekordbox.read_choices(destination / "master.db", FOLDER),
            )
        except Exception:
            pass
        with self.store.connect() as db:
            existing = {
                r[0]
                for r in db.execute(
                    "SELECT source_id FROM tracks WHERE source=?", (str(source),)
                )
            }
        rows.sort(key=lambda row: row["source_id"] not in existing)
        self.progress(job_id, total=len(rows))
        seen = set()
        for index, row in enumerate(rows):
            seen.add(row["source_id"])
            self.ingest(str(source), row)
            self.progress(
                job_id,
                progress=index + 1,
                message=f"Indexed {index + 1} of {len(rows)} tracks",
            )
        # Entries absent from the collection remain in Dex history.
        with self.store.connect() as db:
            for t in db.execute(
                "SELECT id,source_id FROM tracks WHERE source=?", (str(source),)
            ).fetchall():
                if t["source_id"] not in seen:
                    db.execute(
                        "UPDATE tracks SET state='removed' WHERE id=?", (t["id"],)
                    )
        self.store.set_setting("library_hash", source_hash)
        self.store.set_setting("last_scan", now())
        self.store.set_setting("last_scan_source", str(source))
        from .relocating import Relocating
        from .tagging import Tagging

        # Files that moved into the music folder get their rekordbox path back.
        repaired = Relocating(self).repair(str(source), rows)
        # Newly imported tracks rekordbox now lists get the tags and playlists chosen for them.
        tagged = Tagging(self).after_scan()
        return " ".join(filter(None, [repaired, tagged])) or None

    def ingest(self, source, row):
        path = row["path"]
        sig = audio.signature(path)
        available = sig != "missing"
        with self.store.connect() as db:
            previous = db.execute(
                "SELECT * FROM tracks WHERE source=? AND source_id=?",
                (source, row["source_id"]),
            ).fetchone()
            if not previous and source not in ("local", "demo"):
                local = db.execute(
                    "SELECT * FROM tracks WHERE source='local' AND path=?", (path,)
                ).fetchone()
                if local:
                    db.execute(
                        "UPDATE tracks SET source=?,source_id=? WHERE id=?",
                        (source, row["source_id"], local["id"]),
                    )
                    db.execute(
                        "UPDATE manual_edits SET library_status='pending' WHERE track_id=?",
                        (local["id"],),
                    )
                    previous = db.execute(
                        "SELECT * FROM tracks WHERE id=?", (local["id"],)
                    ).fetchone()
        m = row["metadata"]
        file_metadata, file_hash, error = {}, None, None
        unchanged = previous and previous["signature"] == sig and not previous["error"]
        if unchanged or (previous and not available):
            file_metadata, file_hash = (
                json.loads(previous["file_metadata"]),
                previous["file_hash"],
            )
        elif available:
            try:
                file_metadata = audio.read(path)
                file_hash = audio.digest(path)
                m["duration"] = file_metadata["duration"]
                m["format"] = file_metadata["format"]
            except Exception as exc:
                error = f"Cannot read audio: {type(exc).__name__}"
        if file_metadata:
            m["duration"] = file_metadata.get("duration", m.get("duration", 0))
            m["format"] = file_metadata.get("format", m.get("format", ""))
        state = "indexed" if available else "unavailable"
        accepted = json.loads(previous["accepted"]) if previous else {}
        with self.store.connect() as db:
            manual = {
                e["field"]: dict(e)
                for e in db.execute(
                    "SELECT * FROM manual_edits WHERE track_id=?",
                    (previous["id"] if previous else -1,),
                )
            }

        def differs(k, v):
            if k in manual:
                baseline = json.loads(manual[k]["baseline"])
                return (
                    source != "local"
                    and str(m.get(k, "")) not in (str(v), baseline["library"])
                ) or (
                    available
                    and str(file_metadata.get(k, "")) not in (str(v), baseline["file"])
                )
            return str(m.get(k, "")) != str(v) or (
                available and str(file_metadata.get(k, "")) != str(v)
            )

        if accepted and any(differs(k, v) for k, v in accepted.items()):
            state = "conflict"
        with self.store.connect() as db:
            rid, release = self.store.entities(
                db, source, row["source_id"], {**m, **accepted}
            )
            for k, e in manual.items():
                file_status = (
                    "saved"
                    if available and str(file_metadata.get(k, "")) == e["value"]
                    else "pending"
                )
                library_status = (
                    "not_in_rekordbox"
                    if source == "local"
                    else "saved"
                    if str(m.get(k, "")) == e["value"]
                    else "pending"
                )
                db.execute(
                    "UPDATE manual_edits SET file_status=?,library_status=? WHERE track_id=? AND field=?",
                    (file_status, library_status, previous["id"], k),
                )
            db.execute(
                """INSERT INTO tracks(source,source_id,recording_id,release_id,path,available,signature,file_hash,metadata,file_metadata,playlists,state,error,scanned_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source,source_id) DO UPDATE SET
                recording_id=excluded.recording_id,release_id=excluded.release_id,path=excluded.path,available=excluded.available,
                signature=excluded.signature,file_hash=excluded.file_hash,metadata=excluded.metadata,file_metadata=excluded.file_metadata,
                playlists=excluded.playlists,state=excluded.state,error=excluded.error,scanned_at=excluded.scanned_at""",
                (
                    source,
                    row["source_id"],
                    rid,
                    release,
                    path,
                    int(available),
                    sig,
                    file_hash,
                    dump(m),
                    dump(file_metadata),
                    dump(row["playlists"]),
                    state,
                    error,
                    now(),
                ),
            )
            if previous and (
                (available and file_hash != previous["file_hash"])
                or json.loads(previous["metadata"]) != m
            ):
                db.execute(
                    "UPDATE proposals SET status='stale' WHERE track_id=? AND status='pending'",
                    (previous["id"],),
                )
                db.execute(
                    "UPDATE tracks SET evidence='[]' WHERE id=?", (previous["id"],)
                )
            elif previous:
                # A move/reconnect with unchanged contents must preserve reviewed work.
                db.execute(
                    "UPDATE proposals SET signature=? WHERE track_id=? AND status='pending'",
                    (sig, previous["id"]),
                )

            if "stats" in row:
                db.execute(
                    "UPDATE tracks SET stats=? WHERE source=? AND source_id=?",
                    (dump(row["stats"]), source, row["source_id"]),
                )
            if "my_tags" in row:
                db.execute(
                    "UPDATE tracks SET my_tags=?,my_tags_loaded=1 WHERE source=? AND source_id=?",
                    (dump(row["my_tags"]), source, row["source_id"]),
                )

    def load_my_tags(self):
        """Backfill the new field from the last completed, immutable scan copy."""
        if not self.lock.acquire(False):
            raise ValueError("Another operation is running")
        try:
            with self.store.connect() as db:
                job = db.execute(
                    "SELECT id FROM jobs WHERE kind='scan' AND state='complete' ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
            if not job:
                raise ValueError("Scan your rekordbox library first")
            copy = self.store.root / "snapshots" / job["id"] / "master.db"
            source = str(
                Path(self.store.setting("rekordbox_db", str(rekordbox.DEFAULT_DB)))
                .expanduser()
                .resolve()
            )
            if not copy.exists() or audio.digest(copy) != self.store.setting(
                "library_hash"
            ):
                raise ValueError(
                    "No matching scan snapshot remains. Rescan rekordbox before loading My Tags"
                )
            scan_source = self.store.setting("last_scan_source")
            with self.store.connect() as db:
                sources = {
                    r[0]
                    for r in db.execute(
                        "SELECT DISTINCT source FROM tracks WHERE source NOT IN ('local','demo')"
                    )
                }
            if (scan_source and scan_source != source) or (
                not scan_source and sources != {source}
            ):
                raise ValueError(
                    "The saved scan belongs to a different library. Rescan the selected library first"
                )
            membership = rekordbox.read_my_tags(copy)
            with self.store.connect() as db:
                for t in db.execute(
                    "SELECT id,source_id FROM tracks WHERE source=?", (source,)
                ).fetchall():
                    db.execute(
                        "UPDATE tracks SET my_tags=?,my_tags_loaded=1 WHERE id=?",
                        (dump(membership.get(t["source_id"], [])), t["id"]),
                    )
            self.store.log(
                "my_tags", "Loaded native My Tags from the last completed library scan"
            )
            return {
                "message": "My Tags loaded from the last scan. Rescan rekordbox to pick up newer tag changes."
            }
        finally:
            self.lock.release()

    def duplicates(self, tracks=None):
        tracks = [t for t in tracks or self.store.tracks() if t["state"] != "removed"]
        groups = []
        exact = defaultdict(list)
        probable = defaultdict(list)
        for t in tracks:
            if t["file_hash"]:
                exact[t["file_hash"]].append(t)
            m = {**t["metadata"], **t["accepted"]}
            title = normalized(m.get("title", ""))
            # Group candidates conservatively; full differences stay visible to user.
            import re

            base = normalized(re.sub(r"\([^)]*\)|\[[^]]*\]", "", m.get("title", "")))
            if title and m.get("artist"):
                probable[(normalized(m["artist"]), base)].append(t)
        exact_sets = set()
        for group in exact.values():
            if len(group) > 1:
                groups.append(
                    {
                        "kind": "exact",
                        "tracks": [t["id"] for t in group],
                        "warnings": [],
                        "note": "",
                    }
                )
                exact_sets.add(frozenset(t["id"] for t in group))
        for group in probable.values():
            if len(group) < 2 or frozenset(t["id"] for t in group) in exact_sets:
                continue
            versions = {
                version_signature(
                    {**t["metadata"], **t["accepted"]}.get("title", ""),
                    {**t["metadata"], **t["accepted"]}.get("version", ""),
                )
                for t in group
            }
            duration = [float(t["metadata"].get("duration") or 0) for t in group]
            bpms = [
                float(t["metadata"].get("bpm") or 0)
                for t in group
                if t["metadata"].get("bpm")
            ]
            titles = {
                normalized({**t["metadata"], **t["accepted"]}.get("title", ""))
                for t in group
            }
            warnings = []
            if len(titles) > 1 and len(versions) == 1:
                warnings.append("Titles differ beyond punctuation")
            if max(duration) - min(duration) > max(2, max(duration) * 0.01):
                warnings.append("Duration differs significantly")
            if bpms and max(bpms) - min(bpms) > 1:
                warnings.append("BPM differs; check speed and half/double time")
            if len(versions) > 1:
                warnings.append("Different version labels")
            groups.append(
                {
                    "kind": "related" if warnings else "probable",
                    "tracks": [t["id"] for t in group],
                    "warnings": warnings,
                    "note": ""
                    if warnings
                    else "Matched by artist, title, version, duration and BPM, not by audio",
                }
            )
        return groups
