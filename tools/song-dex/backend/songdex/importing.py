"""Reviewed, collision-safe local music imports into the main music folder.

Files move by default. One that rekordbox already lists moves too, and the scan
that ends the import points its rekordbox entry at the new place. Copy keeps the
originals; index leaves every file where it is and only adds it to the Dex.
"""

from __future__ import annotations

import errno
import json
import os
import plistlib
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import audio, rekordbox
from .db import dump, now
from .operations import Operations


def default_music_folder():
    candidates = [
        Path.home() / "Documents/GTsCollection",
        Path.home() / "Documents/GT's Collection",
    ]
    return str(next((p for p in candidates if p.is_dir()), candidates[0]))


def entry_dates(entries):
    """Prefer Finder's Date Added; unindexed volumes retain filesystem dates."""
    if not entries or not Path("/usr/bin/mdls").is_file():
        return

    def key(path):
        return str(path).removeprefix("/System/Volumes/Data")

    by_path = {key(e["path"]): e for e in entries}
    try:
        result = subprocess.run(
            [
                "/usr/bin/mdls",
                "-name",
                "kMDItemPath",
                "-name",
                "kMDItemDateAdded",
                "-plist",
                "-",
                *[e["path"] for e in entries],
            ],
            capture_output=True,
            timeout=3,
            check=False,
        )
        records = plistlib.loads(result.stdout)
        for record in records if isinstance(records, list) else [records]:
            entry = by_path.get(key(record.get("kMDItemPath", "")))
            added = record.get("kMDItemDateAdded")
            if entry and isinstance(added, datetime):
                entry["added_at"] = added.replace(tzinfo=timezone.utc).timestamp()
                entry["date_basis"] = "added"
    except (
        OSError,
        subprocess.TimeoutExpired,
        ValueError,
        plistlib.InvalidFileException,
    ):
        pass


def new_to_rekordbox(entry):
    """Imported files rekordbox has no entry for; importing the others would duplicate them."""
    return entry["status"] == "complete" and not entry.get("repoint")


class Importing:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def browse(self, path):
        directory = Path(path or Path.home() / "Downloads").expanduser().resolve()
        if not directory.is_dir():
            raise ValueError(
                "Folder is unavailable. Reconnect the drive or choose another location"
            )
        entries = []
        try:
            for p in directory.iterdir():
                if p.name.startswith(".") or p.is_symlink():
                    continue
                if p.is_dir() or (p.is_file() and p.suffix.lower() in audio.PLAYABLE):
                    stat = p.stat()
                    entries.append(
                        {
                            "path": str(p),
                            "name": p.name,
                            "folder": p.is_dir(),
                            "added_at": getattr(stat, "st_birthtime", stat.st_mtime),
                            "date_basis": "created"
                            if hasattr(stat, "st_birthtime")
                            else "modified",
                        }
                    )
        except OSError as exc:
            raise ValueError(
                "Cannot open this folder. Check filesystem permissions"
            ) from exc
        if len(entries) > 5000:
            raise ValueError(
                "This folder has over 5,000 entries. Enter a more specific subfolder"
            )
        entry_dates(entries)
        entries.sort(
            key=lambda x: (
                not x["folder"],
                -x["added_at"],
                x["name"].casefold(),
            )
        )
        return {
            "path": str(directory),
            "parent": str(directory.parent),
            "entries": entries,
            "shortcuts": [
                {"name": n, "path": str(p)}
                for n, p in [
                    ("Downloads", Path.home() / "Downloads"),
                    ("Documents", Path.home() / "Documents"),
                    ("External drives", Path("/Volumes")),
                    (
                        "Music folder",
                        Path(
                            self.store.setting("music_folder", default_music_folder())
                        ),
                    ),
                ]
            ],
        }

    def preview(self, paths, mode):
        if mode not in ("copy", "move", "index") or not paths or len(paths) > 200:
            raise ValueError("Choose files or folders and a valid import method")
        root = (
            Path(self.store.setting("music_folder", default_music_folder()))
            .expanduser()
            .resolve()
        )
        if not root.is_dir():
            raise ValueError("Set an existing main music folder in Settings first")
        files, seen, errors = [], set(), []
        for raw in paths:
            selected = Path(raw).expanduser()
            if selected.is_symlink():
                raise ValueError(
                    "Choose the original folder or file, rather than a symbolic link"
                )
            selected = selected.resolve()
            if not selected.exists():
                raise ValueError(f"Selected location is unavailable: {selected}")
            if selected.is_dir() and (
                selected in root.parents or (root == selected and mode != "index")
            ):
                raise ValueError(
                    "Select a source outside the destination folder; avoid importing its parent"
                )
            if selected.is_dir():

                def onerror(exc):
                    errors.append(str(exc))

                candidates = []
                for folder, dirs, names in os.walk(
                    selected, followlinks=False, onerror=onerror
                ):
                    dirs[:] = sorted(
                        d
                        for d in dirs
                        if not d.startswith(".") and not (Path(folder) / d).is_symlink()
                    )
                    for name in sorted(names):
                        p = Path(folder) / name
                        if (
                            not name.startswith(".")
                            and p.suffix.lower() in audio.PLAYABLE
                            and not p.is_symlink()
                        ):
                            candidates.append(
                                (p, Path(selected.name) / p.relative_to(selected))
                            )
                        if len(candidates) > 10000:
                            raise ValueError(
                                "Import at most 10,000 music files at a time"
                            )
            else:
                candidates = [(selected, Path(selected.name))]
            for p, relative in candidates:
                if p in seen or p.suffix.lower() not in audio.PLAYABLE:
                    continue
                seen.add(p)
                files.append((p, relative))
        if errors:
            raise ValueError(
                "Some source folders cannot be read. Check permissions before previewing again"
            )
        if not files or len(files) > 10000:
            raise ValueError("Choose between 1 and 10,000 supported music files")
        tracks = self.store.tracks()
        known = {t["file_hash"]: t for t in tracks if t["file_hash"]}
        known_paths = {Path(t["path"]).resolve() for t in tracks}
        library = self.store.setting("last_scan_source")
        listed = {
            Path(t["path"]).resolve(): t["path"]
            for t in tracks
            if t["source"] == library and t["state"] != "removed"
        }
        planned_hashes, destinations, entries = set(), set(), []
        for p, relative in files:
            if any(c in str(p) for c in ("\n", "\r")):
                raise ValueError(
                    "Music paths cannot contain line breaks because rekordbox playlists use one path per line"
                )
            try:
                metadata = audio.read(p)
                sha = audio.digest(p)
            except Exception as exc:
                entries.append(
                    {
                        "source": str(p),
                        "status": "skipped",
                        "reason": f"Cannot read audio ({type(exc).__name__})",
                    }
                )
                continue
            # A file already in the music folder stays where it is, however deep.
            dest = p if mode == "index" or p.is_relative_to(root) else root / relative
            status, reason = "ready", ""
            # A file rekordbox lists from outside the music folder moves with its entry.
            repoint = (
                listed.get(p) if mode == "move" and not p.is_relative_to(root) else None
            )
            if repoint and sha not in planned_hashes:
                reason = "Already in rekordbox; its entry will point to the moved file"
            elif p in known_paths or sha in known or sha in planned_hashes:
                status, reason = (
                    "skipped",
                    "Already in the Dex or repeated in this selection",
                )
            elif p == dest:
                status, reason = (
                    "ready",
                    "Added where it is"
                    if mode == "index"
                    else "Already in the music folder; index without copying",
                )
            if status == "ready" and p != dest:
                suffix = 1
                original = dest
                while dest in destinations or dest.exists():
                    dest = original.with_name(
                        f"{original.stem} ({suffix}){original.suffix}"
                    )
                    suffix += 1
                if dest != original:
                    reason = (
                        reason + ". " if reason else ""
                    ) + "Name collision; a numbered filename will be used"
            if p != dest and (
                dest.is_relative_to(root) is False
                or dest.resolve().is_relative_to(root) is False
            ):
                raise ValueError("Destination resolves outside the main music folder")
            if status == "ready":
                planned_hashes.add(sha)
                destinations.add(dest)
            entries.append(
                {
                    "source": str(p),
                    "destination": str(dest),
                    "hash": sha,
                    "metadata": metadata,
                    "size": p.stat().st_size,
                    "status": status,
                    "reason": reason,
                    "source_id": str(uuid4()),
                    **({"repoint": repoint} if repoint and status == "ready" else {}),
                }
            )
        plan = {"root": str(root), "mode": mode, "entries": entries}
        iid = str(uuid4())
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO imports VALUES (?,?,?,?)",
                (iid, "preview", dump(plan), now()),
            )
        return {"id": iid, **plan}

    def get(self, iid):
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM imports WHERE id=?", (iid,)).fetchone()
        if not row:
            raise ValueError("Import preview not found")
        return {"id": iid, "state": row["state"], **json.loads(row["plan"])}

    def persist(self, iid, state, plan):
        with self.store.connect() as db:
            db.execute(
                "UPDATE imports SET state=?,plan=? WHERE id=?", (state, dump(plan), iid)
            )

    def run(self, job_id, payload):
        iid = payload["import_id"]
        saved = self.get(iid)
        plan = {k: saved[k] for k in ("root", "mode", "entries")}
        root = Path(plan["root"])
        if (
            str(root) != self.store.setting("music_folder", default_music_folder())
            or not root.is_dir()
        ):
            raise ValueError(
                "Music folder changed or disconnected; restore the setting before resuming"
            )
        if self.store.setting("demo"):
            raise ValueError("Exit the demo before importing music")
        if any(
            e.get("repoint") and e["status"] not in ("skipped", "complete")
            for e in plan["entries"]
        ):
            # Their rekordbox entries are rewritten below, so stop before moving anything.
            Operations(self.service).guard()
        self.persist(iid, "running", plan)
        self.service.progress(job_id, total=len(plan["entries"]))
        failures = 0
        for index, entry in enumerate(plan["entries"]):
            if entry["status"] in ("skipped", "complete"):
                self.service.progress(job_id, progress=index + 1)
                continue
            try:
                source, dest = Path(entry["source"]), Path(entry["destination"])
                if entry["status"] == "ready" and not entry.get("repoint"):
                    with self.store.connect() as db:
                        known = db.execute(
                            "SELECT id FROM tracks WHERE file_hash=?", (entry["hash"],)
                        ).fetchone()
                    if known:
                        entry["status"], entry["reason"] = (
                            "skipped",
                            "Added to the Dex since this preview",
                        )
                        self.persist(iid, "running", plan)
                        self.service.progress(job_id, progress=index + 1)
                        continue
                if dest != source and (
                    not dest.resolve().is_relative_to(root) or root.resolve() != root
                ):
                    raise ValueError(
                        "Destination folder changed; refusing to follow a link outside the music folder"
                    )
                if entry["status"] == "publishing" and dest.exists():
                    if audio.digest(dest) != entry["hash"]:
                        raise ValueError(
                            "Destination already exists with different contents; it will not be overwritten"
                        )
                    entry["status"] = "copied"
                if dest == source:
                    if audio.digest(dest) != entry["hash"]:
                        raise ValueError("Source changed since preview")
                elif entry["status"] in ("copied", "indexed", "moving"):
                    if not dest.is_file() or audio.digest(dest) != entry["hash"]:
                        raise ValueError(
                            "Copied file is missing or changed; inspect it before resuming"
                        )
                else:
                    if not source.is_file() or audio.digest(source) != entry["hash"]:
                        raise ValueError("Source changed or disconnected since preview")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    # Write to a private sibling, then publish atomically without overwriting.
                    temporary = dest.with_name(".songdex-import-" + entry["source_id"])
                    if temporary.exists():
                        temporary.unlink()
                    shutil.copy2(source, temporary)
                    try:
                        with temporary.open("rb") as stream:
                            os.fsync(stream.fileno())
                        if audio.digest(temporary) != entry["hash"]:
                            raise ValueError("Copy verification failed")
                        # Journal the publish intent. Recovery accepts only this expected hash.
                        entry["status"] = "publishing"
                        self.persist(iid, "running", plan)
                        try:
                            os.link(temporary, dest)
                        except OSError as exc:
                            if exc.errno not in (
                                errno.EPERM,
                                errno.ENOTSUP,
                                errno.EOPNOTSUPP,
                            ):
                                raise
                            # FAT/exFAT cannot create hard links. Exclusive creation still
                            # prevents overwriting; an incomplete copy blocks retry and
                            # leaves the original intact for user inspection.
                            with (
                                dest.open("xb") as output,
                                temporary.open("rb") as input_file,
                            ):
                                shutil.copyfileobj(input_file, output)
                                output.flush()
                                os.fsync(output.fileno())
                            if audio.digest(dest) != entry["hash"]:
                                raise ValueError(
                                    "Destination copy did not verify; original retained"
                                )
                    finally:
                        temporary.unlink(missing_ok=True)
                    entry["status"] = "copied"
                    self.persist(iid, "running", plan)
                if entry.get("repoint"):
                    # Remembered before the source goes, so any later scan can finish the job.
                    self.store.set_setting(
                        "moved_files",
                        {
                            **self.store.setting("moved_files", {}),
                            entry["repoint"]: str(dest),
                        },
                    )
                else:
                    self.service.ingest(
                        "local",
                        {
                            "source_id": entry["source_id"],
                            "path": str(dest),
                            "metadata": entry["metadata"],
                            "playlists": [],
                        },
                    )
                entry["status"] = "indexed"
                self.persist(iid, "running", plan)
                if plan["mode"] == "move" and source != dest:
                    # Never break an existing Dex/rekordbox file reference by moving it.
                    if not entry.get("repoint") and any(
                        Path(t["path"]).resolve() == source for t in self.store.tracks()
                    ):
                        raise ValueError(
                            "Source is referenced by the Dex; retained the source"
                        )
                    entry["status"] = "moving"
                    self.persist(iid, "running", plan)
                    if source.exists():
                        if (
                            audio.digest(source) != entry["hash"]
                            or audio.digest(dest) != entry["hash"]
                        ):
                            raise ValueError(
                                "Source or copy changed; retained the source"
                            )
                        source.unlink()
                entry["status"], entry["error"] = "complete", None
                self.store.log(
                    "import_music", f"{plan['mode'].capitalize()} verified: {dest}"
                )
            except Exception as exc:
                entry["error"] = str(exc)
                failures += 1
            self.persist(iid, "partial" if failures else "running", plan)
            self.service.progress(
                job_id,
                progress=index + 1,
                message=f"Processed {index + 1} of {len(plan['entries'])} music files",
            )
        self.persist(iid, "partial" if failures else "complete", plan)
        note = self.check_library(job_id)
        if failures:
            raise ValueError(
                f"{failures} imports need attention. Originals retained unless a verified move completed. Open the import receipt to inspect or resume"
            )
        # Rekordbox can import this standard playlist using File > Import > Import Playlist.
        playlist = self.store.root / "imports" / (iid + ".m3u8")
        playlist.parent.mkdir(exist_ok=True)
        paths = [e["destination"] for e in plan["entries"] if new_to_rekordbox(e)]
        playlist.write_text("#EXTM3U\n" + "\n".join(paths) + "\n", encoding="utf-8")
        return note

    def check_library(self, job_id):
        """Rescan rekordbox after an import, which repoints entries whose files moved."""
        source = self.store.setting("last_scan_source")
        if not source or source != str(
            Path(self.store.setting("rekordbox_db", str(rekordbox.DEFAULT_DB)))
            .expanduser()
            .resolve()
        ):
            return None
        try:
            return self.service.scan(job_id, {})
        except Exception as exc:
            return f"Imported, but rekordbox was not rescanned: {exc}"
