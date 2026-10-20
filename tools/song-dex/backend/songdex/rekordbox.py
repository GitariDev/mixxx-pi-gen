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


def playlist_namer(db):
    """Full "Folder / Playlist" name for a playlist ID."""
    folders = {p.ID: p for p in db.get_playlist()}

    def full_name(pid):
        names, seen = [], set()
        while pid in folders and pid not in seen:
            seen.add(pid)
            p = folders[pid]
            names.append(p.Name)
            pid = p.ParentID
        return " / ".join(reversed(names))

    return full_name


def read_choices(path, own_folder=None):
    """The My Tags and normal playlists a track can be given.

    Smart playlists are left out, as are the playlists inside `own_folder`
    (Song Dex's own lists). Categories and folders are listed apart, as the
    places new My Tags and playlists can go.
    """
    from pyrekordbox.db6 import tables

    with database(path) as db:
        rows = list(db.query(tables.DjmdMyTag))
        categories = {str(t.ID): t for t in rows if t.Attribute == 1}
        tags = sorted(
            (t for t in rows if t.Attribute == 0),
            key=lambda t: (
                getattr(categories.get(str(t.ParentID)), "Seq", None) or 0,
                t.Seq or 0,
            ),
        )
        full_name = playlist_namer(db)
        playlists = list(db.get_playlist())
        own = next(
            (p.ID for p in playlists if p.Name == own_folder and p.ParentID == "root"),
            None,
        )
        return {
            "tags": [
                {
                    "id": str(t.ID),
                    "name": t.Name or "Unnamed tag",
                    "category": getattr(categories.get(str(t.ParentID)), "Name", ""),
                }
                for t in tags
            ],
            "playlists": sorted(
                (
                    {"id": str(p.ID), "name": full_name(p.ID)}
                    for p in playlists
                    if p.Attribute == 0 and (own is None or p.ParentID != own)
                ),
                key=lambda p: p["name"].casefold(),
            ),
            # Where new My Tags and playlists can go.
            "categories": [
                {"id": str(c.ID), "name": c.Name or "My Tags"}
                for c in sorted(categories.values(), key=lambda c: c.Seq or 0)
            ],
            "folders": sorted(
                (
                    {"id": str(p.ID), "name": full_name(p.ID)}
                    for p in playlists
                    if p.Attribute == 1 and p.ID != own and p.ParentID != own
                ),
                key=lambda p: p["name"].casefold(),
            ),
        }


def read_collection(path):
    from pyrekordbox.db6 import tables

    with database(path) as db:
        my_tags = tag_membership(db)
        full_name = playlist_namer(db)
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


# Smart playlist property → how to read it from a DjmdContent row.
SMART_TEXT = {
    "artist": "ArtistName",
    "album": "AlbumName",
    "albumArtist": "AlbumArtistName",
    "originalArtist": "OrgArtistName",
    "producer": "ComposerName",
    "comments": "Commnt",
    "fileName": "FileNameL",
    "genre": "GenreName",
    "key": "KeyName",
    "label": "LabelName",
    "mixName": "Subtitle",
    "remixedBy": "RemixerName",
    "name": "Title",
    "grouping": "ColorID",
}
SMART_NUMBER = {
    "bpm": lambda c: (c.BPM or 0) / 100,
    "counter": lambda c: c.DJPlayCount or 0,
    "rating": lambda c: c.Rating or 0,
    "duration": lambda c: c.Length or 0,
    "year": lambda c: c.ReleaseYear or 0,
}
SMART_DATE = {
    "stockDate": lambda c: str(c.StockDate or "")[:10],
    "dateCreated": lambda c: str(c.created_at or "")[:10],
    "dateReleased": lambda c: str(c.ReleaseDate or "")[:10],
}
SMART_LABELS = {
    "albumArtist": "Album artist",
    "originalArtist": "Original artist",
    "fileName": "File name",
    "mixName": "Mix name",
    "remixedBy": "Remixer",
    "name": "Title",
    "grouping": "Colour",
    "counter": "Play count",
    "stockDate": "Date added",
    "dateCreated": "Date created",
    "dateReleased": "Release date",
    "myTag": "My Tag",
    "bpm": "BPM",
}
SMART_OPERATORS = {
    1: "is",
    2: "is not",
    3: "is greater than",
    4: "is less than",
    5: "is between",
    6: "is in the last",
    7: "is not in the last",
    8: "contains",
    9: "does not contain",
    10: "starts with",
    11: "ends with",
}


def smart_matcher(rule, today=None):
    """A test of one smart playlist rule against (content row, its My Tag IDs)."""
    from datetime import date

    from dateutil.relativedelta import relativedelta

    prop, op = rule["property"], int(rule["operator"])
    left, right = rule["left"], rule.get("right", "")
    if prop == "myTag":
        if op not in (8, 9):
            raise ValueError(f"Unsupported My Tag rule {op}")
        return lambda c, tags: (left in tags) == (op == 8)
    if prop in SMART_TEXT:
        column = SMART_TEXT[prop]
        want = str(left).casefold()
        tests = {
            1: lambda v: v == want,
            2: lambda v: v != want,
            8: lambda v: want in v,
            9: lambda v: want not in v,
            10: lambda v: v.startswith(want),
            11: lambda v: v.endswith(want),
        }
        test = tests[op]
        return lambda c, tags: test(str(getattr(c, column) or "").casefold())
    if prop in SMART_NUMBER:
        read, low = SMART_NUMBER[prop], float(left)
        high = float(right) if right != "" else low
        # rekordbox shows BPM to two places; "is 120" takes 120.00 to 120.99.
        exact = (
            (lambda v: int(v) == low)
            if prop == "bpm" and low.is_integer()
            else (lambda v: v == low)
        )
        tests = {
            1: exact,
            2: lambda v: not exact(v),
            3: lambda v: v > low,
            4: lambda v: v < low,
            5: lambda v: low <= v <= high,
        }
        test = tests[op]
        return lambda c, tags: test(read(c))
    if prop in SMART_DATE:
        read, today = SMART_DATE[prop], today or date.today()
        if op in (6, 7):
            units = {
                "day": "days",
                "week": "weeks",
                "month": "months",
                "year": "years",
            }
            since = str(
                today - relativedelta(**{units[rule.get("unit") or "day"]: int(left)})
            )
            return lambda c, tags: bool(read(c)) and ((read(c) >= since) == (op == 6))
        tests = {
            1: lambda v: v == left,
            2: lambda v: v != left,
            3: lambda v: v > left,
            4: lambda v: v < left,
            5: lambda v: left <= v <= (right or left),
        }
        test = tests[op]
        return lambda c, tags: bool(read(c)) and test(read(c))
    raise ValueError(f"Unsupported smart playlist property {prop}")


def describe_rule(rule, tag_names):
    prop = rule["property"]
    name = SMART_LABELS.get(prop, prop[:1].upper() + prop[1:])
    value = (
        tag_names.get(rule["left"], "a removed My Tag")
        if prop == "myTag"
        else rule["left"]
    )
    op = int(rule["operator"])
    if op == 5:
        value = f"{value} and {rule.get('right', '')}"
    elif op in (6, 7):
        value = f"{value} {rule.get('unit') or 'day'}s"
    elif value == "":
        value = "blank"
    return f"{name} {SMART_OPERATORS.get(op, '?')} {value}"


def read_playlists(path):
    """rekordbox's playlist tree: folders, playlists and smart playlists, each with
    its parent and place. Smart playlists also carry their rules, in words, and the
    content IDs those rules match in this copy of the library.
    """
    from pyrekordbox.db6 import tables

    with database(path) as db:
        tags = {}
        for link in db.query(tables.DjmdSongMyTag):
            tags.setdefault(str(link.ContentID), set()).add(str(link.MyTagID))
        tag_names = {
            str(t.ID): t.Name or "Unnamed tag" for t in db.query(tables.DjmdMyTag)
        }
        contents = None
        nodes = []
        for p in db.get_playlist():
            kind = {0: "playlist", 1: "folder", 4: "smart"}.get(p.Attribute)
            if kind is None:
                continue
            node = {
                "id": str(p.ID),
                "name": p.Name or "Untitled",
                "parent": str(p.ParentID or "root"),
                "kind": kind,
                "seq": int(p.Seq or 0),
            }
            if kind == "smart":
                try:
                    parsed = read_smart_list(p.SmartList or "")
                    tests = [smart_matcher(r) for r in parsed["rules"]]
                    combine = all if parsed["match"] == "all" else any
                    if contents is None:
                        contents = list(db.get_content())
                    node["rules"] = [
                        describe_rule(r, tag_names) for r in parsed["rules"]
                    ]
                    node["match"] = parsed["match"]
                    node["tracks"] = [
                        str(c.ID)
                        for c in contents
                        if tests
                        and combine(t(c, tags.get(str(c.ID), ())) for t in tests)
                    ]
                except Exception as exc:
                    node["tracks"] = []
                    node["error"] = f"Song Dex cannot read these rules: {exc}"
            nodes.append(node)
        nodes.sort(key=lambda n: (n["parent"], n["seq"], n["name"].casefold()))
        return {"nodes": nodes}


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


def create_lists(db, create):
    """Make new My Tags, playlists and folders: create = [{"id", "kind", "name", "parent"}].

    A My Tag goes last in its category, made the way rekordbox makes its own; a
    playlist or folder goes last in its folder ("root" for the top level), which
    may be one made earlier in the list. One with that
    name already there is used instead. Returns {given id: rekordbox ID} and the
    playlists to register in masterPlaylists6.xml.
    """
    from datetime import datetime

    from pyrekordbox.db6 import tables

    ids, registered = {}, []
    for item in create:
        name = item["name"].strip()
        if item["kind"] == "tag":
            rows = list(db.query(tables.DjmdMyTag))
            category = next(
                (t for t in rows if str(t.ID) == item["parent"] and t.Attribute == 1),
                None,
            )
            if category is None:
                raise ValueError(
                    "A My Tag category was removed in rekordbox. Rescan and create the tag again"
                )
            siblings = [t for t in rows if str(t.ParentID) == item["parent"]]
            same = next((t for t in siblings if t.Name == name), None)
            if same is not None:
                ids[item["id"]] = str(same.ID)
                continue
            stamp = datetime.now()
            tag = tables.DjmdMyTag.create(
                ID=str(db.generate_unused_id(tables.DjmdMyTag, is_28_bit=False)),
                Seq=max((t.Seq or 0 for t in siblings), default=0) + 1,
                Name="New tag",
                Attribute=0,
                ParentID=item["parent"],
                UUID=str(uuid4()),
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(tag)
            # Named after adding, as pyrekordbox does for playlists, so the change is counted.
            tag.Name = name
            ids[item["id"]] = str(tag.ID)
        elif item["kind"] in ("playlist", "folder"):
            # The folder may be one made just before.
            parent_id = ids.get(item["parent"], item["parent"])
            parent = None
            if parent_id != "root":
                parent = db.get_playlist(ID=parent_id)
                if parent is None or parent.Attribute != 1:
                    raise ValueError(
                        "A playlist folder was removed in rekordbox. Rescan and create the playlist again"
                    )
            attribute = 0 if item["kind"] == "playlist" else 1
            same = db.get_playlist(Name=name, ParentID=parent_id).first()
            if same is not None and same.Attribute == attribute:
                ids[item["id"]] = str(same.ID)
                continue
            make = db.create_playlist if attribute == 0 else db.create_playlist_folder
            playlist = make(name, parent=parent)
            registered.append((playlist.ID, playlist.ParentID, playlist.Attribute))
            ids[item["id"]] = str(playlist.ID)
        else:
            raise ValueError("Only My Tags, playlists and folders can be created")
    return ids, registered


def assign(path, plan, create=()):
    """Give entries My Tags and playlist places: plan = {content id: {"tags", "playlists"}}.

    Only adds. A new place goes at the end of its playlist, and a tag row is made
    the way rekordbox makes its own (no track number). Assignments an entry
    already has are left as they are. `create` lists new My Tags and playlists
    (see create_lists) made first; the plan may name them by their given IDs.
    """
    from datetime import datetime

    from pyrekordbox.db6 import tables

    require_stopped()
    added, expected = {"my_tags": 0, "playlists": 0}, set()
    xml = Path(path).parent / "masterPlaylists6.xml"
    with database(path) as db:
        require_writable(db)
        ids, registered = create_lists(db, create)
        if registered and not xml.is_file():
            raise ValueError("masterPlaylists6.xml is missing beside the library")
        tags = {str(t.ID): t for t in db.query(tables.DjmdMyTag)}
        for content_id, wanted in plan.items():
            content_id = str(content_id)
            if db.get_content(ID=content_id) is None:
                raise ValueError("rekordbox entry no longer exists")
            held = {str(r.MyTagID) for r in db.get_my_tag_songs(ContentID=content_id)}
            for tag_id in (ids.get(str(t), str(t)) for t in wanted.get("tags", [])):
                if tag_id not in tags or tags[tag_id].Attribute != 0:
                    raise ValueError(
                        "A My Tag was removed in rekordbox. Rescan and choose again"
                    )
                expected.add(("my_tags", content_id, tag_id))
                if tag_id in held:
                    continue
                stamp = datetime.now()
                db.add(
                    tables.DjmdSongMyTag.create(
                        ID=str(uuid4()),
                        MyTagID=tag_id,
                        ContentID=content_id,
                        UUID=str(uuid4()),
                        created_at=stamp,
                        updated_at=stamp,
                    )
                )
                held.add(tag_id)
                added["my_tags"] += 1
            listed = {
                str(s.PlaylistID)
                for s in db.query(tables.DjmdSongPlaylist).filter_by(
                    ContentID=content_id
                )
            }
            for playlist_id in (
                ids.get(str(p), str(p)) for p in wanted.get("playlists", [])
            ):
                playlist = db.get_playlist(ID=playlist_id)
                if playlist is None or playlist.Attribute != 0:
                    raise ValueError(
                        "A playlist was removed in rekordbox. Rescan and choose again"
                    )
                expected.add(("playlists", content_id, playlist_id))
                if playlist_id in listed:
                    continue
                db.add_to_playlist(playlist, content_id)
                listed.add(playlist_id)
                added["playlists"] += 1
        db.commit()
    if registered:
        register_playlists(xml, registered)
    with database(path) as db:
        actual = {
            ("playlists", str(r.ContentID), str(r.PlaylistID))
            for r in db.query(tables.DjmdSongPlaylist)
        } | {
            ("my_tags", str(r.ContentID), str(r.MyTagID))
            for r in db.query(tables.DjmdSongMyTag)
        }
        names = {str(t.ID): t.Name for t in db.query(tables.DjmdMyTag)} | {
            str(p.ID): p.Name for p in db.get_playlist()
        }
        made = {item["id"]: item["name"].strip() for item in create}
        if not expected <= actual or any(
            names.get(real) != made[given] for given, real in ids.items()
        ):
            raise ValueError("rekordbox verification failed")
    return {**added, "created": ids}


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
