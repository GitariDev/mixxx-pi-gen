"""Immediate catalog corrections with independent, recoverable destination writes."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from uuid import uuid4

from . import audio, rekordbox
from .backups import Backups
from .db import dump, now
from .operations import replace_copy


def revision(track):
    return hashlib.sha256(
        dump(
            [
                track["metadata"],
                track["file_metadata"],
                track["accepted"],
                track["overrides"],
                track["path"],
                track["source"],
                track["source_id"],
            ]
        ).encode()
    ).hexdigest()


# More tracks than this are approved by a background job instead of one request.
BATCH = 5


class Editing:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def statuses(self, tid=None):
        with self.store.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM manual_edits"
                    + (" WHERE track_id=?" if tid is not None else ""),
                    (tid,) if tid is not None else (),
                )
            ]

    def save(self, tid, changes, expected):
        if not self.service.lock.acquire(False):
            raise ValueError("Another operation is running; try again when it finishes")
        try:
            return self._save(tid, changes, expected)
        finally:
            self.service.lock.release()

    def _save(self, tid, changes, expected):
        if not changes or set(changes) - set(audio.FIELDS):
            raise ValueError("Choose editable metadata fields")
        changes = {k: v.strip() for k, v in changes.items()}
        for k, v in changes.items():
            if not v or len(v) > 255:
                raise ValueError(
                    "Values must contain 1–255 characters; blank fields do not erase metadata"
                )
            if k == "year" and (not v.isdigit() or not 1000 <= int(v) <= 2999):
                raise ValueError("Year must be four digits")
        t = self.store.track(tid)
        if revision(t) != expected:
            raise ValueError(
                "This entry changed while you were editing. Reload the editor before saving"
            )
        accepted, overrides = (
            {**t["accepted"], **changes},
            {**t["overrides"], **changes},
        )
        with self.store.connect() as db:
            db.execute(
                "UPDATE tracks SET accepted=?,overrides=? WHERE id=?",
                (dump(accepted), dump(overrides), tid),
            )
            rid, release = self.store.entities(
                db, t["source"], t["source_id"], {**t["metadata"], **accepted}
            )
            db.execute(
                "UPDATE tracks SET recording_id=?,release_id=? WHERE id=?",
                (rid, release, tid),
            )
            for k, v in changes.items():
                db.execute(
                    """INSERT INTO manual_edits VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(track_id,field) DO UPDATE SET value=excluded.value,file_status=excluded.file_status,
                    library_status=excluded.library_status,baseline=excluded.baseline,created_at=excluded.created_at""",
                    (
                        tid,
                        k,
                        v,
                        "pending",
                        "not_in_rekordbox"
                        if t["source"] in ("local", "demo")
                        else "pending",
                        dump(
                            {
                                "library": str(t["metadata"].get(k, "")),
                                "file": str(t["file_metadata"].get(k, "")),
                            }
                        ),
                        now(),
                    ),
                )
                db.execute(
                    "UPDATE proposals SET status='superseded' WHERE track_id=? AND field=? AND status='pending'",
                    (tid, k),
                )
            db.execute(
                "INSERT INTO history(track_id,kind,detail,created_at) VALUES (?,?,?,?)",
                (
                    tid,
                    "manual",
                    "Saved to Dex: "
                    + ", ".join(f"{k} → {v}" for k, v in changes.items()),
                    now(),
                ),
            )
        return self._sync(tid)

    def plan(self, ids):
        """Group pending suggestions into one set of changes per track."""
        proposals = {p["id"]: p for p in self.store.proposals()}
        # Suggestions retired since the page loaded (track removed or changed) are skipped.
        live = [i for i in ids if i in proposals]
        if not live or len(set(ids)) != len(ids):
            raise ValueError("Selection is empty or stale; refresh the review")
        changes = {}
        for i in live:
            p = proposals[i]
            fields = changes.setdefault(p["track_id"], {})
            if p["field"] in fields:
                raise ValueError("Choose only one proposal per field")
            fields[p["field"]] = (p["new_value"], i)
        return changes

    def approve(self, ids):
        """Accept suggestions: saved in the Dex, then written wherever a destination is ready.

        A few tracks are done on the spot; a larger batch runs as a background job.
        """
        changes = self.plan(ids)
        skipped = len(ids)
        ids = [i for fields in changes.values() for _, i in fields.values()]
        skipped = (
            f" {skipped - len(ids)} skipped: their track was removed or changed."
            if skipped > len(ids)
            else ""
        )
        if len(changes) > BATCH:
            return {
                "job_id": self.service.start("approve", {"ids": ids}),
                "message": f"Approving {len(ids)} fields on {len(changes)} tracks in the background."
                + skipped,
            }
        result = {}
        for tid, fields in changes.items():
            result = self.save(
                tid,
                {k: v for k, (v, _) in fields.items()},
                revision(self.store.track(tid)),
            )
        with self.store.connect() as db:
            db.executemany(
                "UPDATE proposals SET status='applied' WHERE id=?", [(i,) for i in ids]
            )
        waiting = sum(
            "pending" in (e["file_status"], e["library_status"])
            for tid in changes
            for e in self.statuses(tid)
        )
        return {
            "approved": len(ids),
            "tracks": len(changes),
            "message": (
                result["message"]
                if len(changes) == 1
                else f"Approved {len(ids)} fields on {len(changes)} tracks in Song Dex. "
                + (
                    f"{waiting} are waiting to sync to rekordbox or audio tags."
                    if waiting
                    else "Available destinations updated."
                )
            )
            + skipped,
        }

    def approve_job(self, job_id, ids):
        """Background approval; suggestions that changed since it was started are skipped."""
        current = {p["id"] for p in self.store.proposals()}
        changes = (
            self.plan([i for i in ids if i in current]) if current & set(ids) else {}
        )
        self.service.progress(job_id, total=len(changes))
        skipped = 0
        for index, (tid, fields) in enumerate(changes.items()):
            self.require_space()
            try:
                self._save(
                    tid,
                    {k: v for k, (v, _) in fields.items()},
                    revision(self.store.track(tid)),
                )
                with self.store.connect() as db:
                    db.executemany(
                        "UPDATE proposals SET status='applied' WHERE id=?",
                        [(i,) for _, i in fields.values()],
                    )
            except ValueError:
                skipped += 1
            self.service.progress(
                job_id,
                progress=index + 1,
                message=f"Approved {index + 1} of {len(changes)} tracks",
            )
        return skipped

    def pending(self):
        """Tracks with an edit still to write; one removed from rekordbox has nowhere to go."""
        with self.store.connect() as db:
            removed = {
                r[0] for r in db.execute("SELECT id FROM tracks WHERE state='removed'")
            }
        return sorted(
            {
                e["track_id"]
                for e in self.statuses()
                if "pending" in (e["file_status"], e["library_status"])
            }
            - removed
        )

    def sync_pending(self, job_id):
        """Background job: retry every saved edit that has not reached rekordbox or its file."""
        ids = self.pending()
        self.service.progress(job_id, total=len(ids))
        for index, tid in enumerate(ids):
            self.require_space()
            self._sync(tid)
            self.service.progress(
                job_id,
                progress=index + 1,
                message=f"Synced {index + 1} of {len(ids)} tracks",
            )
        return len(self.pending())

    def sync(self, tid):
        if not self.service.lock.acquire(False):
            raise ValueError("Another operation is running")
        try:
            return self._sync(tid)
        finally:
            self.service.lock.release()

    def require_space(self):
        """Stop a batch outright; one save would only note the shortage per destination."""
        source = Path(
            self.store.setting("rekordbox_db", str(rekordbox.DEFAULT_DB))
        ).expanduser()
        if source.is_file():
            audio.require_space(self.store.root, source, copies=3)

    def journal(self, wid, tid, kind, state, manifest):
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO local_writes VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,manifest=excluded.manifest",
                (wid, tid, kind, state, dump(manifest), now()),
            )

    def status(self, tid, destination, status, changes):
        column = "file_status" if destination == "file" else "library_status"
        with self.store.connect() as db:
            db.executemany(
                f"UPDATE manual_edits SET {column}=? WHERE track_id=? AND field=? AND value=?",
                [(status, tid, k, v) for k, v in changes.items()],
            )

    def _sync(self, tid):
        t = self.store.track(tid)
        notes = []
        if t["state"] == "removed":
            return {
                "saved": True,
                "message": "Saved in Song Dex only: this entry is no longer in rekordbox.",
                "statuses": self.statuses(tid),
            }
        for dest in ("file", "library"):
            column = dest + "_status"
            edits = self.statuses(tid)
            changes = {
                e["field"]: e["value"]
                for e in edits
                if e[column] not in ("saved", "not_in_rekordbox")
            }
            if not changes or t["source"] == "demo":
                continue
            try:
                self._write(t, changes, dest)
            except Exception as exc:
                self.status(tid, dest, "pending", changes)
                notes.append(
                    ("Audio tags: " if dest == "file" else "rekordbox: ") + str(exc)
                )
        return {
            "saved": True,
            "message": "Saved in Song Dex. "
            + (" ".join(notes) if notes else "Available destinations updated."),
            "statuses": self.statuses(tid),
        }

    def _write(self, t, changes, dest):
        tid = t["id"]
        if rekordbox.live_check_running(self.store.root):
            raise ValueError("Queued until the live rekordbox check is finished")
        with self.store.connect() as db:
            unresolved = db.execute(
                "SELECT id FROM local_writes WHERE state IN ('preparing','writing','restoring','recovery_required')"
            ).fetchone()
            old = db.execute(
                "SELECT id FROM operations WHERE state NOT IN ('complete','restored')"
            ).fetchone()
        if unresolved or old:
            raise ValueError("Restore the interrupted write in History first")
        if dest == "file":
            target = Path(t["path"])
            if not target.is_file():
                raise ValueError(
                    "File offline; reconnect its drive, check availability, then sync saved edits"
                )
            if target.suffix.lower() not in audio.SUPPORTED:
                raise ValueError(
                    "Tag writing is not supported for this format; your Dex edit is saved"
                )
            if not t["file_hash"] or audio.digest(target) != t["file_hash"]:
                raise ValueError(
                    "File changed since it was scanned. Rescan and review it before syncing"
                )
            for e in self.statuses(tid):
                if e["field"] in changes and str(
                    t["file_metadata"].get(e["field"], "")
                ) not in (json.loads(e["baseline"])["file"], e["value"]):
                    raise ValueError(
                        "Audio tags have a conflicting external edit. Review and save your chosen value again"
                    )
            with self.store.connect() as db:
                if db.execute(
                    "SELECT id FROM tracks WHERE path=? AND id<>?", (str(target), tid)
                ).fetchone():
                    raise ValueError(
                        "Multiple entries reference this file; resolve the shared file before writing tags"
                    )
        else:
            cap = rekordbox.capability(self.store.root)
            if not cap["enabled"]:
                raise ValueError("Queued until direct-write compatibility is verified")
            target = (
                Path(self.store.setting("rekordbox_db", str(rekordbox.DEFAULT_DB)))
                .expanduser()
                .resolve()
            )
            if str(target) != t["source"]:
                raise ValueError("This entry belongs to a different rekordbox database")
            if audio.digest(target) != self.store.setting("library_hash"):
                raise ValueError("Library changed; rescan before syncing saved edits")
            for e in self.statuses(tid):
                if e["field"] in changes and str(
                    t["metadata"].get(e["field"], "")
                ) not in (json.loads(e["baseline"])["library"], e["value"]):
                    raise ValueError(
                        "rekordbox has a conflicting external edit. Review and save your chosen value again"
                    )
        rekordbox.require_stopped()
        audio.require_space(self.store.root, target, copies=2 if dest == "file" else 3)
        wid = str(uuid4())
        folder = self.store.root / "backups" / ("manual-" + wid)
        folder.mkdir(parents=True)
        backup = folder / ("original" + target.suffix)
        staged = folder / ("staged" + target.suffix)
        manifest = {
            "path": str(target),
            "backup": str(backup),
            "before": audio.digest(target),
            "changes": changes,
            "before_metadata": t["metadata"],
        }
        self.journal(wid, tid, dest, "preparing", manifest)
        try:
            if dest == "library":
                rekordbox.snapshot(target, folder / "snapshot")
                shutil.copy2(folder / "snapshot/master.db", backup)
                staged = folder / "stage" / "master.db"
                staged.parent.mkdir()
            else:
                shutil.copy2(target, backup)
            if audio.digest(backup) != manifest["before"]:
                raise ValueError("Source changed during backup")
            shutil.copy2(backup, staged)
            if dest == "file":
                audio.write(staged, changes)
            else:
                rekordbox.write_collection(staged, {t["source_id"]: changes})
            manifest["after"] = audio.digest(staged)
            self.journal(wid, tid, dest, "writing", manifest)
            rekordbox.require_stopped()
            if audio.digest(target) != manifest["before"]:
                raise ValueError("Destination changed during preparation")
            replace_copy(staged, target)
            if audio.digest(target) != manifest["after"]:
                raise ValueError("Destination verification failed")
            with self.store.connect() as db:
                if dest == "file":
                    db.execute(
                        "UPDATE tracks SET file_hash=?,signature=?,file_metadata=?,available=1 WHERE id=?",
                        (
                            manifest["after"],
                            audio.signature(target),
                            dump(audio.read(target)),
                            tid,
                        ),
                    )
                else:
                    db.execute(
                        "UPDATE tracks SET metadata=? WHERE id=?",
                        (dump({**t["metadata"], **changes}), tid),
                    )
                    db.execute(
                        "INSERT OR REPLACE INTO settings VALUES (?,?)",
                        ("library_hash", dump(manifest["after"])),
                    )
            self.status(tid, dest, "saved", changes)
            self.journal(wid, tid, dest, "complete", manifest)
            self.store.log(
                "metadata_sync", f"Saved {dest} metadata with backup {wid}", tid
            )
        except Exception as exc:
            manifest["error"] = str(exc)
            # Until "after" is journaled the destination is untouched: nothing needs
            # recovering, and later writes must not wait on this one.
            self.journal(
                wid,
                tid,
                dest,
                "recovery_required" if "after" in manifest else "failed",
                manifest,
            )
            raise
        finally:
            # A restore reads only the backup; the working copies would triple its size.
            staged.unlink(missing_ok=True)
            for name in ("snapshot", "stage"):
                shutil.rmtree(folder / name, ignore_errors=True)
        # This write is now the one that can be undone here; earlier backups are spent.
        Backups(self.service).prune([str(target)])

    def restore(self, wid):
        if not self.service.lock.acquire(False):
            raise ValueError("Another operation is running")
        try:
            with self.store.connect() as db:
                row = db.execute(
                    "SELECT * FROM local_writes WHERE id=?", (wid,)
                ).fetchone()
            if not row or row["state"] in ("restored", "failed"):
                raise ValueError("No restorable write")
            m = json.loads(row["manifest"])
            if m.get("backup_deleted"):
                raise ValueError("This backup was deleted, so it cannot be restored")
            target, backup = Path(m["path"]), Path(m["backup"])
            # Without an "after" digest the write stopped while preparing, before the
            # destination was replaced, so whatever it holds now is not ours to undo.
            if "after" not in m:
                self.status(row["track_id"], row["kind"], "pending", m["changes"])
                self.journal(wid, row["track_id"], row["kind"], "restored", m)
                self.store.log(
                    "restore",
                    "Cleared an interrupted write that never reached its destination; your Dex correction remains saved for later syncing",
                    row["track_id"],
                )
                Backups(self.service).prune([m["path"]])
                return {
                    "restored": True,
                    "message": "Interrupted write cleared. Nothing had been written; your Dex correction is still saved for syncing.",
                }
            rekordbox.require_stopped()
            if not target.is_file() or audio.digest(target) not in (
                m["before"],
                m.get("after"),
            ):
                raise ValueError(
                    "Destination is missing or has newer changes; restoration blocked"
                )
            # A failure before the backup exists is safe to dismiss only if nothing changed.
            if audio.digest(target) != m["before"]:
                if not backup.is_file() or audio.digest(backup) != m["before"]:
                    raise ValueError("Original backup cannot be verified")
                self.journal(wid, row["track_id"], row["kind"], "restoring", m)
                replace_copy(backup, target)
            if audio.digest(target) != m["before"]:
                raise ValueError("Restore verification failed")
            if row["kind"] == "file":
                with self.store.connect() as db:
                    db.execute(
                        "UPDATE tracks SET file_hash=?,signature=?,file_metadata=? WHERE id=?",
                        (
                            m["before"],
                            audio.signature(target),
                            dump(audio.read(target)),
                            row["track_id"],
                        ),
                    )
            else:
                self.store.set_setting("library_hash", m["before"])
                with self.store.connect() as db:
                    db.execute(
                        "UPDATE tracks SET metadata=? WHERE id=?",
                        (dump(m["before_metadata"]), row["track_id"]),
                    )
            self.status(row["track_id"], row["kind"], "pending", m["changes"])
            self.journal(wid, row["track_id"], row["kind"], "restored", m)
            self.store.log(
                "restore",
                "Restored destination; your Dex correction remains saved for later syncing",
                row["track_id"],
            )
            Backups(self.service).prune([str(target)])
            return {"restored": True}
        finally:
            self.service.lock.release()
