"""The backups taken before each write: what they hold, their size, and removal.

Every write keeps a copy of what it replaced under `<data>/backups`. A restore
refuses to overwrite newer changes, so only the latest change to a destination can
be undone in the app. Backups that can no longer be undone are spent, and are
removed after each write, at the end of each job and when Song Dex starts.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import audio
from .db import dump

UNFINISHED = ("preparing", "writing", "restoring", "recovery_required")


def size(path):
    files = [path] if path.is_file() else path.rglob("*")
    return sum(p.stat().st_size for p in files if p.is_file())


class Backups:
    def __init__(self, service):
        self.service, self.store = service, service.store
        self.root = self.store.root / "backups"

    def items(self, paths=None):
        """Every backup. `paths` limits which destinations are compared (None: all)."""
        with self.store.connect() as db:
            writes = {
                "manual-" + r["id"]: dict(r)
                for r in db.execute("SELECT * FROM local_writes")
            }
            operations = {
                r["id"]: dict(r) for r in db.execute("SELECT * FROM operations")
            }
            tracks = {
                r["id"]: {**json.loads(r["metadata"]), **json.loads(r["accepted"])}
                for r in db.execute("SELECT id,metadata,accepted FROM tracks")
            }
        digests = {}

        def status(state, path, expected):
            """Whether the destination still is what the write left behind.

            Unknown counts as neither: the destination was not compared, or it is
            offline and may still match once its drive is back.
            """
            known = (paths is None or path in paths) and Path(path).is_file()
            if known and path not in digests:
                digests[path] = audio.digest(path)
            held = known and digests[path] == expected
            return {
                "undoable": state == "complete" and held,
                "spent": state in ("restored", "failed")
                or (state == "complete" and known and not held),
            }

        items = []
        for entry in self.root.iterdir() if self.root.is_dir() else ():
            item = {
                "id": entry.name,
                "label": entry.name,
                "detail": "Not created by a write in this catalog",
                "state": "",
                "created_at": datetime.fromtimestamp(
                    entry.stat().st_mtime, timezone.utc
                ).isoformat(),
                "size": size(entry),
                "undoable": False,
                "spent": False,
                "locked": False,
            }
            if entry.name in writes:
                row = writes[entry.name]
                m, t = json.loads(row["manifest"]), tracks.get(row["track_id"], {})
                changes = ", ".join(
                    f"{k.replace('_', ' ')} → {v}"
                    for k, v in m.get("changes", {}).items()
                )
                item |= {
                    "label": "Audio tags" if row["kind"] == "file" else "rekordbox",
                    "detail": " · ".join(
                        filter(None, [t.get("title"), t.get("artist"), changes])
                    ),
                    **status(row["state"], m["path"], m.get("after")),
                }
            elif entry.name in operations:
                row = operations[entry.name]
                m = json.loads(row["manifest"])
                item |= {
                    "label": m.get("kind") or "metadata applied",
                    "detail": m.get("detail") or f"{len(m['tracks'])} tracks",
                    **status(row["state"], m["source"], m.get("after_library_hash")),
                }
            else:
                items.append(item)
                continue
            item |= {
                "state": row["state"],
                "created_at": row["created_at"],
                "locked": row["state"] in UNFINISHED,
            }
            items.append(item)
        return sorted(items, key=lambda i: i["created_at"], reverse=True)

    def list(self):
        items = self.items()
        return {
            "items": items,
            "total": sum(i["size"] for i in items),
            "free": shutil.disk_usage(self.store.root).free,
        }

    def delete(self, ids):
        if not self.service.lock.acquire(blocking=False):
            raise ValueError("Another operation is running")
        try:
            known = {i["id"]: i for i in self.items(paths=())}
            if not ids or len(set(ids)) != len(ids) or set(ids) - set(known):
                raise ValueError("Backups changed; refresh and choose again")
            if any(known[i]["locked"] for i in ids):
                raise ValueError(
                    "An unfinished write needs its backup to recover. "
                    "Restore or clear that write first."
                )
            for name in ids:
                self.remove(name)
            freed = sum(known[i]["size"] for i in ids)
            detail = f"Deleted {len(ids)} backups, freeing {freed // audio.MB} MB"
            self.store.log("backups", detail)
            return {"deleted": len(ids), "freed": freed, "message": detail + "."}
        finally:
            self.service.lock.release()

    def remove(self, name):
        path = self.root / name
        shutil.rmtree(path) if path.is_dir() else path.unlink()
        # The journal entry stays; it just can no longer be restored.
        table, key = (
            ("local_writes", name[len("manual-") :])
            if name.startswith("manual-")
            else ("operations", name)
        )
        with self.store.connect() as db:
            row = db.execute(
                f"SELECT manifest FROM {table} WHERE id=?", (key,)
            ).fetchone()
            if row:
                db.execute(
                    f"UPDATE {table} SET manifest=? WHERE id=?",
                    (dump({**json.loads(row[0]), "backup_deleted": True}), key),
                )

    def prune(self, paths=None):
        """Delete spent backups; the caller holds the service lock, or nothing runs yet.

        Never raises: this follows a write that already succeeded, and whatever is
        left behind is picked up by the next run.
        """
        try:
            spent = [i for i in self.items(paths) if i["spent"]]
            for item in spent:
                self.remove(item["id"])
            if spent and paths is None:
                freed = sum(i["size"] for i in spent) // audio.MB
                self.store.log(
                    "backups",
                    f"Removed {len(spent)} backups that could no longer be undone, freeing {freed} MB",
                )
            return len(spent)
        except (OSError, sqlite3.Error):
            return 0
