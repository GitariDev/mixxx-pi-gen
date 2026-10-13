"""Find missing rekordbox files in the main music folder and repoint their entries.

A file is matched by name and size, or by name and length when its tags were
edited after rekordbox measured it. Anything less certain is listed for the user
instead of written.
"""

from __future__ import annotations

import os
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from . import audio, rekordbox
from .db import now
from .importing import default_music_folder
from .operations import Operations


def name_key(name):
    # macOS may hand back a decomposed name for one rekordbox stored composed.
    return unicodedata.normalize("NFC", name).casefold()


def identity(path):
    s = os.stat(path)
    return s.st_dev, s.st_ino


def same_audio(row, path):
    if row.get("size") and path.stat().st_size == row["size"]:
        return True
    length = float(row["metadata"].get("duration") or 0)
    try:
        return bool(length) and abs(audio.read(path)["duration"] - length) <= 1
    except Exception:
        return False


def plan(rows, root, moved=None):
    """Return ({content id: new path}, entries needing a look) for missing files.

    `moved` maps old paths to where Song Dex itself put the file; those are trusted.
    """
    moved = moved or {}
    missing, taken = [], set()
    for row in rows:
        if Path(row["path"]).is_file():
            taken.add(identity(row["path"]))
        elif row["path"]:
            missing.append(row)
    if not missing:
        return {}, []
    files = defaultdict(list)
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in names:
            if not name.startswith(".") and Path(name).suffix.lower() in audio.PLAYABLE:
                files[name_key(name)].append(Path(folder) / name)
    moves, review, choices, folders = {}, [], [], defaultdict(Counter)

    def claim(row, path):
        taken.add(identity(path))
        moves[row["source_id"]] = str(path)
        folders[Path(row["path"]).parent][path.parent] += 1

    for row in missing:
        known = Path(moved.get(row["path"], ""))
        if known.is_file() and identity(known) not in taken:
            claim(row, known)
            continue
        named = [
            p
            for p in files.get(name_key(Path(row["path"]).name), [])
            if identity(p) not in taken
        ]
        found = [p for p in named if same_audio(row, p)]
        if len(found) == 1:
            claim(row, found[0])
        elif found:
            choices.append((row, found))
        elif named:
            review.append(
                {
                    "source_id": row["source_id"],
                    "path": row["path"],
                    "candidates": [str(p) for p in named],
                    "reason": "Same file name, but a different size and length",
                }
            )
    # Several identical copies: follow the folder this entry's neighbours moved to.
    for row, found in choices:
        target = folders[Path(row["path"]).parent].most_common(1)
        free = [p for p in found if identity(p) not in taken]
        near = [p for p in free if target and p.parent == target[0][0]]
        if len(near) == 1 or len(free) == 1:
            claim(row, (near or free)[0])
        elif free:
            review.append(
                {
                    "source_id": row["source_id"],
                    "path": row["path"],
                    "candidates": [str(p) for p in free],
                    "reason": "More than one matching file",
                }
            )
    return moves, review


class Relocating:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def repair(self, source, rows):
        """Repoint what `plan` finds; the caller holds the operation lock.

        Returns a sentence for the job, or None when nothing was missing nearby.
        """
        root = Path(self.store.setting("music_folder", default_music_folder()))
        if not root.is_dir():
            return None
        moved = self.store.setting("moved_files", {})
        moves, review = plan(rows, root, moved)
        self.store.set_setting("relocation_review", review)
        note = (
            f" {len(review)} missing files have a possible match that needs a look."
            if review
            else ""
        )
        paths = {row["source_id"]: row["path"] for row in rows}
        if not moves:
            self.forget(moved, paths, moves)
            return note.strip() or None
        try:
            result = Operations(self.service).change_library(
                "paths repaired",
                f"Repointed {len(moves)} rekordbox entries to files found in the music folder",
                list(moves),
                lambda staged: rekordbox.relocate(staged, moves),
            )
        except ValueError as exc:
            # Nothing was written; the next scan finds the same files again.
            return (
                f"Found {len(moves)} missing files in the music folder, but rekordbox "
                f"was not updated: {exc}{note}"
            )
        manifest = result["manifest"]
        if manifest["library_status"] != "complete":
            raise ValueError(
                f"Found {len(moves)} missing files in the music folder, but rekordbox "
                f"was not updated: {manifest.get('error')}. Restore the operation in History."
            )
        with self.store.connect() as db:
            for source_id, new in moves.items():
                track = db.execute(
                    "SELECT id FROM tracks WHERE source=? AND source_id=?",
                    (source, source_id),
                ).fetchone()
                if track:
                    db.execute(
                        "INSERT INTO history(track_id,kind,detail,created_at) VALUES (?,?,?,?)",
                        (
                            track["id"],
                            "path repaired",
                            f"{paths[source_id]} → {new}",
                            now(),
                        ),
                    )
        self.forget(moved, paths, moves)
        return f"Repointed {len(moves)} missing files found in the music folder.{note}"

    def forget(self, moved, paths, moves):
        """Drop remembered moves that rekordbox now reflects or no longer needs."""
        waiting = set(paths.values()) - {paths[i] for i in moves}
        kept = {old: new for old, new in moved.items() if old in waiting}
        if kept != moved:
            self.store.set_setting("moved_files", kept)
