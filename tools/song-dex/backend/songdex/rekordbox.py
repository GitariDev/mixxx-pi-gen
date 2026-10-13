from __future__ import annotations

import importlib.metadata
import plistlib
import shutil
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psutil

from .audio import digest

TARGET_VERSION = "7.2.18"
DB_VERSION = "6000"
DEFAULT_DB = Path.home() / "Library/Pioneer/rekordbox/master.db"


def installed_version():
    p = Path("/Applications/rekordbox 7/rekordbox.app/Contents/Info.plist")
    if not p.exists():
        return "unavailable"
    with p.open("rb") as f:
        return ".".join(
            plistlib.load(f).get("CFBundleShortVersionString", "").split(".")[:3]
        )


def require_stopped():
    try:
        processes = list(psutil.process_iter(["name"]))
    except (psutil.Error, OSError) as exc:
        raise ValueError(
            "Cannot check rekordbox processes; run Song Dex from your terminal with process access"
        ) from exc
    running = [
        p.info["name"]
        for p in processes
        if "rekordbox" in (p.info["name"] or "").lower()
    ]
    if running:
        raise ValueError(
            "Quit rekordbox and rekordboxAgent before scanning or applying changes: "
            + ", ".join(sorted(set(running)))
        )


def snapshot(source: Path, destination: Path):
    require_stopped()
    if source.name != "master.db" or not source.is_file():
        raise ValueError("Choose the rekordbox master.db file")
    wal = Path(str(source) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError(
            "rekordbox has an outstanding database journal. Open and quit rekordbox normally before retrying."
        )
    destination.mkdir(parents=True, exist_ok=True)
    before = digest(source)
    shutil.copy2(source, destination / "master.db")
    xml = source.parent / "masterPlaylists6.xml"
    if xml.exists():
        shutil.copy2(xml, destination / xml.name)
    require_stopped()
    if digest(source) != before:
        raise ValueError("Library changed while taking the snapshot; retry")
    return before


@contextmanager
def database(path):
    from pyrekordbox import Rekordbox6Database

    db = Rekordbox6Database(path=path, db_dir=Path(path).parent)
    # Playlist structure is not edited by metadata cleanup; avoid rewriting its XML.
    db.playlist_xml = None
    try:
        yield db
    finally:
        db.close()
        db.engine.dispose()


def metadata(c):
    return {
        "title": c.Title or "",
        "artist": c.ArtistName or "",
        "album": c.AlbumName or "",
        "album_artist": c.AlbumArtistName or "",
        "genre": c.GenreName or "",
        "label": c.LabelName or "",
        "year": str(c.ReleaseYear or ""),
        "version": c.Subtitle or "",
        "bpm": (c.BPM or 0) / 100,
        "key": c.KeyName or "",
        "duration": c.Length or 0,
        "bitrate": (c.BitRate or 0) * 1000,
        "format": Path(c.FolderPath or "").suffix[1:].upper(),
    }


def tag_membership(db):
    from pyrekordbox.db6 import tables

    tags = {str(t.ID): t for t in db.query(tables.DjmdMyTag)}

    def describe(tag):
        names, seen, parent = [], {str(tag.ID)}, str(tag.ParentID)
        while parent in tags and parent not in seen:
            seen.add(parent)
            names.append(tags[parent].Name or "Unnamed category")
            parent = str(tags[parent].ParentID)
        return {
            "id": str(tag.ID),
            "name": tag.Name or "Unnamed tag",
            "category": " / ".join(reversed(names)),
        }

    membership = {}
    for link in db.query(tables.DjmdSongMyTag):
        tag = tags.get(str(link.MyTagID))
        if tag:
            membership.setdefault(str(link.ContentID), []).append(describe(tag))
    return membership


def read_my_tags(path):
    with database(path) as db:
        return tag_membership(db)


def read_collection(path):
    from pyrekordbox.db6 import tables

    with database(path) as db:
        my_tags = tag_membership(db)
        folders = {p.ID: p for p in db.get_playlist()}

        def full_name(pid):
            names, seen = [], set()
            while pid in folders and pid not in seen:
                seen.add(pid)
                p = folders[pid]
                names.append(p.Name)
                pid = p.ParentID
            return " / ".join(reversed(names))

        cues = Counter(str(c.ContentID) for c in db.get_cue())
        membership = {}
        for s in db.query(tables.DjmdSongPlaylist):
            membership.setdefault(str(s.ContentID), []).append(
                {
                    "name": full_name(s.PlaylistID),
                    "id": s.PlaylistID,
                    "position": s.TrackNo,
                }
            )
        return [
            {
                "source_id": str(c.ID),
                "path": c.FolderPath or "",
                # As rekordbox measured it; tag edits made since are not reflected.
                "size": int(c.FileSize or 0),
                "metadata": metadata(c),
                "playlists": membership.get(str(c.ID), []),
                "my_tags": my_tags.get(str(c.ID), []),
                # Work that belongs to this entry alone and cannot move to another.
                "stats": {
                    "cues": cues[str(c.ID)],
                    "plays": int(c.DJPlayCount or 0),
                    "rating": int(c.Rating or 0),
                    # The day rekordbox added the entry (its Date Added column).
                    "added": str(c.StockDate or ""),
                },
            }
            for c in db.get_content()
        ]


def set_metadata(db, content, changes):
    from pyrekordbox.db6 import tables

    def named(kind, value):
        result = getattr(db, f"get_{kind}")(Name=value).first()
        return result or getattr(db, f"add_{kind}")(value)

    for field, column in (
        ("title", "Title"),
        ("version", "Subtitle"),
        ("year", "ReleaseYear"),
    ):
        if field in changes:
            setattr(
                content,
                column,
                int(changes[field]) if field == "year" else changes[field],
            )
    for field, column in (
        ("artist", "ArtistID"),
        ("genre", "GenreID"),
        ("label", "LabelID"),
    ):
        if field in changes:
            setattr(content, column, named(field, changes[field]).ID)
    if "album" in changes or "album_artist" in changes:
        name = changes.get("album", content.AlbumName or "")
        artist_name = changes.get("album_artist", content.AlbumArtistName or "")
        artist = named("artist", artist_name) if artist_name else None
        artist_id = artist.ID if artist else None
        album = db.get_album(Name=name, AlbumArtistID=artist_id).first()
        if not album:
            # Never change an existing shared album/artist row: only reassign this track.
            album = tables.DjmdAlbum.create(
                ID=db.generate_unused_id(tables.DjmdAlbum),
                UUID=str(uuid4()),
                Name=name,
                AlbumArtistID=artist_id,
            )
            db.add(album)
        content.AlbumID = album.ID


def require_writable(db):
    """Refuse libraries outside what the copied-library and live checks covered."""
    from pyrekordbox.db6 import tables

    version = db.get_property().first()
    if version is None or str(version.DBVersion) != DB_VERSION:
        raise ValueError(
            "This rekordbox database version has not been checked for writes"
        )
    for table in (tables.DjmdContent, tables.DjmdPlaylist):
        synced = db.query(table).filter(
            table.usn.is_not(None) | (table.rb_local_synced != 0)
        )
        if synced.first() is not None:
            raise ValueError(
                "Cloud Library Sync has been used on this library; direct writes "
                "could create duplicates or be overwritten, so they stay disabled"
            )


def write_collection(path, updates):
    require_stopped()
    with database(path) as db:
        require_writable(db)
        for source_id, changes in updates.items():
            c = db.get_content(ID=source_id)
            if c is None:
                raise ValueError("rekordbox entry no longer exists")
            set_metadata(db, c, changes)
        db.commit()
    with database(path) as db:
        for source_id, changes in updates.items():
            actual = metadata(db.get_content(ID=source_id))
            if any(str(actual.get(k, "")) != str(v) for k, v in changes.items()):
                raise ValueError("rekordbox verification failed")


def signed32(value):
    # rekordbox writes 32-bit IDs as signed integers inside smart playlist rules.
    number = int(value)
    return number - 2**32 if number >= 2**31 else number


def smart_list(playlist_id, rules, match="all", auto_update=0):
    """Serialize rules exactly as rekordbox stores them in djmdPlaylist.SmartList."""
    from xml.sax.saxutils import escape

    from pyrekordbox.db6.smartlist import Condition

    if not rules or match not in ("all", "any"):
        raise ValueError(
            "A smart playlist needs at least one rule and all/any matching"
        )

    def attr(value):
        return escape(str(value), {'"': "&quot;"})

    parts = []
    for rule in rules:
        c = Condition(
            rule["property"],
            int(rule["operator"]),
            rule.get("unit", ""),
            str(rule["left"]),
            str(rule.get("right", "")),
        )
        left = signed32(c.value_left) if c.property == "myTag" else c.value_left
        parts.append(
            f'<CONDITION PropertyName="{c.property}" Operator="{c.operator}" '
            f'ValueUnit="{attr(c.unit)}" ValueLeft="{attr(left)}" '
            f'ValueRight="{attr(c.value_right)}"/>'
        )
    return (
        f'<NODE Id="{signed32(playlist_id)}" LogicalOperator="{1 if match == "all" else 2}" '
        f'AutomaticUpdate="{int(auto_update)}">' + "".join(parts) + "</NODE>"
    )


def read_smart_list(source):
    import xml.etree.ElementTree as ET

    root = ET.fromstring(source)
    rules = []
    for c in root.findall("CONDITION"):
        left = c.get("ValueLeft", "")
        if c.get("PropertyName") == "myTag":
            left = str(int(left) % 2**32)
        rules.append(
            {
                "property": c.get("PropertyName"),
                "operator": int(c.get("Operator")),
                "unit": c.get("ValueUnit", ""),
                "left": left,
                "right": c.get("ValueRight", ""),
            }
        )
    return {
        "id": str(int(root.get("Id")) % 2**32),
        "match": "all" if root.get("LogicalOperator") == "1" else "any",
        "auto_update": int(root.get("AutomaticUpdate", 0)),
        "rules": rules,
    }


def register_playlists(xml_path, entries):
    """Append new playlists to masterPlaylists6.xml without touching rekordbox's own lines."""
    import time

    text = xml_path.read_bytes().decode("utf-8")
    end = text.rfind("</PLAYLISTS>")
    start = text.rfind("\n", 0, end) + 1
    if end < 0 or text.count("</PLAYLISTS>") != 1 or text[start:end].strip():
        raise ValueError(
            "masterPlaylists6.xml has an unfamiliar layout; nothing was written"
        )
    newline = "\r\n" if "\r\n" in text else "\n"
    last = text.rfind("<NODE ", 0, end)
    indent = (
        text[text.rfind("\n", 0, last) + 1 : last]
        if last >= 0
        else text[start:end] + "  "
    )
    stamp = int(time.time() * 1000)
    lines = ""
    for playlist_id, parent_id, attribute in entries:
        hex_id = f"{int(playlist_id):X}"
        if f'Id="{hex_id}"' in text:
            raise ValueError("Playlist is already registered in masterPlaylists6.xml")
        parent = "0" if parent_id == "root" else f"{int(parent_id):X}"
        lines += (
            f'{indent}<NODE Id="{hex_id}" ParentId="{parent}" Attribute="{int(attribute)}" '
            f'Timestamp="{stamp}" Lib_Type="0" CheckType="0"/>{newline}'
        )
    xml_path.write_bytes((text[:start] + lines + text[start:]).encode("utf-8"))


def playlist_state(db, folder_name):
    folder = db.get_playlist(Name=folder_name, ParentID="root").first()
    state = {}
    for p in db.get_playlist(ParentID=folder.ID) if folder is not None else []:
        if p.Attribute == 4:
            state[p.Name] = read_smart_list(p.SmartList)
        else:
            songs = sorted(
                db.get_playlist_songs(PlaylistID=p.ID), key=lambda s: s.TrackNo
            )
            state[p.Name] = [str(s.ContentID) for s in songs]
    return state


def write_playlists(path, plan):
    """Create or refresh playlists inside one root folder; other playlists are not touched.

    plan = {"folder": name, "playlists": [{"name", "tracks": [content ids]} or
    {"name", "rules": [...], "match": "all" | "any"}]}
    """
    from pyrekordbox.db6.smartlist import SmartList

    require_stopped()
    xml = Path(path).parent / "masterPlaylists6.xml"
    if not xml.is_file():
        raise ValueError("masterPlaylists6.xml is missing beside the library")
    names = [item["name"] for item in plan["playlists"]]
    if not plan["folder"] or not all(names) or len(set(names)) != len(names):
        raise ValueError("Playlists need unique names inside a named folder")
    created = []
    with database(path) as db:
        require_writable(db)
        folder = db.get_playlist(Name=plan["folder"], ParentID="root").first()
        if folder is None:
            folder = db.create_playlist_folder(plan["folder"])
            created.append(folder)
        elif folder.Attribute != 1:
            raise ValueError(f'"{plan["folder"]}" exists and is not a playlist folder')
        for item in plan["playlists"]:
            smart = "rules" in item
            playlist = db.get_playlist(Name=item["name"], ParentID=folder.ID).first()
            if playlist is not None and playlist.Attribute != (4 if smart else 0):
                raise ValueError(
                    f'"{item["name"]}" exists as a different kind of playlist'
                )
            if smart:
                if playlist is None:
                    playlist = db.create_smart_playlist(
                        item["name"], SmartList(), parent=folder
                    )
                    created.append(playlist)
                rules = smart_list(playlist.ID, item["rules"], item.get("match", "all"))
                if playlist.SmartList != rules:
                    playlist.SmartList = rules
                continue
            wanted = [str(i) for i in item["tracks"]]
            if len(set(wanted)) != len(wanted):
                raise ValueError(f'"{item["name"]}" lists a track more than once')
            if playlist is None:
                playlist = db.create_playlist(item["name"], parent=folder)
                created.append(playlist)
            # Membership is synchronized in place so the existing manual order survives.
            songs = sorted(
                db.get_playlist_songs(PlaylistID=playlist.ID), key=lambda s: s.TrackNo
            )
            for song in songs:
                if str(song.ContentID) not in wanted:
                    db.remove_from_playlist(playlist, song)
            present = {str(s.ContentID) for s in songs}
            for content_id in wanted:
                if content_id in present:
                    continue
                if db.get_content(ID=content_id) is None:
                    raise ValueError("rekordbox entry no longer exists")
                db.add_to_playlist(playlist, content_id)
        entries = [(p.ID, p.ParentID, p.Attribute) for p in created]
        db.commit()
    if entries:
        register_playlists(xml, entries)
    with database(path) as db:
        actual = playlist_state(db, plan["folder"])
        for item in plan["playlists"]:
            found = actual.get(item["name"])
            if "rules" in item:
                ok = isinstance(found, dict) and found == read_smart_list(
                    smart_list(found["id"], item["rules"], item.get("match", "all"))
                )
            else:
                ok = isinstance(found, list) and set(found) == {
                    str(i) for i in item["tracks"]
                }
            if not ok:
                raise ValueError("rekordbox verification failed")
    return {"created": len(entries), "playlists": len(names)}


def merge_entries(path, merges, own_folder=None):
    """Give duplicate entries' playlist places and My Tags to the entry being kept.

    merges = [{"keep": content id, "remove": [content ids]}]. Rows are re-pointed in
    place, so playlist order survives. Nothing is deleted from the collection, and
    playlists inside `own_folder` (Song Dex's own lists) are left alone.
    """
    from pyrekordbox.db6 import tables

    require_stopped()
    moved, expected = {"playlists": 0, "my_tags": 0}, set()
    with database(path) as db:
        require_writable(db)
        folder = (
            own_folder and db.get_playlist(Name=own_folder, ParentID="root").first()
        )
        own = {p.ID for p in db.get_playlist(ParentID=folder.ID)} if folder else set()
        for merge in merges:
            keep, remove = str(merge["keep"]), [str(i) for i in merge["remove"]]
            if not remove or keep in remove:
                raise ValueError("Choose one entry to keep and others to merge")
            if any(db.get_content(ID=i) is None for i in [keep, *remove]):
                raise ValueError("rekordbox entry no longer exists")
            for table, column, kind in (
                (tables.DjmdSongPlaylist, "PlaylistID", "playlists"),
                (tables.DjmdSongMyTag, "MyTagID", "my_tags"),
            ):
                held = {
                    getattr(r, column)
                    for r in db.query(table).filter_by(ContentID=keep)
                }
                rows = db.query(table).filter(table.ContentID.in_(remove))
                for row in sorted(rows, key=lambda r: r.TrackNo or 0):
                    target = getattr(row, column)
                    if target in held or (kind == "playlists" and target in own):
                        continue
                    row.ContentID = keep
                    held.add(target)
                    expected.add((kind, keep, target))
                    moved[kind] += 1
        db.commit()
    with database(path) as db:
        actual = {
            ("playlists", str(r.ContentID), r.PlaylistID)
            for r in db.query(tables.DjmdSongPlaylist)
        } | {
            ("my_tags", str(r.ContentID), r.MyTagID)
            for r in db.query(tables.DjmdSongMyTag)
        }
        if not expected <= actual:
            raise ValueError("rekordbox verification failed")
    return moved


def relocate(path, moves):
    """Point entries at files that moved: moves = {content id: new file path}.

    Only the path changes, which is all rekordbox's own Relocate changes, so cues,
    grids and playlist places stay with the entry. Analysis files hold the file
    name alone and are left as they are.
    """
    require_stopped()
    changed = []
    with database(path) as db:
        require_writable(db)
        used = {c.FolderPath for c in db.get_content()}
        for source_id, new in moves.items():
            c = db.get_content(ID=source_id)
            if c is None:
                raise ValueError("rekordbox entry no longer exists")
            if new in used:
                raise ValueError("Another rekordbox entry already uses this file")
            used.add(new)
            changed.append({"id": str(source_id), "from": c.FolderPath, "to": new})
            c.FolderPath = new
            name = new.rsplit("/", 1)[-1]
            if c.FileNameL != name:
                c.FileNameL = name
        db.commit()
    with database(path) as db:
        for source_id, new in moves.items():
            if db.get_content(ID=source_id).FolderPath != new:
                raise ValueError("rekordbox verification failed")
    return {"moves": changed}


def live_check_running(root):
    """True while marked test changes from `songdex.livecheck` sit in the library."""
    import json

    path = root / "compatibility" / "live" / "state.json"
    return path.exists() and json.loads(path.read_text()).get("state") == "started"


def capability(root):
    import json

    path = root / "compatibility.json"
    report = json.loads(path.read_text()) if path.exists() else {}
    version = installed_version()
    if live_check_running(root):
        return {
            "enabled": False,
            "version": version,
            "report": report,
            "reason": "A live rekordbox check is in progress; finish or cancel it first.",
        }
    enabled = (
        report.get("rekordbox_version") == version == TARGET_VERSION
        and report.get("adapter_version") == importlib.metadata.version("pyrekordbox")
        and report.get("clone_roundtrip") is True
        and report.get("rekordbox_restart_verified") is True
    )
    return {
        "enabled": enabled,
        "version": version,
        "report": report,
        "reason": ""
        if enabled
        else "Direct writes are locked until copied-library round trips and a rekordbox restart are verified for this version.",
    }
