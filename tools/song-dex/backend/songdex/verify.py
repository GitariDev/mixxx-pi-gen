"""Probe a COPIED rekordbox database. Never enables live writes by itself.

Usage: python -m songdex.verify --source /path/to/master.db --output .data/compatibility
The source is read only; writes take place under output/probe/master.db.
"""

import argparse
import importlib.metadata
import json
import shutil
from pathlib import Path

from . import audio, rekordbox
from .db import now


def tables_snapshot(path):
    with rekordbox.database(path) as db:
        with db.engine.connect() as conn:
            names = [
                r[0]
                for r in conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            ]
            return {
                name: [
                    dict(r._mapping)
                    for r in conn.exec_driver_sql(
                        'SELECT * FROM "' + name.replace('"', '""') + '"'
                    )
                ]
                for name in names
            }


def update_count_consistent(snapshot):
    """rekordbox keeps localUpdateCount equal to the newest row stamp across all tables."""
    count = next(
        r["int_1"]
        for r in snapshot["agentRegistry"]
        if r["registry_id"] == "localUpdateCount"
    )
    return count == max(
        r["rb_local_usn"] or 0
        for rows in snapshot.values()
        for r in rows
        if "rb_local_usn" in r
    )


def probe_playlists(dbpath, before, ids):
    """Create, then refresh, a folder with a normal and a smart playlist on the copy."""
    xml = dbpath.parent / "masterPlaylists6.xml"
    xml_before = xml.read_text(encoding="utf-8").splitlines()
    native = [r for r in before["djmdPlaylist"] if r["Attribute"] == 4]
    for row in native:
        parsed = rekordbox.read_smart_list(row["SmartList"])
        assert (
            rekordbox.smart_list(
                row["ID"], parsed["rules"], parsed["match"], parsed["auto_update"]
            )
            == row["SmartList"]
        ), "A rekordbox smart playlist does not match the known rule format"
    folder = "Song Dex verification"
    assert not any(r["Name"] == folder for r in before["djmdPlaylist"]), (
        "Probe folder already exists in the copied library"
    )
    smart = {
        "name": "Probe smart",
        "rules": [{"property": "year", "operator": 5, "left": "1990", "right": "1999"}],
    }
    plan = {
        "folder": folder,
        "playlists": [{"name": "Probe", "tracks": ids[:3]}, smart],
    }
    rekordbox.write_playlists(dbpath, plan)
    plan["playlists"][0]["tracks"] = [ids[2], ids[3], ids[0]]
    rekordbox.write_playlists(dbpath, plan)
    after = tables_snapshot(dbpath)
    old_ids = {str(r["ID"]) for r in before["djmdPlaylist"]}
    added = [r for r in after["djmdPlaylist"] if str(r["ID"]) not in old_ids]
    assert sorted(r["Name"] for r in added) == sorted([folder, "Probe", "Probe smart"])
    probe = next(str(r["ID"]) for r in added if r["Name"] == "Probe")
    for name, old_rows in before.items():
        new_rows = after[name]
        if name == "djmdPlaylist":
            assert [r for r in new_rows if str(r["ID"]) in old_ids] == old_rows, (
                "Existing playlist changed"
            )
        elif name == "djmdSongPlaylist":
            mine = [r for r in new_rows if str(r["PlaylistID"]) == probe]
            assert [r for r in new_rows if r not in mine] == old_rows, (
                "Existing playlist membership changed"
            )
            mine.sort(key=lambda r: r["TrackNo"])
            assert [str(r["ContentID"]) for r in mine] == [ids[0], ids[2], ids[3]]
            assert [r["TrackNo"] for r in mine] == [1, 2, 3]
        elif name == "agentRegistry":
            assert [r for r in new_rows if r["registry_id"] != "localUpdateCount"] == [
                r for r in old_rows if r["registry_id"] != "localUpdateCount"
            ], "Unrelated registry data changed"
        else:
            assert old_rows == new_rows, f"{name} changed unexpectedly"
    xml_after = xml.read_text(encoding="utf-8").splitlines()
    assert all(line in xml_after for line in xml_before), "Playlist XML line changed"
    assert len(xml_after) - len(xml_before) == 3, "Playlist XML registration mismatch"
    shutil.copy2(dbpath.parent.parent / "original" / xml.name, xml)
    return {
        "playlist_roundtrip": True,
        "native_smart_lists_matched": len(native),
        "update_count_consistent": update_count_consistent(after),
    }


def verify(source, output):
    source, output = source.resolve(), output.resolve()
    if output == source.parent or source.is_relative_to(output):
        raise ValueError("Output must be separate from the source library")
    original_hash = rekordbox.snapshot(source, output / "original")
    working = output / "probe"
    if working.exists():
        raise ValueError("Use a fresh output directory for each verification run")
    shutil.copytree(output / "original", working)
    dbpath = working / "master.db"
    before = tables_snapshot(dbpath)
    rows = rekordbox.read_collection(dbpath)
    if not rows:
        raise ValueError("A representative copied library must contain tracks")
    target = rows[0]["source_id"]
    changes = dict(
        title="Song Dex verification (Extended Mix)",
        artist="Song Dex Test Artist",
        album="Song Dex Test Release",
        album_artist="Song Dex Album Artist",
        genre="Test genre",
        label="Song Dex Test Label",
        year="2001",
        version="Extended Mix",
    )
    rekordbox.write_collection(dbpath, {target: changes})
    after = tables_snapshot(dbpath)
    # Existing rows outside the one edited entry must survive byte-for-byte in SQL values.
    changed_content_columns = {
        "Title",
        "ArtistID",
        "AlbumID",
        "GenreID",
        "LabelID",
        "ReleaseYear",
        "Subtitle",
        "updated_at",
        "usn",
        "rb_local_usn",
    }
    append_tables = {"djmdArtist", "djmdAlbum", "djmdGenre", "djmdLabel"}
    for name, old_rows in before.items():
        new_rows = after[name]
        if name == "djmdContent":
            new_by_id = {str(r["ID"]): r for r in new_rows}
            assert len(old_rows) == len(new_rows), "Content count changed"
            for old in old_rows:
                actual = new_by_id[str(old["ID"])]
                excluded = (
                    changed_content_columns if str(old["ID"]) == target else set()
                )
                assert {k: v for k, v in old.items() if k not in excluded} == {
                    k: v for k, v in actual.items() if k not in excluded
                }, "Unrelated track data changed"
        elif name in append_tables:
            new_by_id = {str(r["ID"]): r for r in new_rows}
            assert all(new_by_id[str(r["ID"])] == r for r in old_rows), (
                f"Existing {name} row changed"
            )
        elif name == "agentRegistry":
            # The adapter must increment bookkeeping; all unrelated registry records survive.
            old_by = {r["registry_id"]: r for r in old_rows}
            new_by = {r["registry_id"]: r for r in new_rows}
            for key, row in old_by.items():
                if key != "localUpdateCount":
                    assert new_by[key] == row, "Unrelated registry data changed"
        else:
            assert old_rows == new_rows, f"{name} changed unexpectedly"
    playlists = probe_playlists(dbpath, after, [r["source_id"] for r in rows[:4]])
    if update_count_consistent(before):
        assert update_count_consistent(after), "Update counter out of step"
        assert playlists.pop("update_count_consistent"), "Update counter out of step"
    # Restore the copied library and compare exact bytes, leaving the source untouched.
    shutil.copy2(output / "original/master.db", dbpath)
    assert audio.digest(dbpath) == original_hash
    assert audio.digest(source) == original_hash, "Source was unexpectedly changed"
    report = {
        "created_at": now(),
        "rekordbox_version": rekordbox.installed_version(),
        "adapter_version": importlib.metadata.version("pyrekordbox"),
        "clone_roundtrip": True,
        "rekordbox_restart_verified": False,
        "verified_formats": [],
        "entry_count": len(rows),
        "source_unchanged": True,
        "protected_tables": len(before),
        **playlists,
        "note": "SQL reopen and restore verified. Actual rekordbox UI restart and per-format readback still required before enabling live writes.",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=rekordbox.DEFAULT_DB)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.source, args.output), indent=2))
