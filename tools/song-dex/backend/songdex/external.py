"""Copies of the library on an external drive, made on request.

Each backup is a dated folder under `<drive>/Song Dex Backups` holding the parts
chosen: the rekordbox database, the whole rekordbox folder (analysis, artwork and
rekordbox's own backups), the Song Dex catalog. Music is kept once per drive in
`Song Dex Backups/Music`, mirroring each file's full path, so a later backup only
copies files that are new or changed. Nothing on the drive is ever deleted.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from . import audio, rekordbox
from .db import dump, now

VOLUMES = Path("/Volumes")
FOLDER = "Song Dex Backups"
SCOPES = {
    "database": "rekordbox database",
    "rekordbox": "rekordbox folder",
    "library": "whole library",
}
# Room left on the drive beyond what the copies need.
MARGIN = 100 * audio.MB
PARTIAL = ".songdex-partial"
RESTORE = """Song Dex backup, {created}: {label}.

rekordbox/  Quit rekordbox, then copy these files over the rekordbox folder
            ({source}). master.db alone restores the collection and playlists.
songdex/    Quit Song Dex, then copy songdex.sqlite3 into its data folder.
../Music/   Every music file in the collection, under its original full path.
            Copy a file back to the path shown below Music to restore it.

backup.json lists every track's original path and its copy.
"""


def external(path):
    """A mounted drive other than the startup disk."""
    try:
        return os.path.ismount(path) and path.stat().st_dev != Path("/").stat().st_dev
    except OSError:
        return False


def size(path):
    files = [path] if path.is_file() else path.rglob("*")
    total = 0
    for p in files:
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def unchanged(source, target):
    """The copy already matches: same size and modification time.

    FAT and exFAT drives keep times to two seconds.
    """
    try:
        a, b = source.stat(), target.stat()
    except OSError:
        return False
    return a.st_size == b.st_size and abs(a.st_mtime - b.st_mtime) <= 2


def copy(source, target):
    """Copy under a temporary name, so an interrupted copy never looks complete."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + PARTIAL)
    try:
        shutil.copy2(source, partial)
        os.replace(partial, target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


class ExternalBackup:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def source(self):
        return (
            Path(self.store.setting("rekordbox_db", str(rekordbox.DEFAULT_DB)))
            .expanduser()
            .resolve()
        )

    def music(self):
        """The collection's music files: the ones that can be copied, and missing."""
        source, found, missing = str(self.source()), {}, 0
        for t in self.store.tracks():
            if t["source"] != source or t["state"] == "removed" or t["path"] in found:
                continue
            path = Path(t["path"])
            try:
                found[t["path"]] = path.stat().st_size if path.is_file() else None
            except OSError:
                found[t["path"]] = None
            missing += found[t["path"]] is None
        return {p: n for p, n in found.items() if n is not None}, missing

    def rekordbox_files(self):
        """The rekordbox folder's files other than the database, which is snapshot."""
        root = self.source().parent
        skip = {"master.db", "master.db-wal", "master.db-shm", "masterPlaylists6.xml"}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                path = Path(dirpath) / name
                if (Path(dirpath) == root and name in skip) or name.startswith("."):
                    continue
                if path.is_file() and not path.is_symlink():
                    yield path

    def drives(self):
        last = {}
        for entry in self.store.setting("external_backups", []):
            last.setdefault(entry["drive"], entry)
        found = []
        for p in sorted(VOLUMES.iterdir()) if VOLUMES.is_dir() else ():
            if p.name.startswith(".") or p.is_symlink() or not external(p):
                continue
            try:
                usage = shutil.disk_usage(p)
            except OSError:
                continue
            found.append(
                {
                    "path": str(p),
                    "name": p.name,
                    "free": usage.free,
                    "total": usage.total,
                    "writable": os.access(p, os.W_OK),
                    "last": last.get(str(p)),
                }
            )
        return found

    def overview(self):
        source = self.source()
        files, missing = self.music()
        database = (
            sum(
                size(p)
                for p in (source, source.parent / "masterPlaylists6.xml")
                if p.is_file()
            )
            if source.is_file()
            else 0
        )
        return {
            "drives": self.drives(),
            "rekordbox_db": str(source),
            "sizes": {
                "database": database,
                "rekordbox": database
                + sum(p.stat().st_size for p in self.rekordbox_files())
                if source.is_file()
                else 0,
                "music": sum(files.values()),
                "catalog": self.store.path.stat().st_size,
            },
            "music_files": len(files),
            "music_missing": missing,
        }

    def drive(self, path):
        chosen = Path(path)
        for d in self.drives():
            if Path(d["path"]) == chosen:
                if not d["writable"]:
                    raise ValueError(f"{d['name']} is read-only; choose another drive")
                return chosen
        raise ValueError("That drive is not connected; refresh and choose again")

    def start(self, drive, scope, catalog):
        if scope not in SCOPES:
            raise ValueError("Choose what to back up")
        root = self.drive(drive)
        # Every scope includes the rekordbox database.
        if not self.source().is_file():
            raise ValueError(
                "rekordbox's master.db was not found; check the library path in Settings"
            )
        stamp = datetime.now().strftime("%Y-%m-%d %H.%M.%S")
        payload = {
            "drive": str(root),
            "scope": scope,
            "catalog": bool(catalog),
            "folder": str(root / FOLDER / stamp),
        }
        return {
            "job_id": self.service.start("external_backup", payload),
            "message": f"Backing up the {SCOPES[scope]} to {root.name}",
        }

    def run(self, job_id, payload):
        """Make the backup; returns (state, message)."""
        drive, scope = Path(payload["drive"]), payload["scope"]
        folder = Path(payload["folder"])
        progress = self.service.progress
        if not external(drive):
            raise ValueError(f"{drive.name} is no longer connected")
        source = self.source()
        progress(job_id, message="Planning the backup")

        # (source, target) pairs to copy, after the database snapshot.
        plan, skipped = [], {"unchanged": 0, "on_drive": 0}
        if scope in ("rekordbox", "library"):
            for p in self.rekordbox_files():
                plan.append((p, folder / "rekordbox" / p.relative_to(source.parent)))
        missing, mapping = 0, []
        if scope == "library":
            files, missing = self.music()
            mirror = drive / FOLDER / "Music"
            for path in sorted(files):
                p = Path(path)
                if p.is_relative_to(drive):
                    skipped["on_drive"] += 1
                    continue
                target = mirror / p.relative_to(p.anchor)
                mapping.append({"path": path, "backup": str(target)})
                if unchanged(p, target):
                    skipped["unchanged"] += 1
                else:
                    plan.append((p, target))

        needed = sum(p.stat().st_size for p, _ in plan) + self.store.path.stat().st_size
        needed += sum(
            p.stat().st_size
            for p in (source, source.parent / "masterPlaylists6.xml")
            if p.is_file()
        )
        free = shutil.disk_usage(drive).free
        if needed + MARGIN > free:
            raise ValueError(
                f"{drive.name} needs {needed // audio.MB} MB free for this backup "
                f"but has {free // audio.MB} MB. Free some space or choose a smaller backup."
            )

        total = len(plan) + 1 + bool(payload["catalog"])
        progress(job_id, total=total, progress=0)
        progress(job_id, message="Copying the rekordbox database")
        rekordbox.snapshot(source, folder / "rekordbox")
        done = 1
        if payload["catalog"]:
            progress(job_id, progress=done, message="Copying the Song Dex catalog")
            (folder / "songdex").mkdir(parents=True, exist_ok=True)
            target = folder / "songdex" / self.store.path.name
            out = sqlite3.connect(target)
            try:
                with self.store.connect() as db:
                    db.backup(out)
            finally:
                out.close()
            done += 1

        failed, copied = [], 0
        for index, (p, target) in enumerate(plan):
            try:
                copy(p, target)
                copied += p.stat().st_size
            except OSError as exc:
                failed.append({"path": str(p), "error": exc.strerror or str(exc)})
            if index % 10 == 0 or index == len(plan) - 1:
                progress(
                    job_id,
                    progress=done + index + 1,
                    message=f"Copied {index + 1} of {len(plan)} files · "
                    f"{copied // audio.MB} MB",
                )

        manifest = {
            "created_at": now(),
            "scope": scope,
            "catalog": payload["catalog"],
            "rekordbox_db": str(source),
            "copied_files": len(plan) - len(failed),
            "copied_bytes": copied,
            "unchanged_files": skipped["unchanged"],
            "already_on_drive": skipped["on_drive"],
            "missing_files": missing,
            "failed": failed,
            "tracks": mapping,
        }
        (folder / "backup.json").write_text(dump(manifest))
        (folder / "README.txt").write_text(
            RESTORE.format(
                created=folder.name, label=SCOPES[scope], source=source.parent
            )
        )
        record = {
            "drive": str(drive),
            "name": drive.name,
            "folder": str(folder),
            "scope": scope,
            "catalog": payload["catalog"],
            "finished_at": manifest["created_at"],
            "failed": len(failed),
        }
        history = self.store.setting("external_backups", [])
        self.store.set_setting("external_backups", [record, *history][:50])

        detail = (
            f"Backed up the {SCOPES[scope]} to {drive.name} · "
            f"{len(plan) - len(failed)} files, {copied // audio.MB} MB copied"
        )
        if skipped["unchanged"]:
            detail += f" · {skipped['unchanged']} music files already up to date"
        if missing:
            detail += f" · {missing} music files were offline or missing"
        if skipped["on_drive"]:
            detail += f" · {skipped['on_drive']} music files already live on this drive"
        self.store.log("backups", detail)
        if failed:
            return (
                "partial",
                f"{detail}. {len(failed)} files could not be copied; see backup.json "
                "on the drive, then resume to try them again.",
            )
        return "complete", detail + "."
