from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from . import audio, rekordbox
from .backups import Backups
from .db import dump, now


def replace_copy(source, target):
    """Atomic replacement on the target volume (including external drives)."""
    target = Path(target)
    temporary = target.with_name("." + target.name + ".songdex-" + uuid4().hex)
    try:
        shutil.copy2(source, temporary)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


class Operations:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def save(self, opid, state, manifest):
        # SQLite is the durable operation journal; backups are immutable siblings.
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO operations VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,manifest=excluded.manifest",
                (opid, state, dump(manifest), now()),
            )

    def apply(self, ids):
        if not self.service.lock.acquire(False):
            raise ValueError("Another operation is running")
        try:
            return self._apply(ids)
        finally:
            self.service.lock.release()

    def guard(self):
        cap = rekordbox.capability(self.store.root)
        if not cap["enabled"]:
            raise ValueError(cap["reason"])
        rekordbox.require_stopped()
        with self.store.connect() as db:
            unresolved = db.execute(
                "SELECT id FROM operations WHERE state IN ('preparing','writing','restoring','recovery_required') UNION SELECT id FROM local_writes WHERE state IN ('preparing','writing','restoring','recovery_required')"
            ).fetchone()
        if unresolved:
            raise ValueError(
                "Restore the interrupted operation in History before applying more changes"
            )
        return cap

    def refresh(self, source, path, source_ids):
        """Re-index the given rekordbox entries from a copy of the library."""
        wanted = set(source_ids)
        for row in rekordbox.read_collection(path):
            if row["source_id"] in wanted:
                self.service.ingest(str(source), row)

    def library_change(self, kind, detail, affected, mutate):
        """Run `mutate(staged master.db)` on a copy, then swap it in with its playlist XML.

        For changes that live only in rekordbox's database (playlists, My Tags).
        Journaled like a metadata apply and restorable from History.
        """
        if not self.service.lock.acquire(False):
            raise ValueError("Another operation is running")
        try:
            return self.change_library(kind, detail, affected, mutate)
        finally:
            self.service.lock.release()

    def change_library(self, kind, detail, affected, mutate):
        """`library_change` for a caller that already holds the operation lock."""
        self.guard()
        source = (
            Path(self.store.setting("rekordbox_db", str(rekordbox.DEFAULT_DB)))
            .expanduser()
            .resolve()
        )
        xml = source.parent / "masterPlaylists6.xml"
        if not xml.is_file():
            raise ValueError("masterPlaylists6.xml is missing beside the library")
        expected = self.store.setting("library_hash")
        if not expected or audio.digest(source) != expected:
            raise ValueError(
                "rekordbox changed after the scan. Rescan and review again."
            )
        audio.require_space(self.store.root, source)
        opid = str(uuid4())
        root = self.store.root / "backups" / opid
        root.mkdir(parents=True)
        manifest = {
            "kind": kind,
            "detail": detail,
            "affected": sorted(affected),
            "source": str(source),
            "before_library_hash": expected,
            "after_library_hash": None,
            "before_xml_hash": audio.digest(xml),
            "after_xml_hash": None,
            "proposals": [],
            "tracks": [],
            "library_status": "pending",
            "dex_status": "pending",
        }
        self.save(opid, "preparing", manifest)
        try:
            rekordbox.snapshot(source, root / "original")
            shutil.copytree(root / "original", root / "staged")
            staged = root / "staged/master.db"
            manifest["result"] = mutate(staged)
            manifest["after_library_hash"] = audio.digest(staged)
            manifest["after_xml_hash"] = audio.digest(staged.parent / xml.name)
            self.save(opid, "writing", manifest)
            rekordbox.require_stopped()
            if (
                audio.digest(source) != expected
                or audio.digest(xml) != manifest["before_xml_hash"]
            ):
                raise ValueError("Library changed while preparing writes")
            replace_copy(staged.parent / xml.name, xml)
            replace_copy(staged, source)
            if audio.digest(source) != manifest["after_library_hash"]:
                raise ValueError("Library replacement verification failed")
            manifest["library_status"] = "complete"
            self.save(opid, "writing", manifest)
            self.refresh(source, staged, affected)
            self.store.set_setting("library_hash", manifest["after_library_hash"])
            manifest["dex_status"] = "complete"
            self.save(opid, "complete", manifest)
            self.store.log(kind, detail)
        except Exception as exc:
            manifest["error"] = str(exc)
            self.save(opid, "recovery_required", manifest)
            self.store.log("write interrupted", f"Operation {opid}: {exc}")
        finally:
            # A restore reads only `original`.
            shutil.rmtree(root / "staged", ignore_errors=True)
        Backups(self.service).prune([str(source)])
        return {"id": opid, "manifest": manifest}

    def _apply(self, ids):
        cap = self.guard()
        proposals = {p["id"]: p for p in self.store.proposals()}
        if not ids or len(ids) != len(set(ids)) or any(i not in proposals for i in ids):
            raise ValueError("Selection is empty or stale; refresh the review")
        changes, selected = {}, {}
        for pid in ids:
            p = proposals[pid]
            t = selected.setdefault(p["track_id"], self.store.track(p["track_id"]))
            if t["source"] == "demo" or not t["available"] or t["state"] == "removed":
                raise ValueError("Only available real library tracks can be updated")
            if (
                p["signature"] != t["signature"]
                or audio.signature(t["path"]) != t["signature"]
                or audio.digest(t["path"]) != t["file_hash"]
            ):
                raise ValueError(
                    "An audio file changed after review. Rescan before applying."
                )
            ext = Path(t["path"]).suffix.lower()
            if ext not in cap["report"].get("verified_formats", []):
                raise ValueError(
                    f"{ext} has not passed the format compatibility checks"
                )
            if p["field"] not in audio.FIELDS:
                raise ValueError("Field is not writable")
            if p["field"] == "year" and (
                not p["new_value"].isdigit() or not 1000 <= int(p["new_value"]) <= 2999
            ):
                raise ValueError("Year must be four digits")
            change = changes.setdefault(t["id"], {})
            if p["field"] in change:
                raise ValueError("Choose only one proposal per field")
            change[p["field"]] = p["new_value"]
        paths = [Path(t["path"]).resolve() for t in selected.values()]
        if len(set(paths)) != len(paths):
            raise ValueError(
                "Multiple rekordbox entries reference the same file; review them individually"
            )
        source = (
            Path(self.store.setting("rekordbox_db", str(rekordbox.DEFAULT_DB)))
            .expanduser()
            .resolve()
        )
        if any(t["source"] != str(source) for t in selected.values()):
            raise ValueError("Selected tracks belong to a different library")
        expected = self.store.setting("library_hash")
        if not expected or audio.digest(source) != expected:
            raise ValueError(
                "rekordbox changed after the scan. Rescan and review again."
            )
        audio.require_space(
            self.store.root, source, *(t["path"] for t in selected.values())
        )
        opid = str(uuid4())
        root = self.store.root / "backups" / opid
        root.mkdir(parents=True)
        manifest = {
            "source": str(source),
            "before_library_hash": expected,
            "after_library_hash": None,
            "proposals": ids,
            "tracks": [],
            "library_status": "pending",
            "dex_status": "pending",
        }
        self.save(opid, "preparing", manifest)
        try:
            rekordbox.snapshot(source, root / "original")
            shutil.copytree(root / "original", root / "staged")
            for tid, t in selected.items():
                backup = root / f"{tid}{Path(t['path']).suffix.lower()}"
                shutil.copy2(t["path"], backup)
                entry = {
                    "id": tid,
                    "path": t["path"],
                    "backup": str(backup),
                    "before_hash": t["file_hash"],
                    "after_hash": None,
                    "file_status": "pending",
                    "changes": changes[tid],
                    "old_accepted": t["accepted"],
                    "old_overrides": t["overrides"],
                    "old_metadata": t["metadata"],
                }
                manifest["tracks"].append(entry)
                self.save(opid, "preparing", manifest)
                staged = root / ("staged-" + backup.name)
                shutil.copy2(backup, staged)
                audio.write(staged, changes[tid])
                entry["staged"] = str(staged)
                entry["after_hash"] = audio.digest(staged)
            rekordbox.write_collection(
                root / "staged/master.db",
                {t["source_id"]: changes[tid] for tid, t in selected.items()},
            )
            manifest["after_library_hash"] = audio.digest(root / "staged/master.db")
            self.save(opid, "writing", manifest)
            rekordbox.require_stopped()
            if audio.digest(source) != expected:
                raise ValueError("Library changed while preparing writes")
            for entry in manifest["tracks"]:
                rekordbox.require_stopped()
                if audio.digest(entry["path"]) != entry["before_hash"]:
                    raise ValueError("File changed while preparing writes")
                replace_copy(entry["staged"], entry["path"])
                if audio.digest(entry["path"]) != entry["after_hash"]:
                    raise ValueError("Audio file replacement verification failed")
                entry["file_status"] = "complete"
                self.save(opid, "writing", manifest)
            rekordbox.require_stopped()
            if audio.digest(source) != expected:
                raise ValueError("Library changed before final commit")
            replace_copy(root / "staged/master.db", source)
            if audio.digest(source) != manifest["after_library_hash"]:
                raise ValueError("Library replacement verification failed")
            manifest["library_status"] = "complete"
            self.save(opid, "writing", manifest)
            with self.store.connect() as db:
                for entry in manifest["tracks"]:
                    t = selected[entry["id"]]
                    accepted = {**t["accepted"], **entry["changes"]}
                    overrides = dict(t["overrides"])
                    for pid in ids:
                        p = proposals[pid]
                        if p["track_id"] == t["id"] and p["source"] == "manual":
                            overrides[p["field"]] = p["new_value"]
                    metadata = {**t["metadata"], **entry["changes"]}
                    rid, release = self.store.entities(
                        db, t["source"], t["source_id"], metadata
                    )
                    db.execute(
                        "UPDATE tracks SET metadata=?,accepted=?,overrides=?,signature=?,file_hash=?,file_metadata=?,state='indexed',recording_id=?,release_id=? WHERE id=?",
                        (
                            dump(metadata),
                            dump(accepted),
                            dump(overrides),
                            audio.signature(t["path"]),
                            entry["after_hash"],
                            dump(audio.read(t["path"])),
                            rid,
                            release,
                            t["id"],
                        ),
                    )
                    db.execute(
                        "UPDATE proposals SET status='stale' WHERE track_id=? AND status='pending'",
                        (t["id"],),
                    )
                    db.execute(
                        "INSERT INTO history(track_id,kind,detail,created_at) VALUES (?,?,?,?)",
                        (t["id"], "metadata applied", dump(entry["changes"]), now()),
                    )
                db.executemany(
                    "UPDATE proposals SET status='applied' WHERE id=?",
                    [(i,) for i in ids],
                )
                db.execute(
                    "INSERT OR REPLACE INTO settings VALUES (?,?)",
                    ("library_hash", dump(manifest["after_library_hash"])),
                )
                manifest["dex_status"] = "complete"
                db.execute(
                    "UPDATE operations SET state='complete',manifest=? WHERE id=?",
                    (dump(manifest), opid),
                )
            self.store.log(
                "apply", f"Applied {len(ids)} approved fields to {len(selected)} tracks"
            )
        except Exception as exc:
            manifest["error"] = str(exc)
            self.save(opid, "recovery_required", manifest)
            self.store.log("write interrupted", f"Operation {opid}: {exc}")
        finally:
            # A restore reads only `original` and each file's backup.
            shutil.rmtree(root / "staged", ignore_errors=True)
            for staged in root.glob("staged-*"):
                staged.unlink()
        Backups(self.service).prune([str(source)])
        return {"id": opid, "manifest": manifest}

    def restore(self, opid):
        if not self.service.lock.acquire(False):
            raise ValueError("Another operation is running")
        try:
            rekordbox.require_stopped()
            with self.store.connect() as db:
                row = db.execute(
                    "SELECT * FROM operations WHERE id=?", (opid,)
                ).fetchone()
            if not row:
                raise ValueError("Operation not found")
            if row["state"] == "restored":
                return {"state": "restored"}
            m = json.loads(row["manifest"])
            # Without this, a missing backup would read as "nothing was written".
            if m.get("backup_deleted"):
                raise ValueError("This backup was deleted, so it cannot be restored")
            root = self.store.root / "backups" / opid
            source = Path(m["source"])
            xml = source.parent / "masterPlaylists6.xml"
            if m.get("before_xml_hash") and audio.digest(xml) not in {
                m["before_xml_hash"],
                m["after_xml_hash"],
            }:
                raise ValueError(
                    "Playlists changed since this operation. Restore blocked to protect newer edits."
                )
            # Compare before touching anything, including edits made after a successful run.
            if audio.digest(source) not in {
                m["before_library_hash"],
                m["after_library_hash"],
            }:
                raise ValueError(
                    "Library changed since this operation. Restore blocked to protect newer edits."
                )
            for e in m["tracks"]:
                if audio.digest(e["path"]) not in {e["before_hash"], e["after_hash"]}:
                    raise ValueError(
                        "A file changed since this operation. Restore blocked to protect newer edits."
                    )
                if audio.digest(e["backup"]) != e["before_hash"]:
                    raise ValueError("Backup verification failed")
            if not (root / "original/master.db").exists():
                # Preparation failed before any writes.
                self.save(opid, "restored", m)
                return {"state": "restored"}
            if audio.digest(root / "original/master.db") != m["before_library_hash"]:
                raise ValueError("Library backup verification failed")
            self.save(opid, "restoring", m)
            for e in m["tracks"]:
                rekordbox.require_stopped()
                replace_copy(e["backup"], e["path"])
                if audio.digest(e["path"]) != e["before_hash"]:
                    raise ValueError("Restored audio file failed verification")
            rekordbox.require_stopped()
            if audio.digest(source) not in {
                m["before_library_hash"],
                m["after_library_hash"],
            }:
                raise ValueError(
                    "Library changed during restoration; retry after review"
                )
            if m.get("before_xml_hash"):
                replace_copy(root / "original" / xml.name, xml)
            replace_copy(root / "original/master.db", source)
            if m.get("affected"):
                self.refresh(source, root / "original/master.db", m["affected"])
            with self.store.connect() as db:
                for e in m["tracks"]:
                    track = db.execute(
                        "SELECT source,source_id FROM tracks WHERE id=?", (e["id"],)
                    ).fetchone()
                    rid, release = self.store.entities(
                        db, track["source"], track["source_id"], e["old_metadata"]
                    )
                    db.execute(
                        "UPDATE tracks SET metadata=?,accepted=?,overrides=?,file_metadata=?,signature=?,file_hash=?,state='indexed',recording_id=?,release_id=? WHERE id=?",
                        (
                            dump(e["old_metadata"]),
                            dump(e["old_accepted"]),
                            dump(e["old_overrides"]),
                            dump(audio.read(e["path"])),
                            audio.signature(e["path"]),
                            e["before_hash"],
                            rid,
                            release,
                            e["id"],
                        ),
                    )
                    db.execute(
                        "INSERT INTO history(track_id,kind,detail,created_at) VALUES (?,?,?,?)",
                        (
                            e["id"],
                            "metadata restored",
                            f"Restored operation {opid}",
                            now(),
                        ),
                    )
                db.execute(
                    "INSERT OR REPLACE INTO settings VALUES (?,?)",
                    ("library_hash", dump(m["before_library_hash"])),
                )
            self.save(opid, "restored", m)
            self.store.log("restore", f"Restored operation {opid}")
            Backups(self.service).prune([str(source)])
            return {"state": "restored"}
        finally:
            self.service.lock.release()
